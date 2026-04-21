"""
Unit tests for :class:`gam.auth.jwt.JWKSAuthentication` (TGF-313).

Covers header parsing, signing-algorithm rejection, audience/issuer/expiry
validation, and the structure of the returned principal. Tests mock
``PyJWKClient.get_signing_key_from_jwt`` so signature verification runs
against a local RSA keypair — no network calls or real IdP required.

The :class:`TestLocalJWKSHarness` class exercises the dev-harness script
end-to-end (real HTTP, real PyJWKClient fetch) to prove that the same
authentication class works against a JWKS endpoint it has never seen before.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import override_settings
from rest_framework import exceptions
from rest_framework.test import APIRequestFactory

from gam.auth.jwt import JWKSAuthentication, JWTPrincipal, _get_jwks_client

TEST_ISSUER = "https://issuer.test.griddy"
TEST_AUDIENCE = "griddy-api-test"
TEST_KID = "test-kid"


@pytest.fixture(scope="module")
def rsa_keypair() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def other_keypair() -> rsa.RSAPrivateKey:
    """Second keypair used to simulate mismatched-signature scenarios."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def clear_jwks_client_cache():
    """Ensure each test gets a fresh :func:`_get_jwks_client` cache."""
    _get_jwks_client.cache_clear()
    yield
    _get_jwks_client.cache_clear()


@pytest.fixture
def configured_settings():
    with override_settings(
        JWKS_URL="http://example.test/.well-known/jwks.json",
        JWT_AUDIENCE=TEST_AUDIENCE,
        JWT_ISSUER=TEST_ISSUER,
    ):
        yield


@pytest.fixture
def factory() -> APIRequestFactory:
    return APIRequestFactory()


def _encode(
    private_key: rsa.RSAPrivateKey,
    *,
    algorithm: str = "RS256",
    audience: str = TEST_AUDIENCE,
    issuer: str = TEST_ISSUER,
    expires_in: int = 3600,
    extra_claims: dict[str, Any] | None = None,
    headers: dict[str, Any] | None = None,
    key_override: Any = None,
) -> str:
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "iss": issuer,
        "aud": audience,
        "sub": "user_123",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    if extra_claims:
        claims.update(extra_claims)
    signing_material = key_override if key_override is not None else private_key
    return jwt.encode(
        claims,
        signing_material,
        algorithm=algorithm,
        headers={"kid": TEST_KID, **(headers or {})},
    )


def _patch_signing_key(public_key: Any):
    """Patch PyJWKClient.get_signing_key_from_jwt to return ``public_key``."""
    mock_signing = MagicMock()
    mock_signing.key = public_key
    return patch(
        "gam.auth.jwt.PyJWKClient.get_signing_key_from_jwt",
        return_value=mock_signing,
    )


# ---------------------------------------------------------------------------
# JWTPrincipal
# ---------------------------------------------------------------------------


class TestJWTPrincipal:
    def test_is_authenticated_is_true(self):
        principal = JWTPrincipal(claims={"sub": "u1"})
        assert principal.is_authenticated is True

    def test_is_anonymous_is_false(self):
        principal = JWTPrincipal(claims={"sub": "u1"})
        assert principal.is_anonymous is False

    def test_subject_reads_sub_claim(self):
        principal = JWTPrincipal(claims={"sub": "user_42"})
        assert principal.subject == "user_42"

    def test_subject_is_none_when_missing(self):
        principal = JWTPrincipal(claims={})
        assert principal.subject is None

    def test_claims_are_preserved(self):
        claims = {"sub": "u1", "email": "user@griddy.test", "roles": ["admin"]}
        principal = JWTPrincipal(claims=claims)
        assert principal.claims == claims

    def test_principal_is_immutable(self):
        principal = JWTPrincipal(claims={"sub": "u1"})
        with pytest.raises(FrozenInstanceError):
            principal.claims = {}  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Header parsing
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("configured_settings")
class TestHeaderParsing:
    def test_missing_header_returns_none(self, factory):
        request = factory.get("/api/v1/leagues/")
        assert JWKSAuthentication().authenticate(request) is None

    def test_non_bearer_scheme_returns_none(self, factory):
        request = factory.get("/", HTTP_AUTHORIZATION="Basic dXNlcjpwdw==")
        assert JWKSAuthentication().authenticate(request) is None

    def test_bearer_without_token_raises(self, factory):
        request = factory.get("/", HTTP_AUTHORIZATION="Bearer")
        with pytest.raises(exceptions.AuthenticationFailed):
            JWKSAuthentication().authenticate(request)

    def test_bearer_with_extra_parts_raises(self, factory):
        request = factory.get("/", HTTP_AUTHORIZATION="Bearer a b c")
        with pytest.raises(exceptions.AuthenticationFailed):
            JWKSAuthentication().authenticate(request)

    def test_authenticate_header_advertises_bearer(self, factory):
        request = factory.get("/")
        assert JWKSAuthentication().authenticate_header(request) == "Bearer"


