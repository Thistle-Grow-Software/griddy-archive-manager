from django.db.models import Count, Q, Sum
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.mixins import (
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from archive.api.filters import GameFilter
from archive.api.pagination import GamePagination
from archive.api.serializers.game import (
    GameDetailSerializer,
    GameListSerializer,
    GameWriteSerializer,
)
from archive.api.serializers.game_actions import (
    FullBoxscoreSerializer,
    GameSummarySerializer,
)
from archive.models import (
    ExtraPointsBoxscore,
    FieldGoalsBoxscore,
    FumblesBoxscore,
    Game,
    KickingBoxscore,
    PassingBoxscore,
    PuntingBoxscore,
    ReceivingBoxscore,
    ReturnBoxscore,
    RushingBoxscore,
    TacklesBoxscore,
)
from gam.auth.permissions import CatalogPermissionMixin


class GameViewSet(
    CatalogPermissionMixin,
    ListModelMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    GenericViewSet,
):
    pagination_class = GamePagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = GameFilter
    search_fields = ["competition_name", "notes"]
    ordering_fields = ["date_local", "week", "final_home_score", "final_away_score"]

    def get_queryset(self):
        qs = Game.objects.select_related(
            "league", "season", "venue", "home_team", "away_team"
        ).prefetch_related("quarter_scores", "completeness")
        if self.action == "retrieve":
            qs = qs.annotate(asset_count=Count("assets"))
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return GameListSerializer
        if self.action == "retrieve":
            return GameDetailSerializer
        if self.action == "full_boxscore":
            return FullBoxscoreSerializer
        if self.action == "summary":
            return GameSummarySerializer
        return GameWriteSerializer

    @action(detail=True, methods=["get"], url_path="full-boxscore")
    def full_boxscore(self, request, pk=None):
        game = self.get_object()
        team_select = ["team"]
        data = {
            "passing": PassingBoxscore.objects.filter(game=game).select_related(
                *team_select
            ),
            "rushing": RushingBoxscore.objects.filter(game=game).select_related(
                *team_select
            ),
            "receiving": ReceivingBoxscore.objects.filter(game=game).select_related(
                *team_select
            ),
            "tackles": TacklesBoxscore.objects.filter(game=game).select_related(
                *team_select
            ),
            "fumbles": FumblesBoxscore.objects.filter(game=game).select_related(
                *team_select
            ),
            "field_goals": FieldGoalsBoxscore.objects.filter(game=game).select_related(
                *team_select
            ),
            "extra_points": ExtraPointsBoxscore.objects.filter(
                game=game
            ).select_related(*team_select),
            "kicking": KickingBoxscore.objects.filter(game=game).select_related(
                *team_select
            ),
            "punting": PuntingBoxscore.objects.filter(game=game).select_related(
                *team_select
            ),
            "returns": ReturnBoxscore.objects.filter(game=game).select_related(
                *team_select
            ),
        }
        serializer = FullBoxscoreSerializer(data)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        game = (
            Game.objects.select_related("home_team", "away_team")
            .prefetch_related("quarter_scores", "drives")
            .get(pk=pk)
        )
        drive_agg = game.drives.aggregate(
            total_drives=Count("id"),
            scoring_drives=Count("id", filter=Q(ended_with_score=True)),
            total_yards=Sum("yards_gained"),
        )
        data = {
            "id": game.id,
            "date_local": game.date_local,
            "home_team": game.home_team,
            "away_team": game.away_team,
            "final_home_score": game.final_home_score,
            "final_away_score": game.final_away_score,
            "quarter_scores": game.quarter_scores.all(),
            "drives": {
                "total_drives": drive_agg["total_drives"] or 0,
                "scoring_drives": drive_agg["scoring_drives"] or 0,
                "total_yards": drive_agg["total_yards"] or 0,
            },
        }
        serializer = GameSummarySerializer(data)
        return Response(serializer.data)
