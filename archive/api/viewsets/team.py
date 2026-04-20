from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.mixins import (
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from archive.api.pagination import DefaultCursorPagination
from archive.api.serializers.game import GameListSerializer
from archive.api.serializers.team import (
    TeamDetailSerializer,
    TeamListSerializer,
    TeamWriteSerializer,
)
from archive.api.serializers.venue import VenueDetailSerializer
from archive.models import Game, Team, TeamVenueOccupancy


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
        if self.action == "schedule":
            return GameListSerializer
        if self.action == "current_venue":
            return VenueDetailSerializer
        return TeamWriteSerializer

    @action(detail=True, methods=["get"])
    def schedule(self, request, pk=None):
        team = self.get_object()
        season_year = request.query_params.get("season_year")
        if not season_year:
            return Response(
                {"detail": "season_year query parameter is required."}, status=400
            )
        games = (
            Game.objects.filter(
                Q(home_team=team) | Q(away_team=team),
                season__year=int(season_year),
            )
            .select_related("home_team", "away_team", "venue")
            .order_by("date_local")
        )
        serializer = GameListSerializer(games, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="current-venue")
    def current_venue(self, request, pk=None):
        team = self.get_object()
        occupancy = (
            TeamVenueOccupancy.objects.filter(team=team)
            .filter(Q(end_date__isnull=True) | Q(end_date__gte="2020-01-01"))
            .select_related("venue")
            .order_by("-start_date")
            .first()
        )
        if not occupancy:
            return Response(
                {"detail": "No venue occupancy found for this team."}, status=404
            )
        serializer = VenueDetailSerializer(occupancy.venue)
        return Response(serializer.data)
