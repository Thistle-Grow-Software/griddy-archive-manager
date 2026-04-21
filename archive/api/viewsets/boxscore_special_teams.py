from rest_framework.mixins import CreateModelMixin, ListModelMixin
from rest_framework.viewsets import GenericViewSet

from archive.api.serializers.boxscore_special_teams import (
    ExtraPointsBoxscoreSerializer,
    ExtraPointsBoxscoreWriteSerializer,
    FieldGoalsBoxscoreSerializer,
    FieldGoalsBoxscoreWriteSerializer,
    KickingBoxscoreSerializer,
    KickingBoxscoreWriteSerializer,
    PuntingBoxscoreSerializer,
    PuntingBoxscoreWriteSerializer,
    ReturnBoxscoreSerializer,
    ReturnBoxscoreWriteSerializer,
)
from archive.api.viewsets.game_nested import GameNestedMixin
from archive.models import (
    ExtraPointsBoxscore,
    FieldGoalsBoxscore,
    KickingBoxscore,
    PuntingBoxscore,
    ReturnBoxscore,
)


class FieldGoalsBoxscoreViewSet(
    GameNestedMixin, ListModelMixin, CreateModelMixin, GenericViewSet
):
    queryset = FieldGoalsBoxscore.objects.none()

    def get_queryset(self):
        return FieldGoalsBoxscore.objects.filter(
            game_id=self.kwargs["game_pk"]
        ).select_related("team")

    def get_serializer_class(self):
        if self.action == "create":
            return FieldGoalsBoxscoreWriteSerializer
        return FieldGoalsBoxscoreSerializer


class ExtraPointsBoxscoreViewSet(
    GameNestedMixin, ListModelMixin, CreateModelMixin, GenericViewSet
):
    queryset = ExtraPointsBoxscore.objects.none()

    def get_queryset(self):
        return ExtraPointsBoxscore.objects.filter(
            game_id=self.kwargs["game_pk"]
        ).select_related("team")

    def get_serializer_class(self):
        if self.action == "create":
            return ExtraPointsBoxscoreWriteSerializer
        return ExtraPointsBoxscoreSerializer


class KickingBoxscoreViewSet(
    GameNestedMixin, ListModelMixin, CreateModelMixin, GenericViewSet
):
    queryset = KickingBoxscore.objects.none()

    def get_queryset(self):
        return KickingBoxscore.objects.filter(
            game_id=self.kwargs["game_pk"]
        ).select_related("team")

    def get_serializer_class(self):
        if self.action == "create":
            return KickingBoxscoreWriteSerializer
        return KickingBoxscoreSerializer


class PuntingBoxscoreViewSet(
    GameNestedMixin, ListModelMixin, CreateModelMixin, GenericViewSet
):
    queryset = PuntingBoxscore.objects.none()

    def get_queryset(self):
        return PuntingBoxscore.objects.filter(
            game_id=self.kwargs["game_pk"]
        ).select_related("team")

    def get_serializer_class(self):
        if self.action == "create":
            return PuntingBoxscoreWriteSerializer
        return PuntingBoxscoreSerializer


class ReturnBoxscoreViewSet(
    GameNestedMixin, ListModelMixin, CreateModelMixin, GenericViewSet
):
    queryset = ReturnBoxscore.objects.none()

    def get_queryset(self):
        return ReturnBoxscore.objects.filter(
            game_id=self.kwargs["game_pk"]
        ).select_related("team")

    def get_serializer_class(self):
        if self.action == "create":
            return ReturnBoxscoreWriteSerializer
        return ReturnBoxscoreSerializer
