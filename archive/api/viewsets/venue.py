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
from archive.api.serializers.venue import (
    VenueDetailSerializer,
    VenueListSerializer,
    VenueWriteSerializer,
)
from archive.models import Venue
from gam.auth.permissions import CatalogPermissionMixin


class VenueViewSet(
    CatalogPermissionMixin,
    ListModelMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    GenericViewSet,
):
    queryset = Venue.objects.all()
    pagination_class = DefaultCursorPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["city", "state"]
    search_fields = ["name", "city"]

    def get_serializer_class(self):
        if self.action == "list":
            return VenueListSerializer
        if self.action == "retrieve":
            return VenueDetailSerializer
        return VenueWriteSerializer
