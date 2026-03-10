from django.test import TestCase

from archive.models import League, Level, Season


class LeagueModelTest(TestCase):
    def test_str(self):
        league = League(short_name="NFL", long_name="National Football League")
        assert str(league) == "NFL"

    def test_default_level(self):
        league = League(short_name="XFL", long_name="XFL")
        assert league.level == Level.OTHER


class SeasonModelTest(TestCase):
    def test_str_with_label(self):
        league = League.objects.create(
            short_name="NFL", long_name="National Football League", level=Level.PRO
        )
        season = Season.objects.create(league=league, year=2024, label="2024")
        assert str(season) == "NFL 2024"

    def test_str_without_label(self):
        league = League.objects.create(
            short_name="NFL", long_name="National Football League", level=Level.PRO
        )
        season = Season.objects.create(league=league, year=2024)
        assert str(season) == "NFL 2024"
