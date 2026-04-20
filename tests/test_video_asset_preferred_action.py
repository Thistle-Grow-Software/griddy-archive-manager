"""Tests for VideoAsset preferred custom action (TGF-307)."""

import pytest
from django.test import Client

from archive.models import (
    Franchise,
    Game,
    League,
    Season,
    Team,
    Venue,
    VideoAsset,
)


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def nfl():
    return League.objects.create(
        short_name="NFL", long_name="National Football League", level="PRO"
    )


@pytest.fixture
def season_2024(nfl):
    return Season.objects.create(league=nfl, year=2024, label="2024")


@pytest.fixture
def season_2025(nfl):
    return Season.objects.create(league=nfl, year=2025, label="2025")


@pytest.fixture
def steelers_franchise(nfl):
    return Franchise.objects.create(name="Pittsburgh Steelers", league=nfl)


@pytest.fixture
def ravens_franchise(nfl):
    return Franchise.objects.create(name="Baltimore Ravens", league=nfl)


@pytest.fixture
def steelers(steelers_franchise):
    return Team.objects.create(
        franchise=steelers_franchise,
        name="Pittsburgh Steelers",
        short_name="PIT",
    )


@pytest.fixture
def ravens(ravens_franchise):
    return Team.objects.create(
        franchise=ravens_franchise,
        name="Baltimore Ravens",
        short_name="BAL",
    )


@pytest.fixture
def heinz_field():
    return Venue.objects.create(name="Heinz Field", city="Pittsburgh", state="PA")


@pytest.fixture
def game_2024(nfl, season_2024, steelers, ravens, heinz_field):
    return Game.objects.create(
        league=nfl,
        season=season_2024,
        date_local="2024-09-08",
        week=1,
        home_team=steelers,
        away_team=ravens,
        venue=heinz_field,
    )


@pytest.fixture
def game_2025(nfl, season_2025, steelers, ravens, heinz_field):
    return Game.objects.create(
        league=nfl,
        season=season_2025,
        date_local="2025-09-07",
        week=1,
        home_team=steelers,
        away_team=ravens,
        venue=heinz_field,
    )


@pytest.fixture
def preferred_2024(game_2024):
    return VideoAsset.objects.create(
        game=game_2024,
        file_path="/media/2024_wk1_preferred.mkv",
        asset_type="FULL",
        quality_tier="A",
        is_preferred=True,
    )


@pytest.fixture
def non_preferred_2024(game_2024):
    return VideoAsset.objects.create(
        game=game_2024,
        file_path="/media/2024_wk1_condensed.mp4",
        asset_type="CONDENSED",
        quality_tier="B",
        is_preferred=False,
    )


@pytest.fixture
def preferred_2025(game_2025):
    return VideoAsset.objects.create(
        game=game_2025,
        file_path="/media/2025_wk1_preferred.mkv",
        asset_type="FULL",
        quality_tier="A",
        is_preferred=True,
    )


@pytest.mark.django_db
def test_preferred_returns_200(client, preferred_2024):
    """GET /api/v1/video-assets/preferred/ returns 200."""
    response = client.get(
        "/api/v1/video-assets/preferred/", HTTP_ACCEPT="application/json"
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_preferred_only_returns_preferred_assets(
    client, preferred_2024, non_preferred_2024
):
    """Only assets with is_preferred=True are returned."""
    response = client.get(
        "/api/v1/video-assets/preferred/", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["is_preferred"] is True


@pytest.mark.django_db
def test_preferred_filters_by_season_year(client, preferred_2024, preferred_2025):
    """?season_year=2024 returns only preferred assets from that season."""
    response = client.get(
        "/api/v1/video-assets/preferred/?season_year=2024",
        HTTP_ACCEPT="application/json",
    )
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["game"] == preferred_2024.game_id


@pytest.mark.django_db
def test_preferred_without_season_year_returns_all(
    client, preferred_2024, preferred_2025
):
    """Without season_year, returns all preferred assets."""
    response = client.get(
        "/api/v1/video-assets/preferred/", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 2


@pytest.mark.django_db
def test_preferred_uses_list_serializer(client, preferred_2024):
    """Response uses VideoAssetListSerializer fields."""
    response = client.get(
        "/api/v1/video-assets/preferred/", HTTP_ACCEPT="application/json"
    )
    result = response.json()["results"][0]
    assert "id" in result
    assert "game" in result
    assert "asset_type" in result
    assert "quality_tier" in result
    assert "is_preferred" in result
    assert "created_at" in result


@pytest.mark.django_db
def test_preferred_empty_when_no_preferred(client, non_preferred_2024):
    """Returns empty results when no preferred assets exist."""
    response = client.get(
        "/api/v1/video-assets/preferred/", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 0