# ---------------------------------------------------------------------------
# Successful decode
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("configured_settings")
class TestValidToken:
    def test_returns_principal_and_claims(self, factory, rsa_keypair):
        token = _encode(rsa_keypair)
        public_key = rsa_keypair.public_key()
        request = factory.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")

        with _patch_signing_key(public_key):
            principal, auth = JWKSAuthentication().authenticate(request)

        assert isinstance(principal, JWTPrincipal)
        assert principal.subject == "user_123"
        assert auth["iss"] == TEST_ISSUER
        assert auth["aud"] == TEST_AUDIENCE

    def test_extra_claims_preserved_on_principal(self, factory, rsa_keypair):
        token = _encode(
            rsa_keypair,
            extra_claims={"email": "user@griddy.test", "role": "admin"},
        )
        public_key = rsa_keypair.public_key()
        request = factory.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")

        with _patch_signing_key(public_key):
            principal, _ = JWKSAuthentication().authenticate(request)

        assert principal.claims["email"] == "user@griddy.test"
        assert principal.claims["role"] == "admin"


# ---------------------------------------------------------------------------
# Invalid tokens
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("configured_settings")
class TestInvalidTokens:
    def test_expired_token_rejected(self, factory, rsa_keypair):
        token = _encode(rsa_keypair, expires_in=-60)
        public_key = rsa_keypair.public_key()
        request = factory.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")

        with (
            _patch_signing_key(public_key),
            pytest.raises(exceptions.AuthenticationFailed, match="expired"),
        ):
            JWKSAuthentication().authenticate(request)

    def test_wrong_audience_rejected(self, factory, rsa_keypair):
        token = _encode(rsa_keypair, audience="some-other-api")
        public_key = rsa_keypair.public_key()
        request = factory.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")

        with (
            _patch_signing_key(public_key),
            pytest.raises(exceptions.AuthenticationFailed, match="audience"),
        ):
            JWKSAuthentication().authenticate(request)

    def test_wrong_issuer_rejected(self, factory, rsa_keypair):
        token = _encode(rsa_keypair, issuer="https://evil.example")
        public_key = rsa_keypair.public_key()
        request = factory.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")

        with (
            _patch_signing_key(public_key),
            pytest.raises(exceptions.AuthenticationFailed, match="issuer"),
        ):
            JWKSAuthentication().authenticate(request)

    def test_signed_by_different_key_rejected(
        self, factory, rsa_keypair, other_keypair
    ):
        """Token signed by an attacker's key must not verify against the JWKS key."""
        token = _encode(other_keypair)  # signed by wrong key
        public_key = rsa_keypair.public_key()  # JWKS returns the right key
        request = factory.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")

        with (
            _patch_signing_key(public_key),
            pytest.raises(exceptions.AuthenticationFailed, match="signature"),
        ):
            JWKSAuthentication().authenticate(request)

    def test_malformed_token_rejected(self, factory, rsa_keypair):
        request = factory.get("/", HTTP_AUTHORIZATION="Bearer not-a-real-jwt")

        with (
            _patch_signing_key(rsa_keypair.public_key()),
            pytest.raises(exceptions.AuthenticationFailed),
        ):
            JWKSAuthentication().authenticate(request)


