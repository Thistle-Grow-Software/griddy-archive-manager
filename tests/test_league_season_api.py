"""Tests for League and Season serializers and viewsets (TGF-289)."""

import pytest
from django.test import Client
from django.urls import reverse

from archive.api.serializers.league import (
    LeagueDetailSerializer,
    LeagueListSerializer,
    LeagueWriteSerializer,
)
from archive.api.serializers.season import (
    SeasonDetailSerializer,
    SeasonListSerializer,
    SeasonWriteSerializer,
)
from archive.models import League, Season


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def nfl():
    return League.objects.create(
        short_name="NFL", long_name="National Football League", level="PRO"
    )


@pytest.fixture
def ncaa():
    return League.objects.create(
        short_name="NCAA",
        long_name="National Collegiate Athletic Association",
        level="COLLEGE",
    )


@pytest.fixture
def season_2024(nfl):
    return Season.objects.create(league=nfl, year=2024, label="2024")


@pytest.fixture
def season_2025(nfl):
    return Season.objects.create(league=nfl, year=2025, label="2025")


# --- LeagueListSerializer ---


@pytest.mark.django_db
def test_league_list_serializer_fields(nfl, season_2024, season_2025):
    """LeagueListSerializer includes id, long_name, short_name, level, seasons_count."""
    from django.db.models import Count

    qs = League.objects.annotate(seasons_count=Count("seasons"))
    serializer = LeagueListSerializer(qs.get(pk=nfl.pk))
    data = serializer.data
    assert data["id"] == nfl.pk
    assert data["long_name"] == "National Football League"
    assert data["short_name"] == "NFL"
    assert data["level"] == "PRO"
    assert data["seasons_count"] == 2


# --- LeagueDetailSerializer ---


@pytest.mark.django_db
def test_league_detail_serializer_includes_seasons(nfl, season_2024, season_2025):
    """LeagueDetailSerializer includes all fields plus nested seasons list."""
    league = League.objects.prefetch_related("seasons").get(pk=nfl.pk)
    serializer = LeagueDetailSerializer(league)
    data = serializer.data
    assert data["id"] == nfl.pk
    assert data["short_name"] == "NFL"
    assert data["long_name"] == "National Football League"
    assert data["level"] == "PRO"
    assert data["country"] == "US"
    assert "notes" in data
    assert "bonus_data" in data
    assert "external_ids" in data
    assert len(data["seasons"]) == 2
    season_years = {s["year"] for s in data["seasons"]}
    assert season_years == {2024, 2025}


# --- LeagueWriteSerializer ---


@pytest.mark.django_db
def test_league_write_serializer_creates():
    """LeagueWriteSerializer can create a league with plain field values."""
    serializer = LeagueWriteSerializer(
        data={"short_name": "XFL", "long_name": "XFL", "level": "PRO"}
    )
    assert serializer.is_valid(), serializer.errors
    league = serializer.save()
    assert league.pk is not None
    assert league.short_name == "XFL"


# --- SeasonListSerializer ---


@pytest.mark.django_db
def test_season_list_serializer_fields(nfl, season_2024):
    """SeasonListSerializer includes id, league, year, label, start_date, end_date."""
    season = Season.objects.select_related("league").get(pk=season_2024.pk)
    serializer = SeasonListSerializer(season)
    data = serializer.data
    assert data["id"] == season_2024.pk
    assert data["league"] == nfl.pk
    assert data["year"] == 2024
    assert data["label"] == "2024"
    assert "start_date" in data
    assert "end_date" in data


# --- SeasonDetailSerializer ---


@pytest.mark.django_db
def test_season_detail_serializer_all_fields(nfl, season_2024):
    """SeasonDetailSerializer includes all fields."""
    season = Season.objects.select_related("league").get(pk=season_2024.pk)
    serializer = SeasonDetailSerializer(season)
    data = serializer.data
    assert data["id"] == season_2024.pk
    assert data["league"] == nfl.pk
    assert data["year"] == 2024
    assert "bonus_data" in data
    assert "external_ids" in data


# --- SeasonWriteSerializer ---


@pytest.mark.django_db
def test_season_write_serializer_creates(nfl):
    """SeasonWriteSerializer can create a season."""
    serializer = SeasonWriteSerializer(
        data={"league": nfl.pk, "year": 2023, "label": "2023"}
    )
    assert serializer.is_valid(), serializer.errors
    season = serializer.save()
    assert season.pk is not None
    assert season.year == 2023


# --- LeagueViewSet endpoints ---


@pytest.mark.django_db
def test_league_list_returns_200(client, nfl):
    """GET /api/v1/leagues/ returns 200."""
    response = client.get("/api/v1/leagues/", HTTP_ACCEPT="application/json")
    assert response.status_code == 200


@pytest.mark.django_db
def test_league_list_returns_paginated_results(client, nfl, ncaa):
    """GET /api/v1/leagues/ returns paginated league list."""
    response = client.get("/api/v1/leagues/", HTTP_ACCEPT="application/json")
    data = response.json()
    # CursorPagination wraps results in a dict with next/previous/results
    assert "results" in data
    assert len(data["results"]) == 2


