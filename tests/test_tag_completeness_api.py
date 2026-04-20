"""Tests for Tag, AssetTag, and GameCompleteness serializers and viewsets (TGF-304)."""

import pytest
from django.test import Client
from django.urls import reverse

from archive.models import (
    Acquisition,
    AssetTag,
    Franchise,
    Game,
    GameCompleteness,
    League,
    Season,
    Source,
    Tag,
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
    return Acquisition.objects.create(source=source)


@pytest.fixture
def asset(game, acquisition):
    return VideoAsset.objects.create(
        game=game,
        acquisition=acquisition,
        file_path="/media/games/test.mkv",
        asset_type="FULL",
    )


@pytest.fixture
def tag_hd():
    return Tag.objects.create(name="HD")


@pytest.fixture
def tag_favorite():
    return Tag.objects.create(name="Favorite")


@pytest.fixture
def asset_tag(asset, tag_hd):
    return AssetTag.objects.create(asset=asset, tag=tag_hd)


@pytest.fixture
def completeness(game):
    return GameCompleteness.objects.create(
        game=game,
        scope="NFL_ALL",
        status="COMPLETE",
        has_full=True,
        has_condensed=True,
        has_all22=False,
        best_full_quality_score=85,
    )


@pytest.fixture
def completeness_partial(game):
    return GameCompleteness.objects.create(
        game=game,
        scope="STEELERS_ALL",
        status="PARTIAL",
        has_full=True,
        has_condensed=False,
        has_all22=False,
    )


# --- Tag CRUD ---


@pytest.mark.django_db
def test_tag_list(client, tag_hd, tag_favorite):
    """GET /api/v1/tags/ returns tags."""
    response = client.get("/api/v1/tags/", HTTP_ACCEPT="application/json")
    assert response.status_code == 200
    assert len(response.json()["results"]) == 2


@pytest.mark.django_db
def test_tag_retrieve(client, tag_hd):
    """GET /api/v1/tags/<id>/ returns tag."""
    response = client.get(f"/api/v1/tags/{tag_hd.pk}/", HTTP_ACCEPT="application/json")
    assert response.status_code == 200
    assert response.json()["name"] == "HD"


@pytest.mark.django_db
def test_tag_create(client):
    """POST /api/v1/tags/ creates a tag."""
    response = client.post(
        "/api/v1/tags/",
        data={"name": "4K"},
        content_type="application/json",
    )
    assert response.status_code == 201
    assert Tag.objects.filter(name="4K").exists()


@pytest.mark.django_db
def test_tag_update(client, tag_hd):
    """PUT /api/v1/tags/<id>/ updates the tag."""
    response = client.put(
        f"/api/v1/tags/{tag_hd.pk}/",
        data={"name": "HD 1080p"},
        content_type="application/json",
    )
    assert response.status_code == 200
    tag_hd.refresh_from_db()
    assert tag_hd.name == "HD 1080p"


@pytest.mark.django_db
def test_tag_delete(client, tag_hd):
    """DELETE /api/v1/tags/<id>/ deletes the tag."""
    response = client.delete(f"/api/v1/tags/{tag_hd.pk}/")
    assert response.status_code == 204
    assert not Tag.objects.filter(pk=tag_hd.pk).exists()


# --- AssetTag LIST, CREATE, DELETE ---


@pytest.mark.django_db
def test_asset_tag_list(client, asset_tag):
    """GET /api/v1/asset-tags/ returns asset tags."""
    response = client.get("/api/v1/asset-tags/", HTTP_ACCEPT="application/json")
    assert response.status_code == 200
    data = response.json()["results"]
    assert len(data) == 1
    assert data[0]["asset"] == asset_tag.asset_id
    assert data[0]["tag"] == asset_tag.tag_id


@pytest.mark.django_db
def test_asset_tag_create(client, asset, tag_favorite):
    """POST /api/v1/asset-tags/ creates an asset tag."""
    response = client.post(
        "/api/v1/asset-tags/",
        data={"asset": asset.pk, "tag": tag_favorite.pk},
        content_type="application/json",
    )
    assert response.status_code == 201
    assert AssetTag.objects.filter(asset=asset, tag=tag_favorite).exists()


@pytest.mark.django_db
def test_asset_tag_delete(client, asset_tag):
    """DELETE /api/v1/asset-tags/<id>/ deletes the asset tag."""
    response = client.delete(f"/api/v1/asset-tags/{asset_tag.pk}/")
    assert response.status_code == 204
    assert not AssetTag.objects.filter(pk=asset_tag.pk).exists()


@pytest.mark.django_db
def test_asset_tag_update_not_allowed(client, asset_tag):
    """PUT /api/v1/asset-tags/<id>/ is not supported."""
    response = client.put(
        f"/api/v1/asset-tags/{asset_tag.pk}/",
        data={"asset": asset_tag.asset_id, "tag": asset_tag.tag_id},
        content_type="application/json",
    )
    assert response.status_code == 405


# --- GameCompleteness ---


@pytest.mark.django_db
def test_completeness_list(client, completeness):
    """GET /api/v1/game-completeness/ returns results."""
    response = client.get("/api/v1/game-completeness/", HTTP_ACCEPT="application/json")
    assert response.status_code == 200
    assert "results" in response.json()


@pytest.mark.django_db
def test_completeness_retrieve(client, completeness):
    """GET /api/v1/game-completeness/<id>/ returns detail."""
    response = client.get(
        f"/api/v1/game-completeness/{completeness.pk}/",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["scope"] == "NFL_ALL"
    assert data["best_full_quality_score"] == 85
    assert "computed_at" in data


@pytest.mark.django_db
def test_completeness_create(client, game):
    """POST /api/v1/game-completeness/ creates a record."""
    response = client.post(
        "/api/v1/game-completeness/",
        data={
            "game": game.pk,
            "scope": "UGA_ALL",
            "status": "MISSING",
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    assert GameCompleteness.objects.filter(scope="UGA_ALL").exists()


@pytest.mark.django_db
def test_completeness_update(client, completeness, game):
    """PUT /api/v1/game-completeness/<id>/ updates the record."""
    response = client.put(
        f"/api/v1/game-completeness/{completeness.pk}/",
        data={
            "game": game.pk,
            "scope": "NFL_ALL",
            "status": "COMPLETE_NEEDS_UPGRADE",
            "has_full": True,
        },
        content_type="application/json",
    )
    assert response.status_code == 200
    completeness.refresh_from_db()
    assert completeness.status == "COMPLETE_NEEDS_UPGRADE"


@pytest.mark.django_db
def test_completeness_delete_not_allowed(client, completeness):
    """DELETE /api/v1/game-completeness/<id>/ is not supported."""
    response = client.delete(f"/api/v1/game-completeness/{completeness.pk}/")
    assert response.status_code == 405


# --- GameCompleteness filters ---


@pytest.mark.django_db
def test_completeness_filter_by_scope(client, completeness, completeness_partial):
    """?scope=NFL_ALL filters by scope."""
    response = client.get(
        "/api/v1/game-completeness/?scope=NFL_ALL", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["scope"] == "NFL_ALL"


@pytest.mark.django_db
def test_completeness_filter_by_status(client, completeness, completeness_partial):
    """?status=PARTIAL filters by status."""
    response = client.get(
        "/api/v1/game-completeness/?status=PARTIAL", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 1


@pytest.mark.django_db
def test_completeness_filter_by_has_condensed(
    client, completeness, completeness_partial
):
    """?has_condensed=true filters."""
    response = client.get(
        "/api/v1/game-completeness/?has_condensed=true", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["scope"] == "NFL_ALL"


# --- Router registration ---


@pytest.mark.django_db
def test_tags_registered():
    url = reverse("tag-list")
    assert url == "/api/v1/tags/"


@pytest.mark.django_db
def test_asset_tags_registered():
    url = reverse("assettag-list")
    assert url == "/api/v1/asset-tags/"


@pytest.mark.django_db
def test_game_completeness_registered():
    url = reverse("gamecompleteness-list")
    assert url == "/api/v1/game-completeness/"
