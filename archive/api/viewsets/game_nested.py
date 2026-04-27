from rest_framework.generics import get_object_or_404
from rest_framework.mixins import CreateModelMixin, ListModelMixin
from rest_framework.viewsets import GenericViewSet

from archive.api.serializers.game_nested import (
    DriveSerializer,
    DriveWriteSerializer,
    GameReplaySerializer,
    GameReplayWriteSerializer,
    QuarterScoreSerializer,
    QuarterScoreWriteSerializer,
)
from archive.models import Drive, Game, GameReplay, QuarterScore
from gam.auth.permissions import CatalogPermissionMixin


class GameNestedMixin(CatalogPermissionMixin):
    """Mixin that scopes querysets to the parent game from the URL."""

    pagination_class = None  # Nested endpoints return all results for a single game

    def get_game(self):
        return get_object_or_404(Game, pk=self.kwargs["game_pk"])

    def perform_create(self, serializer):
        serializer.save(game=self.get_game())


class GameQuarterScoreViewSet(
    GameNestedMixin, ListModelMixin, CreateModelMixin, GenericViewSet
):
    queryset = QuarterScore.objects.none()

    def get_queryset(self):
        return QuarterScore.objects.filter(
            game_id=self.kwargs["game_pk"]
        ).select_related("team")

    def get_serializer_class(self):
        if self.action == "create":
            return QuarterScoreWriteSerializer
        return QuarterScoreSerializer


class GameDriveViewSet(
    GameNestedMixin, ListModelMixin, CreateModelMixin, GenericViewSet
):
    queryset = Drive.objects.none()

    def get_queryset(self):
        return (
            Drive.objects.filter(game_id=self.kwargs["game_pk"])
            .select_related("team")
            .order_by("sequence")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return DriveWriteSerializer
        return DriveSerializer


class GameReplayViewSet(
    GameNestedMixin, ListModelMixin, CreateModelMixin, GenericViewSet
):
    queryset = GameReplay.objects.none()

    def get_queryset(self):
        return GameReplay.objects.filter(game_id=self.kwargs["game_pk"])

    def get_serializer_class(self):
        if self.action == "create":
            return GameReplayWriteSerializer
        return GameReplaySerializer