# ---------------------------------------------------------------------------
# Signing-algorithm enforcement
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("configured_settings")
class TestAlgorithmEnforcement:
    def test_alg_none_rejected(self, factory):
        # "alg: none" unsigned token — the classic downgrade attack.
        token = jwt.encode(
            {
                "iss": TEST_ISSUER,
                "aud": TEST_AUDIENCE,
                "sub": "attacker",
                "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            },
            key="",
            algorithm="none",
        )
        request = factory.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")

        with (
            _patch_signing_key("unused"),
            pytest.raises(exceptions.AuthenticationFailed),
        ):
            JWKSAuthentication().authenticate(request)

    def test_hs256_rejected_when_expecting_rs256(self, factory):
        """HS256 tokens (symmetric) must not verify — confused-deputy attack."""
        token = jwt.encode(
            {
                "iss": TEST_ISSUER,
                "aud": TEST_AUDIENCE,
                "sub": "attacker",
                "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            },
            key="shared-secret",
            algorithm="HS256",
            headers={"kid": TEST_KID},
        )
        request = factory.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")

        # Return an RSA public key from JWKS — PyJWT must refuse HS256 against it.
        with (
            _patch_signing_key(
                rsa.generate_private_key(
                    public_exponent=65537, key_size=2048
                ).public_key()
            ),
            pytest.raises(exceptions.AuthenticationFailed),
        ):
            JWKSAuthentication().authenticate(request)


# ---------------------------------------------------------------------------
# Misconfiguration
# ---------------------------------------------------------------------------


class TestMisconfiguration:
    def test_missing_jwks_url_raises(self, factory, rsa_keypair):
        with override_settings(
            JWKS_URL=None,
            JWT_AUDIENCE=TEST_AUDIENCE,
            JWT_ISSUER=TEST_ISSUER,
        ):
            token = _encode(rsa_keypair)
            request = factory.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
            with pytest.raises(exceptions.AuthenticationFailed, match="JWKS_URL"):
                JWKSAuthentication().authenticate(request)

    def test_missing_audience_raises(self, factory, rsa_keypair):
        with override_settings(
            JWKS_URL="http://example.test/jwks",
            JWT_AUDIENCE=None,
            JWT_ISSUER=TEST_ISSUER,
        ):
            token = _encode(rsa_keypair)
            request = factory.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
            with pytest.raises(
                exceptions.AuthenticationFailed,
                match="JWT_AUDIENCE and JWT_ISSUER",
            ):
                JWKSAuthentication().authenticate(request)

    def test_missing_issuer_raises(self, factory, rsa_keypair):
        with override_settings(
            JWKS_URL="http://example.test/jwks",
            JWT_AUDIENCE=TEST_AUDIENCE,
            JWT_ISSUER=None,
        ):
            token = _encode(rsa_keypair)
            request = factory.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
            with pytest.raises(
                exceptions.AuthenticationFailed,
                match="JWT_AUDIENCE and JWT_ISSUER",
            ):
                JWKSAuthentication().authenticate(request)


# ---------------------------------------------------------------------------
# End-to-end harness: real HTTP JWKS + real PyJWKClient fetch
# ---------------------------------------------------------------------------


class TestLocalJWKSHarness:
    """Exercise the full stack via ``scripts/local_jwks_server.py``.

    This proves that a freshly-minted token signed by the dev harness can be
    verified by :class:`JWKSAuthentication` against the harness' JWKS endpoint
    over real HTTP — no mocks. If this test passes, the auth class is ready
    to talk to any real IdP (Clerk, Auth0, etc.) in staging.
    """

    def test_end_to_end_token_validation(self, factory):
        import socket

        from scripts.local_jwks_server import _issue_token, serve

        # Pick an ephemeral free port to avoid conflicts with concurrent CI runs.
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        server, private_key = serve("127.0.0.1", port, kid=TEST_KID)
        try:
            token = _issue_token(
                private_key,
                kid=TEST_KID,
                issuer=TEST_ISSUER,
                audience=TEST_AUDIENCE,
                subject="harness_user",
                ttl_seconds=60,
            )
            with override_settings(
                JWKS_URL=f"http://127.0.0.1:{port}/.well-known/jwks.json",
                JWT_AUDIENCE=TEST_AUDIENCE,
                JWT_ISSUER=TEST_ISSUER,
            ):
                _get_jwks_client.cache_clear()
                request = factory.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
                principal, claims = JWKSAuthentication().authenticate(request)
                assert principal.subject == "harness_user"
                assert claims["iss"] == TEST_ISSUER
                assert claims["aud"] == TEST_AUDIENCE
        finally:
            server.shutdown()
            server.server_close()
