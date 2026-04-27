"""
Unit and integration tests for :class:`gam.auth.permissions.HasAPIPermission`
and the catalog/holdings permission mixins (TGF-316).

The unit block exercises claim parsing, action dispatch, and the various
``required_permissions`` shapes the class supports. The integration block
proves enforcement actually fires through DRF on a real viewset for each of
the four catalog entries.
"""

from __future__ import annotations

import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIRequestFactory, force_authenticate

from archive.api.viewsets.league import LeagueViewSet
from archive.api.viewsets.source import SourceViewSet
from archive.models import League, Source
from gam.auth.jwt import JWTPrincipal
from gam.auth.permissions import (
    CATALOG_PERMISSIONS,
    HOLDINGS_PERMISSIONS,
    CatalogPermissionMixin,
    HasAPIPermission,
    HoldingsPermissionMixin,
    Permissions,
)

# Every test in this module verifies the real enforcement path; opt out of
# the project-wide conftest bypass.
pytestmark = pytest.mark.enforce_api_permissions


# ---------------------------------------------------------------------------
# Token-claim parsing
# ---------------------------------------------------------------------------


class _StubView:
    def __init__(self, action="list", required_permissions=None):
        self.action = action
        self.required_permissions = required_permissions


def _request(factory, *, claims, method="get"):
    builder = getattr(factory, method)
    request = builder("/")
    request.auth = claims
    return request


@pytest.fixture
def factory() -> APIRequestFactory:
    return APIRequestFactory()


class TestTokenPermissionParsing:
    @pytest.mark.parametrize(
        "claim_value,expected",
        [
            (["catalog:read", "holdings:read"], {"catalog:read", "holdings:read"}),
            ("catalog:read holdings:read", {"catalog:read", "holdings:read"}),
            ("catalog:read", {"catalog:read"}),
            ("", set()),
            ([], set()),
            (None, set()),
        ],
    )
    def test_normalizes_claim_shapes(self, factory, claim_value, expected):
        request = _request(factory, claims={"permissions": claim_value})
        view = _StubView(action="list", required_permissions=["catalog:read"])
        # When the required perm is in the parsed set, permission is granted.
        # We use this to indirectly verify normalization.
        result = HasAPIPermission().has_permission(request, view)
        assert result is ("catalog:read" in expected)

    def test_missing_permissions_claim_is_empty(self, factory):
        request = _request(factory, claims={"sub": "u1"})
        view = _StubView(action="list", required_permissions=["catalog:read"])
        assert HasAPIPermission().has_permission(request, view) is False

    def test_request_auth_none_is_empty(self, factory):
        request = _request(factory, claims=None)
        view = _StubView(action="list", required_permissions=["catalog:read"])
        assert HasAPIPermission().has_permission(request, view) is False

    def test_request_auth_non_dict_is_empty(self, factory):
        """Defensive: if auth ever becomes a non-dict, treat as no perms."""
        request = _request(factory, claims="some-opaque-token")
        view = _StubView(action="list", required_permissions=["catalog:read"])
        assert HasAPIPermission().has_permission(request, view) is False


# ---------------------------------------------------------------------------
# required_permissions resolution
# ---------------------------------------------------------------------------


