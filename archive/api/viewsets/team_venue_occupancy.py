from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.mixins import (
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework.viewsets import GenericViewSet

from archive.api.pagination import DefaultCursorPagination
from archive.api.serializers.team_venue_occupancy import (
    TeamVenueOccupancyDetailSerializer,
    TeamVenueOccupancyListSerializer,
    TeamVenueOccupancyWriteSerializer,
)
from archive.models import TeamVenueOccupancy
from gam.auth.permissions import CatalogPermissionMixin


class TeamVenueOccupancyViewSet(
    CatalogPermissionMixin,
    ListModelMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    GenericViewSet,
):
    pagination_class = DefaultCursorPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["team", "venue"]

    def get_queryset(self):
        return TeamVenueOccupancy.objects.select_related("team", "venue").all()

    def get_serializer_class(self):
        if self.action == "list":
            return TeamVenueOccupancyListSerializer
        if self.action == "retrieve":
            return TeamVenueOccupancyDetailSerializer
        return TeamVenueOccupancyWriteSerializer
