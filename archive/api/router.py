from django.urls import path
from rest_framework.routers import DefaultRouter

from archive.api.viewsets.boxscore import (
    FumblesBoxscoreViewSet,
    PassingBoxscoreViewSet,
    ReceivingBoxscoreViewSet,
    RushingBoxscoreViewSet,
    TacklesBoxscoreViewSet,
)
from archive.api.viewsets.franchise import FranchiseViewSet
from archive.api.viewsets.game import GameViewSet
from archive.api.viewsets.game_nested import (
    GameDriveViewSet,
    GameQuarterScoreViewSet,
    GameReplayViewSet,
)
from archive.api.viewsets.league import LeagueViewSet
from archive.api.viewsets.org_unit import OrgUnitViewSet
from archive.api.viewsets.season import SeasonViewSet
from archive.api.viewsets.team import TeamViewSet
from archive.api.viewsets.team_affiliation import TeamAffiliationViewSet
from archive.api.viewsets.team_venue_occupancy import TeamVenueOccupancyViewSet
from archive.api.viewsets.venue import VenueViewSet

router = DefaultRouter()
router.register("leagues", LeagueViewSet, basename="league")
router.register("seasons", SeasonViewSet, basename="season")
router.register("franchises", FranchiseViewSet, basename="franchise")
router.register("teams", TeamViewSet, basename="team")
router.register("org-units", OrgUnitViewSet, basename="orgunit")
router.register("team-affiliations", TeamAffiliationViewSet, basename="teamaffiliation")
router.register("venues", VenueViewSet, basename="venue")
router.register(
    "team-venue-occupancies",
    TeamVenueOccupancyViewSet,
    basename="teamvenueoccupancy",
)
router.register("games", GameViewSet, basename="game")

game_nested_urls = [
    path(
        "games/<int:game_pk>/quarter-scores/",
        GameQuarterScoreViewSet.as_view({"get": "list", "post": "create"}),
        name="game-quarter-scores",
    ),
    path(
        "games/<int:game_pk>/drives/",
        GameDriveViewSet.as_view({"get": "list", "post": "create"}),
        name="game-drives",
    ),
    path(
        "games/<int:game_pk>/replays/",
        GameReplayViewSet.as_view({"get": "list", "post": "create"}),
        name="game-replays",
    ),
    path(
        "games/<int:game_pk>/boxscores/passing/",
        PassingBoxscoreViewSet.as_view({"get": "list", "post": "create"}),
        name="game-boxscores-passing",
    ),
    path(
        "games/<int:game_pk>/boxscores/rushing/",
        RushingBoxscoreViewSet.as_view({"get": "list", "post": "create"}),
        name="game-boxscores-rushing",
    ),
    path(
        "games/<int:game_pk>/boxscores/receiving/",
        ReceivingBoxscoreViewSet.as_view({"get": "list", "post": "create"}),
        name="game-boxscores-receiving",
    ),
    path(
        "games/<int:game_pk>/boxscores/tackles/",
        TacklesBoxscoreViewSet.as_view({"get": "list", "post": "create"}),
        name="game-boxscores-tackles",
    ),
    path(
        "games/<int:game_pk>/boxscores/fumbles/",
        FumblesBoxscoreViewSet.as_view({"get": "list", "post": "create"}),
        name="game-boxscores-fumbles",
    ),
]

urlpatterns = router.urls + game_nested_urls
