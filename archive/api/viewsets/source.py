from rest_framework.viewsets import ModelViewSet

from archive.api.pagination import DefaultCursorPagination
from archive.api.serializers.source import (
    SourceDetailSerializer,
    SourceListSerializer,
    SourceWriteSerializer,
)
from archive.models import Source


class SourceViewSet(ModelViewSet):
    queryset = Source.objects.all()
    pagination_class = DefaultCursorPagination

    def get_serializer_class(self):
        if self.action == "list":
            return SourceListSerializer
        if self.action == "retrieve":
            return SourceDetailSerializer
        return SourceWriteSerializer
