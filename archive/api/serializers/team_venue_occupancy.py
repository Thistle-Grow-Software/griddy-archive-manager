from rest_framework import serializers

from archive.models import TeamVenueOccupancy


class TeamVenueOccupancyListSerializer(serializers.ModelSerializer):
    team = serializers.PrimaryKeyRelatedField(read_only=True)
    venue = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = TeamVenueOccupancy
        fields = ["id", "team", "venue", "start_date", "end_date"]


class TeamVenueOccupancyDetailSerializer(serializers.ModelSerializer):
    team = serializers.PrimaryKeyRelatedField(read_only=True)
    venue = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = TeamVenueOccupancy
        fields = [
            "id",
            "team",
            "venue",
            "start_date",
            "end_date",
            "bonus_data",
            "external_ids",
        ]


class TeamVenueOccupancyWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamVenueOccupancy
        fields = [
            "team",
            "venue",
            "start_date",
            "end_date",
            "bonus_data",
            "external_ids",
        ]
