from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase

from archive.models import (
    Acquisition,
    AssetTag,
    AssetType,
    Drive,
    Franchise,
    Game,
    GameCompleteness,
    GameType,
    League,
    Level,
    OrgUnit,
    PassingBoxscore,
    Play,
    PlayStat,
    QualityTier,
    QuarterScore,
    ReceivingBoxscore,
    Rights,
    RushingBoxscore,
    Season,
    Source,
    SourceType,
    Tag,
    Team,
    TeamAffiliation,
    TeamStandingsSnapshot,
    TeamVenueOccupancy,
    Venue,
    VideoAsset,
)

# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------


def make_league(**kwargs):
    defaults = {
        "short_name": "NFL",
        "long_name": "National Football League",
        "level": Level.PRO,
    }
    defaults.update(kwargs)
    return League.objects.create(**defaults)


def make_season(league=None, **kwargs):
    if league is None:
        league = make_league()
    defaults = {
        "league": league,
        "year": 2024,
        "label": "2024",
        "start_date": date(2024, 9, 5),
        "end_date": date(2025, 2, 9),
    }
    defaults.update(kwargs)
    return Season.objects.create(**defaults)


def make_team(name="Pittsburgh Steelers", short_name="PIT", **kwargs):
    defaults = {"name": name, "short_name": short_name, "city": "Pittsburgh"}
    defaults.update(kwargs)
    return Team.objects.create(**defaults)


def make_venue(**kwargs):
    defaults = {
        "name": "Acrisure Stadium",
        "city": "Pittsburgh",
        "state": "PA",
        "capacity": 68400,
    }
    defaults.update(kwargs)
    return Venue.objects.create(**defaults)


def make_game(league=None, season=None, home_team=None, away_team=None, **kwargs):
    if league is None:
        league = make_league()
    if season is None:
        season = make_season(league=league)
    if home_team is None:
        home_team = make_team()
    if away_team is None:
        away_team = make_team(name="Cleveland Browns", short_name="CLE")
    defaults = {
        "league": league,
        "season": season,
        "home_team": home_team,
        "away_team": away_team,
        "date_local": date(2024, 9, 8),
        "game_type": GameType.REG,
    }
    defaults.update(kwargs)
    return Game.objects.create(**defaults)


# ---------------------------------------------------------------
# League
# ---------------------------------------------------------------


class LeagueModelTest(TestCase):
    def test_str(self):
        league = League(short_name="NFL", long_name="National Football League")
        assert str(league) == "NFL"

    def test_default_level(self):
        league = League(short_name="XFL", long_name="XFL")
        assert league.level == Level.OTHER

    def test_unique_short_name(self):
        make_league()
        with self.assertRaises(IntegrityError):
            make_league(long_name="Duplicate League")

    def test_unique_long_name(self):
        make_league()
        with self.assertRaises(IntegrityError):
            make_league(short_name="NFL2")

    def test_bonus_data_default_null(self):
        league = make_league()
        assert league.bonus_data is None

    def test_external_ids_default_empty_dict(self):
        league = make_league()
        assert league.external_ids == {}


# ---------------------------------------------------------------
# Season
# ---------------------------------------------------------------


class SeasonModelTest(TestCase):
    def test_str_with_label(self):
        league = make_league()
        season = make_season(league=league)
        assert str(season) == "NFL 2024"

    def test_str_without_label(self):
        league = make_league()
        season = Season.objects.create(league=league, year=2024)
        assert str(season) == "NFL 2024"

    def test_unique_league_year(self):
        league = make_league()
        make_season(league=league)
        with self.assertRaises(IntegrityError):
            make_season(league=league, label="Duplicate")


