from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.mixins import (
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework.viewsets import GenericViewSet

from archive.api.pagination import DefaultCursorPagination
from archive.api.serializers.team_affiliation import (
    TeamAffiliationDetailSerializer,
    TeamAffiliationListSerializer,
    TeamAffiliationWriteSerializer,
)
from archive.models import TeamAffiliation


class TeamAffiliationViewSet(
    ListModelMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    GenericViewSet,
):
    pagination_class = DefaultCursorPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["team", "org_unit", "season"]

    def get_queryset(self):
        return TeamAffiliation.objects.select_related(
            "team", "org_unit", "season"
        ).all()

    def get_serializer_class(self):
        if self.action == "list":
            return TeamAffiliationListSerializer
        if self.action == "retrieve":
            return TeamAffiliationDetailSerializer
        return TeamAffiliationWriteSerializer
