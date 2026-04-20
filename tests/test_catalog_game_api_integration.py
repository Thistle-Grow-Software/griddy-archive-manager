"""
Catalog and Game domain API integration tests using DRF's APIClient (TGF-308).

Comprehensive request-level tests covering all Catalog and Game domain viewsets,
filters, search, ordering, and nested endpoints.
"""

import pytest
from rest_framework.test import APIClient

from archive.models import (
    Acquisition,
    Drive,
    Franchise,
    Game,
    GameReplay,
    League,
    OrgUnit,
    QuarterScore,
    Season,
    Source,
    Team,
    TeamAffiliation,
    TeamVenueOccupancy,
    Venue,
    VideoAsset,
)


@pytest.fixture
def api_client():
    return APIClient()


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
    return Season.objects.create(
        league=nfl,
        year=2024,
        label="2024",
        start_date="2024-09-05",
        end_date="2025-02-09",
    )


@pytest.fixture
def season_2023(nfl):
    return Season.objects.create(league=nfl, year=2023, label="2023")


@pytest.fixture
def afc(nfl):
    return OrgUnit.objects.create(
        league=nfl,
        short_name="AFC",
        long_name="American Football Conference",
        org_type="CONFERENCE",
    )


@pytest.fixture
def afc_north(nfl, afc):
    return OrgUnit.objects.create(
        league=nfl,
        short_name="AFCN",
        long_name="AFC North",
        org_type="DIVISION",
        parent=afc,
    )


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
        state="PA",
        mascot="Steely McBeam",
    )


@pytest.fixture
def ravens(ravens_franchise):
    return Team.objects.create(
        franchise=ravens_franchise,
        name="Baltimore Ravens",
        short_name="BAL",
        city="Baltimore",
        state="MD",
    )


@pytest.fixture
def heinz_field():
    return Venue.objects.create(
        name="Heinz Field", city="Pittsburgh", state="PA", capacity=68400
    )


@pytest.fixture
def steelers_affiliation(steelers, afc_north, season_2024):
    return TeamAffiliation.objects.create(
        team=steelers, org_unit=afc_north, season=season_2024
    )


@pytest.fixture
def steelers_occupancy(steelers, heinz_field):
    return TeamVenueOccupancy.objects.create(
        team=steelers, venue=heinz_field, start_date="2001-08-18"
    )


@pytest.fixture
def game_wk1(nfl, season_2024, steelers, ravens, heinz_field):
    return Game.objects.create(
        league=nfl,
        season=season_2024,
        date_local="2024-09-08",
        week=1,
        game_type="REG",
        home_team=steelers,
        away_team=ravens,
        venue=heinz_field,
        final_home_score=18,
        final_away_score=21,
        broadcast_channel="CBS",
        status="Final",
        competition_name="",
    )


@pytest.fixture
def game_wk2(nfl, season_2024, ravens, steelers, heinz_field):
    return Game.objects.create(
        league=nfl,
        season=season_2024,
        date_local="2024-09-15",
        week=2,
        game_type="REG",
        home_team=ravens,
        away_team=steelers,
        venue=heinz_field,
        final_home_score=28,
        final_away_score=14,
        broadcast_channel="FOX",
        status="Final",
    )


@pytest.fixture
def playoff_game(nfl, season_2024, steelers, ravens, heinz_field):
    return Game.objects.create(
        league=nfl,
        season=season_2024,
        date_local="2025-01-12",
        week=18,
        game_type="POST",
        home_team=steelers,
        away_team=ravens,
        venue=heinz_field,
        competition_name="AFC Wild Card",
    )


@pytest.fixture
def quarter_scores(game_wk1, steelers, ravens):
    return [
        QuarterScore.objects.create(game=game_wk1, team=steelers, period=1, points=7),
        QuarterScore.objects.create(game=game_wk1, team=ravens, period=1, points=14),
    ]


@pytest.fixture
def drive(game_wk1, steelers):
    return Drive.objects.create(
        game=game_wk1, sequence=1, team=steelers, yards_gained=75, ended_with_score=True
    )


