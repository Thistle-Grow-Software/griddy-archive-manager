"""Tests for defensive boxscore serializers and endpoints (TGF-296)."""

import pytest
from django.test import Client

from archive.api.serializers.boxscore import (
    FumblesBoxscoreSerializer,
    TacklesBoxscoreSerializer,
)
from archive.models import (
    Franchise,
    FumblesBoxscore,
    Game,
    League,
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


@pytest.fixture
def tackles_stat(game, steelers):
    return TacklesBoxscore.objects.create(
        game=game,
        team=steelers,
        side="home",
        player_name="T.J. Watt",
        jersey_number=90,
        position="OLB",
        tackles=6,
        assists=2,
        sacks=2.0,
        sack_yards=15,
        qb_hits=3,
        tackles_for_loss=3,
        tackles_for_loss_yards=12,
    )


@pytest.fixture
def fumbles_stat(game, steelers):
    return FumblesBoxscore.objects.create(
        game=game,
        team=steelers,
        side="home",
        player_name="Minkah Fitzpatrick",
        jersey_number=39,
        position="FS",
        fumbles=0,
        forced_fumbles=2,
        opp_recoveries=1,
        opp_recovery_yards=15,
    )


# --- TacklesBoxscoreSerializer ---


@pytest.mark.django_db
def test_tackles_serializer_fields(tackles_stat):
    """TacklesBoxscoreSerializer includes base + tackles-specific fields."""
    stat = TacklesBoxscore.objects.select_related("team").get(pk=tackles_stat.pk)
    serializer = TacklesBoxscoreSerializer(stat)
    data = serializer.data
    assert data["player_name"] == "T.J. Watt"
    assert data["position"] == "OLB"
    assert data["tackles"] == 6
    assert data["assists"] == 2
    assert data["sacks"] == 2.0
    assert data["qb_hits"] == 3
    assert data["tackles_for_loss"] == 3


# --- FumblesBoxscoreSerializer ---


@pytest.mark.django_db
def test_fumbles_serializer_fields(fumbles_stat):
    """FumblesBoxscoreSerializer includes base + fumble-specific fields."""
    stat = FumblesBoxscore.objects.select_related("team").get(pk=fumbles_stat.pk)
    serializer = FumblesBoxscoreSerializer(stat)
    data = serializer.data
    assert data["player_name"] == "Minkah Fitzpatrick"
    assert data["forced_fumbles"] == 2
    assert data["opp_recoveries"] == 1
    assert data["opp_recovery_yards"] == 15


# --- Tackles endpoint ---


@pytest.mark.django_db
def test_tackles_list(client, game, tackles_stat):
    """GET /api/v1/games/<id>/boxscores/tackles/ returns tackles stats."""
    response = client.get(
        f"/api/v1/games/{game.pk}/boxscores/tackles/",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["player_name"] == "T.J. Watt"


@pytest.mark.django_db
def test_tackles_scoped_to_game(client, game, other_game, tackles_stat, ravens):
    """Tackles endpoint only returns stats for the specified game."""
    TacklesBoxscore.objects.create(
        game=other_game,
        team=ravens,
        side="home",
        player_name="Roquan Smith",
        position="ILB",
        tackles=10,
    )
    response = client.get(
        f"/api/v1/games/{game.pk}/boxscores/tackles/",
        HTTP_ACCEPT="application/json",
    )
    assert len(response.json()) == 1


@pytest.mark.django_db
def test_tackles_create(client, game, steelers):
    """POST /api/v1/games/<id>/boxscores/tackles/ creates a tackles stat."""
    response = client.post(
        f"/api/v1/games/{game.pk}/boxscores/tackles/",
        data={
            "team": steelers.pk,
            "side": "home",
            "player_name": "Alex Highsmith",
            "position": "OLB",
            "tackles": 4,
            "assists": 1,
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    assert TacklesBoxscore.objects.filter(
        game=game, player_name="Alex Highsmith"
    ).exists()


@pytest.mark.django_db
def test_tackles_uses_select_related(
    client, game, tackles_stat, django_assert_num_queries
):
    """Tackles endpoint uses select_related('team')."""
    with django_assert_num_queries(1):
        client.get(
            f"/api/v1/games/{game.pk}/boxscores/tackles/",
            HTTP_ACCEPT="application/json",
        )


# --- Fumbles endpoint ---


@pytest.mark.django_db
def test_fumbles_list(client, game, fumbles_stat):
    """GET /api/v1/games/<id>/boxscores/fumbles/ returns fumbles stats."""
    response = client.get(
        f"/api/v1/games/{game.pk}/boxscores/fumbles/",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["player_name"] == "Minkah Fitzpatrick"


@pytest.mark.django_db
def test_fumbles_scoped_to_game(client, game, other_game, fumbles_stat, ravens):
    """Fumbles endpoint only returns stats for the specified game."""
    FumblesBoxscore.objects.create(
        game=other_game,
        team=ravens,
        side="home",
        player_name="Kyle Hamilton",
        position="S",
        forced_fumbles=1,
    )
    response = client.get(
        f"/api/v1/games/{game.pk}/boxscores/fumbles/",
        HTTP_ACCEPT="application/json",
    )
    assert len(response.json()) == 1


@pytest.mark.django_db
def test_fumbles_create(client, game, steelers):
    """POST /api/v1/games/<id>/boxscores/fumbles/ creates a fumbles stat."""
    response = client.post(
        f"/api/v1/games/{game.pk}/boxscores/fumbles/",
        data={
            "team": steelers.pk,
            "side": "home",
            "player_name": "Cameron Heyward",
            "position": "DT",
            "forced_fumbles": 1,
            "opp_recoveries": 1,
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    assert FumblesBoxscore.objects.filter(
        game=game, player_name="Cameron Heyward"
    ).exists()
