from rest_framework import serializers

from archive.models import League


class LeagueListSerializer(serializers.ModelSerializer):
    seasons_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = League
        fields = ["id", "long_name", "short_name", "level", "seasons_count"]


class LeagueDetailSerializer(serializers.ModelSerializer):
    seasons = serializers.SerializerMethodField()

    class Meta:
        model = League
        fields = [
            "id",
            "short_name",
            "long_name",
            "level",
            "country",
            "notes",
            "bonus_data",
            "external_ids",
            "seasons",
        ]

    def get_seasons(self, obj):
        from archive.api.serializers.season import SeasonListSerializer

        return SeasonListSerializer(obj.seasons.all(), many=True).data


class LeagueWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = League
        fields = [
            "short_name",
            "long_name",
            "level",
            "country",
            "notes",
            "bonus_data",
            "external_ids",
        ]
