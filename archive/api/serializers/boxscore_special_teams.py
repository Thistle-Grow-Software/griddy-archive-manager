from rest_framework import serializers

from archive.models import (
    ExtraPointsBoxscore,
    FieldGoalsBoxscore,
    KickingBoxscore,
    PuntingBoxscore,
    ReturnBoxscore,
)

BASE_FIELDS = [
    "id",
    "game",
    "team",
    "side",
    "player_name",
    "jersey_number",
    "position",
]

BASE_WRITE_FIELDS = [
    "team",
    "side",
    "player_name",
    "jersey_number",
    "position",
]


# --- FieldGoals ---


class FieldGoalsBoxscoreSerializer(serializers.ModelSerializer):
    team = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = FieldGoalsBoxscore
        fields = [
            *BASE_FIELDS,
            "attempts",
            "made",
            "blocked",
            "yards",
            "avg_yards",
            "longest",
        ]
        read_only_fields = ["id", "game"]


class FieldGoalsBoxscoreWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldGoalsBoxscore
        fields = [
            *BASE_WRITE_FIELDS,
            "attempts",
            "made",
            "blocked",
            "yards",
            "avg_yards",
            "longest",
        ]


# --- ExtraPoints ---


class ExtraPointsBoxscoreSerializer(serializers.ModelSerializer):
    team = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ExtraPointsBoxscore
        fields = [*BASE_FIELDS, "attempts", "made", "blocked"]
        read_only_fields = ["id", "game"]


class ExtraPointsBoxscoreWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtraPointsBoxscore
        fields = [*BASE_WRITE_FIELDS, "attempts", "made", "blocked"]


# --- Kicking ---


class KickingBoxscoreSerializer(serializers.ModelSerializer):
    team = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = KickingBoxscore
        fields = [
            *BASE_FIELDS,
            "kickoffs",
            "yards",
            "touchbacks",
            "inside_20",
            "out_of_bounds",
            "to_endzone",
            "return_yards",
        ]
        read_only_fields = ["id", "game"]


class KickingBoxscoreWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = KickingBoxscore
        fields = [
            *BASE_WRITE_FIELDS,
            "kickoffs",
            "yards",
            "touchbacks",
            "inside_20",
            "out_of_bounds",
            "to_endzone",
            "return_yards",
        ]


# --- Punting ---


class PuntingBoxscoreSerializer(serializers.ModelSerializer):
    team = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = PuntingBoxscore
        fields = [
            *BASE_FIELDS,
            "attempts",
            "yards",
            "gross_avg",
            "net_avg",
            "blocked",
            "longest",
            "touchbacks",
            "inside_20",
            "return_yards",
        ]
        read_only_fields = ["id", "game"]


class PuntingBoxscoreWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PuntingBoxscore
        fields = [
            *BASE_WRITE_FIELDS,
            "attempts",
            "yards",
            "gross_avg",
            "net_avg",
            "blocked",
            "longest",
            "touchbacks",
            "inside_20",
            "return_yards",
        ]


# --- Returns ---


class ReturnBoxscoreSerializer(serializers.ModelSerializer):
    team = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ReturnBoxscore
        fields = [
            *BASE_FIELDS,
            "return_type",
            "returns",
            "yards",
            "avg_yards",
            "touchdowns",
            "longest",
            "longest_td",
            "fair_catches",
        ]
        read_only_fields = ["id", "game"]


class ReturnBoxscoreWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReturnBoxscore
        fields = [
            *BASE_WRITE_FIELDS,
            "return_type",
            "returns",
            "yards",
            "avg_yards",
            "touchdowns",
            "longest",
            "longest_td",
            "fair_catches",
        ]
