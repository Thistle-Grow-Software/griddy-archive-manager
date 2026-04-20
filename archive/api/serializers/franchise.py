from rest_framework import serializers

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

    def get_teams(self, obj):
        from archive.api.serializers.team import TeamReferenceSerializer

        return TeamReferenceSerializer(obj.teams.all(), many=True).data


class FranchiseWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Franchise
        fields = ["name", "league", "bonus_data", "external_ids"]
