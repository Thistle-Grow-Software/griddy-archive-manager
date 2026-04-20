"""Tests for Game full-boxscore and summary custom actions (TGF-305)."""

import pytest
from django.test import Client

from archive.models import (
    Drive,
    Franchise,
    Game,
    League,
    PassingBoxscore,
    QuarterScore,
    ReceivingBoxscore,
    RushingBoxscore,
    Season,
    TacklesBoxscore,
    Team,
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
        final_home_score=24,
        final_away_score=17,
    )


@pytest.fixture
def passing_stat(game, steelers):
    return PassingBoxscore.objects.create(
        game=game,
        team=steelers,
        side="home",
        player_name="Kenny Pickett",
        position="QB",
        attempts=30,
        completions=20,
        yards=250,
    )


@pytest.fixture
def rushing_stat(game, steelers):
    return RushingBoxscore.objects.create(
        game=game,
        team=steelers,
        side="home",
        player_name="Najee Harris",
        position="RB",
        attempts=18,
        yards=85,
    )


@pytest.fixture
def receiving_stat(game, steelers):
    return ReceivingBoxscore.objects.create(
        game=game,
        team=steelers,
        side="home",
        player_name="George Pickens",
        position="WR",
        receptions=6,
        yards=110,
    )


@pytest.fixture
def tackles_stat(game, steelers):
    return TacklesBoxscore.objects.create(
        game=game,
        team=steelers,
        side="home",
        player_name="T.J. Watt",
        position="OLB",
        tackles=6,
    )


@pytest.fixture
def quarter_scores(game, steelers, ravens):
    return [
        QuarterScore.objects.create(game=game, team=steelers, period=1, points=7),
        QuarterScore.objects.create(game=game, team=steelers, period=2, points=10),
        QuarterScore.objects.create(game=game, team=ravens, period=1, points=3),
        QuarterScore.objects.create(game=game, team=ravens, period=2, points=7),
    ]


@pytest.fixture
def drives(game, steelers, ravens):
    return [
        Drive.objects.create(
            game=game,
            sequence=1,
            team=steelers,
            yards_gained=75,
            ended_with_score=True,
        ),
        Drive.objects.create(
            game=game,
            sequence=2,
            team=ravens,
            yards_gained=45,
            ended_with_score=False,
        ),
        Drive.objects.create(
            game=game,
            sequence=3,
            team=steelers,
            yards_gained=60,
            ended_with_score=True,
        ),
    ]


# --- full-boxscore action ---


@pytest.mark.django_db
def test_full_boxscore_returns_200(client, game):
    """GET /api/v1/games/<id>/full-boxscore/ returns 200."""
    response = client.get(
        f"/api/v1/games/{game.pk}/full-boxscore/", HTTP_ACCEPT="application/json"
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_full_boxscore_has_all_10_categories(client, game):
    """Response contains all 10 boxscore category keys."""
    response = client.get(
        f"/api/v1/games/{game.pk}/full-boxscore/", HTTP_ACCEPT="application/json"
    )
    data = response.json()
    expected_keys = {
        "passing",
        "rushing",
        "receiving",
        "tackles",
        "fumbles",
        "field_goals",
        "extra_points",
        "kicking",
        "punting",
        "returns",
    }
    assert set(data.keys()) == expected_keys


@pytest.mark.django_db
def test_full_boxscore_includes_stats(
    client, game, passing_stat, rushing_stat, receiving_stat, tackles_stat
):
    """Boxscore categories contain the correct stats."""
    response = client.get(
        f"/api/v1/games/{game.pk}/full-boxscore/", HTTP_ACCEPT="application/json"
    )
    data = response.json()
    assert len(data["passing"]) == 1
    assert data["passing"][0]["player_name"] == "Kenny Pickett"
    assert len(data["rushing"]) == 1
    assert len(data["receiving"]) == 1
    assert len(data["tackles"]) == 1
    assert len(data["fumbles"]) == 0  # no fumble stats created


@pytest.mark.django_db
def test_full_boxscore_empty_game(client, game):
    """Full boxscore for game with no stats returns empty arrays."""
    response = client.get(
        f"/api/v1/games/{game.pk}/full-boxscore/", HTTP_ACCEPT="application/json"
    )
    data = response.json()
    for category in data.values():
        assert category == []


# --- summary action ---


@pytest.mark.django_db
def test_summary_returns_200(client, game):
    """GET /api/v1/games/<id>/summary/ returns 200."""
    response = client.get(
        f"/api/v1/games/{game.pk}/summary/", HTTP_ACCEPT="application/json"
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_summary_includes_team_names(client, game):
    """Summary includes home_team and away_team references."""
    response = client.get(
        f"/api/v1/games/{game.pk}/summary/", HTTP_ACCEPT="application/json"
    )
    data = response.json()
    assert data["home_team"]["short_name"] == "PIT"
    assert data["away_team"]["short_name"] == "BAL"


@pytest.mark.django_db
def test_summary_includes_scores(client, game):
    """Summary includes final scores."""
    response = client.get(
        f"/api/v1/games/{game.pk}/summary/", HTTP_ACCEPT="application/json"
    )
    data = response.json()
    assert data["final_home_score"] == 24
    assert data["final_away_score"] == 17


@pytest.mark.django_db
def test_summary_includes_quarter_scores(client, game, quarter_scores):
    """Summary includes quarter scores."""
    response = client.get(
        f"/api/v1/games/{game.pk}/summary/", HTTP_ACCEPT="application/json"
    )
    data = response.json()
    assert len(data["quarter_scores"]) == 4


@pytest.mark.django_db
def test_summary_includes_drive_summary(client, game, drives):
    """Summary includes drive summary with total count, scoring count, and total yards."""
    response = client.get(
        f"/api/v1/games/{game.pk}/summary/", HTTP_ACCEPT="application/json"
    )
    data = response.json()
    assert data["drives"]["total_drives"] == 3
    assert data["drives"]["scoring_drives"] == 2
    assert data["drives"]["total_yards"] == 180  # 75 + 45 + 60
