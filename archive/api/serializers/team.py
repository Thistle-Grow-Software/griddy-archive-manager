from rest_framework import serializers

from archive.models import Team, TeamAffiliation, TeamVenueOccupancy


class TeamReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ["id", "name", "short_name"]


class TeamAffiliationInlineSerializer(serializers.ModelSerializer):
    org_unit = serializers.StringRelatedField()
    season = serializers.StringRelatedField()

    class Meta:
        model = TeamAffiliation
        fields = ["id", "org_unit", "season", "start_date", "end_date"]


class TeamVenueOccupancyInlineSerializer(serializers.ModelSerializer):
    venue = serializers.StringRelatedField()

    class Meta:
        model = TeamVenueOccupancy
        fields = ["id", "venue", "start_date", "end_date"]


class TeamListSerializer(serializers.ModelSerializer):
    franchise = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Team
        fields = [
            "id",
            "name",
            "short_name",
            "city",
            "state",
            "franchise",
            "primary_color",
            "secondary_color",
        ]


class TeamDetailSerializer(serializers.ModelSerializer):
    franchise = serializers.PrimaryKeyRelatedField(read_only=True)
    affiliations = TeamAffiliationInlineSerializer(many=True, read_only=True)
    venue_occupancies = TeamVenueOccupancyInlineSerializer(many=True, read_only=True)

    class Meta:
        model = Team
        fields = [
            "id",
            "franchise",
            "name",
            "alternate_name",
            "short_name",
            "city",
            "state",
            "country",
            "era_start_date",
            "era_end_date",
            "school_name",
            "mascot",
            "logo",
            "primary_color",
            "secondary_color",
            "tertiary_color",
            "additional_colors",
            "bonus_data",
            "external_ids",
            "affiliations",
            "venue_occupancies",
        ]


class TeamWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = [
            "franchise",
            "name",
            "alternate_name",
            "short_name",
            "city",
            "state",
            "country",
            "era_start_date",
            "era_end_date",
            "school_name",
            "mascot",
            "logo",
            "primary_color",
            "secondary_color",
            "tertiary_color",
            "additional_colors",
            "bonus_data",
            "external_ids",
        ]
