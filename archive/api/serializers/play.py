from rest_framework import serializers

from archive.models import Play, PlayStat


class PlayStatInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlayStat
        fields = ["id", "team_abbr", "player_name", "gsis_id", "stat_id", "yards"]


class PlayListSerializer(serializers.ModelSerializer):
    possession_team = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Play
        fields = [
            "id",
            "sequence",
            "quarter",
            "down",
            "yards_to_go",
            "play_type",
            "play_description",
            "possession_team",
            "home_score",
            "visitor_score",
            "is_scoring",
        ]


class PlayDetailSerializer(serializers.ModelSerializer):
    possession_team = serializers.PrimaryKeyRelatedField(read_only=True)
    stats = PlayStatInlineSerializer(many=True, read_only=True)

    class Meta:
        model = Play
        fields = [
            "id",
            "play_id",
            "sequence",
            "quarter",
            "down",
            "yards_to_go",
            "play_type",
            "play_description",
            "play_state",
            "possession_team",
            "home_score",
            "visitor_score",
            "yard_line_number",
            "yard_line_side",
            "is_scoring",
            "is_big_play",
            "is_stp_play",
            "is_marker_play",
            "is_red_zone_play",
            "start_game_clock",
            "end_game_clock",
            "ngs_data",
            "bonus_data",
            "external_ids",
            "stats",
        ]


class PlayWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Play
        fields = [
            "play_id",
            "sequence",
            "quarter",
            "down",
            "yards_to_go",
            "play_type",
            "play_description",
            "play_state",
            "possession_team",
            "home_score",
            "visitor_score",
            "yard_line_number",
            "yard_line_side",
            "is_scoring",
            "is_big_play",
            "is_stp_play",
            "is_marker_play",
            "is_red_zone_play",
            "start_game_clock",
            "end_game_clock",
            "ngs_data",
            "bonus_data",
            "external_ids",
        ]
