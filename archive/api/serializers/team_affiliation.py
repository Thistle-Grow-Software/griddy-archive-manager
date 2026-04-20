from rest_framework import serializers

from archive.models import TeamAffiliation


class TeamAffiliationListSerializer(serializers.ModelSerializer):
    team = serializers.PrimaryKeyRelatedField(read_only=True)
    org_unit = serializers.PrimaryKeyRelatedField(read_only=True)
    season = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = TeamAffiliation
        fields = ["id", "team", "org_unit", "season"]


class TeamAffiliationDetailSerializer(serializers.ModelSerializer):
    team = serializers.PrimaryKeyRelatedField(read_only=True)
    org_unit = serializers.PrimaryKeyRelatedField(read_only=True)
    season = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = TeamAffiliation
        fields = [
            "id",
            "team",
            "org_unit",
            "season",
            "start_date",
            "end_date",
            "bonus_data",
            "external_ids",
        ]


class TeamAffiliationWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamAffiliation
        fields = [
            "team",
            "org_unit",
            "season",
            "start_date",
            "end_date",
            "bonus_data",
            "external_ids",
        ]