class SeasonGetTeamsTest(TestCase):
    """Tests for Season.get_teams() temporal query logic."""

    def setUp(self):
        self.league = make_league()
        self.season = make_season(
            league=self.league,
            start_date=date(2024, 9, 5),
            end_date=date(2025, 2, 9),
        )
        self.team = make_team()
        self.conf = OrgUnit.objects.create(
            league=self.league,
            short_name="AFC",
            long_name="American Football Conference",
            org_type=OrgUnit.OrgType.CONFERENCE,
        )

    def test_affiliation_with_no_dates_matches(self):
        """Affiliation with null start/end dates always matches."""
        TeamAffiliation.objects.create(
            team=self.team, org_unit=self.conf, start_date=None, end_date=None
        )
        teams = self.season.get_teams()
        assert self.team in teams

    def test_affiliation_active_during_season(self):
        """Affiliation that spans the season is included."""
        TeamAffiliation.objects.create(
            team=self.team,
            org_unit=self.conf,
            start_date=date(2020, 1, 1),
            end_date=None,
        )
        teams = self.season.get_teams()
        assert self.team in teams

    def test_affiliation_ended_before_season(self):
        """Affiliation that ended before season start is excluded."""
        TeamAffiliation.objects.create(
            team=self.team,
            org_unit=self.conf,
            start_date=date(2020, 1, 1),
            end_date=date(2024, 8, 1),
        )
        teams = self.season.get_teams()
        assert self.team not in teams

    def test_affiliation_started_after_season(self):
        """Affiliation that started after season end is excluded."""
        TeamAffiliation.objects.create(
            team=self.team,
            org_unit=self.conf,
            start_date=date(2025, 3, 1),
            end_date=None,
        )
        teams = self.season.get_teams()
        assert self.team not in teams

    def test_affiliation_overlaps_season_start(self):
        """Affiliation that ends mid-season is included."""
        TeamAffiliation.objects.create(
            team=self.team,
            org_unit=self.conf,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 10, 1),
        )
        teams = self.season.get_teams()
        assert self.team in teams

    def test_affiliation_from_different_league_excluded(self):
        """Affiliation in a different league is not returned."""
        other_league = make_league(short_name="XFL", long_name="XFL")
        other_conf = OrgUnit.objects.create(
            league=other_league,
            short_name="EAS",
            long_name="Eastern Conference",
            org_type=OrgUnit.OrgType.CONFERENCE,
        )
        TeamAffiliation.objects.create(
            team=self.team, org_unit=other_conf, start_date=None, end_date=None
        )
        teams = self.season.get_teams()
        assert self.team not in teams

    def test_multiple_teams_returned(self):
        """Multiple teams with valid affiliations are all returned."""
        team2 = make_team(name="Baltimore Ravens", short_name="BAL")
        TeamAffiliation.objects.create(
            team=self.team, org_unit=self.conf, start_date=None, end_date=None
        )
        TeamAffiliation.objects.create(
            team=team2, org_unit=self.conf, start_date=None, end_date=None
        )
        teams = self.season.get_teams()
        assert len(teams) == 2
        assert self.team in teams
        assert team2 in teams


# ---------------------------------------------------------------
# Franchise — temporal team tracking
# ---------------------------------------------------------------


class FranchiseModelTest(TestCase):
    def setUp(self):
        self.league = make_league()
        self.franchise = Franchise.objects.create(name="Steelers", league=self.league)

    def test_str(self):
        assert str(self.franchise) == "Steelers (NFL)"

    def test_unique_league_name(self):
        with self.assertRaises(IntegrityError):
            Franchise.objects.create(name="Steelers", league=self.league)


class FranchiseCurrentTeamTest(TestCase):
    def setUp(self):
        self.league = make_league()
        self.franchise = Franchise.objects.create(name="Steelers", league=self.league)

    def test_current_team_returns_open_era(self):
        """current_team returns the team with no era_end_date."""
        old = make_team(
            name="Pittsburgh Steelers (old)",
            short_name="PIT1",
            franchise=self.franchise,
            era_start_date=date(1933, 7, 8),
            era_end_date=date(1999, 12, 31),
        )
        current = make_team(
            name="Pittsburgh Steelers",
            short_name="PIT",
            franchise=self.franchise,
            era_start_date=date(2000, 1, 1),
            era_end_date=None,
        )
        assert self.franchise.current_team == current
        assert self.franchise.current_team != old

    def test_current_team_none_when_all_eras_closed(self):
        """current_team returns None when all eras have end dates."""
        make_team(
            name="Pittsburgh Steelers",
            short_name="PIT",
            franchise=self.franchise,
            era_start_date=date(1933, 7, 8),
            era_end_date=date(1999, 12, 31),
        )
        assert self.franchise.current_team is None

    def test_current_team_none_when_no_teams(self):
        """current_team returns None for franchise with no teams."""
        assert self.franchise.current_team is None


