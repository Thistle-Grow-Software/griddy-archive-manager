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
from functools import lru_cache
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

        claims = self._decode_token(token)
        return (JWTPrincipal(claims=claims), claims)

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
            return jwt.decode(
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
