"""
JWKS-based JWT authentication for DRF.

Validates bearer JWTs against a configurable JWKS endpoint. IdP-agnostic: the
same class works against Clerk, Auth0, or any JWKS-based IdP — only the
``JWKS_URL``, ``JWT_AUDIENCE``, and ``JWT_ISSUER`` settings change.

Returns a lightweight :class:`JWTPrincipal` (not a Django ``User``) to avoid a
DB hit per request. User sync is a separate concern handled downstream.

JWKS key caching is delegated to ``PyJWKClient`` — it caches fetched keys in
process memory and refreshes on cache miss, which is sufficient for current
throughput. Revisit if token-issuer rotates keys more aggressively than the
client refresh cadence tolerates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property, lru_cache
from typing import Any

import jwt
from django.conf import settings
from jwt import PyJWKClient
from rest_framework import authentication, exceptions

ALLOWED_ALGORITHMS = ["RS256"]


@dataclass(frozen=True)
class JWTPrincipal:
    """Lightweight request principal derived from validated JWT claims.

    Mimics the small surface of ``django.contrib.auth`` that DRF and views
    actually read (``is_authenticated``, ``is_anonymous``) without requiring a
    database-backed user row. The raw claims are preserved on ``claims`` for
    downstream authorization logic.
    """

    claims: dict[str, Any] = field(default_factory=dict)

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    @property
    def subject(self) -> str | None:
        return self.claims.get("sub")

    @cached_property
    def user(self):
        """Return the synced Django ``User`` for this principal (DB hit on first access).

        Lazy on purpose: most read-only requests never need a persisted
        user row. Views that record audits, set FKs, or otherwise integrate
        with ``django.contrib.auth`` should access this; pure read paths
        should keep using the principal directly. See
        :func:`gam.auth.sync.get_or_create_user_from_claims` for the upsert
        semantics.
        """
        from gam.auth.sync import get_or_create_user_from_claims

        return get_or_create_user_from_claims(self.claims)

    def __str__(self) -> str:
        return self.subject or "JWTPrincipal"


@lru_cache(maxsize=1)
def _get_jwks_client() -> PyJWKClient:
    """Return a process-wide ``PyJWKClient`` bound to ``settings.JWKS_URL``.

    Cached so we don't rebuild the signing-key cache on every request.
    """
    jwks_url = getattr(settings, "JWKS_URL", None)
    if not jwks_url:
        raise exceptions.AuthenticationFailed(
            "JWKS_URL is not configured; cannot verify tokens."
        )
    return PyJWKClient(jwks_url)


class JWKSAuthentication(authentication.BaseAuthentication):
    """Authenticate requests via bearer JWTs verified against a JWKS endpoint.

    Returns ``None`` when no ``Authorization: Bearer <token>`` header is
    present so other authentication classes (or anonymous access) can still
    apply. Raises :class:`rest_framework.exceptions.AuthenticationFailed` on
    any token that is present but invalid.
    """

    keyword = "Bearer"

    def authenticate(self, request: Any) -> tuple[JWTPrincipal, dict[str, Any]] | None:
        token = self._extract_bearer_token(request)
        if token is None:
            return None
        if not self._looks_like_jwt(token):
            # Let other auth classes (e.g. APIKeyAuthentication) handle it.
            return None

        claims = self._decode_token(token)
        return (JWTPrincipal(claims=claims), claims)

    @staticmethod
    def _looks_like_jwt(token: str) -> bool:
        """Cheap shape check: a JWT is exactly ``header.payload.signature``.

        Returning ``False`` here yields ``None`` from ``authenticate`` so DRF
        falls through to the next configured authentication class instead of
        rejecting the request as a malformed JWT. Without this, a valid API
        key like ``grd_live_<hex>`` would be eaten by the JWT class.
        """
        return token.count(".") == 2

    def authenticate_header(self, request: Any) -> str:
        return self.keyword

    def _extract_bearer_token(self, request: Any) -> str | None:
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header:
            return None

        parts = header.split()
        if parts[0] != self.keyword:
            return None
        if len(parts) == 1:
            raise exceptions.AuthenticationFailed(
                "Invalid Authorization header: no credentials provided."
            )
        if len(parts) > 2:
            raise exceptions.AuthenticationFailed(
                "Invalid Authorization header: token must not contain spaces."
            )
        return parts[1]

    def _decode_token(self, token: str) -> dict[str, Any]:
        audience = getattr(settings, "JWT_AUDIENCE", None)
        issuer = getattr(settings, "JWT_ISSUER", None)
        if not audience or not issuer:
            raise exceptions.AuthenticationFailed(
                "JWT_AUDIENCE and JWT_ISSUER must be configured."
            )

        try:
            signing_key = _get_jwks_client().get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=ALLOWED_ALGORITHMS,
                audience=audience,
                issuer=issuer,
            )
        except jwt.ExpiredSignatureError as exc:
            raise exceptions.AuthenticationFailed("Token has expired.") from exc
        except jwt.InvalidAudienceError as exc:
            raise exceptions.AuthenticationFailed("Invalid audience.") from exc
        except jwt.InvalidIssuerError as exc:
            raise exceptions.AuthenticationFailed("Invalid issuer.") from exc
        except jwt.InvalidAlgorithmError as exc:
            raise exceptions.AuthenticationFailed("Invalid signing algorithm.") from exc
        except jwt.InvalidSignatureError as exc:
            raise exceptions.AuthenticationFailed("Invalid signature.") from exc
        except jwt.DecodeError as exc:
            raise exceptions.AuthenticationFailed(f"Invalid token: {exc}") from exc
        except jwt.PyJWKClientError as exc:
            raise exceptions.AuthenticationFailed(
                f"Unable to resolve signing key: {exc}"
            ) from exc
        except jwt.PyJWTError as exc:
            raise exceptions.AuthenticationFailed(f"Invalid token: {exc}") from exc

        self._enforce_authorized_party(claims)
        return claims

    @staticmethod
    def _enforce_authorized_party(claims: dict[str, Any]) -> None:
        """Reject tokens whose ``azp`` claim is not in ``JWT_AUTHORIZED_PARTIES``.

        If the setting is empty or unset, the check is skipped — useful for
        local dev harnesses that issue tokens without an ``azp`` claim. When
        configured, the claim must be present and exactly match one of the
        allowed origins; this is what binds a Clerk-issued token to the
        portal frontend that requested it.
        """
        allowed = getattr(settings, "JWT_AUTHORIZED_PARTIES", None) or []
        if not allowed:
            return
        azp = claims.get("azp")
        if azp not in allowed:
            raise exceptions.AuthenticationFailed("Invalid authorized party.")
