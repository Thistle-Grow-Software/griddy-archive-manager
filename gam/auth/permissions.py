"""
Permission catalog and DRF permission class for the Griddy API.

The catalog is intentionally small (4 entries). Adding a new permission later
is cheap; removing one is a breaking change once SDK clients depend on it.

Tokens carry permissions in a ``permissions`` claim, accepted as either a
list of strings or a single space-delimited string (mirroring OAuth scope
conventions). The claim is populated by the IdP — for Clerk this is done in
the JWT template (see ``docs/auth/permissions.md``).

Naming convention: ``resource:verb`` (e.g. ``catalog:read``). See
``docs/auth/permissions.md`` for the rationale.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, ClassVar

from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView


class Permissions:
    """Constants for every permission the API recognizes.

    Reference these from viewsets instead of inlining string literals so the
    catalog has a single source of truth and IDEs can find every usage.
    """

    CATALOG_READ = "catalog:read"
    CATALOG_WRITE = "catalog:write"
    HOLDINGS_READ = "holdings:read"
    HOLDINGS_WRITE = "holdings:write"
    VIDEO_PLAYBACK = "video:playback"


# Action → required permissions mappings shared by viewsets in each domain.
# Keys are DRF action names (``list``, ``retrieve``, ``create``, ``update``,
# ``partial_update``, ``destroy``); the ``default`` key catches custom
# ``@action`` methods and any unmapped actions.
CATALOG_PERMISSIONS: dict[str, list[str]] = {
    "list": [Permissions.CATALOG_READ],
    "retrieve": [Permissions.CATALOG_READ],
    "create": [Permissions.CATALOG_WRITE],
    "update": [Permissions.CATALOG_WRITE],
    "partial_update": [Permissions.CATALOG_WRITE],
    "destroy": [Permissions.CATALOG_WRITE],
    "default": [Permissions.CATALOG_READ],
}

HOLDINGS_PERMISSIONS: dict[str, list[str]] = {
    "list": [Permissions.HOLDINGS_READ],
    "retrieve": [Permissions.HOLDINGS_READ],
    "create": [Permissions.HOLDINGS_WRITE],
    "update": [Permissions.HOLDINGS_WRITE],
    "partial_update": [Permissions.HOLDINGS_WRITE],
    "destroy": [Permissions.HOLDINGS_WRITE],
    "default": [Permissions.HOLDINGS_READ],
}


def _coerce_permissions(value: Any) -> set[str]:
    """Normalize a token's ``permissions`` claim into a set of strings.

    Accepts a list/tuple of strings or a single space-delimited string.
    Anything else (including ``None``) becomes an empty set.
    """
    if value is None:
        return set()
    if isinstance(value, str):
        return set(value.split())
    if isinstance(value, Iterable):
        return {str(item) for item in value}
    return set()


class HasAPIPermission(permissions.BasePermission):
    """Check that the JWT carries every permission the view requires.

    Views declare ``required_permissions`` as one of:

    * a list/tuple/string of permission strings (applies to all actions), or
    * a dict keyed by DRF action name (or HTTP method, lowercased), with a
      ``"default"`` key as a fallback for unmapped actions/custom @actions.

    A view with no ``required_permissions`` (or an empty value) is treated as
    not requiring any permission and is left to other permission classes to
    gate. This keeps the class safe to install as a project-wide default.
    """

    message = "Token is missing one or more required permissions."

    def has_permission(self, request: Request, view: APIView) -> bool:
        required = self._required_for_action(request, view)
        if not required:
            return True
        token_perms = self._token_permissions(request)
        return required.issubset(token_perms)

    @staticmethod
    def _token_permissions(request: Request) -> set[str]:
        """Extract permissions from either a JWT claims dict or an APIKey row.

        ``request.auth`` is a ``dict`` for :class:`JWKSAuthentication` and an
        :class:`gam.accounts.models.APIKey` instance for
        :class:`gam.auth.api_key.APIKeyAuthentication`. Both surface
        permissions via the same string catalog (TGF-316), just under
        different attribute names — JWTs use the ``permissions`` claim,
        API keys use the ``scopes`` field.
        """
        auth = getattr(request, "auth", None)
        if auth is None:
            return set()
        if isinstance(auth, dict):
            return _coerce_permissions(auth.get("permissions"))
        scopes = getattr(auth, "scopes", None)
        return _coerce_permissions(scopes)

    @staticmethod
    def _required_for_action(request: Request, view: APIView) -> set[str]:
        spec = getattr(view, "required_permissions", None)
        if not spec:
            return set()
        if isinstance(spec, dict):
            action = getattr(view, "action", None) or request.method.lower()
            value = spec.get(action)
            if value is None:
                value = spec.get("default", [])
            return _coerce_permissions(value)
        return _coerce_permissions(spec)


class CatalogPermissionMixin:
    """Apply :data:`CATALOG_PERMISSIONS` to a viewset.

    Inheriting viewsets get :class:`HasAPIPermission` enforcement automatically.
    Override ``required_permissions`` on the subclass to customize.
    """

    permission_classes: ClassVar[list[type]] = [HasAPIPermission]
    required_permissions: ClassVar[dict[str, list[str]]] = CATALOG_PERMISSIONS


class HoldingsPermissionMixin:
    """Apply :data:`HOLDINGS_PERMISSIONS` to a viewset.

    See :class:`CatalogPermissionMixin` for usage.
    """

    permission_classes: ClassVar[list[type]] = [HasAPIPermission]
    required_permissions: ClassVar[dict[str, list[str]]] = HOLDINGS_PERMISSIONS
