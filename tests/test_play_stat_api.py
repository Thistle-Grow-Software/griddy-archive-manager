"""Tests for PlayStat serializer and nested endpoint (TGF-299)."""

import pytest
from django.test import Client

from archive.api.serializers.play_stat import PlayStatSerializer
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
def play(game, steelers):
    return Play.objects.create(
        game=game,
        play_id=1,
        sequence=1.0,
        quarter=1,
        play_type="RUSH",
        possession_team=steelers,
    )


@pytest.fixture
def other_play(game, ravens):
    return Play.objects.create(
        game=game,
        play_id=2,
        sequence=2.0,
        quarter=1,
        play_type="PASS",
        possession_team=ravens,
    )


@pytest.fixture
def stat1(play):
    return PlayStat.objects.create(
        play=play,
        team_abbr="PIT",
        player_name="N.Harris",
        gsis_id="00-123456",
        stat_id=10,
        yards=5,
    )


@pytest.fixture
def stat2(play):
    return PlayStat.objects.create(
        play=play,
        team_abbr="PIT",
        player_name="N.Harris",
        gsis_id="00-123456",
        stat_id=11,
        yards=5,
    )


# --- PlayStatSerializer ---


@pytest.mark.django_db
def test_play_stat_serializer_fields(stat1):
    """PlayStatSerializer includes id, player_name, stat_id, yards, team_abbr."""
    data = PlayStatSerializer(stat1).data
    assert set(data.keys()) == {"id", "player_name", "stat_id", "yards", "team_abbr"}
    assert data["player_name"] == "N.Harris"
    assert data["stat_id"] == 10
    assert data["yards"] == 5
    assert data["team_abbr"] == "PIT"


# --- LIST endpoint ---


@pytest.mark.django_db
def test_play_stats_list(client, play, stat1, stat2):
    """GET /api/v1/plays/<id>/stats/ returns stats for the play."""
    response = client.get(
        f"/api/v1/plays/{play.pk}/stats/", HTTP_ACCEPT="application/json"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.django_db
def test_play_stats_scoped_to_play(client, play, other_play, stat1):
    """Stats endpoint only returns stats for the specified play."""
    PlayStat.objects.create(
        play=other_play,
        team_abbr="BAL",
        player_name="L.Jackson",
        stat_id=15,
        yards=12,
    )
    response = client.get(
        f"/api/v1/plays/{play.pk}/stats/", HTTP_ACCEPT="application/json"
    )
    assert len(response.json()) == 1


# --- CREATE endpoint ---


@pytest.mark.django_db
def test_play_stats_create(client, play):
    """POST /api/v1/plays/<id>/stats/ creates a stat for the play."""
    response = client.post(
        f"/api/v1/plays/{play.pk}/stats/",
        data={
            "team_abbr": "PIT",
            "player_name": "G.Pickens",
            "stat_id": 21,
            "yards": 45,
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    assert PlayStat.objects.filter(play=play, player_name="G.Pickens").exists()


@pytest.mark.django_db
def test_play_stats_create_injects_play(client, play):
    """Created stat is associated with the correct play from URL."""
    client.post(
        f"/api/v1/plays/{play.pk}/stats/",
        data={
            "team_abbr": "PIT",
            "player_name": "Test Player",
            "stat_id": 1,
            "yards": 0,
        },
        content_type="application/json",
    )
    stat = PlayStat.objects.get(player_name="Test Player")
    assert stat.play_id == play.pk
