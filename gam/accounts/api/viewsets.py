"""
DRF viewset for issuing, listing, and revoking API keys.

Management of API keys is restricted to **JWT-authenticated** principals
(human Clerk sessions). API-key-authenticated requests cannot mint or
revoke other API keys — that would let a stolen key bootstrap further
keys, defeating the point of revocation.
"""

from __future__ import annotations

from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from gam.accounts.api.serializers import (
    APIKeyCreateResponseSerializer,
    APIKeyCreateSerializer,
    APIKeyListSerializer,
)
from gam.accounts.models import APIKey
from gam.auth.api_key import generate_api_key
from gam.auth.jwt import JWTPrincipal


class IsJWTPrincipal(permissions.BasePermission):
    """Restrict the view to JWT-authenticated requests.

    Rejects API-key-authenticated requests so a stolen key cannot mint or
    revoke further keys.
    """

    message = "API key management requires a Clerk session token."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return isinstance(request.user, JWTPrincipal)


class APIKeyViewSet(viewsets.GenericViewSet):
    """List, issue, and revoke API keys for the requesting account.

    All actions are scoped to the principal's :class:`ClerkAccount`; you
    cannot read or revoke another account's keys, even with admin perms.
    """

    permission_classes = (IsJWTPrincipal,)
    serializer_class = APIKeyListSerializer
    pagination_class = None  # Operators rarely have more than a handful.

    def get_queryset(self):
        # ``request.user.user`` triggers the lazy ClerkAccount sync.
        account = self.request.user.user.clerk_account
        return APIKey.objects.filter(account=account)

    def list(self, request: Request) -> Response:
        keys = self.get_queryset()
        return Response(APIKeyListSerializer(keys, many=True).data)

    def retrieve(self, request: Request, pk: str | None = None) -> Response:
        key = self._get_owned_key(pk)
        return Response(APIKeyListSerializer(key).data)

    def create(self, request: Request) -> Response:
        serializer = APIKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = request.user.user.clerk_account
        api_key, plaintext = generate_api_key(
            account,
            name=serializer.validated_data["name"],
            environment=serializer.validated_data["environment"],
            scopes=serializer.validated_data.get("scopes", []),
            expires_at=serializer.validated_data.get("expires_at"),
        )
        response = APIKeyCreateResponseSerializer(
            {
                "api_key": api_key,
                "plaintext": plaintext,
                "warning": (
                    "Store this token now — it will not be shown again. "
                    "If you lose it, revoke this key and issue a new one."
                ),
            }
        )
        return Response(response.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def revoke(self, request: Request, pk: str | None = None) -> Response:
        key = self._get_owned_key(pk)
        if key.is_revoked:
            return Response(APIKeyListSerializer(key).data)
        key.revoked_at = timezone.now()
        key.save(update_fields=["revoked_at"])
        return Response(APIKeyListSerializer(key).data)

    def _get_owned_key(self, pk: str | None) -> APIKey:
        try:
            return self.get_queryset().get(pk=pk)
        except APIKey.DoesNotExist as exc:
            # Same response for "doesn't exist" and "exists but not yours"
            # to avoid leaking IDs across accounts.
            raise PermissionDenied("API key not found.") from exc
