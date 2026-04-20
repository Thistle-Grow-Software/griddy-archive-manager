"""
Boxscore and Play-by-Play API integration tests using DRF's APIClient (TGF-309).

Tests for all 10 boxscore nested endpoints, Play endpoint with filters/ordering,
and PlayStat nested endpoint.
"""

import pytest
from rest_framework.test import APIClient

from archive.models import (
    ExtraPointsBoxscore,
    FieldGoalsBoxscore,
    Franchise,
    FumblesBoxscore,
    Game,
    KickingBoxscore,
    League,
    PassingBoxscore,
    Play,
    PlayStat,
    PuntingBoxscore,
    ReceivingBoxscore,
    ReturnBoxscore,
    RushingBoxscore,
    Season,
    TacklesBoxscore,
    Team,
    Venue,
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
        franchise=steelers_franchise, name="Pittsburgh Steelers", short_name="PIT"
    )


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


@pytest.fixture
def other_game(nfl, season_2024, ravens, steelers, heinz_field):
    return Game.objects.create(
        league=nfl,
        season=season_2024,
        date_local="2024-09-15",
        week=2,
        home_team=ravens,
        away_team=steelers,
        venue=heinz_field,
    )


# ===========================================================================
# Boxscore Endpoints — All 10 Types
# ===========================================================================

BOXSCORE_CONFIGS = [
    (
        "passing",
        PassingBoxscore,
        {"attempts": 30, "completions": 20, "yards": 250},
        ["attempts", "completions", "yards"],
    ),
    ("rushing", RushingBoxscore, {"attempts": 18, "yards": 85}, ["attempts", "yards"]),
    (
        "receiving",
        ReceivingBoxscore,
        {"receptions": 6, "yards": 110},
        ["receptions", "yards"],
    ),
    ("tackles", TacklesBoxscore, {"tackles": 6, "assists": 2}, ["tackles", "assists"]),
    (
        "fumbles",
        FumblesBoxscore,
        {"forced_fumbles": 2, "opp_recoveries": 1},
        ["forced_fumbles", "opp_recoveries"],
    ),
    (
        "field-goals",
        FieldGoalsBoxscore,
        {"attempts": 3, "made": 2},
        ["attempts", "made"],
    ),
    (
        "extra-points",
        ExtraPointsBoxscore,
        {"attempts": 3, "made": 3},
        ["attempts", "made"],
    ),
    ("kicking", KickingBoxscore, {"kickoffs": 5, "yards": 325}, ["kickoffs", "yards"]),
    ("punting", PuntingBoxscore, {"attempts": 4, "yards": 180}, ["attempts", "yards"]),
    (
        "returns",
        ReturnBoxscore,
        {"return_type": "punt", "returns": 3, "yards": 45},
        ["return_type", "returns", "yards"],
    ),
]


@pytest.mark.django_db
class TestBoxscoreEndpoints:
    """Tests for all 10 boxscore nested endpoints."""

    @pytest.mark.parametrize(
        "url_slug,model,create_data,_",
        BOXSCORE_CONFIGS,
        ids=[c[0] for c in BOXSCORE_CONFIGS],
    )
    def test_list_returns_200(
        self, api_client, game, steelers, url_slug, model, create_data, _
    ):
        """Each boxscore endpoint returns 200 for LIST."""
        model.objects.create(
            game=game,
            team=steelers,
            side="home",
            player_name="Player",
            position="POS",
            **create_data,
        )
        response = api_client.get(f"/api/v1/games/{game.pk}/boxscores/{url_slug}/")
        assert response.status_code == 200
        assert len(response.data) == 1

    @pytest.mark.parametrize(
        "url_slug,model,create_data,_",
        BOXSCORE_CONFIGS,
        ids=[c[0] for c in BOXSCORE_CONFIGS],
    )
    def test_create_returns_201(
        self, api_client, game, steelers, url_slug, model, create_data, _
    ):
        """Each boxscore endpoint returns 201 for CREATE."""
        payload = {
            "team": steelers.pk,
            "side": "home",
            "player_name": "New Player",
            "position": "POS",
            **create_data,
        }
        response = api_client.post(
            f"/api/v1/games/{game.pk}/boxscores/{url_slug}/", payload
        )
        assert response.status_code == 201

    @pytest.mark.parametrize(
        "url_slug,model,create_data,expected_fields",
        BOXSCORE_CONFIGS,
        ids=[c[0] for c in BOXSCORE_CONFIGS],
    )
    def test_correct_stat_fields(
        self, api_client, game, steelers, url_slug, model, create_data, expected_fields
    ):
        """Each boxscore type returns the correct stat-specific fields."""
        model.objects.create(
            game=game,
            team=steelers,
            side="home",
            player_name="Player",
            position="POS",
            **create_data,
        )
        response = api_client.get(f"/api/v1/games/{game.pk}/boxscores/{url_slug}/")
        data = response.data[0]
        # Base fields present
        assert "id" in data
        assert "player_name" in data
        assert "position" in data
        # Stat-specific fields present
        for field in expected_fields:
            assert field in data, f"{field} missing from {url_slug} response"

    def test_boxscore_scoped_to_game(self, api_client, game, other_game, steelers):
        """Boxscore endpoint only returns stats for the specified game."""
        PassingBoxscore.objects.create(
            game=game,
            team=steelers,
            side="home",
            player_name="QB1",
            position="QB",
            attempts=20,
            yards=200,
        )
        PassingBoxscore.objects.create(
            game=other_game,
            team=steelers,
            side="away",
            player_name="QB2",
            position="QB",
            attempts=15,
            yards=150,
        )
        response = api_client.get(f"/api/v1/games/{game.pk}/boxscores/passing/")
        assert len(response.data) == 1
        assert response.data[0]["player_name"] == "QB1"


