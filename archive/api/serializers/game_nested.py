from rest_framework import serializers

from archive.models import Drive, GameReplay, QuarterScore


class QuarterScoreSerializer(serializers.ModelSerializer):
    team = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = QuarterScore
        fields = ["id", "team", "period", "points"]
        read_only_fields = ["id"]


class QuarterScoreWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuarterScore
        fields = ["team", "period", "points"]


class DriveSerializer(serializers.ModelSerializer):
    team = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Drive
        fields = [
            "id",
            "sequence",
            "team",
            "yards_gained",
            "plays_count",
            "ended_description",
            "time_of_possession",
        ]
        read_only_fields = ["id"]


class DriveWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Drive
        fields = [
            "sequence",
            "team",
            "started_quarter",
            "started_clock",
            "started_description",
            "started_yard_line",
            "ended_quarter",
            "ended_clock",
            "ended_description",
            "ended_yard_line",
            "ended_with_score",
            "plays_count",
            "first_downs",
            "yards_gained",
            "yards_gained_net",
            "yards_gained_by_penalty",
            "time_of_possession",
            "inside_20",
        ]


class GameReplaySerializer(serializers.ModelSerializer):
    class Meta:
        model = GameReplay
        fields = [
            "id",
            "replay_type",
            "sub_type",
            "title",
            "description",
            "duration",
            "external_id",
            "mcp_playback_id",
            "publish_date",
            "thumbnail_url",
            "bonus_data",
            "external_ids",
        ]
        read_only_fields = ["id"]


class GameReplayWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameReplay
        fields = [
            "replay_type",
            "sub_type",
            "title",
            "description",
            "duration",
            "external_id",
            "mcp_playback_id",
            "publish_date",
            "thumbnail_url",
            "bonus_data",
            "external_ids",
        ]
