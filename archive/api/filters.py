import django_filters
from django.db.models import Q

from archive.models import Game


class GameFilter(django_filters.FilterSet):
    season_year = django_filters.NumberFilter(field_name="season__year")
    league = django_filters.NumberFilter(field_name="league_id")
    team = django_filters.NumberFilter(method="filter_team")
    game_type = django_filters.CharFilter(field_name="game_type")
    week = django_filters.NumberFilter(field_name="week")
    date_from = django_filters.DateFilter(field_name="date_local", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date_local", lookup_expr="lte")
    has_assets = django_filters.BooleanFilter(method="filter_has_assets")

    class Meta:
        model = Game
        fields = []

    def filter_team(self, queryset, name, value):
        return queryset.filter(Q(home_team_id=value) | Q(away_team_id=value))

    def filter_has_assets(self, queryset, name, value):
        if value:
            return queryset.filter(assets__isnull=False).distinct()
        return queryset.filter(assets__isnull=True)