class TestRequiredPermissionsResolution:
    def test_no_required_permissions_passes(self, factory):
        request = _request(factory, claims={"permissions": []})
        view = _StubView(action="list", required_permissions=None)
        assert HasAPIPermission().has_permission(request, view) is True

    def test_empty_required_permissions_passes(self, factory):
        request = _request(factory, claims={"permissions": []})
        view = _StubView(action="list", required_permissions=[])
        assert HasAPIPermission().has_permission(request, view) is True

    def test_list_form_applies_to_all_actions(self, factory):
        request = _request(
            factory,
            claims={"permissions": ["catalog:read"]},
        )
        view = _StubView(action="create", required_permissions=["catalog:read"])
        assert HasAPIPermission().has_permission(request, view) is True

    def test_string_form_treated_as_single_required_perm(self, factory):
        request = _request(factory, claims={"permissions": ["catalog:read"]})
        view = _StubView(action="list", required_permissions="catalog:read")
        assert HasAPIPermission().has_permission(request, view) is True

    def test_dict_form_dispatches_on_action(self, factory):
        view = _StubView(
            action="create",
            required_permissions={
                "list": ["catalog:read"],
                "create": ["catalog:write"],
            },
        )
        # Token has only read; create should be denied.
        request = _request(factory, claims={"permissions": ["catalog:read"]})
        assert HasAPIPermission().has_permission(request, view) is False

        # Add write; create should pass.
        request = _request(
            factory,
            claims={"permissions": ["catalog:read", "catalog:write"]},
        )
        assert HasAPIPermission().has_permission(request, view) is True

    def test_dict_form_falls_back_to_default(self, factory):
        view = _StubView(
            action="merge_into",  # custom @action not in the map
            required_permissions={
                "list": ["catalog:read"],
                "default": ["catalog:write"],
            },
        )
        request = _request(factory, claims={"permissions": ["catalog:write"]})
        assert HasAPIPermission().has_permission(request, view) is True

    def test_unmapped_action_with_no_default_passes(self, factory):
        """Actions absent from the dict and with no `default` aren't gated."""
        view = _StubView(
            action="custom",
            required_permissions={"list": ["catalog:read"]},
        )
        request = _request(factory, claims={"permissions": []})
        assert HasAPIPermission().has_permission(request, view) is True

    def test_subset_match_required(self, factory):
        """All required perms must be present, not just any of them."""
        view = _StubView(
            action="custom",
            required_permissions=["catalog:read", "holdings:read"],
        )
        request = _request(factory, claims={"permissions": ["catalog:read"]})
        assert HasAPIPermission().has_permission(request, view) is False

        request = _request(
            factory, claims={"permissions": ["catalog:read", "holdings:read"]}
        )
        assert HasAPIPermission().has_permission(request, view) is True


# ---------------------------------------------------------------------------
# Mixin wiring
# ---------------------------------------------------------------------------


class TestMixinWiring:
    def test_catalog_mixin_attaches_class_and_map(self):
        assert HasAPIPermission in CatalogPermissionMixin.permission_classes
        assert CatalogPermissionMixin.required_permissions is CATALOG_PERMISSIONS

    def test_holdings_mixin_attaches_class_and_map(self):
        assert HasAPIPermission in HoldingsPermissionMixin.permission_classes
        assert HoldingsPermissionMixin.required_permissions is HOLDINGS_PERMISSIONS

    def test_catalog_map_covers_standard_actions(self):
        for action in (
            "list",
            "retrieve",
            "create",
            "update",
            "partial_update",
            "destroy",
        ):
            assert action in CATALOG_PERMISSIONS
        assert "default" in CATALOG_PERMISSIONS

    def test_holdings_map_covers_standard_actions(self):
        for action in (
            "list",
            "retrieve",
            "create",
            "update",
            "partial_update",
            "destroy",
        ):
            assert action in HOLDINGS_PERMISSIONS
        assert "default" in HOLDINGS_PERMISSIONS

    def test_league_viewset_inherits_catalog_mixin(self):
        assert issubclass(LeagueViewSet, CatalogPermissionMixin)

    def test_source_viewset_inherits_holdings_mixin(self):
        assert issubclass(SourceViewSet, HoldingsPermissionMixin)


# ---------------------------------------------------------------------------
# Integration: enforcement against real viewsets
# ---------------------------------------------------------------------------


# Skip the auth class globally during these tests so request.auth is whatever
# we attach via force_authenticate, not whatever JWKSAuthentication makes of
# an empty header.
_NO_AUTH = {"DEFAULT_AUTHENTICATION_CLASSES": []}


def _force_auth(request, perms):
    principal = JWTPrincipal(claims={"sub": "u1", "permissions": list(perms)})
    force_authenticate(request, user=principal, token={"permissions": list(perms)})


