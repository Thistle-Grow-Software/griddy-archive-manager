from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.mixins import (
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework.viewsets import GenericViewSet

from archive.api.pagination import DefaultCursorPagination
from archive.api.serializers.game_completeness import (
    GameCompletenessDetailSerializer,
    GameCompletenessListSerializer,
    GameCompletenessWriteSerializer,
)
from archive.models import GameCompleteness
from gam.auth.permissions import CatalogPermissionMixin


class GameCompletenessViewSet(
    CatalogPermissionMixin,
    ListModelMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    GenericViewSet,
):
    pagination_class = DefaultCursorPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["scope", "status", "has_full", "has_condensed", "has_all22"]

    def get_queryset(self):
        return GameCompleteness.objects.select_related("game").all()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return GameCompletenessDetailSerializer
        if self.action in ("create", "update", "partial_update"):
            return GameCompletenessWriteSerializer
        return GameCompletenessListSerializer
