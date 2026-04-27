from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.viewsets import ModelViewSet

from archive.api.pagination import DefaultCursorPagination
from archive.api.serializers.acquisition import (
    AcquisitionDetailSerializer,
    AcquisitionListSerializer,
    AcquisitionWriteSerializer,
)
from archive.models import Acquisition
from gam.auth.permissions import HoldingsPermissionMixin


class AcquisitionViewSet(HoldingsPermissionMixin, ModelViewSet):
    pagination_class = DefaultCursorPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["source", "rights"]

    def get_queryset(self):
        return Acquisition.objects.select_related("source").all()

    def get_serializer_class(self):
        if self.action == "list":
            return AcquisitionListSerializer
        if self.action == "retrieve":
            return AcquisitionDetailSerializer
        return AcquisitionWriteSerializer