@pytest.mark.django_db
def test_league_list_includes_seasons_count(client, nfl, season_2024, season_2025):
    """League list results include seasons_count."""
    response = client.get("/api/v1/leagues/", HTTP_ACCEPT="application/json")
    results = response.json()["results"]
    nfl_data = next(r for r in results if r["short_name"] == "NFL")
    assert nfl_data["seasons_count"] == 2


@pytest.mark.django_db
def test_league_retrieve_returns_detail(client, nfl, season_2024):
    """GET /api/v1/leagues/<id>/ returns detail with nested seasons."""
    response = client.get(f"/api/v1/leagues/{nfl.pk}/", HTTP_ACCEPT="application/json")
    assert response.status_code == 200
    data = response.json()
    assert data["short_name"] == "NFL"
    assert len(data["seasons"]) == 1
    assert data["seasons"][0]["year"] == 2024


@pytest.mark.django_db
def test_league_create(client):
    """POST /api/v1/leagues/ creates a new league."""
    response = client.post(
        "/api/v1/leagues/",
        data={
            "short_name": "USFL",
            "long_name": "United States Football League",
            "level": "PRO",
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    assert League.objects.filter(short_name="USFL").exists()


@pytest.mark.django_db
def test_league_update(client, nfl):
    """PUT /api/v1/leagues/<id>/ updates the league."""
    response = client.put(
        f"/api/v1/leagues/{nfl.pk}/",
        data={
            "short_name": "NFL",
            "long_name": "National Football League",
            "level": "PRO",
            "country": "US",
            "notes": "Updated",
        },
        content_type="application/json",
    )
    assert response.status_code == 200
    nfl.refresh_from_db()
    assert nfl.notes == "Updated"


@pytest.mark.django_db
def test_league_delete_not_allowed(client, nfl):
    """DELETE /api/v1/leagues/<id>/ is not supported."""
    response = client.delete(f"/api/v1/leagues/{nfl.pk}/")
    assert response.status_code == 405


# --- SeasonViewSet endpoints ---


@pytest.mark.django_db
def test_season_list_returns_200(client, nfl, season_2024):
    """GET /api/v1/seasons/ returns 200."""
    response = client.get("/api/v1/seasons/", HTTP_ACCEPT="application/json")
    assert response.status_code == 200


@pytest.mark.django_db
def test_season_filter_by_league(client, nfl, ncaa, season_2024):
    """GET /api/v1/seasons/?league=<id> filters by league."""
    Season.objects.create(league=ncaa, year=2024, label="2024")
    response = client.get(
        f"/api/v1/seasons/?league={nfl.pk}", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["league"] == nfl.pk


@pytest.mark.django_db
def test_season_filter_by_year(client, nfl, season_2024, season_2025):
    """GET /api/v1/seasons/?year=2024 filters by year."""
    response = client.get("/api/v1/seasons/?year=2024", HTTP_ACCEPT="application/json")
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["year"] == 2024


@pytest.mark.django_db
def test_season_retrieve_returns_detail(client, nfl, season_2024):
    """GET /api/v1/seasons/<id>/ returns full detail."""
    response = client.get(
        f"/api/v1/seasons/{season_2024.pk}/", HTTP_ACCEPT="application/json"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["year"] == 2024
    assert "bonus_data" in data
    assert "external_ids" in data


@pytest.mark.django_db
def test_season_create(client, nfl):
    """POST /api/v1/seasons/ creates a new season."""
    response = client.post(
        "/api/v1/seasons/",
        data={"league": nfl.pk, "year": 2023, "label": "2023"},
        content_type="application/json",
    )
    assert response.status_code == 201
    assert Season.objects.filter(league=nfl, year=2023).exists()


@pytest.mark.django_db
def test_season_update(client, nfl, season_2024):
    """PUT /api/v1/seasons/<id>/ updates the season."""
    response = client.put(
        f"/api/v1/seasons/{season_2024.pk}/",
        data={"league": nfl.pk, "year": 2024, "label": "2024-25"},
        content_type="application/json",
    )
    assert response.status_code == 200
    season_2024.refresh_from_db()
    assert season_2024.label == "2024-25"


@pytest.mark.django_db
def test_season_delete_not_allowed(client, nfl, season_2024):
    """DELETE /api/v1/seasons/<id>/ is not supported."""
    response = client.delete(f"/api/v1/seasons/{season_2024.pk}/")
    assert response.status_code == 405


# --- N+1 query prevention ---


@pytest.mark.django_db
def test_season_list_uses_select_related(
    client, nfl, season_2024, season_2025, django_assert_num_queries
):
    """Season list should not produce N+1 queries — single query via select_related JOIN."""
    with django_assert_num_queries(1):
        client.get("/api/v1/seasons/", HTTP_ACCEPT="application/json")


# --- Router registration ---


@pytest.mark.django_db
def test_leagues_registered_on_router():
    """LeagueViewSet must be registered at /leagues/."""
    url = reverse("league-list")
    assert url == "/api/v1/leagues/"


@pytest.mark.django_db
def test_seasons_registered_on_router():
    """SeasonViewSet must be registered at /seasons/."""
    url = reverse("season-list")
    assert url == "/api/v1/seasons/"


@pytest.mark.django_db
def test_api_root_lists_endpoints(client):
    """API root should now list leagues and seasons."""
    response = client.get("/api/v1/", HTTP_ACCEPT="application/json")
    data = response.json()
    assert "leagues" in data
    assert "seasons" in data
