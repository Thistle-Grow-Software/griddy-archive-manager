"""Tests for Play serializers and nested endpoint (TGF-298)."""

import pytest
from django.test import Client

from archive.api.serializers.play import PlayDetailSerializer, PlayListSerializer
from archive.models import (
    Franchise,
    Game,
    League,
    Play,
    PlayStat,
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
def play1(game, steelers):
    return Play.objects.create(
        game=game,
        play_id=1,
        sequence=1.0,
        quarter=1,
        down=1,
        yards_to_go=10,
        play_type="RUSH",
        play_description="N.Harris left guard for 5 yards",
        possession_team=steelers,
        home_score=0,
        visitor_score=0,
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
        play_description="K.Pickett pass complete to G.Pickens for 45 yards, TOUCHDOWN",
        possession_team=steelers,
        home_score=7,
        visitor_score=0,
        is_scoring=True,
    )


@pytest.fixture
def play_stat(play1):
    return PlayStat.objects.create(
        play=play1,
        team_abbr="PIT",
        player_name="N.Harris",
        gsis_id="00-123456",
        stat_id=10,
        yards=5,
    )


# --- PlayListSerializer ---


@pytest.mark.django_db
def test_play_list_serializer_fields(play1, steelers):
    """PlayListSerializer includes expected fields."""
    play = Play.objects.select_related("possession_team").get(pk=play1.pk)
    data = PlayListSerializer(play).data
    assert data["id"] == play1.pk
    assert data["sequence"] == 1.0
    assert data["quarter"] == 1
    assert data["down"] == 1
    assert data["yards_to_go"] == 10
    assert data["play_type"] == "RUSH"
    assert data["play_description"] == "N.Harris left guard for 5 yards"
    assert data["possession_team"] == steelers.pk
    assert data["home_score"] == 0
    assert data["visitor_score"] == 0
    assert data["is_scoring"] is False


# --- PlayDetailSerializer ---


@pytest.mark.django_db
def test_play_detail_serializer_includes_stats(play1, play_stat):
    """PlayDetailSerializer includes all fields plus nested PlayStats."""
    play = (
        Play.objects.select_related("possession_team")
        .prefetch_related("stats")
        .get(pk=play1.pk)
    )
    data = PlayDetailSerializer(play).data
    assert "ngs_data" in data
    assert "bonus_data" in data
    assert len(data["stats"]) == 1
    assert data["stats"][0]["player_name"] == "N.Harris"
    assert data["stats"][0]["yards"] == 5


# --- Play endpoint LIST ---


@pytest.mark.django_db
def test_plays_list_returns_200(client, game, play1):
    """GET /api/v1/games/<id>/plays/ returns 200 with paginated results."""
    response = client.get(
        f"/api/v1/games/{game.pk}/plays/", HTTP_ACCEPT="application/json"
    )
    assert response.status_code == 200
    data = response.json()
    assert "results" in data  # PlayPagination provides cursor pagination


@pytest.mark.django_db
def test_plays_ordered_by_sequence(client, game, play1, play2):
    """Plays default to sequence ordering."""
    response = client.get(
        f"/api/v1/games/{game.pk}/plays/", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert results[0]["sequence"] == 1.0
    assert results[1]["sequence"] == 2.0


@pytest.mark.django_db
def test_plays_scoped_to_game(client, game, other_game, play1, ravens):
    """Plays endpoint only returns plays for the specified game."""
    Play.objects.create(
        game=other_game,
        play_id=1,
        sequence=1.0,
        possession_team=ravens,
    )
    response = client.get(
        f"/api/v1/games/{game.pk}/plays/", HTTP_ACCEPT="application/json"
    )
    assert len(response.json()["results"]) == 1


# --- Play endpoint CREATE ---


@pytest.mark.django_db
def test_plays_create(client, game, steelers):
    """POST /api/v1/games/<id>/plays/ creates a play for the game."""
    response = client.post(
        f"/api/v1/games/{game.pk}/plays/",
        data={
            "play_id": 99,
            "sequence": 99.0,
            "quarter": 4,
            "down": 3,
            "yards_to_go": 7,
            "play_type": "PASS",
            "play_description": "Test play",
            "possession_team": steelers.pk,
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    assert Play.objects.filter(game=game, play_id=99).exists()


# --- Play endpoint RETRIEVE ---


@pytest.mark.django_db
def test_plays_retrieve_returns_detail(client, game, play1, play_stat):
    """GET /api/v1/games/<id>/plays/<play_pk>/ returns detail with stats."""
    response = client.get(
        f"/api/v1/games/{game.pk}/plays/{play1.pk}/",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["play_type"] == "RUSH"
    assert len(data["stats"]) == 1


# --- Filters ---


@pytest.mark.django_db
def test_plays_filter_by_quarter(client, game, play1, play2):
    """?quarter=1 filters plays by quarter."""
    response = client.get(
        f"/api/v1/games/{game.pk}/plays/?quarter=1",
        HTTP_ACCEPT="application/json",
    )
    results = response.json()["results"]
    assert len(results) == 2  # both plays are in Q1


@pytest.mark.django_db
def test_plays_filter_by_is_scoring(client, game, play1, play2):
    """?is_scoring=true filters to scoring plays only."""
    response = client.get(
        f"/api/v1/games/{game.pk}/plays/?is_scoring=true",
        HTTP_ACCEPT="application/json",
    )
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["is_scoring"] is True


@pytest.mark.django_db
def test_plays_filter_by_play_type(client, game, play1, play2):
    """?play_type=RUSH filters by play type."""
    response = client.get(
        f"/api/v1/games/{game.pk}/plays/?play_type=RUSH",
        HTTP_ACCEPT="application/json",
    )
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["play_type"] == "RUSH"


# --- PlayPagination ---


@pytest.mark.django_db
def test_play_pagination_page_size():
    """PlayPagination must have page_size=200."""
    from archive.api.pagination import PlayPagination

    assert PlayPagination.page_size == 200
    assert PlayPagination.ordering == "sequence"