class FranchiseTeamForDateTest(TestCase):
    def setUp(self):
        self.league = make_league()
        self.franchise = Franchise.objects.create(name="Commanders", league=self.league)
        self.era1 = make_team(
            name="Washington Redskins",
            short_name="WAS1",
            franchise=self.franchise,
            era_start_date=date(1937, 1, 1),
            era_end_date=date(2019, 12, 31),
        )
        self.era2 = make_team(
            name="Washington Football Team",
            short_name="WAS2",
            franchise=self.franchise,
            era_start_date=date(2020, 1, 1),
            era_end_date=date(2021, 12, 31),
        )
        self.era3 = make_team(
            name="Washington Commanders",
            short_name="WAS3",
            franchise=self.franchise,
            era_start_date=date(2022, 1, 1),
            era_end_date=None,
        )

    def test_returns_correct_era_for_historical_date(self):
        assert self.franchise.team_for_date(date(2015, 10, 1)) == self.era1

    def test_returns_correct_era_for_transition_period(self):
        assert self.franchise.team_for_date(date(2020, 6, 1)) == self.era2

    def test_returns_current_era_for_today(self):
        assert self.franchise.team_for_date(date(2024, 11, 1)) == self.era3

    def test_returns_none_for_date_before_all_eras(self):
        assert self.franchise.team_for_date(date(1900, 1, 1)) is None

    def test_boundary_date_matches_era_start(self):
        """Start date is inclusive."""
        assert self.franchise.team_for_date(date(2020, 1, 1)) == self.era2

    def test_boundary_date_matches_era_end(self):
        """End date is inclusive."""
        assert self.franchise.team_for_date(date(2019, 12, 31)) == self.era1

    def test_team_with_null_start_date(self):
        """A team with no start date matches any date before its end."""
        franchise = Franchise.objects.create(name="OG Team", league=self.league)
        team = make_team(
            name="Original Team",
            short_name="OG",
            franchise=franchise,
            era_start_date=None,
            era_end_date=date(2000, 12, 31),
        )
        assert franchise.team_for_date(date(1800, 1, 1)) == team


# ---------------------------------------------------------------
# Team
# ---------------------------------------------------------------


class TeamModelTest(TestCase):
    def test_str(self):
        team = Team(name="Pittsburgh Steelers")
        assert str(team) == "Pittsburgh Steelers"

    def test_is_current_era_true(self):
        team = Team(name="Test", era_end_date=None)
        assert team.is_current_era is True

    def test_is_current_era_false(self):
        team = Team(name="Test", era_end_date=date(2020, 1, 1))
        assert team.is_current_era is False


class TeamCurrentVenueTest(TestCase):
    def setUp(self):
        self.team = make_team()
        self.venue = make_venue()

    def test_returns_current_venue(self):
        """Team with an active occupancy returns the venue."""
        TeamVenueOccupancy.objects.create(
            team=self.team,
            venue=self.venue,
            start_date=date(2001, 8, 18),
            end_date=None,
        )
        assert self.team.current_venue == self.venue

    def test_returns_none_when_no_occupancies(self):
        assert self.team.current_venue is None

    def test_returns_none_when_all_occupancies_ended(self):
        """Past-only occupancies return None."""
        TeamVenueOccupancy.objects.create(
            team=self.team,
            venue=self.venue,
            start_date=date(1970, 7, 16),
            end_date=date(2000, 12, 16),
        )
        assert self.team.current_venue is None

    def test_returns_most_recent_venue(self):
        """When multiple active occupancies exist, the most recent start wins."""
        old_venue = make_venue(name="Three Rivers", city="Pittsburgh", state="PA")
        TeamVenueOccupancy.objects.create(
            team=self.team,
            venue=old_venue,
            start_date=date(1970, 7, 16),
            end_date=None,
        )
        TeamVenueOccupancy.objects.create(
            team=self.team,
            venue=self.venue,
            start_date=date(2001, 8, 18),
            end_date=None,
        )
        assert self.team.current_venue == self.venue

    @patch("archive.models.timezone")
    def test_venue_with_future_end_date_is_current(self, mock_tz):
        """A venue whose end_date is in the future still counts as current."""
        mock_tz.now.return_value.date.return_value = date(2024, 6, 1)
        TeamVenueOccupancy.objects.create(
            team=self.team,
            venue=self.venue,
            start_date=date(2001, 8, 18),
            end_date=date(2030, 12, 31),
        )
        assert self.team.current_venue == self.venue


# ---------------------------------------------------------------
# OrgUnit — hierarchical structure
# ---------------------------------------------------------------


