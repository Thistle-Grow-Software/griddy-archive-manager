"""
Holdings, Standings, and Custom Action API integration tests using DRF's APIClient (TGF-310).

Tests for Source, Acquisition, VideoAsset, Tag, AssetTag, GameCompleteness,
TeamStandingsSnapshot, and all custom actions (full-boxscore, summary,
schedule, current-venue, preferred).
"""

import pytest
from rest_framework.test import APIClient

from archive.models import (
    Acquisition,
    AssetTag,
    Drive,
    Franchise,
    Game,
    GameCompleteness,
    League,
    PassingBoxscore,
    QuarterScore,
    RushingBoxscore,
    Season,
    Source,
    Tag,
    Team,
    TeamStandingsSnapshot,
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
def acrisure():
    return Venue.objects.create(
        name="Acrisure Stadium", city="Pittsburgh", state="PA", capacity=68400
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
def game2(nfl, season_2024, ravens, steelers, heinz_field):
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
def nfl_plus():
    return Source.objects.create(name="NFL+", source_type="STREAMING")


@pytest.fixture
def youtube():
    return Source.objects.create(name="YouTube", source_type="YOUTUBE")


@pytest.fixture
def acquisition(nfl_plus):
    return Acquisition.objects.create(
        source=nfl_plus, acquired_on="2024-09-01", rights="PERSONAL_ONLY"
    )


@pytest.fixture
def acquisition2(youtube):
    return Acquisition.objects.create(
        source=youtube, acquired_on="2024-09-15", rights="SHAREABLE"
    )


@pytest.fixture
def asset_preferred(game, acquisition):
    return VideoAsset.objects.create(
        game=game,
        acquisition=acquisition,
        file_path="/media/wk1_full.mkv",
        asset_type="FULL",
        quality_tier="A",
        is_preferred=True,
        quality_notes="Excellent HD quality",
    )


@pytest.fixture
def asset_condensed(game):
    return VideoAsset.objects.create(
        game=game,
        file_path="/media/wk1_condensed.mp4",
        asset_type="CONDENSED",
        quality_tier="B",
        is_preferred=False,
    )


@pytest.fixture
def tag_hd():
    return Tag.objects.create(name="HD")


@pytest.fixture
def tag_fav():
    return Tag.objects.create(name="Favorite")


@pytest.fixture
def asset_tag(asset_preferred, tag_hd):
    return AssetTag.objects.create(asset=asset_preferred, tag=tag_hd)


@pytest.fixture
def completeness(game):
    return GameCompleteness.objects.create(
        game=game, scope="NFL_ALL", status="COMPLETE", has_full=True, has_condensed=True
    )


@pytest.fixture
def completeness_partial(game):
    return GameCompleteness.objects.create(
        game=game,
        scope="STEELERS_ALL",
        status="PARTIAL",
        has_full=True,
        has_condensed=False,
    )


@pytest.fixture
def snapshot(steelers, season_2024):
    return TeamStandingsSnapshot.objects.create(
        team=steelers,
        season=season_2024,
        week=1,
        overall_wins=1,
        overall_losses=0,
        overall_win_pct=1.0,
    )


@pytest.fixture
def snapshot_wk2(steelers, season_2024):
    return TeamStandingsSnapshot.objects.create(
        team=steelers,
        season=season_2024,
        week=2,
        overall_wins=2,
        overall_losses=0,
        overall_win_pct=1.0,
    )


# ===========================================================================
# Source ViewSet
# ===========================================================================


@pytest.mark.django_db
class TestSourceViewSet:
    def test_list(self, api_client, nfl_plus):
        assert api_client.get("/api/v1/sources/").status_code == 200

    def test_create(self, api_client):
        r = api_client.post(
            "/api/v1/sources/", {"name": "Paramount+", "source_type": "STREAMING"}
        )
        assert r.status_code == 201

    def test_retrieve(self, api_client, nfl_plus):
        r = api_client.get(f"/api/v1/sources/{nfl_plus.pk}/")
        assert r.data["name"] == "NFL+"

    def test_update(self, api_client, nfl_plus):
        r = api_client.put(
            f"/api/v1/sources/{nfl_plus.pk}/",
            {"name": "NFL+ Premium", "source_type": "STREAMING"},
        )
        assert r.status_code == 200

    def test_delete(self, api_client, nfl_plus):
        assert api_client.delete(f"/api/v1/sources/{nfl_plus.pk}/").status_code == 204


# ===========================================================================
# Acquisition ViewSet
# ===========================================================================


@pytest.mark.django_db
class TestAcquisitionViewSet:
    def test_list(self, api_client, acquisition):
        assert api_client.get("/api/v1/acquisitions/").status_code == 200

    def test_create(self, api_client, nfl_plus):
        r = api_client.post(
            "/api/v1/acquisitions/",
            {
                "source": nfl_plus.pk,
                "acquired_on": "2024-10-01",
                "rights": "PERSONAL_ONLY",
            },
        )
        assert r.status_code == 201

    def test_delete(self, api_client, acquisition):
        assert (
            api_client.delete(f"/api/v1/acquisitions/{acquisition.pk}/").status_code
            == 204
        )

    def test_filter_by_source(self, api_client, acquisition, acquisition2, nfl_plus):
        r = api_client.get(f"/api/v1/acquisitions/?source={nfl_plus.pk}")
        assert len(r.data["results"]) == 1

    def test_filter_by_rights(self, api_client, acquisition, acquisition2):
        r = api_client.get("/api/v1/acquisitions/?rights=SHAREABLE")
        assert len(r.data["results"]) == 1


# ===========================================================================
# VideoAsset ViewSet
# ===========================================================================


@pytest.mark.django_db
class TestVideoAssetViewSet:
    def test_list(self, api_client, asset_preferred):
        assert api_client.get("/api/v1/video-assets/").status_code == 200

    def test_create(self, api_client, game):
        r = api_client.post(
            "/api/v1/video-assets/",
            {
                "game": game.pk,
                "file_path": "/new.mkv",
                "asset_type": "ALL22",
                "quality_tier": "B",
            },
        )
        assert r.status_code == 201

    def test_retrieve(self, api_client, asset_preferred):
        r = api_client.get(f"/api/v1/video-assets/{asset_preferred.pk}/")
        assert r.data["file_path"] == "/media/wk1_full.mkv"

    def test_delete(self, api_client, asset_condensed):
        assert (
            api_client.delete(f"/api/v1/video-assets/{asset_condensed.pk}/").status_code
            == 204
        )

    def test_filter_by_game(self, api_client, asset_preferred, game):
        r = api_client.get(f"/api/v1/video-assets/?game={game.pk}")
        assert all(a["game"] == game.pk for a in r.data["results"])

    def test_filter_by_asset_type(self, api_client, asset_preferred, asset_condensed):
        r = api_client.get("/api/v1/video-assets/?asset_type=FULL")
        assert len(r.data["results"]) == 1

    def test_filter_by_quality_tier(self, api_client, asset_preferred, asset_condensed):
        r = api_client.get("/api/v1/video-assets/?quality_tier=A")
        assert len(r.data["results"]) == 1

    def test_filter_by_is_preferred(self, api_client, asset_preferred, asset_condensed):
        r = api_client.get("/api/v1/video-assets/?is_preferred=true")
        assert len(r.data["results"]) == 1

    def test_search_file_path(self, api_client, asset_preferred, asset_condensed):
        r = api_client.get("/api/v1/video-assets/?search=condensed")
        assert len(r.data["results"]) == 1

    def test_search_quality_notes(self, api_client, asset_preferred, asset_condensed):
        r = api_client.get("/api/v1/video-assets/?search=Excellent")
        assert len(r.data["results"]) == 1


# ===========================================================================
# Tag and AssetTag ViewSets
# ===========================================================================


@pytest.mark.django_db
class TestTagViewSet:
    def test_crud(self, api_client, tag_hd):
        assert api_client.get("/api/v1/tags/").status_code == 200
        assert api_client.post("/api/v1/tags/", {"name": "4K"}).status_code == 201
        assert (
            api_client.put(
                f"/api/v1/tags/{tag_hd.pk}/", {"name": "HD 1080p"}
            ).status_code
            == 200
        )
        assert api_client.delete(f"/api/v1/tags/{tag_hd.pk}/").status_code == 204


@pytest.mark.django_db
class TestAssetTagViewSet:
    def test_list(self, api_client, asset_tag):
        r = api_client.get("/api/v1/asset-tags/")
        assert len(r.data["results"]) == 1

    def test_create(self, api_client, asset_preferred, tag_fav):
        r = api_client.post(
            "/api/v1/asset-tags/", {"asset": asset_preferred.pk, "tag": tag_fav.pk}
        )
        assert r.status_code == 201

    def test_delete(self, api_client, asset_tag):
        assert (
            api_client.delete(f"/api/v1/asset-tags/{asset_tag.pk}/").status_code == 204
        )


# ===========================================================================
# GameCompleteness ViewSet
# ===========================================================================


@pytest.mark.django_db
class TestGameCompletenessViewSet:
    def test_list(self, api_client, completeness):
        assert api_client.get("/api/v1/game-completeness/").status_code == 200

    def test_create(self, api_client, game):
        r = api_client.post(
            "/api/v1/game-completeness/",
            {"game": game.pk, "scope": "UGA_ALL", "status": "MISSING"},
        )
        assert r.status_code == 201

    def test_retrieve(self, api_client, completeness):
        r = api_client.get(f"/api/v1/game-completeness/{completeness.pk}/")
        assert r.data["scope"] == "NFL_ALL"

    def test_update(self, api_client, completeness, game):
        r = api_client.put(
            f"/api/v1/game-completeness/{completeness.pk}/",
            {"game": game.pk, "scope": "NFL_ALL", "status": "COMPLETE_NEEDS_UPGRADE"},
        )
        assert r.status_code == 200

    def test_filter_scope(self, api_client, completeness, completeness_partial):
        r = api_client.get("/api/v1/game-completeness/?scope=NFL_ALL")
        assert len(r.data["results"]) == 1

    def test_filter_status(self, api_client, completeness, completeness_partial):
        r = api_client.get("/api/v1/game-completeness/?status=PARTIAL")
        assert len(r.data["results"]) == 1

    def test_filter_has_full(self, api_client, completeness, completeness_partial):
        r = api_client.get("/api/v1/game-completeness/?has_full=true")
        assert len(r.data["results"]) == 2

    def test_filter_has_condensed(self, api_client, completeness, completeness_partial):
        r = api_client.get("/api/v1/game-completeness/?has_condensed=true")
        assert len(r.data["results"]) == 1

    def test_filter_has_all22(self, api_client, completeness, completeness_partial):
        r = api_client.get("/api/v1/game-completeness/?has_all22=false")
        assert len(r.data["results"]) == 2


# ===========================================================================
# TeamStandingsSnapshot ViewSet
# ===========================================================================


@pytest.mark.django_db
class TestStandingsViewSet:
    def test_list(self, api_client, snapshot):
        assert api_client.get("/api/v1/standings/").status_code == 200

    def test_create(self, api_client, steelers, season_2024):
        r = api_client.post(
            "/api/v1/standings/",
            {
                "team": steelers.pk,
                "season": season_2024.pk,
                "week": 3,
                "overall_wins": 3,
                "overall_losses": 0,
                "overall_win_pct": 1.0,
            },
        )
        assert r.status_code == 201

    def test_retrieve(self, api_client, snapshot):
        r = api_client.get(f"/api/v1/standings/{snapshot.pk}/")
        assert r.data["week"] == 1

    def test_filter_by_team(self, api_client, snapshot, ravens, season_2024):
        TeamStandingsSnapshot.objects.create(
            team=ravens, season=season_2024, week=1, overall_wins=0, overall_losses=1
        )
        r = api_client.get(f"/api/v1/standings/?team={snapshot.team_id}")
        assert all(s["team"] == snapshot.team_id for s in r.data["results"])

    def test_filter_by_season_year(self, api_client, snapshot, season_2023, steelers):
        TeamStandingsSnapshot.objects.create(team=steelers, season=season_2023, week=1)
        r = api_client.get("/api/v1/standings/?season_year=2024")
        assert len(r.data["results"]) == 1

    def test_filter_by_week(self, api_client, snapshot, snapshot_wk2):
        r = api_client.get("/api/v1/standings/?week=1")
        assert len(r.data["results"]) == 1


# ===========================================================================
# Custom Actions
# ===========================================================================


@pytest.mark.django_db
class TestFullBoxscoreAction:
    def test_returns_all_10_categories(self, api_client, game):
        r = api_client.get(f"/api/v1/games/{game.pk}/full-boxscore/")
        assert r.status_code == 200
        expected = {
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
        assert set(r.data.keys()) == expected

    def test_includes_stats(self, api_client, game, steelers):
        PassingBoxscore.objects.create(
            game=game,
            team=steelers,
            side="home",
            player_name="QB",
            position="QB",
            attempts=20,
            yards=200,
        )
        RushingBoxscore.objects.create(
            game=game,
            team=steelers,
            side="home",
            player_name="RB",
            position="RB",
            attempts=15,
            yards=80,
        )
        r = api_client.get(f"/api/v1/games/{game.pk}/full-boxscore/")
        assert len(r.data["passing"]) == 1
        assert len(r.data["rushing"]) == 1


@pytest.mark.django_db
class TestGameSummaryAction:
    def test_returns_game_card(self, api_client, game, steelers, ravens):
        QuarterScore.objects.create(game=game, team=steelers, period=1, points=7)
        Drive.objects.create(
            game=game, sequence=1, team=steelers, yards_gained=75, ended_with_score=True
        )
        r = api_client.get(f"/api/v1/games/{game.pk}/summary/")
        assert r.status_code == 200
        assert r.data["home_team"]["short_name"] == "PIT"
        assert r.data["away_team"]["short_name"] == "BAL"
        assert r.data["final_home_score"] == 24
        assert len(r.data["quarter_scores"]) == 1
        assert r.data["drives"]["total_drives"] == 1
        assert r.data["drives"]["scoring_drives"] == 1


@pytest.mark.django_db
class TestTeamScheduleAction:
    def test_returns_games(self, api_client, steelers, game, game2):
        r = api_client.get(f"/api/v1/teams/{steelers.pk}/schedule/?season_year=2024")
        assert r.status_code == 200
        assert len(r.data) == 2

    def test_ordered_by_date(self, api_client, steelers, game, game2):
        r = api_client.get(f"/api/v1/teams/{steelers.pk}/schedule/?season_year=2024")
        assert r.data[0]["date_local"] <= r.data[1]["date_local"]

    def test_400_without_season_year(self, api_client, steelers):
        r = api_client.get(f"/api/v1/teams/{steelers.pk}/schedule/")
        assert r.status_code == 400


@pytest.mark.django_db
class TestTeamCurrentVenueAction:
    def test_returns_venue(self, api_client, steelers, acrisure):
        TeamVenueOccupancy.objects.create(
            team=steelers, venue=acrisure, start_date="2022-03-01"
        )
        r = api_client.get(f"/api/v1/teams/{steelers.pk}/current-venue/")
        assert r.status_code == 200
        assert r.data["name"] == "Acrisure Stadium"

    def test_404_no_occupancy(self, api_client, steelers):
        r = api_client.get(f"/api/v1/teams/{steelers.pk}/current-venue/")
        assert r.status_code == 404


@pytest.mark.django_db
class TestVideoAssetPreferredAction:
    def test_returns_preferred_only(self, api_client, asset_preferred, asset_condensed):
        r = api_client.get("/api/v1/video-assets/preferred/")
        assert len(r.data["results"]) == 1
        assert r.data["results"][0]["is_preferred"] is True

    def test_filter_by_season_year(self, api_client, asset_preferred):
        r = api_client.get("/api/v1/video-assets/preferred/?season_year=2024")
        assert len(r.data["results"]) == 1

    def test_empty_without_preferred(self, api_client, asset_condensed):
        r = api_client.get("/api/v1/video-assets/preferred/")
        assert len(r.data["results"]) == 0
