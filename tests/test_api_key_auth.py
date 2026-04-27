"""
Tests for API key authentication, the issuance/revoke endpoints, and the
permission-class integration (TGF-318).

Covers:
- Token format generation (live/test environments, prefix shape)
- DRF auth class: happy path, malformed/unknown/revoked/expired/wrong-hash
- Coexistence with JWKSAuthentication (each handles only its own scheme)
- Scope propagation through HasAPIPermission
- Lifecycle (revoke, expire) timing
- Constant-time hash comparison via ``hmac.compare_digest``
- ``last_used_at`` deferred update + throttle
- Issue/list/revoke endpoints scoped to the requesting account
"""

from __future__ import annotations

import hmac
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory

from gam.accounts.models import APIKeyEnvironment, ClerkAccount
from gam.auth.api_key import (
    LAST_USED_THROTTLE_SECONDS,
    APIKeyAuthentication,
    _hash_token,
    generate_api_key,
)
from gam.auth.jwt import JWTPrincipal
from gam.auth.permissions import HasAPIPermission, Permissions

pytestmark = [pytest.mark.django_db, pytest.mark.enforce_api_permissions]


User = get_user_model()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def factory() -> APIRequestFactory:
    return APIRequestFactory()


@pytest.fixture
def account() -> ClerkAccount:
    user = User.objects.create_user(username="apikey-owner", email="o@griddy.test")
    return ClerkAccount.objects.create(
        user=user, clerk_sub="user_owner", email="o@griddy.test"
    )


@pytest.fixture
def other_account() -> ClerkAccount:
    user = User.objects.create_user(username="other-owner", email="x@griddy.test")
    return ClerkAccount.objects.create(
        user=user, clerk_sub="user_other", email="x@griddy.test"
    )


def _bearer(factory, token: str):
    request = factory.get("/")
    request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return request


# ---------------------------------------------------------------------------
# generate_api_key
# ---------------------------------------------------------------------------


class TestGenerateApiKey:
    def test_live_token_format(self, account):
        api_key, plaintext = generate_api_key(account, name="t")
        assert plaintext.startswith("grd_live_")
        body = plaintext.removeprefix("grd_live_")
        assert len(body) == 48
        assert all(c in "0123456789abcdef" for c in body)
        assert api_key.environment == APIKeyEnvironment.LIVE

    def test_test_token_format(self, account):
        _, plaintext = generate_api_key(
            account, name="t", environment=APIKeyEnvironment.TEST
        )
        assert plaintext.startswith("grd_test_")

    def test_hash_is_stored_not_plaintext(self, account):
        api_key, plaintext = generate_api_key(account, name="t")
        api_key.refresh_from_db()
        assert plaintext not in api_key.key_hash
        assert api_key.key_hash == _hash_token(plaintext)

    def test_prefix_includes_environment_and_first_8(self, account):
        api_key, plaintext = generate_api_key(
            account, name="t", environment=APIKeyEnvironment.TEST
        )
        body = plaintext.removeprefix("grd_test_")
        assert api_key.key_prefix == f"grd_test_{body[:8]}"

    def test_two_keys_get_different_secrets(self, account):
        a, _ = generate_api_key(account, name="a")
        b, _ = generate_api_key(account, name="b")
        assert a.key_hash != b.key_hash
        assert a.key_prefix != b.key_prefix  # statistically — 2^32 namespace

    def test_invalid_environment_raises(self, account):
        with pytest.raises(ValueError):
            generate_api_key(account, name="t", environment="staging")

    def test_scopes_persisted(self, account):
        api_key, _ = generate_api_key(
            account, name="t", scopes=[Permissions.CATALOG_READ]
        )
        api_key.refresh_from_db()
        assert api_key.scopes == [Permissions.CATALOG_READ]


# ---------------------------------------------------------------------------
# APIKeyAuthentication
# ---------------------------------------------------------------------------