class OrgUnitModelTest(TestCase):
    def test_str(self):
        league = make_league()
        org = OrgUnit(
            league=league,
            short_name="AFC",
            long_name="American Football Conference",
            org_type=OrgUnit.OrgType.CONFERENCE,
        )
        assert str(org) == "NFL: AFC (CONFERENCE)"

    def test_parent_child_hierarchy(self):
        league = make_league()
        conf = OrgUnit.objects.create(
            league=league,
            short_name="AFC",
            long_name="American Football Conference",
            org_type=OrgUnit.OrgType.CONFERENCE,
        )
        div = OrgUnit.objects.create(
            league=league,
            short_name="AFCN",
            long_name="AFC North",
            org_type=OrgUnit.OrgType.DIVISION,
            parent=conf,
        )
        assert div.parent == conf
        assert conf.children.first() == div

    def test_unique_constraint(self):
        league = make_league()
        OrgUnit.objects.create(
            league=league,
            short_name="AFC",
            long_name="American Football Conference",
            org_type=OrgUnit.OrgType.CONFERENCE,
        )
        with self.assertRaises(IntegrityError):
            OrgUnit.objects.create(
                league=league,
                short_name="AFC",
                long_name="Another AFC",
                org_type=OrgUnit.OrgType.CONFERENCE,
            )


# ---------------------------------------------------------------
# TeamAffiliation
# ---------------------------------------------------------------


class TeamAffiliationModelTest(TestCase):
    def test_str_with_season(self):
        league = make_league()
        season = make_season(league=league)
        team = make_team()
        org = OrgUnit.objects.create(
            league=league,
            short_name="AFCN",
            long_name="AFC North",
            org_type=OrgUnit.OrgType.DIVISION,
        )
        aff = TeamAffiliation.objects.create(team=team, org_unit=org, season=season)
        assert "Pittsburgh Steelers" in str(aff)
        assert "AFCN" in str(aff)

    def test_str_with_date_range(self):
        league = make_league()
        team = make_team()
        org = OrgUnit.objects.create(
            league=league,
            short_name="AFCN",
            long_name="AFC North",
            org_type=OrgUnit.OrgType.DIVISION,
        )
        aff = TeamAffiliation.objects.create(
            team=team,
            org_unit=org,
            start_date=date(2020, 1, 1),
            end_date=None,
        )
        assert "present" in str(aff)

    def test_unique_team_org_season(self):
        league = make_league()
        season = make_season(league=league)
        team = make_team()
        org = OrgUnit.objects.create(
            league=league,
            short_name="AFCN",
            long_name="AFC North",
            org_type=OrgUnit.OrgType.DIVISION,
        )
        TeamAffiliation.objects.create(team=team, org_unit=org, season=season)
        with self.assertRaises(IntegrityError):
            TeamAffiliation.objects.create(team=team, org_unit=org, season=season)


# ---------------------------------------------------------------
# Venue & TeamVenueOccupancy
# ---------------------------------------------------------------


class VenueModelTest(TestCase):
    def test_str(self):
        venue = Venue(name="Acrisure Stadium")
        assert str(venue) == "Acrisure Stadium"

    def test_unique_name_city_state(self):
        make_venue()
        with self.assertRaises(IntegrityError):
            make_venue()


class TeamVenueOccupancyModelTest(TestCase):
    def test_str(self):
        team = make_team()
        venue = make_venue()
        occ = TeamVenueOccupancy(
            team=team, venue=venue, start_date=date(2001, 8, 18), end_date=None
        )
        assert "present" in str(occ)
        assert "Pittsburgh Steelers" in str(occ)


# ---------------------------------------------------------------
# Game — constraints and behavior
# ---------------------------------------------------------------


class GameModelTest(TestCase):
    def setUp(self):
        self.league = make_league()
        self.season = make_season(league=self.league)
        self.home = make_team()
        self.away = make_team(name="Cleveland Browns", short_name="CLE")

    def test_str(self):
        game = make_game(
            league=self.league,
            season=self.season,
            home_team=self.home,
            away_team=self.away,
        )
        assert "Cleveland Browns @ Pittsburgh Steelers" in str(game)

    def test_home_away_distinct_constraint(self):
        """A team cannot play itself."""
        with self.assertRaises(IntegrityError):
            make_game(
                league=self.league,
                season=self.season,
                home_team=self.home,
                away_team=self.home,
            )

    def test_unique_game_identity(self):
        """Same league/season/date/teams cannot be duplicated."""
        make_game(
            league=self.league,
            season=self.season,
            home_team=self.home,
            away_team=self.away,
        )
        with self.assertRaises(IntegrityError):
            make_game(
                league=self.league,
                season=self.season,
                home_team=self.home,
                away_team=self.away,
            )

    def test_scores_nullable(self):
        game = make_game(
            league=self.league,
            season=self.season,
            home_team=self.home,
            away_team=self.away,
        )
        assert game.final_home_score is None
        assert game.final_away_score is None

    def test_default_game_type(self):
        game = Game(
            league=self.league,
            season=self.season,
            home_team=self.home,
            away_team=self.away,
            date_local=date(2024, 9, 8),
        )
        assert game.game_type == GameType.REG


