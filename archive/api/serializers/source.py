from rest_framework import serializers

from archive.models import Source


class SourceListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Source
        fields = ["id", "name", "source_type", "url"]


class SourceDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Source
        fields = [
            "id",
            "name",
            "source_type",
            "url",
            "notes",
            "bonus_data",
            "external_ids",
        ]


class SourceWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Source
        fields = [
            "name",
            "source_type",
            "url",
            "notes",
            "bonus_data",
            "external_ids",
        ]
