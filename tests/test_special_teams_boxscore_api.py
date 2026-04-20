"""Tests for special teams boxscore serializers and endpoints (TGF-297)."""

import pytest
from django.test import Client

from archive.api.serializers.boxscore_special_teams import (
    ExtraPointsBoxscoreSerializer,
    FieldGoalsBoxscoreSerializer,
    KickingBoxscoreSerializer,
    PuntingBoxscoreSerializer,
    ReturnBoxscoreSerializer,
)
from archive.models import (
    ExtraPointsBoxscore,
    FieldGoalsBoxscore,
    Franchise,
    Game,
    KickingBoxscore,
    League,
    PuntingBoxscore,
    ReturnBoxscore,
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
def fg_stat(game, steelers):
    return FieldGoalsBoxscore.objects.create(
        game=game,
        team=steelers,
        side="home",
        player_name="Chris Boswell",
        jersey_number=9,
        position="K",
        attempts=3,
        made=2,
        blocked=0,
        yards=95,
        longest=48,
    )


@pytest.fixture
def xp_stat(game, steelers):
    return ExtraPointsBoxscore.objects.create(
        game=game,
        team=steelers,
        side="home",
        player_name="Chris Boswell",
        jersey_number=9,
        position="K",
        attempts=3,
        made=3,
    )


@pytest.fixture
def kicking_stat(game, steelers):
    return KickingBoxscore.objects.create(
        game=game,
        team=steelers,
        side="home",
        player_name="Chris Boswell",
        jersey_number=9,
        position="K",
        kickoffs=5,
        yards=325,
        touchbacks=3,
    )


@pytest.fixture
def punting_stat(game, steelers):
    return PuntingBoxscore.objects.create(
        game=game,
        team=steelers,
        side="home",
        player_name="Pressley Harvin III",
        jersey_number=6,
        position="P",
        attempts=4,
        yards=180,
        gross_avg=45.0,
        net_avg=40.5,
        longest=55,
        inside_20=2,
    )


@pytest.fixture
def return_stat(game, steelers):
    return ReturnBoxscore.objects.create(
        game=game,
        team=steelers,
        side="home",
        player_name="Gunner Olszewski",
        jersey_number=89,
        position="WR",
        return_type="punt",
        returns=3,
        yards=45,
        avg_yards=15.0,
        fair_catches=2,
    )


# --- Serializer field tests ---


@pytest.mark.django_db
def test_field_goals_serializer_fields(fg_stat):
    """FieldGoalsBoxscoreSerializer includes base + field goal fields."""
    stat = FieldGoalsBoxscore.objects.select_related("team").get(pk=fg_stat.pk)
    data = FieldGoalsBoxscoreSerializer(stat).data
    assert data["player_name"] == "Chris Boswell"
    assert data["attempts"] == 3
    assert data["made"] == 2
    assert data["longest"] == 48


@pytest.mark.django_db
def test_extra_points_serializer_fields(xp_stat):
    """ExtraPointsBoxscoreSerializer includes base + extra point fields."""
    stat = ExtraPointsBoxscore.objects.select_related("team").get(pk=xp_stat.pk)
    data = ExtraPointsBoxscoreSerializer(stat).data
    assert data["player_name"] == "Chris Boswell"
    assert data["attempts"] == 3
    assert data["made"] == 3


@pytest.mark.django_db
def test_kicking_serializer_fields(kicking_stat):
    """KickingBoxscoreSerializer includes base + kicking fields."""
    stat = KickingBoxscore.objects.select_related("team").get(pk=kicking_stat.pk)
    data = KickingBoxscoreSerializer(stat).data
    assert data["kickoffs"] == 5
    assert data["touchbacks"] == 3


@pytest.mark.django_db
def test_punting_serializer_fields(punting_stat):
    """PuntingBoxscoreSerializer includes base + punting fields."""
    stat = PuntingBoxscore.objects.select_related("team").get(pk=punting_stat.pk)
    data = PuntingBoxscoreSerializer(stat).data
    assert data["player_name"] == "Pressley Harvin III"
    assert data["attempts"] == 4
    assert data["gross_avg"] == 45.0
    assert data["inside_20"] == 2


@pytest.mark.django_db
def test_return_serializer_fields(return_stat):
    """ReturnBoxscoreSerializer includes base + return fields."""
    stat = ReturnBoxscore.objects.select_related("team").get(pk=return_stat.pk)
    data = ReturnBoxscoreSerializer(stat).data
    assert data["return_type"] == "punt"
    assert data["returns"] == 3
    assert data["fair_catches"] == 2


# --- Endpoint LIST tests ---


@pytest.mark.django_db
def test_field_goals_list(client, game, fg_stat):
    """GET /api/v1/games/<id>/boxscores/field-goals/ returns stats."""
    response = client.get(
        f"/api/v1/games/{game.pk}/boxscores/field-goals/",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.django_db
def test_extra_points_list(client, game, xp_stat):
    """GET /api/v1/games/<id>/boxscores/extra-points/ returns stats."""
    response = client.get(
        f"/api/v1/games/{game.pk}/boxscores/extra-points/",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.django_db
def test_kicking_list(client, game, kicking_stat):
    """GET /api/v1/games/<id>/boxscores/kicking/ returns stats."""
    response = client.get(
        f"/api/v1/games/{game.pk}/boxscores/kicking/",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.django_db
def test_punting_list(client, game, punting_stat):
    """GET /api/v1/games/<id>/boxscores/punting/ returns stats."""
    response = client.get(
        f"/api/v1/games/{game.pk}/boxscores/punting/",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.django_db
def test_returns_list(client, game, return_stat):
    """GET /api/v1/games/<id>/boxscores/returns/ returns stats."""
    response = client.get(
        f"/api/v1/games/{game.pk}/boxscores/returns/",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


# --- Endpoint CREATE tests ---


@pytest.mark.django_db
def test_field_goals_create(client, game, steelers):
    """POST /api/v1/games/<id>/boxscores/field-goals/ creates a stat."""
    response = client.post(
        f"/api/v1/games/{game.pk}/boxscores/field-goals/",
        data={
            "team": steelers.pk,
            "side": "home",
            "player_name": "Kicker",
            "position": "K",
            "attempts": 1,
            "made": 1,
        },
        content_type="application/json",
    )
    assert response.status_code == 201


@pytest.mark.django_db
def test_extra_points_create(client, game, steelers):
    """POST /api/v1/games/<id>/boxscores/extra-points/ creates a stat."""
    response = client.post(
        f"/api/v1/games/{game.pk}/boxscores/extra-points/",
        data={
            "team": steelers.pk,
            "side": "home",
            "player_name": "Kicker",
            "position": "K",
            "attempts": 2,
            "made": 2,
        },
        content_type="application/json",
    )
    assert response.status_code == 201


@pytest.mark.django_db
def test_kicking_create(client, game, steelers):
    """POST /api/v1/games/<id>/boxscores/kicking/ creates a stat."""
    response = client.post(
        f"/api/v1/games/{game.pk}/boxscores/kicking/",
        data={
            "team": steelers.pk,
            "side": "home",
            "player_name": "Kicker",
            "position": "K",
            "kickoffs": 3,
            "yards": 195,
        },
        content_type="application/json",
    )
    assert response.status_code == 201


@pytest.mark.django_db
def test_punting_create(client, game, steelers):
    """POST /api/v1/games/<id>/boxscores/punting/ creates a stat."""
    response = client.post(
        f"/api/v1/games/{game.pk}/boxscores/punting/",
        data={
            "team": steelers.pk,
            "side": "home",
            "player_name": "Punter",
            "position": "P",
            "attempts": 3,
            "yards": 135,
        },
        content_type="application/json",
    )
    assert response.status_code == 201


@pytest.mark.django_db
def test_returns_create(client, game, steelers):
    """POST /api/v1/games/<id>/boxscores/returns/ creates a stat."""
    response = client.post(
        f"/api/v1/games/{game.pk}/boxscores/returns/",
        data={
            "team": steelers.pk,
            "side": "home",
            "player_name": "Returner",
            "position": "WR",
            "return_type": "kick",
            "returns": 2,
            "yards": 50,
        },
        content_type="application/json",
    )
    assert response.status_code == 201


# --- Game scoping ---


@pytest.mark.django_db
def test_field_goals_scoped_to_game(
    client, game, fg_stat, nfl, season_2024, steelers, ravens, heinz_field
):
    """Field goals endpoint only returns stats for the specified game."""
    other_game = Game.objects.create(
        league=nfl,
        season=season_2024,
        date_local="2024-09-15",
        week=2,
        home_team=ravens,
        away_team=steelers,
        venue=heinz_field,
    )
    FieldGoalsBoxscore.objects.create(
        game=other_game,
        team=ravens,
        side="home",
        player_name="Justin Tucker",
        position="K",
        attempts=2,
        made=2,
    )
    response = client.get(
        f"/api/v1/games/{game.pk}/boxscores/field-goals/",
        HTTP_ACCEPT="application/json",
    )
    assert len(response.json()) == 1


# --- select_related verification ---


@pytest.mark.django_db
def test_field_goals_uses_select_related(
    client, game, fg_stat, django_assert_num_queries
):
    """Field goals endpoint uses select_related('team')."""
    with django_assert_num_queries(1):
        client.get(
            f"/api/v1/games/{game.pk}/boxscores/field-goals/",
            HTTP_ACCEPT="application/json",
        )
