import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from rest_framework.mixins import CreateModelMixin, ListModelMixin, RetrieveModelMixin
from rest_framework.viewsets import GenericViewSet

from archive.api.pagination import DefaultCursorPagination
from archive.api.serializers.standings import (
    TeamStandingsSnapshotDetailSerializer,
    TeamStandingsSnapshotListSerializer,
    TeamStandingsSnapshotWriteSerializer,
)
from archive.models import TeamStandingsSnapshot


class StandingsFilter(django_filters.FilterSet):
    season_year = django_filters.NumberFilter(field_name="season__year")

    class Meta:
        model = TeamStandingsSnapshot
        fields = ["team", "week"]


class TeamStandingsSnapshotViewSet(
    ListModelMixin, CreateModelMixin, RetrieveModelMixin, GenericViewSet
):
    pagination_class = DefaultCursorPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = StandingsFilter
    ordering_fields = ["week", "overall_wins", "overall_win_pct", "points_for"]
    ordering = ["week"]

    def get_queryset(self):
        return TeamStandingsSnapshot.objects.select_related("team", "season").all()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return TeamStandingsSnapshotDetailSerializer
        if self.action == "create":
            return TeamStandingsSnapshotWriteSerializer
        return TeamStandingsSnapshotListSerializer
