from rest_framework import serializers

from archive.models import (
    FumblesBoxscore,
    PassingBoxscore,
    ReceivingBoxscore,
    RushingBoxscore,
    TacklesBoxscore,
)


class PlayerGameStatBaseSerializer(serializers.Serializer):
    """Abstract base defining shared fields for all boxscore serializers."""

    id = serializers.IntegerField(read_only=True)
    game = serializers.PrimaryKeyRelatedField(read_only=True)
    team = serializers.PrimaryKeyRelatedField(read_only=True)
    side = serializers.CharField(read_only=True)
    player_name = serializers.CharField(read_only=True)
    jersey_number = serializers.IntegerField(read_only=True)
    position = serializers.CharField(read_only=True)


class PassingBoxscoreSerializer(serializers.ModelSerializer):
    team = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = PassingBoxscore
        fields = [
            "id",
            "game",
            "team",
            "side",
            "player_name",
            "jersey_number",
            "position",
            "attempts",
            "completions",
            "completion_pct",
            "yards",
            "yards_per_attempt",
            "touchdowns",
            "interceptions",
            "sacks",
            "sack_yards",
            "qb_rating",
            "longest_pass",
            "longest_td_pass",
        ]
        read_only_fields = ["id", "game"]


class PassingBoxscoreWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PassingBoxscore
        fields = [
            "team",
            "side",
            "player_name",
            "jersey_number",
            "position",
            "attempts",
            "completions",
            "completion_pct",
            "yards",
            "yards_per_attempt",
            "touchdowns",
            "interceptions",
            "sacks",
            "sack_yards",
            "qb_rating",
            "longest_pass",
            "longest_td_pass",
        ]


class RushingBoxscoreSerializer(serializers.ModelSerializer):
    team = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = RushingBoxscore
        fields = [
            "id",
            "game",
            "team",
            "side",
            "player_name",
            "jersey_number",
            "position",
            "attempts",
            "yards",
            "avg_yards",
            "touchdowns",
            "longest_rush",
            "longest_td_rush",
        ]
        read_only_fields = ["id", "game"]


class RushingBoxscoreWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RushingBoxscore
        fields = [
            "team",
            "side",
            "player_name",
            "jersey_number",
            "position",
            "attempts",
            "yards",
            "avg_yards",
            "touchdowns",
            "longest_rush",
            "longest_td_rush",
        ]


class ReceivingBoxscoreSerializer(serializers.ModelSerializer):
    team = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ReceivingBoxscore
        fields = [
            "id",
            "game",
            "team",
            "side",
            "player_name",
            "jersey_number",
            "position",
            "receptions",
            "yards",
            "avg_yards",
            "touchdowns",
            "targets",
            "longest_reception",
            "longest_td_reception",
            "yards_after_catch",
        ]
        read_only_fields = ["id", "game"]


class ReceivingBoxscoreWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReceivingBoxscore
        fields = [
            "team",
            "side",
            "player_name",
            "jersey_number",
            "position",
            "receptions",
            "yards",
            "avg_yards",
            "touchdowns",
            "targets",
            "longest_reception",
            "longest_td_reception",
            "yards_after_catch",
        ]


class TacklesBoxscoreSerializer(serializers.ModelSerializer):
    team = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = TacklesBoxscore
        fields = [
            "id",
            "game",
            "team",
            "side",
            "player_name",
            "jersey_number",
            "position",
            "tackles",
            "assists",
            "sacks",
            "sack_yards",
            "qb_hits",
            "tackles_for_loss",
            "tackles_for_loss_yards",
            "safeties",
            "special_teams_tackles",
            "special_teams_assists",
            "special_teams_blocks",
        ]
        read_only_fields = ["id", "game"]


class TacklesBoxscoreWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TacklesBoxscore
        fields = [
            "team",
            "side",
            "player_name",
            "jersey_number",
            "position",
            "tackles",
            "assists",
            "sacks",
            "sack_yards",
            "qb_hits",
            "tackles_for_loss",
            "tackles_for_loss_yards",
            "safeties",
            "special_teams_tackles",
            "special_teams_assists",
            "special_teams_blocks",
        ]


class FumblesBoxscoreSerializer(serializers.ModelSerializer):
    team = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = FumblesBoxscore
        fields = [
            "id",
            "game",
            "team",
            "side",
            "player_name",
            "jersey_number",
            "position",
            "fumbles",
            "own_recoveries",
            "own_recovery_yards",
            "own_recovery_tds",
            "opp_recoveries",
            "opp_recovery_yards",
            "opp_recovery_tds",
            "forced_fumbles",
            "out_of_bounds",
        ]
        read_only_fields = ["id", "game"]


class FumblesBoxscoreWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = FumblesBoxscore
        fields = [
            "team",
            "side",
            "player_name",
            "jersey_number",
            "position",
            "fumbles",
            "own_recoveries",
            "own_recovery_yards",
            "own_recovery_tds",
            "opp_recoveries",
            "opp_recovery_yards",
            "opp_recovery_tds",
            "forced_fumbles",
            "out_of_bounds",
        ]
