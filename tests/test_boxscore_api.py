"""Tests for boxscore serializers and endpoints (TGF-295)."""

import pytest
from django.test import Client

from archive.api.serializers.boxscore import (
    PassingBoxscoreSerializer,
    PlayerGameStatBaseSerializer,
    ReceivingBoxscoreSerializer,
    RushingBoxscoreSerializer,
)
from archive.models import (
    Franchise,
    Game,
    League,
    PassingBoxscore,
    ReceivingBoxscore,
    RushingBoxscore,
    Season,
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
def passing_stat(game, steelers):
    return PassingBoxscore.objects.create(
        game=game,
        team=steelers,
        side="home",
        player_name="Kenny Pickett",
        jersey_number=8,
        position="QB",
        attempts=30,
        completions=20,
        completion_pct=66.7,
        yards=250,
        yards_per_attempt=8.3,
        touchdowns=2,
        interceptions=1,
        sacks=2,
        sack_yards=14,
        qb_rating=92.5,
    )


@pytest.fixture
def rushing_stat(game, steelers):
    return RushingBoxscore.objects.create(
        game=game,
        team=steelers,
        side="home",
        player_name="Najee Harris",
        jersey_number=22,
        position="RB",
        attempts=18,
        yards=85,
        avg_yards=4.7,
        touchdowns=1,
        longest_rush=22,
    )


@pytest.fixture
def receiving_stat(game, steelers):
    return ReceivingBoxscore.objects.create(
        game=game,
        team=steelers,
        side="home",
        player_name="George Pickens",
        jersey_number=14,
        position="WR",
        receptions=6,
        yards=110,
        avg_yards=18.3,
        touchdowns=1,
        targets=9,
        longest_reception=42,
        yards_after_catch=35,
    )


# --- PlayerGameStatBaseSerializer ---


def test_base_serializer_defines_shared_fields():
    """PlayerGameStatBaseSerializer defines shared fields."""
    fields = PlayerGameStatBaseSerializer().fields
    expected = {
        "id",
        "game",
        "team",
        "side",
        "player_name",
        "jersey_number",
        "position",
    }
    assert set(fields.keys()) == expected


# --- PassingBoxscoreSerializer ---


@pytest.mark.django_db
def test_passing_serializer_fields(passing_stat):
    """PassingBoxscoreSerializer includes base + passing-specific fields."""
    stat = PassingBoxscore.objects.select_related("team").get(pk=passing_stat.pk)
    serializer = PassingBoxscoreSerializer(stat)
    data = serializer.data
    assert data["player_name"] == "Kenny Pickett"
    assert data["position"] == "QB"
    assert data["attempts"] == 30
    assert data["completions"] == 20
    assert data["yards"] == 250
    assert data["touchdowns"] == 2
    assert data["interceptions"] == 1
    assert data["qb_rating"] == 92.5


# --- RushingBoxscoreSerializer ---


@pytest.mark.django_db
def test_rushing_serializer_fields(rushing_stat):
    """RushingBoxscoreSerializer includes base + rushing-specific fields."""
    stat = RushingBoxscore.objects.select_related("team").get(pk=rushing_stat.pk)
    serializer = RushingBoxscoreSerializer(stat)
    data = serializer.data
    assert data["player_name"] == "Najee Harris"
    assert data["attempts"] == 18
    assert data["yards"] == 85
    assert data["avg_yards"] == 4.7
    assert data["touchdowns"] == 1
    assert data["longest_rush"] == 22


# --- ReceivingBoxscoreSerializer ---


@pytest.mark.django_db
def test_receiving_serializer_fields(receiving_stat):
    """ReceivingBoxscoreSerializer includes base + receiving-specific fields."""
    stat = ReceivingBoxscore.objects.select_related("team").get(pk=receiving_stat.pk)
    serializer = ReceivingBoxscoreSerializer(stat)
    data = serializer.data
    assert data["player_name"] == "George Pickens"
    assert data["receptions"] == 6
    assert data["yards"] == 110
    assert data["touchdowns"] == 1
    assert data["targets"] == 9
    assert data["yards_after_catch"] == 35


# --- Passing endpoint ---


@pytest.mark.django_db
def test_passing_list(client, game, passing_stat):
    """GET /api/v1/games/<id>/boxscores/passing/ returns passing stats."""
    response = client.get(
        f"/api/v1/games/{game.pk}/boxscores/passing/",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["player_name"] == "Kenny Pickett"


@pytest.mark.django_db
def test_passing_scoped_to_game(client, game, other_game, passing_stat, ravens):
    """Passing endpoint only returns stats for the specified game."""
    PassingBoxscore.objects.create(
        game=other_game,
        team=ravens,
        side="home",
        player_name="Lamar Jackson",
        position="QB",
        attempts=25,
        completions=18,
        yards=280,
    )
    response = client.get(
        f"/api/v1/games/{game.pk}/boxscores/passing/",
        HTTP_ACCEPT="application/json",
    )
    assert len(response.json()) == 1


@pytest.mark.django_db
def test_passing_create(client, game, steelers):
    """POST /api/v1/games/<id>/boxscores/passing/ creates a passing stat."""
    response = client.post(
        f"/api/v1/games/{game.pk}/boxscores/passing/",
        data={
            "team": steelers.pk,
            "side": "home",
            "player_name": "Mason Rudolph",
            "position": "QB",
            "attempts": 5,
            "completions": 3,
            "yards": 45,
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    assert PassingBoxscore.objects.filter(
        game=game, player_name="Mason Rudolph"
    ).exists()


# --- Rushing endpoint ---


@pytest.mark.django_db
def test_rushing_list(client, game, rushing_stat):
    """GET /api/v1/games/<id>/boxscores/rushing/ returns rushing stats."""
    response = client.get(
        f"/api/v1/games/{game.pk}/boxscores/rushing/",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["player_name"] == "Najee Harris"


@pytest.mark.django_db
def test_rushing_create(client, game, steelers):
    """POST /api/v1/games/<id>/boxscores/rushing/ creates a rushing stat."""
    response = client.post(
        f"/api/v1/games/{game.pk}/boxscores/rushing/",
        data={
            "team": steelers.pk,
            "side": "home",
            "player_name": "Jaylen Warren",
            "position": "RB",
            "attempts": 10,
            "yards": 42,
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    assert RushingBoxscore.objects.filter(
        game=game, player_name="Jaylen Warren"
    ).exists()


# --- Receiving endpoint ---


@pytest.mark.django_db
def test_receiving_list(client, game, receiving_stat):
    """GET /api/v1/games/<id>/boxscores/receiving/ returns receiving stats."""
    response = client.get(
        f"/api/v1/games/{game.pk}/boxscores/receiving/",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["player_name"] == "George Pickens"


@pytest.mark.django_db
def test_receiving_create(client, game, steelers):
    """POST /api/v1/games/<id>/boxscores/receiving/ creates a receiving stat."""
    response = client.post(
        f"/api/v1/games/{game.pk}/boxscores/receiving/",
        data={
            "team": steelers.pk,
            "side": "home",
            "player_name": "Pat Freiermuth",
            "position": "TE",
            "receptions": 4,
            "yards": 38,
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    assert ReceivingBoxscore.objects.filter(
        game=game, player_name="Pat Freiermuth"
    ).exists()


# --- select_related verification ---


@pytest.mark.django_db
def test_passing_uses_select_related(
    client, game, passing_stat, django_assert_num_queries
):
    """Passing endpoint uses select_related('team')."""
    with django_assert_num_queries(1):
        client.get(
            f"/api/v1/games/{game.pk}/boxscores/passing/",
            HTTP_ACCEPT="application/json",
        )