# ---------------------------------------------------------------
# QuarterScore
# ---------------------------------------------------------------


class QuarterScoreModelTest(TestCase):
    def setUp(self):
        self.league = make_league()
        self.season = make_season(league=self.league)
        self.home = make_team()
        self.away = make_team(name="Cleveland Browns", short_name="CLE")
        self.game = make_game(
            league=self.league,
            season=self.season,
            home_team=self.home,
            away_team=self.away,
        )

    def test_str(self):
        qs = QuarterScore.objects.create(
            game=self.game, team=self.home, period=1, points=7
        )
        assert "Q1: 7" in str(qs)

    def test_unique_game_team_period(self):
        QuarterScore.objects.create(game=self.game, team=self.home, period=1, points=7)
        with self.assertRaises(IntegrityError):
            QuarterScore.objects.create(
                game=self.game, team=self.home, period=1, points=10
            )

    def test_full_game_scoring(self):
        """Create quarter scores for a complete game and verify totals."""
        home_scores = [7, 3, 14, 0]
        away_scores = [0, 10, 0, 7]
        for period, points in enumerate(home_scores, start=1):
            QuarterScore.objects.create(
                game=self.game, team=self.home, period=period, points=points
            )
        for period, points in enumerate(away_scores, start=1):
            QuarterScore.objects.create(
                game=self.game, team=self.away, period=period, points=points
            )
        from django.db.models import Sum

        home_total = QuarterScore.objects.filter(
            game=self.game, team=self.home
        ).aggregate(total=Sum("points"))["total"]
        away_total = QuarterScore.objects.filter(
            game=self.game, team=self.away
        ).aggregate(total=Sum("points"))["total"]
        assert home_total == 24
        assert away_total == 17


# ---------------------------------------------------------------
# TeamStandingsSnapshot
# ---------------------------------------------------------------


class TeamStandingsSnapshotTest(TestCase):
    def setUp(self):
        self.league = make_league()
        self.season = make_season(league=self.league)
        self.team = make_team()

    def test_str(self):
        snap = TeamStandingsSnapshot.objects.create(
            team=self.team,
            season=self.season,
            week=5,
            overall_wins=3,
            overall_losses=2,
            overall_ties=0,
        )
        assert "Wk5: 3-2-0" in str(snap)

    def test_unique_team_season_week(self):
        TeamStandingsSnapshot.objects.create(team=self.team, season=self.season, week=1)
        with self.assertRaises(IntegrityError):
            TeamStandingsSnapshot.objects.create(
                team=self.team, season=self.season, week=1
            )

    def test_weekly_progression(self):
        """Standings snapshots can track week-over-week progression."""
        for week in range(1, 4):
            TeamStandingsSnapshot.objects.create(
                team=self.team,
                season=self.season,
                week=week,
                overall_wins=week,
                overall_losses=0,
                streak_length=week,
                streak_type="W",
            )
        latest = (
            TeamStandingsSnapshot.objects.filter(team=self.team, season=self.season)
            .order_by("-week")
            .first()
        )
        assert latest.week == 3
        assert latest.overall_wins == 3
        assert latest.streak_type == "W"

    def test_clinch_and_elimination_flags(self):
        snap = TeamStandingsSnapshot.objects.create(
            team=self.team,
            season=self.season,
            week=18,
            clinched_playoff=True,
            clinched_division=True,
            clinched_bye=False,
            eliminated=False,
        )
        assert snap.clinched_playoff is True
        assert snap.clinched_division is True
        assert snap.eliminated is False


# ---------------------------------------------------------------
# Drive
# ---------------------------------------------------------------


