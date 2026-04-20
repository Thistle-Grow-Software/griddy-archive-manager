from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import CursorPagination
from rest_framework.viewsets import ModelViewSet

from archive.api.serializers.video_asset import (
    VideoAssetDetailSerializer,
    VideoAssetListSerializer,
    VideoAssetWriteSerializer,
)
from archive.models import VideoAsset


class VideoAssetPagination(CursorPagination):
    page_size = 50
    ordering = "-created_at"


class VideoAssetViewSet(ModelViewSet):
    pagination_class = VideoAssetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["game", "asset_type", "quality_tier", "is_preferred"]
    search_fields = ["file_path", "quality_notes"]
    ordering_fields = [
        "created_at",
        "quality_tier",
        "file_size_bytes",
        "duration_seconds",
    ]

    def get_queryset(self):
        return VideoAsset.objects.select_related("game", "acquisition").all()

    def get_serializer_class(self):
        if self.action == "list":
            return VideoAssetListSerializer
        if self.action == "retrieve":
            return VideoAssetDetailSerializer
        return VideoAssetWriteSerializer
