from typing import ClassVar
from urllib.parse import urlencode

from django.conf import settings
from django.db.models import Count, Q, Sum
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.mixins import (
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from archive.api.filters import GameFilter
from archive.api.pagination import GamePagination
from archive.api.serializers.game import (
    GameDetailSerializer,
    GameListSerializer,
    GameWriteSerializer,
)
from archive.api.serializers.game_actions import (
    FullBoxscoreSerializer,
    GameSummarySerializer,
)
from archive.api.serializers.playback import PlaybackResponseSerializer
from archive.models import (
    ExtraPointsBoxscore,
    FieldGoalsBoxscore,
    FumblesBoxscore,
    Game,
    KickingBoxscore,
    PassingBoxscore,
    PuntingBoxscore,
    ReceivingBoxscore,
    ReturnBoxscore,
    RushingBoxscore,
    TacklesBoxscore,
)
from gam.auth.permissions import (
    CATALOG_PERMISSIONS,
    CatalogPermissionMixin,
    Permissions,
)
from gam.playback.tokens import mint_playback_token


class GameViewSet(
    CatalogPermissionMixin,
    ListModelMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    GenericViewSet,
):
    pagination_class = GamePagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = GameFilter
    search_fields = ["competition_name", "notes"]
    ordering_fields = ["date_local", "week", "final_home_score", "final_away_score"]

    # Playback is gated by its own scope (video:playback) on top of the
    # shared catalog map — the entitlement check in TGF-360 lives at the
    # scope layer so 403s fall out of the existing permission machinery.
    required_permissions: ClassVar[dict[str, list[str]]] = {
        **CATALOG_PERMISSIONS,
        "playback": [Permissions.VIDEO_PLAYBACK],
    }

    def get_queryset(self):
        qs = Game.objects.select_related(
            "league", "season", "venue", "home_team", "away_team"
        ).prefetch_related("quarter_scores", "completeness")
        if self.action == "retrieve":
            qs = qs.annotate(asset_count=Count("assets"))
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return GameListSerializer
        if self.action == "retrieve":
            return GameDetailSerializer
        if self.action == "full_boxscore":
            return FullBoxscoreSerializer
        if self.action == "summary":
            return GameSummarySerializer
        if self.action == "playback":
            return PlaybackResponseSerializer
        return GameWriteSerializer

    @action(detail=True, methods=["get"], url_path="full-boxscore")
    def full_boxscore(self, request, pk=None):
        game = self.get_object()
        team_select = ["team"]
        data = {
            "passing": PassingBoxscore.objects.filter(game=game).select_related(
                *team_select
            ),
            "rushing": RushingBoxscore.objects.filter(game=game).select_related(
                *team_select
            ),
            "receiving": ReceivingBoxscore.objects.filter(game=game).select_related(
                *team_select
            ),
            "tackles": TacklesBoxscore.objects.filter(game=game).select_related(
                *team_select
            ),
            "fumbles": FumblesBoxscore.objects.filter(game=game).select_related(
                *team_select
            ),
            "field_goals": FieldGoalsBoxscore.objects.filter(game=game).select_related(
                *team_select
            ),
            "extra_points": ExtraPointsBoxscore.objects.filter(
                game=game
            ).select_related(*team_select),
            "kicking": KickingBoxscore.objects.filter(game=game).select_related(
                *team_select
            ),
            "punting": PuntingBoxscore.objects.filter(game=game).select_related(
                *team_select
            ),
            "returns": ReturnBoxscore.objects.filter(game=game).select_related(
                *team_select
            ),
        }
        serializer = FullBoxscoreSerializer(data)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        game = (
            Game.objects.select_related("home_team", "away_team")
            .prefetch_related("quarter_scores", "drives")
            .get(pk=pk)
        )
        drive_agg = game.drives.aggregate(
            total_drives=Count("id"),
            scoring_drives=Count("id", filter=Q(ended_with_score=True)),
            total_yards=Sum("yards_gained"),
        )
        data = {
            "id": game.id,
            "date_local": game.date_local,
            "home_team": game.home_team,
            "away_team": game.away_team,
            "final_home_score": game.final_home_score,
            "final_away_score": game.final_away_score,
            "quarter_scores": game.quarter_scores.all(),
            "drives": {
                "total_drives": drive_agg["total_drives"] or 0,
                "scoring_drives": drive_agg["scoring_drives"] or 0,
                "total_yards": drive_agg["total_yards"] or 0,
            },
        }
        serializer = GameSummarySerializer(data)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def playback(self, request, pk=None):
        """Mint a short-lived, game-scoped HLS playback URL (TGF-360, ADR-0008).

        Returns ``{type, url, expires_at}``. The ``url`` points at
        ``{VIDEO_ORIGIN_URL}/games/{id}/master.m3u8`` with a signed token
        embedded as ``?t=...``; the Worker that fronts R2 (TGF-361 / TGF-363)
        verifies that token with the same shared secret. Entitlement is
        enforced upstream by the ``video:playback`` permission scope.
        """
        # ``get_object`` honours the queryset and raises 404 for unknown ids,
        # which satisfies the AC without an extra existence check.
        try:
            game = Game.objects.only("id").get(pk=pk)
        except Game.DoesNotExist as exc:
            raise NotFound("Unknown game id.") from exc

        subject = self._token_subject(request)
        minted = mint_playback_token(subject=subject, game_id=game.id)

        origin = settings.VIDEO_ORIGIN_URL.rstrip("/")
        query = urlencode({"t": minted.token})
        url = f"{origin}/games/{game.id}/master.m3u8?{query}"

        payload = {
            "type": "hls",
            "url": url,
            "expires_at": minted.expires_at,
        }
        serializer = PlaybackResponseSerializer(payload)
        return Response(serializer.data)

    @staticmethod
    def _token_subject(request) -> str:
        """Derive the token ``sub`` claim from whatever auth principal we have.

        JWT requests expose claims under ``request.auth`` (a dict); API key
        requests expose the :class:`APIKey` row, which carries the owning
        Clerk account's ``clerk_sub``. Either source maps to a single string
        so the minted token stays consistent regardless of which credential
        type the caller used.
        """
        auth = getattr(request, "auth", None)
        if isinstance(auth, dict):
            sub = auth.get("sub")
            if sub:
                return str(sub)
        if auth is not None:
            account = getattr(auth, "account", None)
            sub = getattr(account, "clerk_sub", None)
            if sub:
                return str(sub)
        user = getattr(request, "user", None)
        sub = getattr(user, "subject", None) or getattr(user, "username", None)
        return str(sub) if sub else "anonymous"
