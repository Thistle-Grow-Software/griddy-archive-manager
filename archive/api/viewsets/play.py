from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from rest_framework.generics import get_object_or_404
from rest_framework.mixins import (
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
)
from rest_framework.viewsets import GenericViewSet

from archive.api.pagination import PlayPagination
from archive.api.serializers.play import (
    PlayDetailSerializer,
    PlayListSerializer,
    PlayWriteSerializer,
)
from archive.models import Game, Play


class GamePlayViewSet(
    ListModelMixin, CreateModelMixin, RetrieveModelMixin, GenericViewSet
):
    queryset = Play.objects.none()
    pagination_class = PlayPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["quarter", "play_type", "is_scoring", "possession_team"]
    ordering_fields = ["sequence", "quarter"]

    def get_game(self):
        return get_object_or_404(Game, pk=self.kwargs["game_pk"])

    def get_queryset(self):
        return (
            Play.objects.filter(game_id=self.kwargs["game_pk"])
            .select_related("possession_team")
            .prefetch_related("stats")
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PlayDetailSerializer
        if self.action == "create":
            return PlayWriteSerializer
        return PlayListSerializer

    def perform_create(self, serializer):
        serializer.save(game=self.get_game())
