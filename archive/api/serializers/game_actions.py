from rest_framework import serializers

from archive.api.serializers.boxscore import (
    FumblesBoxscoreSerializer,
    PassingBoxscoreSerializer,
    ReceivingBoxscoreSerializer,
    RushingBoxscoreSerializer,
    TacklesBoxscoreSerializer,
)
from archive.api.serializers.boxscore_special_teams import (
    ExtraPointsBoxscoreSerializer,
    FieldGoalsBoxscoreSerializer,
    KickingBoxscoreSerializer,
    PuntingBoxscoreSerializer,
    ReturnBoxscoreSerializer,
)
from archive.api.serializers.game import QuarterScoreInlineSerializer
from archive.api.serializers.team import TeamReferenceSerializer


class FullBoxscoreSerializer(serializers.Serializer):
    passing = PassingBoxscoreSerializer(many=True)
    rushing = RushingBoxscoreSerializer(many=True)
    receiving = ReceivingBoxscoreSerializer(many=True)
    tackles = TacklesBoxscoreSerializer(many=True)
    fumbles = FumblesBoxscoreSerializer(many=True)
    field_goals = FieldGoalsBoxscoreSerializer(many=True)
    extra_points = ExtraPointsBoxscoreSerializer(many=True)
    kicking = KickingBoxscoreSerializer(many=True)
    punting = PuntingBoxscoreSerializer(many=True)
    returns = ReturnBoxscoreSerializer(many=True)


class DriveSummarySerializer(serializers.Serializer):
    total_drives = serializers.IntegerField()
    scoring_drives = serializers.IntegerField()
    total_yards = serializers.IntegerField()


class GameSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    date_local = serializers.DateField()
    home_team = TeamReferenceSerializer()
    away_team = TeamReferenceSerializer()
    final_home_score = serializers.IntegerField()
    final_away_score = serializers.IntegerField()
    quarter_scores = QuarterScoreInlineSerializer(many=True)
    drives = DriveSummarySerializer()
