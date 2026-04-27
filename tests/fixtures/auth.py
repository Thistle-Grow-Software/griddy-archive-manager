"""
Reusable authentication fixtures and factories (TGF-319).

Used by the integration test suite under ``tests/test_auth_integration.py``
and intentionally exposed for any future story that needs to mint a valid
RS256 JWT or an API key against the local test harness. Built on top of
:mod:`scripts.local_jwks_server` (introduced in TGF-313) so the same
JWKS-issuance machinery backs both end-to-end and integration tests.

Design goals:

* **One JWKS server per session.** Spinning up an HTTP server on every test
  is slow; a session-scoped fixture keeps it alive and reuses its keypair.
* **Parameterized claim minting.** Every JWT field that can vary in real
  traffic (audience, issuer, expiry, ``permissions``, ``azp``) is
  overridable from the call site so individual tests can shape edge cases
  without re-implementing the encoder.
* **Account + API-key factories.** Fixtures return callables (factories)
  rather than single instances so a single test can compose multiple
  accounts/keys without fixture duplication.
"""

from __future__ import annotations

import socket
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, NamedTuple

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth import get_user_model

from gam.accounts.models import APIKey, APIKeyEnvironment, ClerkAccount
from gam.auth.api_key import generate_api_key
from gam.auth.jwt import _get_jwks_client
from scripts.local_jwks_server import _issue_token, serve

DEFAULT_KID = "test-fixture-kid"
DEFAULT_ISSUER = "https://issuer.test.griddy"
DEFAULT_AUDIENCE = "griddy-api-test"


class JWKSHarness(NamedTuple):
    """Bundle of values describing a running fake JWKS server."""

    jwks_url: str
    issuer: str
    audience: str
    kid: str
    private_key: rsa.RSAPrivateKey


def _free_port() -> int:
    """Return an ephemeral port — avoids fixture conflicts in xdist runs."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def jwks_harness() -> Iterator[JWKSHarness]:
    """Run a JWKS server for the test session and yield its endpoints + key.

    Session scope means one process-wide HTTP server, reused by every
    test. The :class:`PyJWKClient` cache inside
    :mod:`gam.auth.jwt` is cleared on entry so the harness URL takes
    effect even if a prior test bound a different one.
    """
    port = _free_port()
    server, private_key = serve("127.0.0.1", port, kid=DEFAULT_KID)
    _get_jwks_client.cache_clear()
    try:
        yield JWKSHarness(
            jwks_url=f"http://127.0.0.1:{port}/.well-known/jwks.json",
            issuer=DEFAULT_ISSUER,
            audience=DEFAULT_AUDIENCE,
            kid=DEFAULT_KID,
            private_key=private_key,
        )
    finally:
        server.shutdown()
        server.server_close()
        _get_jwks_client.cache_clear()


@pytest.fixture
def mint_jwt(jwks_harness: JWKSHarness) -> Callable[..., str]:
    """Return a callable that mints RS256 JWTs against the harness.

    All claims have sensible defaults; pass overrides as keyword args:

    .. code-block:: python

        token = mint_jwt(sub="user_123", permissions=["catalog:read"])
        token = mint_jwt(audience="other-api")  # wrong-audience case
        token = mint_jwt(ttl_seconds=-60)        # expired-token case
    """

    def _mint(
        *,
        sub: str = "user_test",
        audience: str | None = None,
        issuer: str | None = None,
        ttl_seconds: int = 3600,
        permissions: list[str] | None = None,
        azp: str | None = None,
        email: str | None = None,
        kid: str | None = None,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        claims: dict[str, Any] = {}
        if permissions is not None:
            claims["permissions"] = permissions
        if azp is not None:
            claims["azp"] = azp
        if email is not None:
            claims["email"] = email
        if extra_claims:
            claims.update(extra_claims)

        # Negative TTL produces an already-expired token. The harness
        # ``_issue_token`` helper computes ``exp`` from ``now + ttl`` so
        # this works directly without special-casing.
        return _issue_token(
            jwks_harness.private_key,
            kid=kid or jwks_harness.kid,
            issuer=issuer or jwks_harness.issuer,
            audience=audience or jwks_harness.audience,
            subject=sub,
            ttl_seconds=ttl_seconds,
            extra_claims=claims,
        )

    return _mint


@pytest.fixture
def make_account() -> Callable[..., ClerkAccount]:
    """Return a factory for ``(User, ClerkAccount)`` pairs.

    Each call creates a fresh user with a unique username; the returned
    :class:`ClerkAccount` is what most auth-related tests want to attach
    API keys to.
    """
    User = get_user_model()
    counter = {"n": 0}

    def _make(
        *,
        sub: str | None = None,
        email: str | None = None,
    ) -> ClerkAccount:
        counter["n"] += 1
        n = counter["n"]
        return ClerkAccount.objects.create(
            user=User.objects.create_user(
                username=f"fixture-user-{n}",
                email=email or f"u{n}@griddy.test",
            ),
            clerk_sub=sub or f"user_fixture_{n}",
            email=email or f"u{n}@griddy.test",
        )

    return _make


@pytest.fixture
def make_api_key() -> Callable[..., tuple[APIKey, str]]:
    """Return a factory that mints API keys against an existing account.

    Yields ``(api_key_row, plaintext)``. Callers pass the plaintext as
    ``Authorization: Bearer <plaintext>`` to exercise the live auth path.
    """

    def _make(
        account: ClerkAccount,
        *,
        name: str = "fixture-key",
        environment: str = APIKeyEnvironment.LIVE,
        scopes: list[str] | None = None,
        expires_at: datetime | None = None,
    ) -> tuple[APIKey, str]:
        return generate_api_key(
            account,
            name=name,
            environment=environment,
            scopes=scopes,
            expires_at=expires_at,
        )

    return _make


# ---------------------------------------------------------------------------
# Helpers re-exported for tests that prefer module-level imports
# ---------------------------------------------------------------------------


def in_n_seconds(n: int) -> datetime:
    """Return a tz-aware datetime ``n`` seconds in the future.

    Convenience wrapper to keep test bodies readable when expressing
    expiry windows for API keys.
    """
    return datetime.now(UTC) + timedelta(seconds=n)