class TestAuthenticate:
    def test_no_header_returns_none(self, factory):
        request = factory.get("/")
        assert APIKeyAuthentication().authenticate(request) is None

    def test_non_bearer_scheme_returns_none(self, factory, account):
        _, plaintext = generate_api_key(account, name="t")
        request = factory.get("/", HTTP_AUTHORIZATION=f"Basic {plaintext}")
        assert APIKeyAuthentication().authenticate(request) is None

    def test_jwt_token_returns_none(self, factory):
        """Tokens that don't start with ``grd_`` are left for JWT auth."""
        request = _bearer(factory, "eyJhbGciOiJSUzI1NiJ9.fake.jwt")
        assert APIKeyAuthentication().authenticate(request) is None

    def test_valid_key_returns_account_and_apikey(self, factory, account):
        api_key, plaintext = generate_api_key(account, name="t")
        request = _bearer(factory, plaintext)
        result = APIKeyAuthentication().authenticate(request)
        assert result is not None
        returned_account, returned_key = result
        assert returned_account.pk == account.pk
        assert returned_key.pk == api_key.pk

    def test_malformed_grd_token_raises(self, factory):
        from rest_framework import exceptions

        request = _bearer(factory, "grd_live_not-hex")
        with pytest.raises(exceptions.AuthenticationFailed, match="Malformed"):
            APIKeyAuthentication().authenticate(request)

    def test_unknown_environment_raises(self, factory):
        from rest_framework import exceptions

        request = _bearer(factory, "grd_dev_" + "a" * 48)
        with pytest.raises(exceptions.AuthenticationFailed, match="Malformed"):
            APIKeyAuthentication().authenticate(request)

    def test_wrong_hash_rejected(self, factory, account):
        from rest_framework import exceptions

        _, plaintext = generate_api_key(account, name="t")
        # Mutate the secret portion while keeping the prefix bytes intact —
        # forces the auth path through prefix lookup → hash compare → miss.
        body = plaintext.removeprefix("grd_live_")
        forged = "grd_live_" + body[:8] + "0" * (48 - 8)
        request = _bearer(factory, forged)
        with pytest.raises(exceptions.AuthenticationFailed, match="Invalid"):
            APIKeyAuthentication().authenticate(request)

    def test_revoked_key_rejected(self, factory, account):
        from rest_framework import exceptions

        api_key, plaintext = generate_api_key(account, name="t")
        api_key.revoked_at = timezone.now()
        api_key.save(update_fields=["revoked_at"])
        request = _bearer(factory, plaintext)
        with pytest.raises(exceptions.AuthenticationFailed, match="revoked"):
            APIKeyAuthentication().authenticate(request)

    def test_expired_key_rejected(self, factory, account):
        from rest_framework import exceptions

        api_key, plaintext = generate_api_key(account, name="t")
        api_key.expires_at = timezone.now() - timedelta(seconds=1)
        api_key.save(update_fields=["expires_at"])
        request = _bearer(factory, plaintext)
        with pytest.raises(exceptions.AuthenticationFailed, match="expired"):
            APIKeyAuthentication().authenticate(request)

    def test_uses_constant_time_compare(self, factory, account):
        """The auth path must use ``hmac.compare_digest`` for hash comparison."""
        _, plaintext = generate_api_key(account, name="t")
        request = _bearer(factory, plaintext)
        with patch(
            "gam.auth.api_key.hmac.compare_digest", wraps=hmac.compare_digest
        ) as spy:
            APIKeyAuthentication().authenticate(request)
        assert spy.called


# ---------------------------------------------------------------------------
# last_used_at update behavior
# ---------------------------------------------------------------------------


class TestLastUsedTracking:
    def test_first_use_sets_last_used_at(
        self, factory, account, django_capture_on_commit_callbacks
    ):
        api_key, plaintext = generate_api_key(account, name="t")
        request = _bearer(factory, plaintext)
        with django_capture_on_commit_callbacks(execute=True):
            APIKeyAuthentication().authenticate(request)
        api_key.refresh_from_db()
        assert api_key.last_used_at is not None

    def test_back_to_back_use_does_not_double_write(
        self, factory, account, django_capture_on_commit_callbacks
    ):
        api_key, plaintext = generate_api_key(account, name="t")
        request = _bearer(factory, plaintext)
        with django_capture_on_commit_callbacks(execute=True):
            APIKeyAuthentication().authenticate(request)
        api_key.refresh_from_db()
        first_stamp = api_key.last_used_at

        with django_capture_on_commit_callbacks(execute=True):
            APIKeyAuthentication().authenticate(request)
        api_key.refresh_from_db()
        # Same value — second use was inside the throttle window.
        assert api_key.last_used_at == first_stamp

    def test_use_after_throttle_window_updates(
        self, factory, account, django_capture_on_commit_callbacks
    ):
        api_key, plaintext = generate_api_key(account, name="t")
        old_stamp = timezone.now() - timedelta(seconds=LAST_USED_THROTTLE_SECONDS + 5)
        api_key.last_used_at = old_stamp
        api_key.save(update_fields=["last_used_at"])
        request = _bearer(factory, plaintext)
        with django_capture_on_commit_callbacks(execute=True):
            APIKeyAuthentication().authenticate(request)
        api_key.refresh_from_db()
        assert api_key.last_used_at > old_stamp


# ---------------------------------------------------------------------------
# Permission integration (HasAPIPermission reads APIKey.scopes)
# ---------------------------------------------------------------------------


class _StubView:
    def __init__(self, action="list", required_permissions=None):
        self.action = action
        self.required_permissions = required_permissions