class DriveModelTest(TestCase):
    def setUp(self):
        self.league = make_league()
        self.season = make_season(league=self.league)
        self.home = make_team()
        self.away = make_team(name="Cleveland Browns", short_name="CLE")
        self.game = make_game(
            league=self.league,
            season=self.season,
            home_team=self.home,
            away_team=self.away,
        )

    def test_str(self):
        drive = Drive.objects.create(
            game=self.game,
            sequence=1,
            team=self.home,
            ended_description="Touchdown",
        )
        assert "Drive 1: Touchdown" in str(drive)

    def test_unique_game_sequence(self):
        Drive.objects.create(game=self.game, sequence=1)
        with self.assertRaises(IntegrityError):
            Drive.objects.create(game=self.game, sequence=1)

    def test_drive_ordering(self):
        Drive.objects.create(game=self.game, sequence=3)
        Drive.objects.create(game=self.game, sequence=1)
        Drive.objects.create(game=self.game, sequence=2)
        drives = list(Drive.objects.filter(game=self.game))
        assert [d.sequence for d in drives] == [1, 2, 3]


# ---------------------------------------------------------------
# Play & PlayStat
# ---------------------------------------------------------------


class PlayModelTest(TestCase):
    def setUp(self):
        self.league = make_league()
        self.season = make_season(league=self.league)
        self.home = make_team()
        self.away = make_team(name="Cleveland Browns", short_name="CLE")
        self.game = make_game(
            league=self.league,
            season=self.season,
            home_team=self.home,
            away_team=self.away,
        )

    def test_str(self):
        play = Play.objects.create(
            game=self.game, play_id=100, sequence=1.0, play_type="PASS"
        )
        assert "Play 100: PASS" in str(play)

    def test_unique_game_play_id(self):
        Play.objects.create(game=self.game, play_id=1, sequence=1.0)
        with self.assertRaises(IntegrityError):
            Play.objects.create(game=self.game, play_id=1, sequence=2.0)

    def test_play_ordering(self):
        Play.objects.create(game=self.game, play_id=3, sequence=3.0)
        Play.objects.create(game=self.game, play_id=1, sequence=1.0)
        Play.objects.create(game=self.game, play_id=2, sequence=2.0)
        plays = list(Play.objects.filter(game=self.game))
        assert [p.sequence for p in plays] == [1.0, 2.0, 3.0]


class PlayStatModelTest(TestCase):
    def test_str(self):
        league = make_league()
        season = make_season(league=league)
        home = make_team()
        away = make_team(name="Cleveland Browns", short_name="CLE")
        game = make_game(league=league, season=season, home_team=home, away_team=away)
        play = Play.objects.create(game=game, play_id=1, sequence=1.0)
        stat = PlayStat.objects.create(
            play=play,
            player_name="T.J. Watt",
            stat_id=2,
            yards=0,
            team_abbr="PIT",
        )
        assert "T.J. Watt" in str(stat)


# ---------------------------------------------------------------
# Boxscore models — stat aggregation
# ---------------------------------------------------------------


