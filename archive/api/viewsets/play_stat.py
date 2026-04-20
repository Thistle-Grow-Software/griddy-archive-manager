from rest_framework.generics import get_object_or_404
from rest_framework.mixins import CreateModelMixin, ListModelMixin
from rest_framework.viewsets import GenericViewSet

from archive.api.serializers.play_stat import (
    PlayStatSerializer,
    PlayStatWriteSerializer,
)
from archive.models import Play, PlayStat


class PlayStatViewSet(ListModelMixin, CreateModelMixin, GenericViewSet):
    pagination_class = None

    def get_play(self):
        return get_object_or_404(Play, pk=self.kwargs["play_pk"])

    def get_queryset(self):
        return PlayStat.objects.filter(play_id=self.kwargs["play_pk"])

    def get_serializer_class(self):
        if self.action == "create":
            return PlayStatWriteSerializer
        return PlayStatSerializer

    def perform_create(self, serializer):
        serializer.save(play=self.get_play())
