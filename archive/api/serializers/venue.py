from rest_framework import serializers

from archive.models import Venue


class VenueReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = ["id", "name"]


class VenueListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = ["id", "name", "city", "state", "capacity"]


class VenueDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = [
            "id",
            "name",
            "city",
            "state",
            "country",
            "capacity",
            "bonus_data",
            "external_ids",
        ]


class VenueWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = [
            "name",
            "city",
            "state",
            "country",
            "capacity",
            "bonus_data",
            "external_ids",
        ]
