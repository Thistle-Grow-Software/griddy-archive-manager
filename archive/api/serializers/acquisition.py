from rest_framework import serializers

from archive.models import Acquisition


class AcquisitionListSerializer(serializers.ModelSerializer):
    source = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Acquisition
        fields = ["id", "source", "acquired_on", "rights", "cost_usd"]


class AcquisitionDetailSerializer(serializers.ModelSerializer):
    source = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Acquisition
        fields = [
            "id",
            "source",
            "acquired_on",
            "cost_usd",
            "rights",
            "notes",
            "proof_path",
            "bonus_data",
            "external_ids",
        ]


class AcquisitionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Acquisition
        fields = [
            "source",
            "acquired_on",
            "cost_usd",
            "rights",
            "notes",
            "proof_path",
            "bonus_data",
            "external_ids",
        ]
