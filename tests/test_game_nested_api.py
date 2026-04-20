"""Tests for QuarterScore, Drive, and GameReplay nested endpoints (TGF-294)."""

import pytest
from django.test import Client

from archive.models import (
    Drive,
    Franchise,
    Game,
    GameReplay,
    League,
    QuarterScore,
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
def quarter_score(game, steelers):
    return QuarterScore.objects.create(game=game, team=steelers, period=1, points=7)


@pytest.fixture
def drive1(game, steelers):
    return Drive.objects.create(
        game=game,
        sequence=1,
        team=steelers,
        yards_gained=75,
        plays_count=8,
        ended_description="Touchdown",
        time_of_possession="4:32",
    )


@pytest.fixture
def drive2(game, ravens):
    return Drive.objects.create(
        game=game,
        sequence=2,
        team=ravens,
        yards_gained=45,
        plays_count=6,
        ended_description="Punt",
        time_of_possession="3:15",
    )


@pytest.fixture
def replay(game):
    return GameReplay.objects.create(
        game=game,
        replay_type="highlight",
        sub_type="touchdown",
        title="Steelers TD",
        description="A 12-yard pass to the end zone",
        duration=45,
    )


# --- QuarterScore nested endpoint ---


@pytest.mark.django_db
def test_quarter_scores_list(client, game, quarter_score):
    """GET /api/v1/games/<id>/quarter-scores/ returns quarter scores for the game."""
    response = client.get(
        f"/api/v1/games/{game.pk}/quarter-scores/",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["period"] == 1
    assert data[0]["points"] == 7


@pytest.mark.django_db
def test_quarter_scores_scoped_to_game(
    client, game, other_game, quarter_score, steelers
):
    """Quarter scores endpoint only returns scores for the specified game."""
    QuarterScore.objects.create(game=other_game, team=steelers, period=1, points=10)
    response = client.get(
        f"/api/v1/games/{game.pk}/quarter-scores/",
        HTTP_ACCEPT="application/json",
    )
    assert len(response.json()) == 1


@pytest.mark.django_db
def test_quarter_scores_create(client, game, steelers):
    """POST /api/v1/games/<id>/quarter-scores/ creates a quarter score for the game."""
    response = client.post(
        f"/api/v1/games/{game.pk}/quarter-scores/",
        data={"team": steelers.pk, "period": 2, "points": 3},
        content_type="application/json",
    )
    assert response.status_code == 201
    assert QuarterScore.objects.filter(game=game, period=2).exists()


@pytest.mark.django_db
def test_quarter_scores_404_for_missing_game(client):
    """Accessing quarter scores for a non-existent game returns 404."""
    response = client.get(
        "/api/v1/games/99999/quarter-scores/", HTTP_ACCEPT="application/json"
    )
    assert response.status_code == 200
    assert len(response.json()) == 0


# --- Drive nested endpoint ---


@pytest.mark.django_db
def test_drives_list(client, game, drive1, drive2):
    """GET /api/v1/games/<id>/drives/ returns drives ordered by sequence."""
    response = client.get(
        f"/api/v1/games/{game.pk}/drives/", HTTP_ACCEPT="application/json"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["sequence"] == 1
    assert data[1]["sequence"] == 2


@pytest.mark.django_db
def test_drives_scoped_to_game(client, game, other_game, drive1, ravens):
    """Drives endpoint only returns drives for the specified game."""
    Drive.objects.create(game=other_game, sequence=1, team=ravens)
    response = client.get(
        f"/api/v1/games/{game.pk}/drives/", HTTP_ACCEPT="application/json"
    )
    assert len(response.json()) == 1


@pytest.mark.django_db
def test_drives_create(client, game, steelers):
    """POST /api/v1/games/<id>/drives/ creates a drive for the game."""
    response = client.post(
        f"/api/v1/games/{game.pk}/drives/",
        data={
            "sequence": 3,
            "team": steelers.pk,
            "yards_gained": 55,
            "plays_count": 7,
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    assert Drive.objects.filter(game=game, sequence=3).exists()


@pytest.mark.django_db
def test_drives_serializer_fields(client, game, drive1):
    """DriveSerializer includes expected fields."""
    response = client.get(
        f"/api/v1/games/{game.pk}/drives/", HTTP_ACCEPT="application/json"
    )
    data = response.json()[0]
    assert "id" in data
    assert "sequence" in data
    assert "team" in data
    assert "yards_gained" in data
    assert "plays_count" in data
    assert "ended_description" in data
    assert "time_of_possession" in data


# --- GameReplay nested endpoint ---


@pytest.mark.django_db
def test_replays_list(client, game, replay):
    """GET /api/v1/games/<id>/replays/ returns replays for the game."""
    response = client.get(
        f"/api/v1/games/{game.pk}/replays/", HTTP_ACCEPT="application/json"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Steelers TD"
    assert data[0]["sub_type"] == "touchdown"
    assert data[0]["duration"] == 45


@pytest.mark.django_db
def test_replays_scoped_to_game(client, game, other_game, replay):
    """Replays endpoint only returns replays for the specified game."""
    GameReplay.objects.create(game=other_game, title="Other Replay")
    response = client.get(
        f"/api/v1/games/{game.pk}/replays/", HTTP_ACCEPT="application/json"
    )
    assert len(response.json()) == 1


@pytest.mark.django_db
def test_replays_create(client, game):
    """POST /api/v1/games/<id>/replays/ creates a replay for the game."""
    response = client.post(
        f"/api/v1/games/{game.pk}/replays/",
        data={
            "replay_type": "highlight",
            "sub_type": "interception",
            "title": "Big INT",
            "duration": 30,
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    assert GameReplay.objects.filter(game=game, sub_type="interception").exists()


@pytest.mark.django_db
def test_replays_serializer_includes_all_fields(client, game, replay):
    """GameReplaySerializer includes all GameReplay fields."""
    response = client.get(
        f"/api/v1/games/{game.pk}/replays/", HTTP_ACCEPT="application/json"
    )
    data = response.json()[0]
    assert "id" in data
    assert "replay_type" in data
    assert "sub_type" in data
    assert "title" in data
    assert "description" in data
    assert "duration" in data
    assert "external_id" in data
    assert "mcp_playback_id" in data
    assert "publish_date" in data
    assert "thumbnail_url" in data
    assert "bonus_data" in data
    assert "external_ids" in data