class BoxscoreAggregationTest(TestCase):
    """Tests for boxscore stat creation and aggregation queries."""

    def setUp(self):
        self.league = make_league()
        self.season = make_season(league=self.league)
        self.home = make_team()
        self.away = make_team(name="Cleveland Browns", short_name="CLE")
        self.game = make_game(
            league=self.league,
            season=self.season,
            home_team=self.home,
            away_team=self.away,
        )

    def test_passing_boxscore_creation(self):
        stat = PassingBoxscore.objects.create(
            game=self.game,
            team=self.home,
            side="home",
            player_name="Kenny Pickett",
            jersey_number=8,
            position="QB",
            attempts=30,
            completions=20,
            completion_pct=66.7,
            yards=250,
            touchdowns=2,
            interceptions=1,
            qb_rating=95.5,
        )
        assert (
            str(stat)
            == "Kenny Pickett (QB) - 2024-09-08 Cleveland Browns @ Pittsburgh Steelers"
        )
        assert stat.completions == 20

    def test_rushing_boxscore_creation(self):
        stat = RushingBoxscore.objects.create(
            game=self.game,
            team=self.home,
            side="home",
            player_name="Najee Harris",
            jersey_number=22,
            position="RB",
            attempts=18,
            yards=85,
            avg_yards=4.7,
            touchdowns=1,
        )
        assert stat.yards == 85

    def test_receiving_boxscore_creation(self):
        stat = ReceivingBoxscore.objects.create(
            game=self.game,
            team=self.home,
            side="home",
            player_name="George Pickens",
            jersey_number=14,
            position="WR",
            receptions=6,
            yards=120,
            touchdowns=1,
            targets=9,
        )
        assert stat.receptions == 6

    def test_team_passing_aggregation(self):
        """Aggregate passing stats across multiple QBs in a game."""
        from django.db.models import Sum

        PassingBoxscore.objects.create(
            game=self.game,
            team=self.home,
            side="home",
            player_name="QB1",
            attempts=25,
            completions=18,
            yards=200,
            touchdowns=1,
        )
        PassingBoxscore.objects.create(
            game=self.game,
            team=self.home,
            side="home",
            player_name="QB2",
            attempts=5,
            completions=3,
            yards=45,
            touchdowns=1,
        )
        agg = PassingBoxscore.objects.filter(game=self.game, team=self.home).aggregate(
            total_yards=Sum("yards"),
            total_tds=Sum("touchdowns"),
            total_attempts=Sum("attempts"),
            total_completions=Sum("completions"),
        )
        assert agg["total_yards"] == 245
        assert agg["total_tds"] == 2
        assert agg["total_attempts"] == 30
        assert agg["total_completions"] == 21

    def test_team_rushing_aggregation(self):
        """Aggregate rushing stats across multiple rushers."""
        from django.db.models import Sum

        RushingBoxscore.objects.create(
            game=self.game,
            team=self.home,
            side="home",
            player_name="RB1",
            attempts=15,
            yards=75,
            touchdowns=1,
        )
        RushingBoxscore.objects.create(
            game=self.game,
            team=self.home,
            side="home",
            player_name="RB2",
            attempts=8,
            yards=40,
            touchdowns=0,
        )
        agg = RushingBoxscore.objects.filter(game=self.game, team=self.home).aggregate(
            total_yards=Sum("yards"),
            total_tds=Sum("touchdowns"),
        )
        assert agg["total_yards"] == 115
        assert agg["total_tds"] == 1

    def test_game_total_offense_aggregation(self):
        """Combine passing + rushing for total yards in a game."""
        from django.db.models import Sum

        PassingBoxscore.objects.create(
            game=self.game,
            team=self.home,
            side="home",
            player_name="QB1",
            yards=250,
        )
        RushingBoxscore.objects.create(
            game=self.game,
            team=self.home,
            side="home",
            player_name="RB1",
            yards=100,
        )
        pass_yards = (
            PassingBoxscore.objects.filter(game=self.game, team=self.home).aggregate(
                total=Sum("yards")
            )["total"]
            or 0
        )
        rush_yards = (
            RushingBoxscore.objects.filter(game=self.game, team=self.home).aggregate(
                total=Sum("yards")
            )["total"]
            or 0
        )
        assert pass_yards + rush_yards == 350


# ---------------------------------------------------------------
# Holdings — Source, Acquisition, VideoAsset
# ---------------------------------------------------------------


class SourceModelTest(TestCase):
    def test_str(self):
        source = Source(name="NFL+", source_type=SourceType.STREAMING)
        assert str(source) == "NFL+ (STREAMING)"


class AcquisitionModelTest(TestCase):
    def test_str(self):
        source = Source.objects.create(name="NFL+", source_type=SourceType.STREAMING)
        acq = Acquisition.objects.create(
            source=source,
            acquired_on=date(2024, 9, 1),
            cost_usd=Decimal("6.99"),
            rights=Rights.PERSONAL_ONLY,
        )
        assert "NFL+" in str(acq)
        assert "2024-09-01" in str(acq)


class VideoAssetModelTest(TestCase):
    def setUp(self):
        self.league = make_league()
        self.season = make_season(league=self.league)
        self.home = make_team()
        self.away = make_team(name="Cleveland Browns", short_name="CLE")
        self.game = make_game(
            league=self.league,
            season=self.season,
            home_team=self.home,
            away_team=self.away,
        )

    def test_str(self):
        asset = VideoAsset.objects.create(
            game=self.game,
            asset_type=AssetType.FULL,
            file_path="/data/games/pit_cle_2024.mkv",
            quality_tier=QualityTier.A,
        )
        assert "[FULL]" in str(asset)
        assert "A" in str(asset)

    def test_default_quality_tier(self):
        asset = VideoAsset(game=self.game, file_path="/tmp/test.mkv")
        assert asset.quality_tier == QualityTier.C

    def test_unique_preferred_per_game(self):
        """Only one preferred asset per game is allowed."""
        VideoAsset.objects.create(
            game=self.game,
            asset_type=AssetType.FULL,
            file_path="/data/v1.mkv",
            is_preferred=True,
        )
        with self.assertRaises(IntegrityError):
            VideoAsset.objects.create(
                game=self.game,
                asset_type=AssetType.CONDENSED,
                file_path="/data/v2.mkv",
                is_preferred=True,
            )

    def test_multiple_non_preferred_assets(self):
        """Multiple non-preferred assets per game are fine."""
        VideoAsset.objects.create(
            game=self.game,
            asset_type=AssetType.FULL,
            file_path="/data/v1.mkv",
            is_preferred=False,
        )
        VideoAsset.objects.create(
            game=self.game,
            asset_type=AssetType.CONDENSED,
            file_path="/data/v2.mkv",
            is_preferred=False,
        )
        assert self.game.assets.count() == 2

    def test_preferred_across_different_games(self):
        """Different games can each have their own preferred asset."""
        game2 = make_game(
            league=self.league,
            season=self.season,
            home_team=self.home,
            away_team=self.away,
            date_local=date(2024, 10, 6),
        )
        VideoAsset.objects.create(
            game=self.game,
            file_path="/data/v1.mkv",
            is_preferred=True,
        )
        VideoAsset.objects.create(
            game=game2,
            file_path="/data/v2.mkv",
            is_preferred=True,
        )
        assert VideoAsset.objects.filter(is_preferred=True).count() == 2


