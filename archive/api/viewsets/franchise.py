from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.mixins import (
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework.viewsets import GenericViewSet

from archive.api.pagination import DefaultCursorPagination
from archive.api.serializers.franchise import (
    FranchiseDetailSerializer,
    FranchiseListSerializer,
    FranchiseWriteSerializer,
)
from archive.models import Franchise


class FranchiseViewSet(
    ListModelMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    GenericViewSet,
):
    pagination_class = DefaultCursorPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["league"]

    def get_queryset(self):
        qs = Franchise.objects.select_related("league").all()
        if self.action == "retrieve":
            qs = qs.prefetch_related("teams")
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return FranchiseListSerializer
        if self.action == "retrieve":
            return FranchiseDetailSerializer
        return FranchiseWriteSerializer
