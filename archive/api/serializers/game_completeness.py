from rest_framework import serializers

from archive.models import GameCompleteness


class GameCompletenessListSerializer(serializers.ModelSerializer):
    game = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = GameCompleteness
        fields = [
            "id",
            "game",
            "scope",
            "status",
            "has_full",
            "has_condensed",
            "has_all22",
        ]


class GameCompletenessDetailSerializer(serializers.ModelSerializer):
    game = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = GameCompleteness
        fields = [
            "id",
            "game",
            "scope",
            "status",
            "best_full_quality_score",
            "has_full",
            "has_condensed",
            "has_all22",
            "computed_at",
            "bonus_data",
            "external_ids",
        ]


class GameCompletenessWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameCompleteness
        fields = [
            "game",
            "scope",
            "status",
            "best_full_quality_score",
            "has_full",
            "has_condensed",
            "has_all22",
            "bonus_data",
            "external_ids",
        ]
