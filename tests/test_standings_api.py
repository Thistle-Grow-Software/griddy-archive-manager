"""Tests for TeamStandingsSnapshot serializers and viewset (TGF-301)."""

import pytest
from django.test import Client
from django.urls import reverse

from archive.api.serializers.standings import (
    TeamStandingsSnapshotDetailSerializer,
    TeamStandingsSnapshotListSerializer,
)
from archive.models import (
    Franchise,
    League,
    Season,
    Team,
    TeamStandingsSnapshot,
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
def season_2023(nfl):
    return Season.objects.create(league=nfl, year=2023, label="2023")


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
def snapshot_wk1(steelers, season_2024):
    return TeamStandingsSnapshot.objects.create(
        team=steelers,
        season=season_2024,
        week=1,
        overall_wins=1,
        overall_losses=0,
        overall_ties=0,
        overall_win_pct=1.0,
        points_for=24,
        points_against=17,
        division_wins=1,
        division_losses=0,
    )


@pytest.fixture
def snapshot_wk2(steelers, season_2024):
    return TeamStandingsSnapshot.objects.create(
        team=steelers,
        season=season_2024,
        week=2,
        overall_wins=2,
        overall_losses=0,
        overall_ties=0,
        overall_win_pct=1.0,
        points_for=52,
        points_against=30,
    )


@pytest.fixture
def ravens_snapshot(ravens, season_2024):
    return TeamStandingsSnapshot.objects.create(
        team=ravens,
        season=season_2024,
        week=1,
        overall_wins=0,
        overall_losses=1,
        overall_win_pct=0.0,
    )


# --- TeamStandingsSnapshotListSerializer ---


@pytest.mark.django_db
def test_list_serializer_fields(snapshot_wk1, steelers, season_2024):
    """ListSerializer includes id, team, season, week, overall record, win pct."""
    snap = TeamStandingsSnapshot.objects.select_related("team", "season").get(
        pk=snapshot_wk1.pk
    )
    data = TeamStandingsSnapshotListSerializer(snap).data
    assert data["id"] == snapshot_wk1.pk
    assert data["team"] == steelers.pk
    assert data["season"] == season_2024.pk
    assert data["week"] == 1
    assert data["overall_wins"] == 1
    assert data["overall_losses"] == 0
    assert data["overall_win_pct"] == 1.0


# --- TeamStandingsSnapshotDetailSerializer ---


@pytest.mark.django_db
def test_detail_serializer_all_fields(snapshot_wk1):
    """DetailSerializer includes all fields."""
    snap = TeamStandingsSnapshot.objects.select_related("team", "season").get(
        pk=snapshot_wk1.pk
    )
    data = TeamStandingsSnapshotDetailSerializer(snap).data
    assert data["points_for"] == 24
    assert data["points_against"] == 17
    assert data["division_wins"] == 1
    assert "conference_wins" in data
    assert "streak_length" in data
    assert "clinched_playoff" in data
    assert "eliminated" in data
    assert "bonus_data" in data


# --- ViewSet endpoints ---


@pytest.mark.django_db
def test_standings_list_returns_200(client, snapshot_wk1):
    """GET /api/v1/standings/ returns 200."""
    response = client.get("/api/v1/standings/", HTTP_ACCEPT="application/json")
    assert response.status_code == 200
    assert "results" in response.json()


@pytest.mark.django_db
def test_standings_retrieve(client, snapshot_wk1):
    """GET /api/v1/standings/<id>/ returns detail."""
    response = client.get(
        f"/api/v1/standings/{snapshot_wk1.pk}/", HTTP_ACCEPT="application/json"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["points_for"] == 24
    assert "division_wins" in data


@pytest.mark.django_db
def test_standings_create(client, steelers, season_2024):
    """POST /api/v1/standings/ creates a snapshot."""
    response = client.post(
        "/api/v1/standings/",
        data={
            "team": steelers.pk,
            "season": season_2024.pk,
            "week": 3,
            "overall_wins": 3,
            "overall_losses": 0,
            "overall_win_pct": 1.0,
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    assert TeamStandingsSnapshot.objects.filter(team=steelers, week=3).exists()


# --- Filters ---


@pytest.mark.django_db
def test_filter_by_team(client, snapshot_wk1, ravens_snapshot):
    """?team=<id> filters by team."""
    response = client.get(
        f"/api/v1/standings/?team={snapshot_wk1.team_id}",
        HTTP_ACCEPT="application/json",
    )
    results = response.json()["results"]
    assert all(r["team"] == snapshot_wk1.team_id for r in results)


@pytest.mark.django_db
def test_filter_by_season_year(client, snapshot_wk1, season_2023, steelers):
    """?season_year=2024 filters by season year."""
    TeamStandingsSnapshot.objects.create(
        team=steelers, season=season_2023, week=1, overall_wins=5, overall_losses=3
    )
    response = client.get(
        "/api/v1/standings/?season_year=2024", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 1


@pytest.mark.django_db
def test_filter_by_week(client, snapshot_wk1, snapshot_wk2):
    """?week=1 filters by week."""
    response = client.get("/api/v1/standings/?week=1", HTTP_ACCEPT="application/json")
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["week"] == 1


# --- Ordering ---


@pytest.mark.django_db
def test_ordering_by_overall_wins(client, snapshot_wk1, ravens_snapshot):
    """?ordering=-overall_wins orders by wins descending."""
    response = client.get(
        "/api/v1/standings/?ordering=-overall_wins",
        HTTP_ACCEPT="application/json",
    )
    results = response.json()["results"]
    assert results[0]["overall_wins"] >= results[-1]["overall_wins"]


# --- Router registration ---


@pytest.mark.django_db
def test_standings_registered_on_router():
    """Standings viewset must be registered at /standings/."""
    url = reverse("standings-list")
    assert url == "/api/v1/standings/"
