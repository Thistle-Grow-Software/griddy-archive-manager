from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.mixins import (
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework.viewsets import GenericViewSet

from archive.api.pagination import DefaultCursorPagination
from archive.api.serializers.org_unit import (
    OrgUnitDetailSerializer,
    OrgUnitListSerializer,
    OrgUnitWriteSerializer,
)
from archive.models import OrgUnit


class OrgUnitViewSet(
    ListModelMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    GenericViewSet,
):
    pagination_class = DefaultCursorPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["league", "org_type", "parent"]

    def get_queryset(self):
        qs = OrgUnit.objects.select_related("league", "parent").all()
        if self.action == "retrieve":
            qs = qs.prefetch_related("children")
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return OrgUnitListSerializer
        if self.action == "retrieve":
            return OrgUnitDetailSerializer
        return OrgUnitWriteSerializer
