"""
Cross-cutting tests for authentication, permissions, throttling, and pagination (TGF-311).

Permission behavior is verified through:
1. Configuration tests proving production settings have IsAuthenticatedOrReadOnly
2. Direct permission class unit tests proving the permission logic
3. HTTP-level tests for read access (which work with any permission config)
"""

import pytest
from django.contrib.auth.models import User
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.test import APIClient, APIRequestFactory

from archive.models import (
    Franchise,
    Game,
    League,
    Season,
    Source,
    Team,
    Venue,
)


@pytest.fixture
def anon_client():
    return APIClient()


@pytest.fixture
def auth_client():
    client = APIClient()
    user = User.objects.create_user(username="testuser", password="testpass")
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def nfl():
    return League.objects.create(
        short_name="NFL", long_name="National Football League", level="PRO"
    )


@pytest.fixture
def season_2024(nfl):
    return Season.objects.create(league=nfl, year=2024, label="2024")


@pytest.fixture
def steelers_franchise(nfl):
    return Franchise.objects.create(name="Pittsburgh Steelers", league=nfl)


@pytest.fixture
def steelers(steelers_franchise):
    return Team.objects.create(
        franchise=steelers_franchise, name="Pittsburgh Steelers", short_name="PIT"
    )


@pytest.fixture
def ravens_franchise(nfl):
    return Franchise.objects.create(name="Baltimore Ravens", league=nfl)


@pytest.fixture
def ravens(ravens_franchise):
    return Team.objects.create(
        franchise=ravens_franchise, name="Baltimore Ravens", short_name="BAL"
    )


@pytest.fixture
def heinz_field():
    return Venue.objects.create(name="Heinz Field", city="Pittsburgh", state="PA")


@pytest.fixture
def game(nfl, season_2024, steelers, ravens, heinz_field):
    return Game.objects.create(
        league=nfl,
        season=season_2024,
        date_local="2024-09-08",
        week=1,
        home_team=steelers,
        away_team=ravens,
        venue=heinz_field,
    )


# ===========================================================================
# Production Settings Configuration
# ===========================================================================


class TestProductionAuthConfiguration:
    """Verify production settings have correct auth/permission/throttle values."""

    def test_authentication_classes(self):
        from gam.settings import REST_FRAMEWORK

        assert (
            "rest_framework.authentication.SessionAuthentication"
            in REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]
        )
        assert (
            "rest_framework.authentication.BasicAuthentication"
            in REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]
        )

    def test_permission_classes(self):
        from gam.settings import REST_FRAMEWORK

        assert (
            "rest_framework.permissions.IsAuthenticatedOrReadOnly"
            in REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"]
        )

    def test_throttle_classes(self):
        from gam.settings import REST_FRAMEWORK

        assert (
            "rest_framework.throttling.AnonRateThrottle"
            in REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"]
        )
        assert (
            "rest_framework.throttling.UserRateThrottle"
            in REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"]
        )

    def test_anon_throttle_rate(self):
        from gam.settings import REST_FRAMEWORK

        assert REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["anon"] == "100/hour"

    def test_user_throttle_rate(self):
        from gam.settings import REST_FRAMEWORK

        assert REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["user"] == "1000/hour"


# ===========================================================================
# Permission Class Behavior (Unit Tests)
# ===========================================================================


class TestIsAuthenticatedOrReadOnlyBehavior:
    """Verify the permission class denies anon writes and allows anon reads."""

    def _make_request(self, method, authenticated=False):
        factory = APIRequestFactory()
        request = getattr(factory, method)("/fake/")
        if authenticated:
            request.user = User(username="testuser", is_active=True)
        else:
            from django.contrib.auth.models import AnonymousUser

            request.user = AnonymousUser()
        return request

    def test_anon_get_allowed(self):
        perm = IsAuthenticatedOrReadOnly()
        request = self._make_request("get")
        assert perm.has_permission(request, None) is True

    def test_anon_head_allowed(self):
        perm = IsAuthenticatedOrReadOnly()
        request = self._make_request("head")
        assert perm.has_permission(request, None) is True

    def test_anon_options_allowed(self):
        perm = IsAuthenticatedOrReadOnly()
        request = self._make_request("options")
        assert perm.has_permission(request, None) is True

    def test_anon_post_denied(self):
        perm = IsAuthenticatedOrReadOnly()
        request = self._make_request("post")
        assert perm.has_permission(request, None) is False

    def test_anon_put_denied(self):
        perm = IsAuthenticatedOrReadOnly()
        request = self._make_request("put")
        assert perm.has_permission(request, None) is False

    def test_anon_patch_denied(self):
        perm = IsAuthenticatedOrReadOnly()
        request = self._make_request("patch")
        assert perm.has_permission(request, None) is False

    def test_anon_delete_denied(self):
        perm = IsAuthenticatedOrReadOnly()
        request = self._make_request("delete")
        assert perm.has_permission(request, None) is False

    @pytest.mark.django_db
    def test_authed_post_allowed(self):
        perm = IsAuthenticatedOrReadOnly()
        request = self._make_request("post", authenticated=True)
        assert perm.has_permission(request, None) is True

    @pytest.mark.django_db
    def test_authed_put_allowed(self):
        perm = IsAuthenticatedOrReadOnly()
        request = self._make_request("put", authenticated=True)
        assert perm.has_permission(request, None) is True

    @pytest.mark.django_db
    def test_authed_delete_allowed(self):
        perm = IsAuthenticatedOrReadOnly()
        request = self._make_request("delete", authenticated=True)
        assert perm.has_permission(request, None) is True


