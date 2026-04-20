from rest_framework.mixins import CreateModelMixin, ListModelMixin
from rest_framework.viewsets import GenericViewSet

from archive.api.serializers.boxscore import (
    FumblesBoxscoreSerializer,
    FumblesBoxscoreWriteSerializer,
    PassingBoxscoreSerializer,
    PassingBoxscoreWriteSerializer,
    ReceivingBoxscoreSerializer,
    ReceivingBoxscoreWriteSerializer,
    RushingBoxscoreSerializer,
    RushingBoxscoreWriteSerializer,
    TacklesBoxscoreSerializer,
    TacklesBoxscoreWriteSerializer,
)
from archive.api.viewsets.game_nested import GameNestedMixin
from archive.models import (
    FumblesBoxscore,
    PassingBoxscore,
    ReceivingBoxscore,
    RushingBoxscore,
    TacklesBoxscore,
)


class PassingBoxscoreViewSet(
    GameNestedMixin, ListModelMixin, CreateModelMixin, GenericViewSet
):
    def get_queryset(self):
        return PassingBoxscore.objects.filter(
            game_id=self.kwargs["game_pk"]
        ).select_related("team")

    def get_serializer_class(self):
        if self.action == "create":
            return PassingBoxscoreWriteSerializer
        return PassingBoxscoreSerializer


class RushingBoxscoreViewSet(
    GameNestedMixin, ListModelMixin, CreateModelMixin, GenericViewSet
):
    def get_queryset(self):
        return RushingBoxscore.objects.filter(
            game_id=self.kwargs["game_pk"]
        ).select_related("team")

    def get_serializer_class(self):
        if self.action == "create":
            return RushingBoxscoreWriteSerializer
        return RushingBoxscoreSerializer


class ReceivingBoxscoreViewSet(
    GameNestedMixin, ListModelMixin, CreateModelMixin, GenericViewSet
):
    def get_queryset(self):
        return ReceivingBoxscore.objects.filter(
            game_id=self.kwargs["game_pk"]
        ).select_related("team")

    def get_serializer_class(self):
        if self.action == "create":
            return ReceivingBoxscoreWriteSerializer
        return ReceivingBoxscoreSerializer


class TacklesBoxscoreViewSet(
    GameNestedMixin, ListModelMixin, CreateModelMixin, GenericViewSet
):
    def get_queryset(self):
        return TacklesBoxscore.objects.filter(
            game_id=self.kwargs["game_pk"]
        ).select_related("team")

    def get_serializer_class(self):
        if self.action == "create":
            return TacklesBoxscoreWriteSerializer
        return TacklesBoxscoreSerializer


class FumblesBoxscoreViewSet(
    GameNestedMixin, ListModelMixin, CreateModelMixin, GenericViewSet
):
    def get_queryset(self):
        return FumblesBoxscore.objects.filter(
            game_id=self.kwargs["game_pk"]
        ).select_related("team")

    def get_serializer_class(self):
        if self.action == "create":
            return FumblesBoxscoreWriteSerializer
        return FumblesBoxscoreSerializer
