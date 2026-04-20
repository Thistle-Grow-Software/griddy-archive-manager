from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.mixins import (
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework.viewsets import GenericViewSet

from archive.api.filters import GameFilter
from archive.api.pagination import GamePagination
from archive.api.serializers.game import (
    GameDetailSerializer,
    GameListSerializer,
    GameWriteSerializer,
)
from archive.models import Game


class GameViewSet(
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
        return GameWriteSerializer
