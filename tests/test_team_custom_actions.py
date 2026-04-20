"""Tests for Team schedule and current-venue custom actions (TGF-306)."""

import pytest
from django.test import Client

from archive.models import (
    Franchise,
    Game,
    League,
    Season,
    Team,
    TeamVenueOccupancy,
    Venue,
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
def bengals_franchise(nfl):
    return Franchise.objects.create(name="Cincinnati Bengals", league=nfl)


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
def bengals(bengals_franchise):
    return Team.objects.create(
        franchise=bengals_franchise,
        name="Cincinnati Bengals",
        short_name="CIN",
        city="Cincinnati",
    )


@pytest.fixture
def heinz_field():
    return Venue.objects.create(
        name="Heinz Field", city="Pittsburgh", state="PA", capacity=68400
    )


@pytest.fixture
def acrisure():
    return Venue.objects.create(
        name="Acrisure Stadium", city="Pittsburgh", state="PA", capacity=68400
    )


@pytest.fixture
def game_home(nfl, season_2024, steelers, ravens, heinz_field):
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
def game_away(nfl, season_2024, bengals, steelers, heinz_field):
    return Game.objects.create(
        league=nfl,
        season=season_2024,
        date_local="2024-09-15",
        week=2,
        home_team=bengals,
        away_team=steelers,
        venue=heinz_field,
    )


@pytest.fixture
def game_other_season(nfl, season_2025, steelers, ravens, heinz_field):
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
def old_occupancy(steelers, heinz_field):
    return TeamVenueOccupancy.objects.create(
        team=steelers,
        venue=heinz_field,
        start_date="2001-08-18",
        end_date="2022-03-01",
    )


@pytest.fixture
def current_occupancy(steelers, acrisure):
    return TeamVenueOccupancy.objects.create(
        team=steelers,
        venue=acrisure,
        start_date="2022-03-01",
    )


# --- schedule action ---


@pytest.mark.django_db
def test_schedule_returns_200(client, steelers, game_home):
    """GET /api/v1/teams/<id>/schedule/?season_year=2024 returns 200."""
    response = client.get(
        f"/api/v1/teams/{steelers.pk}/schedule/?season_year=2024",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_schedule_includes_home_and_away(client, steelers, game_home, game_away):
    """Schedule includes games where team is both home and away."""
    response = client.get(
        f"/api/v1/teams/{steelers.pk}/schedule/?season_year=2024",
        HTTP_ACCEPT="application/json",
    )
    data = response.json()
    assert len(data) == 2


@pytest.mark.django_db
def test_schedule_ordered_by_date(client, steelers, game_home, game_away):
    """Schedule is ordered by date_local ascending."""
    response = client.get(
        f"/api/v1/teams/{steelers.pk}/schedule/?season_year=2024",
        HTTP_ACCEPT="application/json",
    )
    data = response.json()
    assert data[0]["date_local"] == "2024-09-08"
    assert data[1]["date_local"] == "2024-09-15"


@pytest.mark.django_db
def test_schedule_filters_by_season(client, steelers, game_home, game_other_season):
    """Schedule only returns games from the specified season."""
    response = client.get(
        f"/api/v1/teams/{steelers.pk}/schedule/?season_year=2024",
        HTTP_ACCEPT="application/json",
    )
    data = response.json()
    assert len(data) == 1
    assert data[0]["date_local"] == "2024-09-08"


@pytest.mark.django_db
def test_schedule_requires_season_year(client, steelers):
    """Returns 400 if season_year parameter is missing."""
    response = client.get(
        f"/api/v1/teams/{steelers.pk}/schedule/",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 400
    assert "season_year" in response.json()["detail"]


@pytest.mark.django_db
def test_schedule_empty_season(client, steelers, season_2025):
    """Returns empty list for season with no games."""
    response = client.get(
        f"/api/v1/teams/{steelers.pk}/schedule/?season_year=2025",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 200
    assert response.json() == []


# --- current-venue action ---


@pytest.mark.django_db
def test_current_venue_returns_200(client, steelers, current_occupancy):
    """GET /api/v1/teams/<id>/current-venue/ returns 200."""
    response = client.get(
        f"/api/v1/teams/{steelers.pk}/current-venue/",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_current_venue_returns_most_recent(
    client, steelers, old_occupancy, current_occupancy
):
    """Returns the most recent venue (by start_date), not the old one."""
    response = client.get(
        f"/api/v1/teams/{steelers.pk}/current-venue/",
        HTTP_ACCEPT="application/json",
    )
    data = response.json()
    assert data["name"] == "Acrisure Stadium"


@pytest.mark.django_db
def test_current_venue_includes_detail_fields(client, steelers, current_occupancy):
    """Response includes full venue detail fields."""
    response = client.get(
        f"/api/v1/teams/{steelers.pk}/current-venue/",
        HTTP_ACCEPT="application/json",
    )
    data = response.json()
    assert "city" in data
    assert "state" in data
    assert "country" in data
    assert "capacity" in data


@pytest.mark.django_db
def test_current_venue_404_if_no_occupancy(client, steelers):
    """Returns 404 if no venue occupancy exists for the team."""
    response = client.get(
        f"/api/v1/teams/{steelers.pk}/current-venue/",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 404
