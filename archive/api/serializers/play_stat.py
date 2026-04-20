from rest_framework import serializers

from archive.models import PlayStat


class PlayStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlayStat
        fields = ["id", "player_name", "stat_id", "yards", "team_abbr"]
        read_only_fields = ["id"]


class PlayStatWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlayStat
        fields = ["player_name", "stat_id", "yards", "team_abbr", "gsis_id"]
