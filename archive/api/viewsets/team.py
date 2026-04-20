from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from rest_framework.mixins import (
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework.viewsets import GenericViewSet

from archive.api.pagination import DefaultCursorPagination
from archive.api.serializers.team import (
    TeamDetailSerializer,
    TeamListSerializer,
    TeamWriteSerializer,
)
from archive.models import Team


class TeamViewSet(
    ListModelMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    GenericViewSet,
):
    pagination_class = DefaultCursorPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["franchise", "city", "state"]
    search_fields = ["name", "short_name", "city", "school_name", "mascot"]

    def get_queryset(self):
        return (
            Team.objects.select_related("franchise")
            .prefetch_related("affiliations", "venue_occupancies")
            .all()
        )

    def get_serializer_class(self):
        if self.action == "list":
            return TeamListSerializer
        if self.action == "retrieve":
            return TeamDetailSerializer
        return TeamWriteSerializer
