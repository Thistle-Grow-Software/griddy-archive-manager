from rest_framework import serializers

from archive.models import Season


class SeasonListSerializer(serializers.ModelSerializer):
    league = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Season
        fields = ["id", "league", "year", "label", "start_date", "end_date"]


class SeasonDetailSerializer(serializers.ModelSerializer):
    league = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Season
        fields = [
            "id",
            "league",
            "year",
            "label",
            "start_date",
            "end_date",
            "bonus_data",
            "external_ids",
        ]


class SeasonWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Season
        fields = [
            "league",
            "year",
            "label",
            "start_date",
            "end_date",
            "bonus_data",
            "external_ids",
        ]