# ---------------------------------------------------------------
# Tag & AssetTag
# ---------------------------------------------------------------


class TagModelTest(TestCase):
    def test_str(self):
        tag = Tag(name="classic")
        assert str(tag) == "classic"

    def test_unique_name(self):
        Tag.objects.create(name="classic")
        with self.assertRaises(IntegrityError):
            Tag.objects.create(name="classic")


class AssetTagModelTest(TestCase):
    def test_unique_asset_tag(self):
        league = make_league()
        season = make_season(league=league)
        home = make_team()
        away = make_team(name="Cleveland Browns", short_name="CLE")
        game = make_game(league=league, season=season, home_team=home, away_team=away)
        asset = VideoAsset.objects.create(game=game, file_path="/data/v1.mkv")
        tag = Tag.objects.create(name="classic")
        AssetTag.objects.create(asset=asset, tag=tag)
        with self.assertRaises(IntegrityError):
            AssetTag.objects.create(asset=asset, tag=tag)


# ---------------------------------------------------------------
# GameCompleteness
# ---------------------------------------------------------------


class GameCompletenessModelTest(TestCase):
    def setUp(self):
        self.league = make_league()
        self.season = make_season(league=self.league)
        self.home = make_team()
        self.away = make_team(name="Cleveland Browns", short_name="CLE")
        self.game = make_game(
            league=self.league,
            season=self.season,
            home_team=self.home,
            away_team=self.away,
        )

    def test_str(self):
        gc = GameCompleteness.objects.create(
            game=self.game,
            scope="NFL_ALL",
            status=GameCompleteness.Status.COMPLETE,
        )
        assert "NFL_ALL" in str(gc)
        assert "COMPLETE" in str(gc)

    def test_unique_game_scope(self):
        GameCompleteness.objects.create(
            game=self.game,
            scope="NFL_ALL",
            status=GameCompleteness.Status.MISSING,
        )
        with self.assertRaises(IntegrityError):
            GameCompleteness.objects.create(
                game=self.game,
                scope="NFL_ALL",
                status=GameCompleteness.Status.COMPLETE,
            )

    def test_multiple_scopes_per_game(self):
        """A game can have completeness tracked in multiple scopes."""
        GameCompleteness.objects.create(
            game=self.game,
            scope="NFL_ALL",
            status=GameCompleteness.Status.COMPLETE,
            has_full=True,
        )
        GameCompleteness.objects.create(
            game=self.game,
            scope="STEELERS_ALL",
            status=GameCompleteness.Status.COMPLETE,
            has_full=True,
            has_condensed=True,
        )
        assert self.game.completeness.count() == 2

    def test_scope_status_filtering(self):
        """Filter completeness by scope and status."""
        game2 = make_game(
            league=self.league,
            season=self.season,
            home_team=self.home,
            away_team=self.away,
            date_local=date(2024, 10, 6),
        )
        GameCompleteness.objects.create(
            game=self.game,
            scope="NFL_ALL",
            status=GameCompleteness.Status.COMPLETE,
        )
        GameCompleteness.objects.create(
            game=game2,
            scope="NFL_ALL",
            status=GameCompleteness.Status.MISSING,
        )
        complete = GameCompleteness.objects.filter(
            scope="NFL_ALL", status=GameCompleteness.Status.COMPLETE
        )
        missing = GameCompleteness.objects.filter(
            scope="NFL_ALL", status=GameCompleteness.Status.MISSING
        )
        assert complete.count() == 1
        assert missing.count() == 1
