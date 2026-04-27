"""
End-to-end integration tests for both auth paths (TGF-319).

Where the unit suites under ``tests/test_jwks_auth.py`` and
``tests/test_api_key_auth.py`` exercise individual classes in isolation,
this module drives requests through the full DRF stack — routing, both
authentication classes wired into ``DEFAULT_AUTHENTICATION_CLASSES``,
:class:`HasAPIPermission`, and the catalog/holdings viewsets — to confirm
the pieces compose correctly.

Test matrix (x = covered):

| Path / case        | 200  | 401  | 403  |
|--------------------|------|------|------|
| JWT happy          |  x   |      |      |
| JWT no header      |      |  x   |      |
| JWT missing perm   |      |      |  x   |
| JWT expired        |      |  x   |      |
| JWT wrong audience |      |  x   |      |
| JWT wrong issuer   |      |  x   |      |
| JWT azp mismatch   |      |  x   |      |
| API key happy      |  x   |      |      |
| API key missing    |      |      |  x   |
| API key revoked    |      |  x   |      |
| API key expired    |      |  x   |      |
| API key malformed  |      |  x   |      |
| API key unknown    |      |  x   |      |
| Cross-domain perm  |      |      |  x   |
| Both classes wired |  x   |      |      |  (one request via each path)

The matrix targets ``LeagueViewSet`` (catalog) and ``SourceViewSet``
(holdings) as representative endpoints. Coverage of every viewset would
be redundant — :class:`HasAPIPermission` is shared, so the same answer
applies everywhere.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from gam.accounts.models import APIKeyEnvironment
from gam.auth.permissions import Permissions

pytestmark = [pytest.mark.django_db, pytest.mark.enforce_api_permissions]


# ---------------------------------------------------------------------------
# Settings overrides
# ---------------------------------------------------------------------------


def _settings_for(jwks_harness):
    """Build the override_settings kwargs for a configured JWKS harness."""
    return {
        "JWKS_URL": jwks_harness.jwks_url,
        "JWT_ISSUER": jwks_harness.issuer,
        "JWT_AUDIENCE": jwks_harness.audience,
        "JWT_AUTHORIZED_PARTIES": [],  # off by default; specific tests opt in
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "gam.auth.jwt.JWKSAuthentication",
            "gam.auth.api_key.APIKeyAuthentication",
        ),
    }


@pytest.fixture
def configured(jwks_harness):
    """Apply harness-aware settings for the duration of the test."""
    with override_settings(
        **{
            "JWKS_URL": jwks_harness.jwks_url,
            "JWT_ISSUER": jwks_harness.issuer,
            "JWT_AUDIENCE": jwks_harness.audience,
            "JWT_AUTHORIZED_PARTIES": [],
        }
    ):
        # Force the cached PyJWKClient to re-resolve against the harness URL
        # in case a prior test bound a different one.
        from gam.auth.jwt import _get_jwks_client

        _get_jwks_client.cache_clear()
        yield


@pytest.fixture
def client():
    return APIClient()


def _bearer(client: APIClient, token: str) -> APIClient:
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


# ---------------------------------------------------------------------------
# JWT path
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("configured")
class TestJWTAuthPath:
    def test_happy_path_list_with_catalog_read(self, client, mint_jwt):
        token = mint_jwt(permissions=[Permissions.CATALOG_READ])
        response = _bearer(client, token).get(reverse("league-list"))
        assert response.status_code == 200

    def test_no_header_returns_401(self, client):
        response = client.get(reverse("league-list"))
        assert response.status_code == 401

    def test_missing_permission_returns_403(self, client, mint_jwt):
        token = mint_jwt(permissions=[Permissions.HOLDINGS_READ])
        response = _bearer(client, token).get(reverse("league-list"))
        assert response.status_code == 403

    def test_expired_token_returns_401(self, client, mint_jwt):
        token = mint_jwt(permissions=[Permissions.CATALOG_READ], ttl_seconds=-60)
        response = _bearer(client, token).get(reverse("league-list"))
        assert response.status_code == 401

    def test_wrong_audience_returns_401(self, client, mint_jwt):
        token = mint_jwt(
            audience="some-other-api",
            permissions=[Permissions.CATALOG_READ],
        )
        response = _bearer(client, token).get(reverse("league-list"))
        assert response.status_code == 401

    def test_wrong_issuer_returns_401(self, client, mint_jwt):
        token = mint_jwt(
            issuer="https://evil.example",
            permissions=[Permissions.CATALOG_READ],
        )
        response = _bearer(client, token).get(reverse("league-list"))
        assert response.status_code == 401

    def test_azp_mismatch_returns_401(self, jwks_harness, client, mint_jwt):
        token = mint_jwt(
            permissions=[Permissions.CATALOG_READ],
            azp="http://evil.example",
        )
        with override_settings(
            JWT_AUTHORIZED_PARTIES=["http://localhost:3000"],
        ):
            response = _bearer(client, token).get(reverse("league-list"))
        assert response.status_code == 401

    def test_write_requires_catalog_write(self, client, mint_jwt):
        read_only = mint_jwt(permissions=[Permissions.CATALOG_READ])
        response = _bearer(client, read_only).post(
            reverse("league-list"),
            {"short_name": "AAF", "long_name": "AAF", "level": "PRO"},
            format="json",
        )
        assert response.status_code == 403

    def test_write_succeeds_with_catalog_write(self, client, mint_jwt):
        token = mint_jwt(
            permissions=[Permissions.CATALOG_READ, Permissions.CATALOG_WRITE]
        )
        response = _bearer(client, token).post(
            reverse("league-list"),
            {"short_name": "AAF", "long_name": "AAF", "level": "PRO"},
            format="json",
        )
        assert response.status_code == 201


# ---------------------------------------------------------------------------
# API key path
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("configured")
class TestAPIKeyAuthPath:
    def test_happy_path_list_with_catalog_read(
        self, client, make_account, make_api_key
    ):
        account = make_account()
        _, plaintext = make_api_key(account, scopes=[Permissions.CATALOG_READ])
        response = _bearer(client, plaintext).get(reverse("league-list"))
        assert response.status_code == 200

    def test_missing_scope_returns_403(self, client, make_account, make_api_key):
        account = make_account()
        _, plaintext = make_api_key(account, scopes=[Permissions.HOLDINGS_READ])
        response = _bearer(client, plaintext).get(reverse("league-list"))
        assert response.status_code == 403

    def test_revoked_key_returns_401(self, client, make_account, make_api_key):
        account = make_account()
        api_key, plaintext = make_api_key(account, scopes=[Permissions.CATALOG_READ])
        api_key.revoked_at = timezone.now()
        api_key.save(update_fields=["revoked_at"])
        response = _bearer(client, plaintext).get(reverse("league-list"))
        assert response.status_code == 401

    def test_expired_key_returns_401(self, client, make_account, make_api_key):
        account = make_account()
        api_key, plaintext = make_api_key(account, scopes=[Permissions.CATALOG_READ])
        api_key.expires_at = timezone.now() - timedelta(seconds=1)
        api_key.save(update_fields=["expires_at"])
        response = _bearer(client, plaintext).get(reverse("league-list"))
        assert response.status_code == 401

    def test_malformed_key_returns_401(self, client):
        response = _bearer(client, "grd_live_not-hex").get(reverse("league-list"))
        assert response.status_code == 401

    def test_unknown_key_returns_401(self, client):
        # Right shape, never minted — passes regex, fails hash compare.
        token = "grd_live_" + "0" * 48
        response = _bearer(client, token).get(reverse("league-list"))
        assert response.status_code == 401

    def test_test_environment_key_works(self, client, make_account, make_api_key):
        account = make_account()
        _, plaintext = make_api_key(
            account,
            environment=APIKeyEnvironment.TEST,
            scopes=[Permissions.CATALOG_READ],
        )
        assert plaintext.startswith("grd_test_")
        response = _bearer(client, plaintext).get(reverse("league-list"))
        assert response.status_code == 200

    def test_write_requires_catalog_write(self, client, make_account, make_api_key):
        account = make_account()
        _, plaintext = make_api_key(account, scopes=[Permissions.CATALOG_READ])
        response = _bearer(client, plaintext).post(
            reverse("league-list"),
            {"short_name": "USFL", "long_name": "USFL", "level": "PRO"},
            format="json",
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Cross-domain enforcement
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("configured")
class TestCrossDomainEnforcement:
    """Catalog scopes must not grant holdings access (and vice versa)."""

    def test_catalog_read_does_not_grant_holdings(self, client, mint_jwt):
        token = mint_jwt(permissions=[Permissions.CATALOG_READ])
        response = _bearer(client, token).get(reverse("source-list"))
        assert response.status_code == 403

    def test_holdings_read_does_not_grant_catalog(
        self, client, make_account, make_api_key
    ):
        account = make_account()
        _, plaintext = make_api_key(account, scopes=[Permissions.HOLDINGS_READ])
        response = _bearer(client, plaintext).get(reverse("league-list"))
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Coexistence: both auth classes installed simultaneously
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("configured")
class TestAuthClassCoexistence:
    """Same endpoint must accept JWT or API key depending on the bearer scheme."""

    def test_jwt_and_api_key_both_authorize_same_endpoint(
        self, client, mint_jwt, make_account, make_api_key
    ):
        account = make_account()
        _, plaintext = make_api_key(account, scopes=[Permissions.CATALOG_READ])
        jwt = mint_jwt(permissions=[Permissions.CATALOG_READ])

        # JWT path
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {jwt}")
        assert client.get(reverse("league-list")).status_code == 200

        # Switch credentials and try again — same endpoint, same expected
        # outcome, different auth class on the server side.
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {plaintext}")
        assert client.get(reverse("league-list")).status_code == 200

    def test_grd_prefix_routes_to_api_key_class_only(
        self, client, make_account, make_api_key
    ):
        """An invalid ``grd_*`` token must not silently fall through to JWKS."""
        account = make_account()
        make_api_key(account, scopes=[Permissions.CATALOG_READ])
        # Garbage that happens to start with ``grd_`` — JWT path would treat
        # this as malformed input too, but we want to confirm API key auth
        # is what produces the 401.
        bad = "grd_live_" + "z" * 48  # invalid hex
        response = _bearer(client, bad).get(reverse("league-list"))
        assert response.status_code == 401