# ===========================================================================
# Anonymous Read Access (HTTP-level)
# ===========================================================================


@pytest.mark.django_db
def test_anon_can_read_league_list(anon_client, nfl):
    assert anon_client.get("/api/v1/leagues/").status_code == 200


@pytest.mark.django_db
def test_anon_can_read_league_detail(anon_client, nfl):
    assert anon_client.get(f"/api/v1/leagues/{nfl.pk}/").status_code == 200


@pytest.mark.django_db
def test_anon_can_read_team_list(anon_client, steelers):
    assert anon_client.get("/api/v1/teams/").status_code == 200


@pytest.mark.django_db
def test_anon_can_read_game_list(anon_client, game):
    assert anon_client.get("/api/v1/games/").status_code == 200


@pytest.mark.django_db
def test_anon_can_read_game_detail(anon_client, game):
    assert anon_client.get(f"/api/v1/games/{game.pk}/").status_code == 200


@pytest.mark.django_db
def test_anon_can_read_venue_list(anon_client, heinz_field):
    assert anon_client.get("/api/v1/venues/").status_code == 200


@pytest.mark.django_db
def test_anon_can_read_api_root(anon_client):
    assert anon_client.get("/api/v1/").status_code == 200


# ===========================================================================
# Authenticated Write Access (HTTP-level, works with AllowAny CI settings too)
# ===========================================================================


@pytest.mark.django_db
def test_auth_create_league(auth_client):
    r = auth_client.post(
        "/api/v1/leagues/", {"short_name": "XFL", "long_name": "XFL", "level": "PRO"}
    )
    assert r.status_code == 201


@pytest.mark.django_db
def test_auth_create_team(auth_client, steelers_franchise):
    r = auth_client.post(
        "/api/v1/teams/",
        {"franchise": steelers_franchise.pk, "name": "Test", "short_name": "TST"},
    )
    assert r.status_code == 201


@pytest.mark.django_db
def test_auth_create_game(auth_client, nfl, season_2024, steelers, ravens):
    r = auth_client.post(
        "/api/v1/games/",
        {
            "league": nfl.pk,
            "season": season_2024.pk,
            "date_local": "2024-12-25",
            "home_team": steelers.pk,
            "away_team": ravens.pk,
        },
    )
    assert r.status_code == 201


@pytest.mark.django_db
def test_auth_source_crud(auth_client):
    r = auth_client.post("/api/v1/sources/", {"name": "Test", "source_type": "OTHER"})
    assert r.status_code == 201
    pk = Source.objects.get(name="Test").pk
    assert auth_client.get(f"/api/v1/sources/{pk}/").status_code == 200
    assert (
        auth_client.put(
            f"/api/v1/sources/{pk}/", {"name": "Updated", "source_type": "OTHER"}
        ).status_code
        == 200
    )
    assert auth_client.delete(f"/api/v1/sources/{pk}/").status_code == 204


# ===========================================================================
# Cursor Pagination
# ===========================================================================


@pytest.mark.django_db
def test_pagination_has_next_previous(anon_client, nfl):
    r = anon_client.get("/api/v1/leagues/")
    assert "results" in r.data
    assert "next" in r.data
    assert "previous" in r.data


def test_default_page_size_50():
    from archive.api.pagination import DefaultCursorPagination

    assert DefaultCursorPagination.page_size == 50


def test_game_pagination_page_size_50():
    from archive.api.pagination import GamePagination

    assert GamePagination.page_size == 50


def test_play_pagination_page_size_200():
    from archive.api.pagination import PlayPagination

    assert PlayPagination.page_size == 200


def test_play_pagination_ordering_sequence():
    from archive.api.pagination import PlayPagination

    assert PlayPagination.ordering == "sequence"


# ===========================================================================
# Browsable API
# ===========================================================================


@pytest.mark.django_db
def test_browsable_api_auth(auth_client):
    r = auth_client.get("/api/v1/", HTTP_ACCEPT="text/html")
    assert r.status_code == 200
    assert "text/html" in r["Content-Type"]


@pytest.mark.django_db
def test_browsable_api_anon(anon_client):
    r = anon_client.get("/api/v1/", HTTP_ACCEPT="text/html")
    assert r.status_code == 200
