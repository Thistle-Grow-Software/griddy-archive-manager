"""End-to-end tests for ``GET /api/v1/games/{id}/playback/`` (TGF-360).

Drives the full DRF stack — authentication, :class:`HasAPIPermission`, the
``GameViewSet`` playback action, the playback-token signer — so the response
shape and entitlement gates documented in ADR-0008 are pinned by tests.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from archive.models import Franchise, Game, League, Season, Team
from gam.auth.permissions import Permissions
from gam.playback.tokens import (
    DEFAULT_ALGORITHM,
    DEFAULT_AUDIENCE,
    DEFAULT_ISSUER,
    MAX_TTL_SECONDS,
)

pytestmark = [pytest.mark.django_db, pytest.mark.enforce_api_permissions]


SHARED_SECRET = "test-playback-secret-with-at-least-32-bytes"
LOCAL_ORIGIN = "http://localhost:8787"
PROD_ORIGIN = "https://video.dev.griddy.football"


@pytest.fixture
def configured(jwks_harness):
    with override_settings(
        JWKS_URL=jwks_harness.jwks_url,
        JWT_ISSUER=jwks_harness.issuer,
        JWT_AUDIENCE=jwks_harness.audience,
        JWT_AUTHORIZED_PARTIES=[],
        PLAYBACK_TOKEN_SECRET=SHARED_SECRET,
        PLAYBACK_TOKEN_ALGORITHM=DEFAULT_ALGORITHM,
        PLAYBACK_TOKEN_ISSUER=DEFAULT_ISSUER,
        PLAYBACK_TOKEN_AUDIENCE=DEFAULT_AUDIENCE,
        PLAYBACK_TOKEN_TTL_SECONDS=900,
        VIDEO_ORIGIN_URL=LOCAL_ORIGIN,
    ):
        from gam.auth.jwt import _get_jwks_client

        _get_jwks_client.cache_clear()
        yield


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def nfl():
    return League.objects.create(short_name="NFL", long_name="NFL", level="PRO")


@pytest.fixture
def season(nfl):
    return Season.objects.create(league=nfl, year=2024, label="2024")


@pytest.fixture
def teams(nfl):
    home_fr = Franchise.objects.create(name="Pittsburgh Steelers", league=nfl)
    away_fr = Franchise.objects.create(name="Baltimore Ravens", league=nfl)
    home = Team.objects.create(
        franchise=home_fr, name="Steelers", short_name="PIT", city="Pittsburgh"
    )
    away = Team.objects.create(
        franchise=away_fr, name="Ravens", short_name="BAL", city="Baltimore"
    )
    return home, away


@pytest.fixture
def game(nfl, season, teams):
    home, away = teams
    return Game.objects.create(
        league=nfl,
        season=season,
        date_local="2024-09-08",
        week=1,
        home_team=home,
        away_team=away,
    )


def _bearer(client: APIClient, token: str) -> APIClient:
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.mark.usefixtures("configured")
class TestPlaybackAuthGating:
    def test_unauthenticated_returns_401(self, client, game):
        response = client.get(reverse("game-playback", args=[game.id]))
        assert response.status_code == 401
        assert "url" not in response.json()

    def test_authenticated_without_playback_scope_returns_403(
        self, client, mint_jwt, game
    ):
        # catalog:read alone does not grant playback — entitlement gating
        # rides on the dedicated video:playback scope.
        token = mint_jwt(permissions=[Permissions.CATALOG_READ])
        response = _bearer(client, token).get(reverse("game-playback", args=[game.id]))
        assert response.status_code == 403

    def test_unknown_game_id_returns_404(self, client, mint_jwt):
        token = mint_jwt(permissions=[Permissions.VIDEO_PLAYBACK])
        response = _bearer(client, token).get(reverse("game-playback", args=[999_999]))
        assert response.status_code == 404


@pytest.mark.usefixtures("configured")
class TestPlaybackHappyPath:
    def test_returns_200_with_expected_shape(self, client, mint_jwt, game):
        token = mint_jwt(sub="user_test", permissions=[Permissions.VIDEO_PLAYBACK])
        response = _bearer(client, token).get(reverse("game-playback", args=[game.id]))
        assert response.status_code == 200
        body = response.json()
        assert set(body.keys()) == {"type", "url", "expires_at"}
        assert body["type"] == "hls"

    def test_url_points_at_configured_video_origin(self, client, mint_jwt, game):
        token = mint_jwt(sub="user_test", permissions=[Permissions.VIDEO_PLAYBACK])
        response = _bearer(client, token).get(reverse("game-playback", args=[game.id]))
        parsed = urlparse(response.json()["url"])
        assert f"{parsed.scheme}://{parsed.netloc}" == LOCAL_ORIGIN
        assert parsed.path == f"/games/{game.id}/master.m3u8"

    def test_origin_is_env_driven(self, client, mint_jwt, game):
        """Same code, different env value, different host in the response."""
        token = mint_jwt(sub="user_test", permissions=[Permissions.VIDEO_PLAYBACK])
        with override_settings(VIDEO_ORIGIN_URL=PROD_ORIGIN):
            response = _bearer(client, token).get(
                reverse("game-playback", args=[game.id])
            )
        assert response.json()["url"].startswith(f"{PROD_ORIGIN}/games/{game.id}/")

    def test_token_round_trips_against_worker_secret(self, client, mint_jwt, game):
        """The Worker would verify with the same secret; assert that path works."""
        token = mint_jwt(sub="user_test", permissions=[Permissions.VIDEO_PLAYBACK])
        response = _bearer(client, token).get(reverse("game-playback", args=[game.id]))
        url = response.json()["url"]
        playback_token = parse_qs(urlparse(url).query)["t"][0]

        claims = jwt.decode(
            playback_token,
            SHARED_SECRET,
            algorithms=[DEFAULT_ALGORITHM],
            audience=DEFAULT_AUDIENCE,
            issuer=DEFAULT_ISSUER,
        )
        assert claims["sub"] == "user_test"
        assert claims["gid"] == str(game.id)

    def test_token_ttl_is_at_most_fifteen_minutes(self, client, mint_jwt, game):
        token = mint_jwt(sub="user_test", permissions=[Permissions.VIDEO_PLAYBACK])
        response = _bearer(client, token).get(reverse("game-playback", args=[game.id]))
        body = response.json()
        expires_at = datetime.fromisoformat(body["expires_at"].replace("Z", "+00:00"))
        url = body["url"]
        playback_token = parse_qs(urlparse(url).query)["t"][0]
        claims = jwt.decode(
            playback_token,
            SHARED_SECRET,
            algorithms=[DEFAULT_ALGORITHM],
            audience=DEFAULT_AUDIENCE,
            issuer=DEFAULT_ISSUER,
        )
        assert claims["exp"] - claims["iat"] <= MAX_TTL_SECONDS
        # ``expires_at`` in the body must match the ``exp`` claim in the token.
        assert int(expires_at.timestamp()) == claims["exp"]

    def test_ttl_setting_above_cap_is_clamped(self, client, mint_jwt, game):
        token = mint_jwt(sub="user_test", permissions=[Permissions.VIDEO_PLAYBACK])
        with override_settings(PLAYBACK_TOKEN_TTL_SECONDS=MAX_TTL_SECONDS * 10):
            response = _bearer(client, token).get(
                reverse("game-playback", args=[game.id])
            )
        playback_token = parse_qs(urlparse(response.json()["url"]).query)["t"][0]
        claims = jwt.decode(
            playback_token,
            SHARED_SECRET,
            algorithms=[DEFAULT_ALGORITHM],
            audience=DEFAULT_AUDIENCE,
            issuer=DEFAULT_ISSUER,
        )
        assert claims["exp"] - claims["iat"] == MAX_TTL_SECONDS
