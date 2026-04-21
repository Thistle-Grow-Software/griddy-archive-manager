from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from archive.api.serializers.team import TeamReferenceSerializer
from archive.models import Franchise


class FranchiseListSerializer(serializers.ModelSerializer):
    league = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Franchise
        fields = ["id", "name", "league"]


class FranchiseDetailSerializer(serializers.ModelSerializer):
    league = serializers.PrimaryKeyRelatedField(read_only=True)
    teams = serializers.SerializerMethodField()

    class Meta:
        model = Franchise
        fields = [
            "id",
            "name",
            "league",
            "bonus_data",
            "external_ids",
            "teams",
        ]

    @extend_schema_field(TeamReferenceSerializer(many=True))
    def get_teams(self, obj):
        return TeamReferenceSerializer(obj.teams.all(), many=True).data


class FranchiseWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Franchise
        fields = ["name", "league", "bonus_data", "external_ids"]