# ===========================================================================
# Play Endpoint
# ===========================================================================


@pytest.fixture
def play1(game, steelers):
    return Play.objects.create(
        game=game,
        play_id=1,
        sequence=1.0,
        quarter=1,
        down=1,
        yards_to_go=10,
        play_type="RUSH",
        play_description="Rush left",
        possession_team=steelers,
        is_scoring=False,
    )


@pytest.fixture
def play2(game, steelers):
    return Play.objects.create(
        game=game,
        play_id=2,
        sequence=2.0,
        quarter=1,
        down=2,
        yards_to_go=5,
        play_type="PASS",
        play_description="Pass complete for TD",
        possession_team=steelers,
        is_scoring=True,
    )


@pytest.fixture
def play3(game, ravens):
    return Play.objects.create(
        game=game,
        play_id=3,
        sequence=3.0,
        quarter=2,
        down=1,
        yards_to_go=10,
        play_type="PASS",
        play_description="Pass incomplete",
        possession_team=ravens,
        is_scoring=False,
    )


@pytest.mark.django_db
class TestPlayEndpoint:
    def test_list(self, api_client, game, play1):
        response = api_client.get(f"/api/v1/games/{game.pk}/plays/")
        assert response.status_code == 200
        assert "results" in response.data  # paginated

    def test_create(self, api_client, game, steelers):
        response = api_client.post(
            f"/api/v1/games/{game.pk}/plays/",
            {
                "play_id": 99,
                "sequence": 99.0,
                "quarter": 4,
                "play_type": "RUSH",
                "possession_team": steelers.pk,
            },
        )
        assert response.status_code == 201
        assert Play.objects.filter(game=game, play_id=99).exists()

    def test_filter_by_quarter(self, api_client, game, play1, play2, play3):
        response = api_client.get(f"/api/v1/games/{game.pk}/plays/?quarter=1")
        assert len(response.data["results"]) == 2

    def test_filter_by_play_type(self, api_client, game, play1, play2, play3):
        response = api_client.get(f"/api/v1/games/{game.pk}/plays/?play_type=RUSH")
        assert len(response.data["results"]) == 1

    def test_filter_by_is_scoring(self, api_client, game, play1, play2, play3):
        response = api_client.get(f"/api/v1/games/{game.pk}/plays/?is_scoring=true")
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["is_scoring"] is True

    def test_ordering_by_sequence(self, api_client, game, play1, play2, play3):
        response = api_client.get(f"/api/v1/games/{game.pk}/plays/?ordering=sequence")
        results = response.data["results"]
        assert results[0]["sequence"] < results[-1]["sequence"]

    def test_scoped_to_game(self, api_client, game, other_game, play1, ravens):
        Play.objects.create(
            game=other_game, play_id=1, sequence=1.0, possession_team=ravens
        )
        response = api_client.get(f"/api/v1/games/{game.pk}/plays/")
        assert len(response.data["results"]) == 1

    def test_pagination_uses_cursor(self, api_client, game, play1, play2):
        """PlayPagination provides cursor-based pagination with results wrapper."""
        response = api_client.get(f"/api/v1/games/{game.pk}/plays/")
        assert "results" in response.data
        assert "next" in response.data
        assert "previous" in response.data


# ===========================================================================
# PlayPagination Verification
# ===========================================================================


@pytest.mark.django_db
class TestPlayPagination:
    def test_page_size_is_200(self):
        from archive.api.pagination import PlayPagination

        assert PlayPagination.page_size == 200

    def test_ordering_is_sequence(self):
        from archive.api.pagination import PlayPagination

        assert PlayPagination.ordering == "sequence"


# ===========================================================================
# PlayStat Endpoint
# ===========================================================================


@pytest.fixture
def play_stat(play1):
    return PlayStat.objects.create(
        play=play1, team_abbr="PIT", player_name="N.Harris", stat_id=10, yards=5
    )


@pytest.mark.django_db
class TestPlayStatEndpoint:
    def test_list(self, api_client, play1, play_stat):
        response = api_client.get(f"/api/v1/plays/{play1.pk}/stats/")
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["player_name"] == "N.Harris"

    def test_create(self, api_client, play1):
        response = api_client.post(
            f"/api/v1/plays/{play1.pk}/stats/",
            {
                "team_abbr": "PIT",
                "player_name": "G.Pickens",
                "stat_id": 21,
                "yards": 45,
            },
        )
        assert response.status_code == 201
        assert PlayStat.objects.filter(play=play1, player_name="G.Pickens").exists()

    def test_scoped_to_play(self, api_client, game, play1, play2, play_stat, steelers):
        PlayStat.objects.create(
            play=play2, team_abbr="PIT", player_name="Other", stat_id=15, yards=10
        )
        response = api_client.get(f"/api/v1/plays/{play1.pk}/stats/")
        assert len(response.data) == 1
        assert response.data[0]["player_name"] == "N.Harris"

    def test_stat_fields(self, api_client, play1, play_stat):
        response = api_client.get(f"/api/v1/plays/{play1.pk}/stats/")
        data = response.data[0]
        assert "id" in data
        assert "player_name" in data
        assert "stat_id" in data
        assert "yards" in data
        assert "team_abbr" in data
