from rest_framework.mixins import CreateModelMixin, DestroyModelMixin, ListModelMixin
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from archive.api.pagination import DefaultCursorPagination
from archive.api.serializers.tag import (
    AssetTagSerializer,
    AssetTagWriteSerializer,
    TagSerializer,
)
from archive.models import AssetTag, Tag


class TagViewSet(ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    pagination_class = DefaultCursorPagination


class AssetTagViewSet(
    ListModelMixin, CreateModelMixin, DestroyModelMixin, GenericViewSet
):
    pagination_class = DefaultCursorPagination

    def get_queryset(self):
        return AssetTag.objects.select_related("asset", "tag").all()

    def get_serializer_class(self):
        if self.action == "create":
            return AssetTagWriteSerializer
        return AssetTagSerializer
