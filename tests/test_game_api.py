"""Tests for Game serializers and viewset with filters (TGF-293)."""

import pytest
from django.test import Client
from django.urls import reverse

from archive.api.serializers.game import GameDetailSerializer, GameListSerializer
from archive.models import (
    Acquisition,
    Franchise,
    Game,
    GameCompleteness,
    League,
    QuarterScore,
    Season,
    Source,
    Team,
    Venue,
    VideoAsset,
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
def season_2023(nfl):
    return Season.objects.create(league=nfl, year=2023, label="2023")


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
def game_week1(nfl, season_2024, steelers, ravens, heinz_field):
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
def game_week2(nfl, season_2024, ravens, steelers, heinz_field):
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
def quarter_scores(game_week1, steelers, ravens):
    return [
        QuarterScore.objects.create(game=game_week1, team=steelers, period=1, points=7),
        QuarterScore.objects.create(game=game_week1, team=steelers, period=2, points=3),
        QuarterScore.objects.create(game=game_week1, team=ravens, period=1, points=14),
        QuarterScore.objects.create(game=game_week1, team=ravens, period=2, points=7),
    ]


@pytest.fixture
def completeness(game_week1):
    return GameCompleteness.objects.create(
        game=game_week1, scope="NFL_ALL", status="COMPLETE"
    )


@pytest.fixture
def source():
    return Source.objects.create(name="NFL+", source_type="STREAMING")


@pytest.fixture
def acquisition(source):
    return Acquisition.objects.create(source=source)


@pytest.fixture
def asset(game_week1, acquisition):
    return VideoAsset.objects.create(
        game=game_week1,
        acquisition=acquisition,
        file_path="/media/games/week1.mkv",
        asset_type="FULL",
    )


# --- GameListSerializer ---


@pytest.mark.django_db
def test_game_list_serializer_fields(game_week1, steelers, ravens, heinz_field):
    """GameListSerializer includes expected fields with nested team and venue references."""
    game = Game.objects.select_related("home_team", "away_team", "venue").get(
        pk=game_week1.pk
    )
    serializer = GameListSerializer(game)
    data = serializer.data
    assert data["id"] == game_week1.pk
    assert data["date_local"] == "2024-09-08"
    assert data["week"] == 1
    assert data["game_type"] == "REG"
    assert data["home_team"]["short_name"] == "PIT"
    assert data["away_team"]["short_name"] == "BAL"
    assert data["venue"]["name"] == "Heinz Field"
    assert data["final_home_score"] == 18
    assert data["final_away_score"] == 21
    assert data["broadcast_channel"] == "CBS"
    assert data["status"] == "Final"


# --- GameDetailSerializer ---


@pytest.mark.django_db
def test_game_detail_serializer_all_fields(
    game_week1, quarter_scores, completeness, asset
):
    """GameDetailSerializer includes all fields plus quarter_scores, completeness, asset_count."""
    from django.db.models import Count

    game = (
        Game.objects.select_related(
            "league", "season", "venue", "home_team", "away_team"
        )
        .prefetch_related("quarter_scores", "completeness")
        .annotate(asset_count=Count("assets"))
        .get(pk=game_week1.pk)
    )
    serializer = GameDetailSerializer(game)
    data = serializer.data
    assert data["date_local"] == "2024-09-08"
    assert "league" in data
    assert "season" in data
    assert "notes" in data
    assert "bonus_data" in data
    assert "external_ids" in data
    assert len(data["quarter_scores"]) == 4
    assert len(data["completeness"]) == 1
    assert data["asset_count"] == 1


# --- GameWriteSerializer ---


@pytest.mark.django_db
def test_game_write_serializer_accepts_pks(
    nfl, season_2024, steelers, ravens, heinz_field
):
    """GameWriteSerializer accepts integer PKs for all FK fields."""
    from archive.api.serializers.game import GameWriteSerializer

    serializer = GameWriteSerializer(
        data={
            "league": nfl.pk,
            "season": season_2024.pk,
            "date_local": "2024-12-25",
            "home_team": steelers.pk,
            "away_team": ravens.pk,
            "venue": heinz_field.pk,
        }
    )
    assert serializer.is_valid(), serializer.errors
    game = serializer.save()
    assert game.pk is not None
    assert game.home_team == steelers


# --- GameViewSet endpoints ---


@pytest.mark.django_db
def test_game_list_returns_200(client, game_week1):
    """GET /api/v1/games/ returns 200 with paginated results."""
    response = client.get("/api/v1/games/", HTTP_ACCEPT="application/json")
    assert response.status_code == 200
    assert "results" in response.json()


@pytest.mark.django_db
def test_game_list_uses_game_pagination(client, game_week1, game_week2):
    """Game list is paginated using GamePagination (cursor by -date_local)."""
    response = client.get("/api/v1/games/", HTTP_ACCEPT="application/json")
    results = response.json()["results"]
    # -date_local ordering: week2 (2024-09-15) comes before week1 (2024-09-08)
    assert results[0]["date_local"] == "2024-09-15"
    assert results[1]["date_local"] == "2024-09-08"


@pytest.mark.django_db
def test_game_retrieve_with_detail(client, game_week1, quarter_scores, completeness):
    """GET /api/v1/games/<id>/ returns detail with quarter_scores, completeness, asset_count."""
    response = client.get(
        f"/api/v1/games/{game_week1.pk}/", HTTP_ACCEPT="application/json"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["quarter_scores"]) == 4
    assert len(data["completeness"]) == 1
    assert data["asset_count"] == 0  # no assets for this test


@pytest.mark.django_db
def test_game_create(client, nfl, season_2024, steelers, ravens):
    """POST /api/v1/games/ creates a game."""
    response = client.post(
        "/api/v1/games/",
        data={
            "league": nfl.pk,
            "season": season_2024.pk,
            "date_local": "2024-12-25",
            "home_team": steelers.pk,
            "away_team": ravens.pk,
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    assert Game.objects.filter(date_local="2024-12-25").exists()


@pytest.mark.django_db
def test_game_update(client, game_week1, nfl, season_2024, steelers, ravens):
    """PUT /api/v1/games/<id>/ updates the game."""
    response = client.put(
        f"/api/v1/games/{game_week1.pk}/",
        data={
            "league": nfl.pk,
            "season": season_2024.pk,
            "date_local": "2024-09-08",
            "home_team": steelers.pk,
            "away_team": ravens.pk,
            "final_home_score": 24,
            "final_away_score": 21,
            "notes": "Updated score",
        },
        content_type="application/json",
    )
    assert response.status_code == 200
    game_week1.refresh_from_db()
    assert game_week1.final_home_score == 24


@pytest.mark.django_db
def test_game_delete_not_allowed(client, game_week1):
    """DELETE /api/v1/games/<id>/ is not supported."""
    response = client.delete(f"/api/v1/games/{game_week1.pk}/")
    assert response.status_code == 405


# --- GameFilter ---


@pytest.mark.django_db
def test_filter_by_season_year(
    client, game_week1, game_week2, season_2023, nfl, steelers, ravens
):
    """?season_year=2023 returns only 2023 season games."""
    Game.objects.create(
        league=nfl,
        season=season_2023,
        date_local="2023-09-10",
        week=1,
        home_team=steelers,
        away_team=ravens,
    )
    response = client.get(
        "/api/v1/games/?season_year=2023", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["date_local"] == "2023-09-10"


@pytest.mark.django_db
def test_filter_by_league(client, nfl, game_week1):
    """?league=<id> filters by league."""
    response = client.get(
        f"/api/v1/games/?league={nfl.pk}", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) >= 1


@pytest.mark.django_db
def test_filter_by_team_home_or_away(client, steelers, game_week1, game_week2):
    """?team=<id> finds games where team is home OR away."""
    response = client.get(
        f"/api/v1/games/?team={steelers.pk}", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    # steelers is home in week1, away in week2
    assert len(results) == 2


@pytest.mark.django_db
def test_filter_by_game_type(client, game_week1, playoff_game):
    """?game_type=POST returns only postseason games."""
    response = client.get(
        "/api/v1/games/?game_type=POST", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["game_type"] == "POST"


@pytest.mark.django_db
def test_filter_by_week(client, game_week1, game_week2):
    """?week=1 returns only week 1 games."""
    response = client.get("/api/v1/games/?week=1", HTTP_ACCEPT="application/json")
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["week"] == 1


@pytest.mark.django_db
def test_filter_by_date_range(client, game_week1, game_week2):
    """?date_from=...&date_to=... filters by date range."""
    response = client.get(
        "/api/v1/games/?date_from=2024-09-10&date_to=2024-09-20",
        HTTP_ACCEPT="application/json",
    )
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["date_local"] == "2024-09-15"


@pytest.mark.django_db
def test_filter_has_assets_true(client, game_week1, game_week2, asset):
    """?has_assets=true returns only games with assets."""
    response = client.get(
        "/api/v1/games/?has_assets=true", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 1


@pytest.mark.django_db
def test_filter_has_assets_false(client, game_week1, game_week2, asset):
    """?has_assets=false returns only games without assets."""
    response = client.get(
        "/api/v1/games/?has_assets=false", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 1


# --- Search ---


@pytest.mark.django_db
def test_search_by_competition_name(client, game_week1, playoff_game):
    """?search=Wild Card finds by competition_name."""
    response = client.get(
        "/api/v1/games/?search=Wild+Card", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 1


# --- Ordering ---


@pytest.mark.django_db
def test_ordering_by_week(client, game_week1, game_week2):
    """?ordering=week orders ascending by week."""
    response = client.get(
        "/api/v1/games/?ordering=week", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert results[0]["week"] <= results[1]["week"]


# --- Router registration ---


@pytest.mark.django_db
def test_games_registered_on_router():
    """GameViewSet must be registered at /games/."""
    url = reverse("game-list")
    assert url == "/api/v1/games/"
