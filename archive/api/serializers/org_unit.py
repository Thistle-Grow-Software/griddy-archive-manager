from rest_framework import serializers

from archive.models import OrgUnit


class OrgUnitListSerializer(serializers.ModelSerializer):
    league = serializers.PrimaryKeyRelatedField(read_only=True)
    parent = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = OrgUnit
        fields = ["id", "short_name", "long_name", "org_type", "league", "parent"]


class OrgUnitChildSerializer(serializers.ModelSerializer):
    """Lightweight serializer for nested children in detail view."""

    class Meta:
        model = OrgUnit
        fields = ["id", "short_name", "long_name", "org_type"]


class OrgUnitDetailSerializer(serializers.ModelSerializer):
    league = serializers.PrimaryKeyRelatedField(read_only=True)
    parent = serializers.PrimaryKeyRelatedField(read_only=True)
    children = OrgUnitChildSerializer(many=True, read_only=True)

    class Meta:
        model = OrgUnit
        fields = [
            "id",
            "short_name",
            "long_name",
            "org_type",
            "league",
            "parent",
            "bonus_data",
            "external_ids",
            "children",
        ]


class OrgUnitWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrgUnit
        fields = [
            "short_name",
            "long_name",
            "org_type",
            "league",
            "parent",
            "bonus_data",
            "external_ids",
        ]
