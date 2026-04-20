from django.db.models import Count
from rest_framework.mixins import (
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework.viewsets import GenericViewSet

from archive.api.pagination import DefaultCursorPagination
from archive.api.serializers.league import (
    LeagueDetailSerializer,
    LeagueListSerializer,
    LeagueWriteSerializer,
)
from archive.models import League


class LeagueViewSet(
    ListModelMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    GenericViewSet,
):
    pagination_class = DefaultCursorPagination

    def get_queryset(self):
        qs = League.objects.all()
        if self.action == "list":
            qs = qs.annotate(seasons_count=Count("seasons"))
        elif self.action == "retrieve":
            qs = qs.prefetch_related("seasons")
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return LeagueListSerializer
        if self.action == "retrieve":
            return LeagueDetailSerializer
        return LeagueWriteSerializer
