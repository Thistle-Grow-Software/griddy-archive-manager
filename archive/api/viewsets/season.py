from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.mixins import (
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework.viewsets import GenericViewSet

from archive.api.pagination import DefaultCursorPagination
from archive.api.serializers.season import (
    SeasonDetailSerializer,
    SeasonListSerializer,
    SeasonWriteSerializer,
)
from archive.models import Season


class SeasonViewSet(
    ListModelMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    GenericViewSet,
):
    pagination_class = DefaultCursorPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["league", "year"]

    def get_queryset(self):
        return Season.objects.select_related("league").all()

    def get_serializer_class(self):
        if self.action == "list":
            return SeasonListSerializer
        if self.action == "retrieve":
            return SeasonDetailSerializer
        return SeasonWriteSerializer