@pytest.fixture
def replay(game_wk1):
    return GameReplay.objects.create(
        game=game_wk1, replay_type="highlight", title="TD catch", duration=30
    )


@pytest.fixture
def source():
    return Source.objects.create(name="NFL+", source_type="STREAMING")


@pytest.fixture
def acquisition(source):
    return Acquisition.objects.create(source=source)


@pytest.fixture
def asset(game_wk1, acquisition):
    return VideoAsset.objects.create(
        game=game_wk1,
        acquisition=acquisition,
        file_path="/media/games/wk1.mkv",
        asset_type="FULL",
    )


# ===========================================================================
# League ViewSet
# ===========================================================================


@pytest.mark.django_db
class TestLeagueViewSet:
    def test_list(self, api_client, nfl, ncaa):
        response = api_client.get("/api/v1/leagues/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 2

    def test_detail(self, api_client, nfl, season_2024):
        response = api_client.get(f"/api/v1/leagues/{nfl.pk}/")
        assert response.status_code == 200
        assert response.data["short_name"] == "NFL"
        assert len(response.data["seasons"]) == 1

    def test_create(self, api_client):
        response = api_client.post(
            "/api/v1/leagues/",
            {"short_name": "XFL", "long_name": "XFL", "level": "PRO"},
        )
        assert response.status_code == 201

    def test_update(self, api_client, nfl):
        response = api_client.put(
            f"/api/v1/leagues/{nfl.pk}/",
            {
                "short_name": "NFL",
                "long_name": "National Football League",
                "level": "PRO",
                "notes": "Updated",
            },
        )
        assert response.status_code == 200
        nfl.refresh_from_db()
        assert nfl.notes == "Updated"


# ===========================================================================
# Season ViewSet
# ===========================================================================


@pytest.mark.django_db
class TestSeasonViewSet:
    def test_list(self, api_client, season_2024):
        response = api_client.get("/api/v1/seasons/")
        assert response.status_code == 200

    def test_detail(self, api_client, season_2024):
        response = api_client.get(f"/api/v1/seasons/{season_2024.pk}/")
        assert response.status_code == 200
        assert response.data["year"] == 2024

    def test_create(self, api_client, nfl):
        response = api_client.post(
            "/api/v1/seasons/", {"league": nfl.pk, "year": 2025, "label": "2025"}
        )
        assert response.status_code == 201

    def test_filter_by_league(self, api_client, nfl, season_2024):
        response = api_client.get(f"/api/v1/seasons/?league={nfl.pk}")
        assert response.status_code == 200
        assert all(s["league"] == nfl.pk for s in response.data["results"])

    def test_filter_by_year(self, api_client, season_2024, season_2023):
        response = api_client.get("/api/v1/seasons/?year=2024")
        assert len(response.data["results"]) == 1


# ===========================================================================
# Franchise ViewSet
# ===========================================================================


@pytest.mark.django_db
class TestFranchiseViewSet:
    def test_list(self, api_client, steelers_franchise):
        response = api_client.get("/api/v1/franchises/")
        assert response.status_code == 200

    def test_detail_with_teams(self, api_client, steelers_franchise, steelers):
        response = api_client.get(f"/api/v1/franchises/{steelers_franchise.pk}/")
        assert response.status_code == 200
        assert len(response.data["teams"]) == 1

    def test_create(self, api_client, nfl):
        response = api_client.post(
            "/api/v1/franchises/", {"name": "Cleveland Browns", "league": nfl.pk}
        )
        assert response.status_code == 201

    def test_update(self, api_client, steelers_franchise, nfl):
        response = api_client.put(
            f"/api/v1/franchises/{steelers_franchise.pk}/",
            {"name": "Pittsburgh Steelers (Updated)", "league": nfl.pk},
        )
        assert response.status_code == 200


# ===========================================================================
# Team ViewSet
# ===========================================================================


@pytest.mark.django_db
class TestTeamViewSet:
    def test_list(self, api_client, steelers):
        response = api_client.get("/api/v1/teams/")
        assert response.status_code == 200

    def test_detail_with_nested(
        self, api_client, steelers, steelers_affiliation, steelers_occupancy
    ):
        response = api_client.get(f"/api/v1/teams/{steelers.pk}/")
        assert response.status_code == 200
        assert len(response.data["affiliations"]) == 1
        assert len(response.data["venue_occupancies"]) == 1

    def test_create(self, api_client, steelers_franchise):
        response = api_client.post(
            "/api/v1/teams/",
            {
                "franchise": steelers_franchise.pk,
                "name": "Pittsburgh Maulers",
                "short_name": "MAU",
            },
        )
        assert response.status_code == 201

    def test_filter_by_franchise(self, api_client, steelers, ravens):
        response = api_client.get(f"/api/v1/teams/?franchise={steelers.franchise_id}")
        assert len(response.data["results"]) == 1

    def test_filter_by_city(self, api_client, steelers, ravens):
        response = api_client.get("/api/v1/teams/?city=Pittsburgh")
        assert len(response.data["results"]) == 1

    def test_filter_by_state(self, api_client, steelers, ravens):
        response = api_client.get("/api/v1/teams/?state=PA")
        assert len(response.data["results"]) == 1

    def test_search_by_name(self, api_client, steelers, ravens):
        response = api_client.get("/api/v1/teams/?search=Steelers")
        assert len(response.data["results"]) == 1

    def test_search_by_mascot(self, api_client, steelers, ravens):
        response = api_client.get("/api/v1/teams/?search=Steely")
        assert len(response.data["results"]) == 1


# ===========================================================================
# OrgUnit ViewSet
# ===========================================================================


@pytest.mark.django_db
class TestOrgUnitViewSet:
    def test_list(self, api_client, afc_north):
        response = api_client.get("/api/v1/org-units/")
        assert response.status_code == 200

    def test_detail_with_children(self, api_client, afc, afc_north):
        response = api_client.get(f"/api/v1/org-units/{afc.pk}/")
        assert response.status_code == 200
        assert len(response.data["children"]) == 1

    def test_create(self, api_client, nfl):
        response = api_client.post(
            "/api/v1/org-units/",
            {
                "short_name": "NFC",
                "long_name": "National Football Conference",
                "org_type": "CONFERENCE",
                "league": nfl.pk,
            },
        )
        assert response.status_code == 201

    def test_update(self, api_client, afc_north, nfl):
        response = api_client.put(
            f"/api/v1/org-units/{afc_north.pk}/",
            {
                "short_name": "AFCN",
                "long_name": "AFC North (Updated)",
                "org_type": "DIVISION",
                "league": nfl.pk,
            },
        )
        assert response.status_code == 200


# ===========================================================================
# TeamAffiliation ViewSet
# ===========================================================================


@pytest.mark.django_db
class TestTeamAffiliationViewSet:
    def test_list(self, api_client, steelers_affiliation):
        response = api_client.get("/api/v1/team-affiliations/")
        assert response.status_code == 200

    def test_detail(self, api_client, steelers_affiliation):
        response = api_client.get(
            f"/api/v1/team-affiliations/{steelers_affiliation.pk}/"
        )
        assert response.status_code == 200

    def test_create(self, api_client, steelers, afc_north):
        response = api_client.post(
            "/api/v1/team-affiliations/",
            {"team": steelers.pk, "org_unit": afc_north.pk, "start_date": "2024-01-01"},
        )
        assert response.status_code == 201

    def test_update(self, api_client, steelers_affiliation, steelers, afc_north):
        response = api_client.put(
            f"/api/v1/team-affiliations/{steelers_affiliation.pk}/",
            {
                "team": steelers.pk,
                "org_unit": afc_north.pk,
                "start_date": "2024-09-01",
                "end_date": "2025-02-09",
            },
        )
        assert response.status_code == 200


# ===========================================================================
# Venue ViewSet
# ===========================================================================


@pytest.mark.django_db
class TestVenueViewSet:
    def test_list(self, api_client, heinz_field):
        response = api_client.get("/api/v1/venues/")
        assert response.status_code == 200

    def test_detail(self, api_client, heinz_field):
        response = api_client.get(f"/api/v1/venues/{heinz_field.pk}/")
        assert response.status_code == 200
        assert response.data["name"] == "Heinz Field"

    def test_create(self, api_client):
        response = api_client.post(
            "/api/v1/venues/",
            {
                "name": "Lambeau Field",
                "city": "Green Bay",
                "state": "WI",
                "capacity": 81441,
            },
        )
        assert response.status_code == 201

    def test_update(self, api_client, heinz_field):
        response = api_client.put(
            f"/api/v1/venues/{heinz_field.pk}/",
            {
                "name": "Heinz Field",
                "city": "Pittsburgh",
                "state": "PA",
                "capacity": 68500,
            },
        )
        assert response.status_code == 200


# ===========================================================================
# TeamVenueOccupancy ViewSet
# ===========================================================================


@pytest.mark.django_db
class TestTeamVenueOccupancyViewSet:
    def test_list(self, api_client, steelers_occupancy):
        response = api_client.get("/api/v1/team-venue-occupancies/")
        assert response.status_code == 200

    def test_detail(self, api_client, steelers_occupancy):
        response = api_client.get(
            f"/api/v1/team-venue-occupancies/{steelers_occupancy.pk}/"
        )
        assert response.status_code == 200

    def test_create(self, api_client, steelers, heinz_field):
        TeamVenueOccupancy.objects.all().delete()
        response = api_client.post(
            "/api/v1/team-venue-occupancies/",
            {"team": steelers.pk, "venue": heinz_field.pk, "start_date": "2022-03-01"},
        )
        assert response.status_code == 201

    def test_update(self, api_client, steelers_occupancy, steelers, heinz_field):
        response = api_client.put(
            f"/api/v1/team-venue-occupancies/{steelers_occupancy.pk}/",
            {
                "team": steelers.pk,
                "venue": heinz_field.pk,
                "start_date": "2001-08-18",
                "end_date": "2022-03-01",
            },
        )
        assert response.status_code == 200


# ===========================================================================
# Game ViewSet
# ===========================================================================


@pytest.mark.django_db
class TestGameViewSet:
    def test_list(self, api_client, game_wk1):
        response = api_client.get("/api/v1/games/")
        assert response.status_code == 200
        assert "results" in response.data

    def test_detail(self, api_client, game_wk1, quarter_scores):
        response = api_client.get(f"/api/v1/games/{game_wk1.pk}/")
        assert response.status_code == 200
        assert response.data["home_team"]["short_name"] == "PIT"
        assert len(response.data["quarter_scores"]) == 2

    def test_create(self, api_client, nfl, season_2024, steelers, ravens):
        response = api_client.post(
            "/api/v1/games/",
            {
                "league": nfl.pk,
                "season": season_2024.pk,
                "date_local": "2024-12-25",
                "home_team": steelers.pk,
                "away_team": ravens.pk,
            },
        )
        assert response.status_code == 201

    def test_update(self, api_client, game_wk1, nfl, season_2024, steelers, ravens):
        response = api_client.put(
            f"/api/v1/games/{game_wk1.pk}/",
            {
                "league": nfl.pk,
                "season": season_2024.pk,
                "date_local": "2024-09-08",
                "home_team": steelers.pk,
                "away_team": ravens.pk,
                "notes": "Updated via API",
            },
        )
        assert response.status_code == 200


# ===========================================================================
# GameFilter
# ===========================================================================


@pytest.mark.django_db
class TestGameFilter:
    def test_filter_season_year(
        self, api_client, game_wk1, season_2023, nfl, steelers, ravens
    ):
        Game.objects.create(
            league=nfl,
            season=season_2023,
            date_local="2023-09-10",
            week=1,
            home_team=steelers,
            away_team=ravens,
        )
        response = api_client.get("/api/v1/games/?season_year=2024")
        assert len(response.data["results"]) == 1

    def test_filter_league(self, api_client, nfl, game_wk1):
        response = api_client.get(f"/api/v1/games/?league={nfl.pk}")
        assert len(response.data["results"]) >= 1

    def test_filter_team_home_or_away(self, api_client, steelers, game_wk1, game_wk2):
        response = api_client.get(f"/api/v1/games/?team={steelers.pk}")
        assert len(response.data["results"]) == 2

    def test_filter_game_type(self, api_client, game_wk1, playoff_game):
        response = api_client.get("/api/v1/games/?game_type=POST")
        assert len(response.data["results"]) == 1

    def test_filter_week(self, api_client, game_wk1, game_wk2):
        response = api_client.get("/api/v1/games/?week=1")
        assert len(response.data["results"]) == 1

    def test_filter_date_range(self, api_client, game_wk1, game_wk2):
        response = api_client.get(
            "/api/v1/games/?date_from=2024-09-10&date_to=2024-09-20"
        )
        assert len(response.data["results"]) == 1

    def test_filter_has_assets_true(self, api_client, game_wk1, game_wk2, asset):
        response = api_client.get("/api/v1/games/?has_assets=true")
        assert len(response.data["results"]) == 1

    def test_filter_has_assets_false(self, api_client, game_wk1, game_wk2, asset):
        response = api_client.get("/api/v1/games/?has_assets=false")
        assert len(response.data["results"]) == 1


# ===========================================================================
# Game Search and Ordering
# ===========================================================================


@pytest.mark.django_db
class TestGameSearchAndOrdering:
    def test_search_competition_name(self, api_client, game_wk1, playoff_game):
        response = api_client.get("/api/v1/games/?search=Wild+Card")
        assert len(response.data["results"]) == 1

    def test_ordering_by_week(self, api_client, game_wk1, game_wk2):
        response = api_client.get("/api/v1/games/?ordering=week")
        results = response.data["results"]
        assert results[0]["week"] <= results[1]["week"]

    def test_ordering_by_date(self, api_client, game_wk1, game_wk2):
        response = api_client.get("/api/v1/games/?ordering=date_local")
        results = response.data["results"]
        assert results[0]["date_local"] <= results[1]["date_local"]


# ===========================================================================
# Nested Game Endpoints
# ===========================================================================


@pytest.mark.django_db
class TestGameNestedEndpoints:
    def test_quarter_scores_list(self, api_client, game_wk1, quarter_scores):
        response = api_client.get(f"/api/v1/games/{game_wk1.pk}/quarter-scores/")
        assert response.status_code == 200
        assert len(response.data) == 2

    def test_quarter_scores_create(self, api_client, game_wk1, steelers):
        response = api_client.post(
            f"/api/v1/games/{game_wk1.pk}/quarter-scores/",
            {"team": steelers.pk, "period": 3, "points": 10},
        )
        assert response.status_code == 201

    def test_drives_list(self, api_client, game_wk1, drive):
        response = api_client.get(f"/api/v1/games/{game_wk1.pk}/drives/")
        assert response.status_code == 200
        assert len(response.data) == 1

    def test_drives_create(self, api_client, game_wk1, steelers):
        response = api_client.post(
            f"/api/v1/games/{game_wk1.pk}/drives/",
            {"sequence": 2, "team": steelers.pk, "yards_gained": 60},
        )
        assert response.status_code == 201

    def test_replays_list(self, api_client, game_wk1, replay):
        response = api_client.get(f"/api/v1/games/{game_wk1.pk}/replays/")
        assert response.status_code == 200
        assert len(response.data) == 1

    def test_replays_create(self, api_client, game_wk1):
        response = api_client.post(
            f"/api/v1/games/{game_wk1.pk}/replays/",
            {"replay_type": "highlight", "title": "Big play", "duration": 20},
        )
        assert response.status_code == 201

    def test_nested_scoped_to_game(
        self, api_client, game_wk1, game_wk2, quarter_scores, steelers
    ):
        """Quarter scores for game_wk2 should not include game_wk1 data."""
        QuarterScore.objects.create(game=game_wk2, team=steelers, period=1, points=3)
        response = api_client.get(f"/api/v1/games/{game_wk2.pk}/quarter-scores/")
        assert len(response.data) == 1
