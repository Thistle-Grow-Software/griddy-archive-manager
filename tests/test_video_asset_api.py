"""Tests for VideoAsset serializers and viewset (TGF-303)."""

import pytest
from django.test import Client
from django.urls import reverse

from archive.api.serializers.video_asset import (
    VideoAssetDetailSerializer,
    VideoAssetListSerializer,
)
from archive.models import (
    Acquisition,
    Franchise,
    Game,
    League,
    Season,
    Source,
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
        city="Pittsburgh",
    )


@pytest.fixture
def ravens(ravens_franchise):
    return Team.objects.create(
        franchise=ravens_franchise,
        name="Baltimore Ravens",
        short_name="BAL",
        city="Baltimore",
    )


@pytest.fixture
def heinz_field():
    return Venue.objects.create(
        name="Heinz Field", city="Pittsburgh", state="PA", capacity=68400
    )


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


@pytest.fixture
def source():
    return Source.objects.create(name="NFL+", source_type="STREAMING")


@pytest.fixture
def acquisition(source):
    return Acquisition.objects.create(source=source, rights="PERSONAL_ONLY")


@pytest.fixture
def asset_full(game, acquisition):
    return VideoAsset.objects.create(
        game=game,
        acquisition=acquisition,
        asset_type="FULL",
        file_path="/media/games/steelers_ravens_2024_full.mkv",
        container="mkv",
        video_codec="hevc",
        audio_codec="aac",
        resolution_w=1920,
        resolution_h=1080,
        duration_seconds=11400,
        file_size_bytes=8_500_000_000,
        quality_tier="A",
        quality_notes="Excellent quality, no commercials",
        is_preferred=True,
        checksum_sha256="abc123def456",
    )


@pytest.fixture
def asset_condensed(game):
    return VideoAsset.objects.create(
        game=game,
        asset_type="CONDENSED",
        file_path="/media/games/steelers_ravens_2024_condensed.mp4",
        container="mp4",
        duration_seconds=2400,
        file_size_bytes=1_200_000_000,
        quality_tier="B",
    )


# --- VideoAssetListSerializer ---


@pytest.mark.django_db
def test_list_serializer_fields(asset_full, game):
    """ListSerializer includes id, game, asset_type, quality_tier, file_size, duration, is_preferred, created_at."""
    asset = VideoAsset.objects.select_related("game").get(pk=asset_full.pk)
    data = VideoAssetListSerializer(asset).data
    assert data["id"] == asset_full.pk
    assert data["game"] == game.pk
    assert data["asset_type"] == "FULL"
    assert data["quality_tier"] == "A"
    assert data["file_size_bytes"] == 8_500_000_000
    assert data["duration_seconds"] == 11400
    assert data["is_preferred"] is True
    assert "created_at" in data


# --- VideoAssetDetailSerializer ---


@pytest.mark.django_db
def test_detail_serializer_all_fields(asset_full):
    """DetailSerializer includes all fields."""
    asset = VideoAsset.objects.select_related("game", "acquisition").get(
        pk=asset_full.pk
    )
    data = VideoAssetDetailSerializer(asset).data
    assert data["file_path"] == "/media/games/steelers_ravens_2024_full.mkv"
    assert data["video_codec"] == "hevc"
    assert data["audio_codec"] == "aac"
    assert data["resolution_w"] == 1920
    assert data["resolution_h"] == 1080
    assert data["quality_notes"] == "Excellent quality, no commercials"
    assert data["checksum_sha256"] == "abc123def456"
    assert "source_url" in data
    assert "bonus_data" in data


# --- ViewSet endpoints ---


@pytest.mark.django_db
def test_video_asset_list(client, asset_full, asset_condensed):
    """GET /api/v1/video-assets/ returns assets."""
    response = client.get("/api/v1/video-assets/", HTTP_ACCEPT="application/json")
    assert response.status_code == 200
    assert "results" in response.json()


@pytest.mark.django_db
def test_video_asset_retrieve(client, asset_full):
    """GET /api/v1/video-assets/<id>/ returns detail."""
    response = client.get(
        f"/api/v1/video-assets/{asset_full.pk}/", HTTP_ACCEPT="application/json"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["video_codec"] == "hevc"
    assert data["checksum_sha256"] == "abc123def456"


@pytest.mark.django_db
def test_video_asset_create(client, game):
    """POST /api/v1/video-assets/ creates an asset."""
    response = client.post(
        "/api/v1/video-assets/",
        data={
            "game": game.pk,
            "asset_type": "ALL22",
            "file_path": "/media/games/all22.mkv",
            "quality_tier": "B",
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    assert VideoAsset.objects.filter(game=game, asset_type="ALL22").exists()


@pytest.mark.django_db
def test_video_asset_update(client, asset_condensed, game):
    """PUT /api/v1/video-assets/<id>/ updates the asset."""
    response = client.put(
        f"/api/v1/video-assets/{asset_condensed.pk}/",
        data={
            "game": game.pk,
            "asset_type": "CONDENSED",
            "file_path": "/media/games/steelers_ravens_2024_condensed.mp4",
            "quality_tier": "A",
        },
        content_type="application/json",
    )
    assert response.status_code == 200
    asset_condensed.refresh_from_db()
    assert asset_condensed.quality_tier == "A"


@pytest.mark.django_db
def test_video_asset_delete(client, asset_condensed):
    """DELETE /api/v1/video-assets/<id>/ deletes the asset."""
    response = client.delete(f"/api/v1/video-assets/{asset_condensed.pk}/")
    assert response.status_code == 204
    assert not VideoAsset.objects.filter(pk=asset_condensed.pk).exists()


# --- Filters ---


@pytest.mark.django_db
def test_filter_by_game(client, asset_full, game):
    """?game=<id> filters by game."""
    response = client.get(
        f"/api/v1/video-assets/?game={game.pk}", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert all(r["game"] == game.pk for r in results)


@pytest.mark.django_db
def test_filter_by_asset_type(client, asset_full, asset_condensed):
    """?asset_type=FULL filters by asset type."""
    response = client.get(
        "/api/v1/video-assets/?asset_type=FULL", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["asset_type"] == "FULL"


@pytest.mark.django_db
def test_filter_by_quality_tier(client, asset_full, asset_condensed):
    """?quality_tier=A filters by quality tier."""
    response = client.get(
        "/api/v1/video-assets/?quality_tier=A", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 1


@pytest.mark.django_db
def test_filter_by_is_preferred(client, asset_full, asset_condensed):
    """?is_preferred=true filters to preferred assets."""
    response = client.get(
        "/api/v1/video-assets/?is_preferred=true", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["is_preferred"] is True


# --- Search ---


@pytest.mark.django_db
def test_search_by_file_path(client, asset_full, asset_condensed):
    """?search=condensed finds by file_path."""
    response = client.get(
        "/api/v1/video-assets/?search=condensed", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 1


# --- Router ---


@pytest.mark.django_db
def test_video_assets_registered_on_router():
    """VideoAssetViewSet must be registered at /video-assets/."""
    url = reverse("videoasset-list")
    assert url == "/api/v1/video-assets/"
