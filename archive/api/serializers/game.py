from rest_framework import serializers

from archive.api.serializers.team import TeamReferenceSerializer
from archive.api.serializers.venue import VenueReferenceSerializer
from archive.models import Game, GameCompleteness, QuarterScore


class QuarterScoreInlineSerializer(serializers.ModelSerializer):
    team = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = QuarterScore
        fields = ["id", "team", "period", "points"]


class GameCompletenessInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameCompleteness
        fields = [
            "id",
            "scope",
            "status",
            "best_full_quality_score",
            "has_full",
            "has_condensed",
            "has_all22",
            "computed_at",
        ]


class GameListSerializer(serializers.ModelSerializer):
    home_team = TeamReferenceSerializer(read_only=True)
    away_team = TeamReferenceSerializer(read_only=True)
    venue = VenueReferenceSerializer(read_only=True)

    class Meta:
        model = Game
        fields = [
            "id",
            "date_local",
            "kickoff_time_local",
            "week",
            "game_type",
            "home_team",
            "away_team",
            "final_home_score",
            "final_away_score",
            "venue",
            "broadcast_channel",
            "status",
        ]


class GameDetailSerializer(serializers.ModelSerializer):
    home_team = TeamReferenceSerializer(read_only=True)
    away_team = TeamReferenceSerializer(read_only=True)
    venue = VenueReferenceSerializer(read_only=True)
    league = serializers.PrimaryKeyRelatedField(read_only=True)
    season = serializers.PrimaryKeyRelatedField(read_only=True)
    quarter_scores = QuarterScoreInlineSerializer(many=True, read_only=True)
    completeness = GameCompletenessInlineSerializer(many=True, read_only=True)
    asset_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Game
        fields = [
            "id",
            "league",
            "season",
            "ordinal",
            "date_local",
            "kickoff_time_local",
            "week",
            "game_type",
            "competition_name",
            "neutral_site",
            "venue",
            "home_team",
            "away_team",
            "final_home_score",
            "final_away_score",
            "overtime_periods",
            "ap_rank_home",
            "ap_rank_away",
            "broadcast_channel",
            "status",
            "kickoff_utc",
            "notes",
            "bonus_data",
            "external_ids",
            "quarter_scores",
            "completeness",
            "asset_count",
        ]


class GameWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Game
        fields = [
            "league",
            "season",
            "ordinal",
            "date_local",
            "kickoff_time_local",
            "week",
            "game_type",
            "competition_name",
            "neutral_site",
            "venue",
            "home_team",
            "away_team",
            "final_home_score",
            "final_away_score",
            "overtime_periods",
            "ap_rank_home",
            "ap_rank_away",
            "broadcast_channel",
            "status",
            "kickoff_utc",
            "notes",
            "bonus_data",
            "external_ids",
        ]