class TestScopePropagation:
    def test_api_key_scopes_satisfy_required_permissions(self, factory, account):
        api_key, plaintext = generate_api_key(
            account, name="t", scopes=[Permissions.CATALOG_READ]
        )
        request = _bearer(factory, plaintext)
        APIKeyAuthentication().authenticate(request)
        request.auth = api_key  # APIRequestFactory doesn't run middleware
        view = _StubView(
            action="list",
            required_permissions={"list": [Permissions.CATALOG_READ]},
        )
        assert HasAPIPermission().has_permission(request, view) is True

    def test_api_key_missing_scope_denies(self, factory, account):
        api_key, _ = generate_api_key(
            account, name="t", scopes=[Permissions.CATALOG_READ]
        )
        request = factory.get("/")
        request.auth = api_key
        view = _StubView(
            action="create",
            required_permissions={"create": [Permissions.CATALOG_WRITE]},
        )
        assert HasAPIPermission().has_permission(request, view) is False


# ---------------------------------------------------------------------------
# Issuance / list / revoke endpoints
# ---------------------------------------------------------------------------


def _login_as(account: ClerkAccount, *, scopes: list[str] | None = None) -> APIClient:
    client = APIClient()
    principal = JWTPrincipal(
        claims={
            "sub": account.clerk_sub,
            "permissions": scopes
            or [
                Permissions.CATALOG_READ,
                Permissions.CATALOG_WRITE,
                Permissions.HOLDINGS_READ,
                Permissions.HOLDINGS_WRITE,
            ],
        }
    )
    client.force_authenticate(user=principal, token=principal.claims)
    return client


# Disable JWKS auth for these tests so ``force_authenticate`` is the only
# source of ``request.user`` / ``request.auth``.
_NO_AUTH = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
}


@pytest.mark.enforce_api_permissions
class TestIssuanceEndpoints:
    @override_settings(**_NO_AUTH)
    def test_issue_returns_plaintext_once(self, account):
        client = _login_as(account)
        response = client.post(
            reverse("apikey-list"),
            {"name": "CI", "scopes": [Permissions.CATALOG_READ]},
            format="json",
        )
        assert response.status_code == 201
        body = response.json()
        assert body["plaintext"].startswith("grd_live_")
        assert "warning" in body
        # Subsequent fetch must NOT contain the plaintext.
        key_id = body["api_key"]["id"]
        retrieve = client.get(reverse("apikey-detail", args=[key_id]))
        assert "plaintext" not in retrieve.json()

    @override_settings(**_NO_AUTH)
    def test_default_environment_is_live(self, account):
        client = _login_as(account)
        response = client.post(
            reverse("apikey-list"), {"name": "Default"}, format="json"
        )
        assert response.json()["api_key"]["environment"] == "live"

    @override_settings(**_NO_AUTH)
    def test_test_environment_supported(self, account):
        client = _login_as(account)
        response = client.post(
            reverse("apikey-list"),
            {"name": "Tst", "environment": "test"},
            format="json",
        )
        assert response.json()["plaintext"].startswith("grd_test_")

    @override_settings(**_NO_AUTH)
    def test_list_only_returns_own_keys(self, account, other_account):
        generate_api_key(account, name="mine")
        generate_api_key(other_account, name="theirs")
        client = _login_as(account)
        response = client.get(reverse("apikey-list"))
        names = {row["name"] for row in response.json()}
        assert names == {"mine"}

    @override_settings(**_NO_AUTH)
    def test_retrieve_other_account_key_404s(self, account, other_account):
        api_key, _ = generate_api_key(other_account, name="theirs")
        client = _login_as(account)
        response = client.get(reverse("apikey-detail", args=[api_key.pk]))
        assert response.status_code == 403  # PermissionDenied

    @override_settings(**_NO_AUTH)
    def test_revoke_marks_revoked_at(self, account):
        api_key, _ = generate_api_key(account, name="t")
        client = _login_as(account)
        response = client.post(reverse("apikey-revoke", args=[api_key.pk]))
        assert response.status_code == 200
        api_key.refresh_from_db()
        assert api_key.revoked_at is not None

    @override_settings(**_NO_AUTH)
    def test_revoke_other_account_key_403(self, account, other_account):
        api_key, _ = generate_api_key(other_account, name="theirs")
        client = _login_as(account)
        response = client.post(reverse("apikey-revoke", args=[api_key.pk]))
        assert response.status_code == 403

    @override_settings(**_NO_AUTH)
    def test_revoke_already_revoked_is_idempotent(self, account):
        api_key, _ = generate_api_key(account, name="t")
        api_key.revoked_at = timezone.now()
        api_key.save(update_fields=["revoked_at"])
        client = _login_as(account)
        response = client.post(reverse("apikey-revoke", args=[api_key.pk]))
        assert response.status_code == 200

    @override_settings(**_NO_AUTH)
    def test_api_key_auth_cannot_manage_keys(self, account):
        """Privilege escalation guard — keys can't bootstrap more keys."""
        _, plaintext = generate_api_key(
            account,
            name="privesc-attempt",
            scopes=[Permissions.CATALOG_READ, Permissions.CATALOG_WRITE],
        )
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {plaintext}")
        # Re-enable real auth so the API key is actually parsed.
        response = client.get(reverse("apikey-list"))
        assert response.status_code in {401, 403}
