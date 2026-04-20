from rest_framework import serializers

from archive.models import TeamStandingsSnapshot


class TeamStandingsSnapshotListSerializer(serializers.ModelSerializer):
    team = serializers.PrimaryKeyRelatedField(read_only=True)
    season = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = TeamStandingsSnapshot
        fields = [
            "id",
            "team",
            "season",
            "week",
            "overall_wins",
            "overall_losses",
            "overall_ties",
            "overall_win_pct",
        ]


class TeamStandingsSnapshotDetailSerializer(serializers.ModelSerializer):
    team = serializers.PrimaryKeyRelatedField(read_only=True)
    season = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = TeamStandingsSnapshot
        fields = [
            "id",
            "team",
            "season",
            "week",
            "overall_wins",
            "overall_losses",
            "overall_ties",
            "overall_win_pct",
            "points_for",
            "points_against",
            "conference_wins",
            "conference_losses",
            "conference_rank",
            "division_wins",
            "division_losses",
            "division_rank",
            "home_wins",
            "home_losses",
            "road_wins",
            "road_losses",
            "streak_length",
            "streak_type",
            "clinched_playoff",
            "clinched_division",
            "clinched_bye",
            "eliminated",
            "bonus_data",
            "external_ids",
        ]


class TeamStandingsSnapshotWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamStandingsSnapshot
        fields = [
            "team",
            "season",
            "week",
            "overall_wins",
            "overall_losses",
            "overall_ties",
            "overall_win_pct",
            "points_for",
            "points_against",
            "conference_wins",
            "conference_losses",
            "conference_rank",
            "division_wins",
            "division_losses",
            "division_rank",
            "home_wins",
            "home_losses",
            "road_wins",
            "road_losses",
            "streak_length",
            "streak_type",
            "clinched_playoff",
            "clinched_division",
            "clinched_bye",
            "eliminated",
            "bonus_data",
            "external_ids",
        ]