@pytest.mark.django_db
@pytest.mark.enforce_api_permissions
class TestEnforcementOnLeagueViewSet:
    """Demonstrates ``catalog:read`` and ``catalog:write`` enforcement."""

    def setup_method(self):
        League.objects.create(short_name="NFL", long_name="NFL", level="PRO")

    @override_settings(**_NO_AUTH)
    def test_list_denied_without_catalog_read(self):
        from rest_framework.test import APIClient

        client = APIClient()
        principal = JWTPrincipal(claims={"sub": "u1", "permissions": []})
        client.force_authenticate(user=principal, token={"permissions": []})
        response = client.get(reverse("league-list"))
        assert response.status_code == 403

    @override_settings(**_NO_AUTH)
    def test_list_allowed_with_catalog_read(self):
        from rest_framework.test import APIClient

        client = APIClient()
        principal = JWTPrincipal(
            claims={"sub": "u1", "permissions": [Permissions.CATALOG_READ]}
        )
        client.force_authenticate(
            user=principal, token={"permissions": [Permissions.CATALOG_READ]}
        )
        response = client.get(reverse("league-list"))
        assert response.status_code == 200

    @override_settings(**_NO_AUTH)
    def test_create_denied_with_only_read(self):
        from rest_framework.test import APIClient

        client = APIClient()
        principal = JWTPrincipal(
            claims={"sub": "u1", "permissions": [Permissions.CATALOG_READ]}
        )
        client.force_authenticate(
            user=principal, token={"permissions": [Permissions.CATALOG_READ]}
        )
        response = client.post(
            reverse("league-list"),
            {"short_name": "AAF", "long_name": "AAF", "level": "PRO"},
            format="json",
        )
        assert response.status_code == 403

    @override_settings(**_NO_AUTH)
    def test_create_allowed_with_catalog_write(self):
        from rest_framework.test import APIClient

        client = APIClient()
        perms = [Permissions.CATALOG_READ, Permissions.CATALOG_WRITE]
        principal = JWTPrincipal(claims={"sub": "u1", "permissions": perms})
        client.force_authenticate(user=principal, token={"permissions": perms})
        response = client.post(
            reverse("league-list"),
            {"short_name": "AAF", "long_name": "AAF", "level": "PRO"},
            format="json",
        )
        assert response.status_code == 201


@pytest.mark.django_db
@pytest.mark.enforce_api_permissions
class TestEnforcementOnSourceViewSet:
    """Demonstrates ``holdings:read`` and ``holdings:write`` enforcement."""

    def setup_method(self):
        Source.objects.create(name="Test Source", source_type="STREAMING")

    @override_settings(**_NO_AUTH)
    def test_list_denied_without_holdings_read(self):
        from rest_framework.test import APIClient

        client = APIClient()
        principal = JWTPrincipal(
            claims={"sub": "u1", "permissions": [Permissions.CATALOG_READ]}
        )
        client.force_authenticate(
            user=principal, token={"permissions": [Permissions.CATALOG_READ]}
        )
        response = client.get(reverse("source-list"))
        assert response.status_code == 403

    @override_settings(**_NO_AUTH)
    def test_list_allowed_with_holdings_read(self):
        from rest_framework.test import APIClient

        client = APIClient()
        perms = [Permissions.HOLDINGS_READ]
        principal = JWTPrincipal(claims={"sub": "u1", "permissions": perms})
        client.force_authenticate(user=principal, token={"permissions": perms})
        response = client.get(reverse("source-list"))
        assert response.status_code == 200

    @override_settings(**_NO_AUTH)
    def test_destroy_denied_with_only_read(self):
        from rest_framework.test import APIClient

        client = APIClient()
        source = Source.objects.first()
        perms = [Permissions.HOLDINGS_READ]
        principal = JWTPrincipal(claims={"sub": "u1", "permissions": perms})
        client.force_authenticate(user=principal, token={"permissions": perms})
        response = client.delete(reverse("source-detail", args=[source.pk]))
        assert response.status_code == 403

    @override_settings(**_NO_AUTH)
    def test_destroy_allowed_with_holdings_write(self):
        from rest_framework.test import APIClient

        client = APIClient()
        source = Source.objects.first()
        perms = [Permissions.HOLDINGS_READ, Permissions.HOLDINGS_WRITE]
        principal = JWTPrincipal(claims={"sub": "u1", "permissions": perms})
        client.force_authenticate(user=principal, token={"permissions": perms})
        response = client.delete(reverse("source-detail", args=[source.pk]))
        assert response.status_code == 204
