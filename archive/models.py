from typing import List

from django.db import models
from django.db.models import Q
from django.utils import timezone

# -------------------------
# Enums / Choices
# -------------------------


class Level(models.TextChoices):
    HS = "HS", "High School"
    COLLEGE = "COLLEGE", "College"
    PRO = "PRO", "Professional"
    OTHER = "OTHER", "Other"


class GameType(models.TextChoices):
    REG = "REG", "Regular Season"
    CONF = "CONF", "Conference Championship"
    POST = "POST", "Postseason"
    BOWL = "BOWL", "Bowl"
    PLAYOFF = "PLAYOFF", "Playoff"
    EXHIB = "EXHIB", "Exhibition/Spring"
    OTHER = "OTHER", "Other"


class AssetType(models.TextChoices):
    FULL = "FULL", "Full Broadcast"
    CONDENSED = "CONDENSED", "Condensed"
    COACHES = "COACHES", "Coaches Film"
    ALL22 = "ALL22", "All-22"
    HIGHLIGHTS = "HIGHLIGHTS", "Highlights"
    RADIO = "RADIO", "Radio Audio"
    OTHER = "OTHER", "Other"


class Rights(models.TextChoices):
    PERSONAL_ONLY = "PERSONAL_ONLY", "Personal use only"
    SHAREABLE = "SHAREABLE", "Shareable"
    UNKNOWN = "UNKNOWN", "Unknown"


class QualityTier(models.TextChoices):
    A = "A", "Tier A (Best Available)"
    B = "B", "Tier B (Very Good)"
    C = "C", "Tier C (Good)"
    D = "D", "Tier D (Filler)"


class SourceType(models.TextChoices):
    STREAMING = "STREAMING", "Streaming Service"
    YOUTUBE = "YOUTUBE", "YouTube"
    PHYSICAL = "PHYSICAL", "Physical Media (DVD/Blu-ray/etc.)"
    DVR = "DVR", "Personal Capture (DVR/OTA/Cable)"
    FILE_TRADE = "FILE_TRADE", "Other File Source"
    OTHER = "OTHER", "Other"


# -------------------------
# Catalog (what exists)
# -------------------------


class GamBaseModel(models.Model):
    bonus_data = models.JSONField(
        null=True,
        help_text="Data supplied by third party providers that we haven't decided how or if to use yet.",
    )
    external_ids = models.JSONField(blank=True, default=dict)

    class Meta:
        abstract = True


class League(GamBaseModel):
    short_name = models.CharField(max_length=10, unique=True)
    long_name = models.CharField(max_length=120, unique=True)
    level = models.CharField(max_length=16, choices=Level.choices, default=Level.OTHER)
    country = models.CharField(max_length=60, default="US")  # ISO-3166-1 alpha-2
    notes = models.TextField(blank=True, default="")

    def __str__(self) -> str:
        return self.short_name


class Season(GamBaseModel):
    league = models.ForeignKey(League, on_delete=models.PROTECT, related_name="seasons")
    year = models.IntegerField()  # e.g. 2025
    label = models.CharField(
        max_length=40, blank=True, default=""
    )  # "2025", "2024-25", etc.
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["league", "year"], name="uniq_season_league_year"
            )
        ]

    def __str__(self) -> str:
        return f"{self.league.short_name} {self.label or self.year}"

    def get_teams(self) -> List[Team]:
        affiliations = TeamAffiliation.objects.select_related("team").filter(
            # Affiliation started before the season began
            Q(start_date__isnull=True) | Q(start_date__lte=self.end_date),
            Q(end_date__isnull=True) | Q(end_date__gte=self.start_date),
            org_unit__league=self.league,
        )
        return [ta.team for ta in affiliations]


class Franchise(GamBaseModel):
    """Groups era-specific Team records under a single franchise identity."""

    name = models.CharField(max_length=160)
    league = models.ForeignKey(
        League, on_delete=models.PROTECT, related_name="franchises"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["league", "name"], name="uniq_franchise_league_name"
            )
        ]
        verbose_name_plural = "franchises"

    def __str__(self):
        return f"{self.name} ({self.league.short_name})"

    @property
    def current_team(self):
        return self.teams.filter(era_end_date__isnull=True).first()

    def team_for_date(self, target_date):
        return self.teams.filter(
            Q(era_start_date__isnull=True) | Q(era_start_date__lte=target_date),
            Q(era_end_date__isnull=True) | Q(era_end_date__gte=target_date),
        ).first()


class Team(GamBaseModel):
    """
    Single table across all levels/leagues.
    League-specific org concepts (conference/division/classification/etc.)
    should be modeled via TeamAffiliation (below).
    """

    franchise = models.ForeignKey(
        Franchise,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="teams",
    )
    name = models.CharField(max_length=140)  # "Georgia", "Pittsburgh Steelers"
    alternate_name = models.CharField(max_length=140, null=True)
    short_name = models.CharField(max_length=40, blank=True, default="")  # "UGA", "PIT"
    city = models.CharField(max_length=80, blank=True, default="")
    era_start_date = models.DateField(null=True, blank=True)
    era_end_date = models.DateField(null=True, blank=True)
    state = models.CharField(max_length=60, blank=True, default="", null=True)
    country = models.CharField(max_length=60, default="US")
    # Useful for HS + college:
    school_name = models.CharField(max_length=160, blank=True, default="")
    mascot = models.CharField(max_length=80, blank=True, default="")

    logo = models.ImageField(upload_to="teams/logos/", null=True)
    primary_color = models.CharField(max_length=6, null=True)
    secondary_color = models.CharField(max_length=6, null=True)
    tertiary_color = models.CharField(max_length=6, null=True)
    additional_colors = models.JSONField(null=True)

    class Meta:
        # Not truly unique globally, but this helps reduce duplicates.
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["short_name"]),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def is_current_era(self):
        return self.era_end_date is None

    @property
    def current_venue(self):
        today = timezone.now().date()
        occupancy = (
            self.venue_occupancies.filter(
                Q(end_date__isnull=True) | Q(end_date__gte=today)
            )
            .order_by("-start_date")
            .select_related("venue")
            .first()
        )
        return occupancy.venue if occupancy else None


class OrgUnit(GamBaseModel):
    """
    A flexible container for "conference", "division", "region", "classification", etc.
    Examples:
      - NCAA: SEC, Big Ten, ACC, etc. (type=CONFERENCE)
      - NFL: AFC North (type=DIVISION), AFC (type=CONFERENCE)
      - HS: GHSA AAAAAAA (type=CLASSIFICATION), Region 8 (type=REGION)
    Scoped to a league.
    """

    class OrgType(models.TextChoices):
        CONFERENCE = "CONFERENCE", "Conference"
        DIVISION = "DIVISION", "Division"
        REGION = "REGION", "Region"
        CLASSIFICATION = "CLASSIFICATION", "Classification"
        LEAGUE_TIER = "LEAGUE_TIER", "League Tier"
        OTHER = "OTHER", "Other"

    league = models.ForeignKey(
        League, on_delete=models.PROTECT, related_name="org_units"
    )
    short_name = models.CharField(max_length=10)
    long_name = models.CharField(max_length=120)
    org_type = models.CharField(
        max_length=20, choices=OrgType.choices, default=OrgType.OTHER
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["league", "org_type", "short_name"], name="uniq_orgunit_scope"
            )
        ]
        indexes = [
            models.Index(fields=["league", "org_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.league.short_name}: {self.short_name} ({self.org_type})"


class TeamAffiliation(GamBaseModel):
    """
    Many-to-many between Team and OrgUnit with optional season scoping.
    Supports realignment over time.
    """

    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="affiliations"
    )
    org_unit = models.ForeignKey(
        OrgUnit, on_delete=models.PROTECT, related_name="team_links"
    )

    # Option A: attach to a Season (simple)
    season = models.ForeignKey(
        Season,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="team_affiliations",
    )

    # Option B: date range (more precise, optional)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["team", "org_unit", "season"], name="uniq_team_orgunit_season"
            )
        ]

    def __str__(self) -> str:
        scope = self.season or f"{self.start_date} - {self.end_date or 'present'}"
        return f"{self.team} → {self.org_unit} ({scope})"


class Venue(GamBaseModel):
    name = models.CharField(max_length=160)
    city = models.CharField(max_length=80, blank=True, default="")
    state = models.CharField(max_length=60, blank=True, default="", null=True)
    country = models.CharField(max_length=60, default="US")
    capacity = models.IntegerField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name", "city", "state"], name="uniq_venue_city_state"
            )
        ]

    def __str__(self) -> str:
        return self.name


class TeamVenueOccupancy(GamBaseModel):
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="venue_occupancies"
    )
    venue = models.ForeignKey(
        Venue, on_delete=models.PROTECT, related_name="team_occupancies"
    )

    start_date = models.DateField(null=True)
    end_date = models.DateField(null=True)

    def __str__(self) -> str:
        end = self.end_date or "present"
        return f"{self.team} @ {self.venue} ({self.start_date} - {end})"


class Game(GamBaseModel):
    league = models.ForeignKey(League, on_delete=models.PROTECT, related_name="games")
    season = models.ForeignKey(Season, on_delete=models.PROTECT, related_name="games")
    ordinal = models.IntegerField(null=True)
    date_local = models.DateField()
    kickoff_time_local = models.TimeField(null=True, blank=True)

    week = models.IntegerField(null=True)
    game_type = models.CharField(
        max_length=16, choices=GameType.choices, default=GameType.REG
    )
    competition_name = models.CharField(
        max_length=160, blank=True, default=""
    )  # "Rose Bowl", "SEC Championship", etc.

    neutral_site = models.BooleanField(default=False)
    venue = models.ForeignKey(
        Venue, null=True, blank=True, on_delete=models.PROTECT, related_name="games"
    )

    home_team = models.ForeignKey(
        Team, on_delete=models.PROTECT, related_name="home_games"
    )
    away_team = models.ForeignKey(
        Team, on_delete=models.PROTECT, related_name="away_games"
    )

    final_home_score = models.IntegerField(null=True, blank=True)
    final_away_score = models.IntegerField(null=True, blank=True)
    overtime_periods = models.IntegerField(null=True, blank=True)

    # Rankings at game time (AP Poll, per your requirement)
    ap_rank_home = models.IntegerField(null=True, blank=True)
    ap_rank_away = models.IntegerField(null=True, blank=True)

    broadcast_channel = models.CharField(max_length=40, blank=True, default="")
    status = models.CharField(max_length=20, blank=True, default="")
    kickoff_utc = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~Q(home_team=models.F("away_team")),
                name="chk_home_away_distinct",
            ),
            # This helps dedupe "same league/season/date/teams" games.
            models.UniqueConstraint(
                fields=["league", "season", "date_local", "home_team", "away_team"],
                name="uniq_game_identity_basic",
            ),
        ]
        indexes = [
            models.Index(fields=["league", "season", "date_local"]),
            models.Index(fields=["home_team", "date_local"]),
            models.Index(fields=["away_team", "date_local"]),
        ]

    def __str__(self) -> str:
        return f"{self.date_local} {self.away_team} @ {self.home_team}"


class QuarterScore(GamBaseModel):
    game = models.ForeignKey(
        Game, on_delete=models.CASCADE, related_name="quarter_scores"
    )
    team = models.ForeignKey(Team, on_delete=models.PROTECT)
    period = models.PositiveSmallIntegerField()  # 1-4 quarters, 5+ OT
    points = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["game", "team", "period"],
                name="uniq_quarter_score",
            ),
        ]
        ordering = ["game", "team", "period"]

    def __str__(self):
        return f"{self.game} - {self.team} Q{self.period}: {self.points}"


class TeamStandingsSnapshot(GamBaseModel):
    team = models.ForeignKey(
        Team, on_delete=models.PROTECT, related_name="standings_snapshots"
    )
    season = models.ForeignKey(
        Season, on_delete=models.PROTECT, related_name="standings_snapshots"
    )
    week = models.PositiveSmallIntegerField()

    overall_wins = models.PositiveSmallIntegerField(default=0)
    overall_losses = models.PositiveSmallIntegerField(default=0)
    overall_ties = models.PositiveSmallIntegerField(default=0)
    overall_win_pct = models.FloatField(default=0.0)
    points_for = models.PositiveIntegerField(default=0)
    points_against = models.PositiveIntegerField(default=0)

    conference_wins = models.PositiveSmallIntegerField(default=0)
    conference_losses = models.PositiveSmallIntegerField(default=0)
    conference_rank = models.PositiveSmallIntegerField(null=True, blank=True)

    division_wins = models.PositiveSmallIntegerField(default=0)
    division_losses = models.PositiveSmallIntegerField(default=0)
    division_rank = models.PositiveSmallIntegerField(null=True, blank=True)

    home_wins = models.PositiveSmallIntegerField(default=0)
    home_losses = models.PositiveSmallIntegerField(default=0)
    road_wins = models.PositiveSmallIntegerField(default=0)
    road_losses = models.PositiveSmallIntegerField(default=0)

    streak_length = models.PositiveSmallIntegerField(default=0)
    streak_type = models.CharField(max_length=1, blank=True, default="")  # W, L, T

    clinched_playoff = models.BooleanField(default=False)
    clinched_division = models.BooleanField(default=False)
    clinched_bye = models.BooleanField(default=False)
    eliminated = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["team", "season", "week"],
                name="uniq_standings_snapshot",
            ),
        ]
        indexes = [
            models.Index(fields=["season", "week"]),
        ]

    def __str__(self):
        return (
            f"{self.team} {self.season} Wk{self.week}: "
            f"{self.overall_wins}-{self.overall_losses}-{self.overall_ties}"
        )


class Drive(GamBaseModel):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="drives")
    sequence = models.PositiveSmallIntegerField()
    team = models.ForeignKey(
        Team, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    started_quarter = models.PositiveSmallIntegerField(null=True, blank=True)
    started_clock = models.CharField(max_length=8, blank=True, default="")
    started_description = models.CharField(max_length=60, blank=True, default="")
    started_yard_line = models.CharField(max_length=20, blank=True, default="")

    ended_quarter = models.PositiveSmallIntegerField(null=True, blank=True)
    ended_clock = models.CharField(max_length=8, blank=True, default="")
    ended_description = models.CharField(max_length=60, blank=True, default="")
    ended_yard_line = models.CharField(max_length=20, blank=True, default="")
    ended_with_score = models.BooleanField(default=False)

    plays_count = models.PositiveSmallIntegerField(default=0)
    first_downs = models.PositiveSmallIntegerField(default=0)
    yards_gained = models.IntegerField(default=0)
    yards_gained_net = models.IntegerField(default=0)
    yards_gained_by_penalty = models.IntegerField(default=0)
    time_of_possession = models.CharField(max_length=8, blank=True, default="")
    inside_20 = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["game", "sequence"],
                name="uniq_drive_game_seq",
            ),
        ]
        ordering = ["game", "sequence"]

    def __str__(self):
        return f"{self.game} Drive {self.sequence}: {self.ended_description}"


class Play(GamBaseModel):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="plays")
    play_id = models.IntegerField()
    sequence = models.FloatField()
    quarter = models.PositiveSmallIntegerField(null=True, blank=True)
    down = models.PositiveSmallIntegerField(null=True, blank=True)
    yards_to_go = models.PositiveSmallIntegerField(null=True, blank=True)
    play_type = models.CharField(max_length=40, blank=True, default="")
    play_description = models.TextField(blank=True, default="")
    play_state = models.CharField(max_length=20, blank=True, default="")
    possession_team = models.ForeignKey(
        Team, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    home_score = models.PositiveSmallIntegerField(default=0)
    visitor_score = models.PositiveSmallIntegerField(default=0)
    yard_line_number = models.PositiveSmallIntegerField(null=True, blank=True)
    yard_line_side = models.CharField(max_length=5, blank=True, default="")
    is_scoring = models.BooleanField(default=False)
    is_big_play = models.BooleanField(default=False)
    is_stp_play = models.BooleanField(default=False)
    is_marker_play = models.BooleanField(default=False)
    is_red_zone_play = models.BooleanField(null=True, blank=True)
    start_game_clock = models.CharField(max_length=8, blank=True, default="")
    end_game_clock = models.CharField(max_length=8, blank=True, default="")
    ngs_data = models.JSONField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["game", "play_id"],
                name="uniq_play_game_playid",
            ),
        ]
        indexes = [
            models.Index(fields=["game", "sequence"]),
            models.Index(fields=["game", "quarter"]),
        ]
        ordering = ["game", "sequence"]

    def __str__(self):
        return f"{self.game} Play {self.play_id}: {self.play_type}"


class PlayStat(GamBaseModel):
    play = models.ForeignKey(Play, on_delete=models.CASCADE, related_name="stats")
    team_abbr = models.CharField(max_length=5, blank=True, default="")
    player_name = models.CharField(max_length=120, blank=True, default="")
    gsis_id = models.CharField(max_length=20, blank=True, default="")
    stat_id = models.IntegerField()
    yards = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.player_name} stat {self.stat_id}: {self.yards}yds"


class PlayerGameStatBase(GamBaseModel):
    """Abstract base for per-game player stat lines."""

    class Meta:
        abstract = True

    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.PROTECT)
    side = models.CharField(max_length=4)  # "home" or "away"
    player_name = models.CharField(max_length=120)
    jersey_number = models.IntegerField(null=True, blank=True)
    position = models.CharField(max_length=10, blank=True, default="")

    def __str__(self):
        return f"{self.player_name} ({self.position}) - {self.game}"


class PassingBoxscore(PlayerGameStatBase):
    attempts = models.IntegerField(default=0)
    completions = models.IntegerField(default=0)
    completion_pct = models.FloatField(null=True, blank=True)
    yards = models.IntegerField(default=0)
    yards_per_attempt = models.FloatField(null=True, blank=True)
    touchdowns = models.IntegerField(default=0)
    interceptions = models.IntegerField(default=0)
    sacks = models.IntegerField(default=0)
    sack_yards = models.IntegerField(default=0)
    qb_rating = models.FloatField(null=True, blank=True)
    longest_pass = models.IntegerField(null=True, blank=True)
    longest_td_pass = models.IntegerField(null=True, blank=True)


class RushingBoxscore(PlayerGameStatBase):
    attempts = models.IntegerField(default=0)
    yards = models.IntegerField(default=0)
    avg_yards = models.FloatField(null=True, blank=True)
    touchdowns = models.IntegerField(default=0)
    longest_rush = models.IntegerField(null=True, blank=True)
    longest_td_rush = models.IntegerField(null=True, blank=True)


class ReceivingBoxscore(PlayerGameStatBase):
    receptions = models.IntegerField(default=0)
    yards = models.IntegerField(default=0)
    avg_yards = models.FloatField(null=True, blank=True)
    touchdowns = models.IntegerField(default=0)
    targets = models.IntegerField(null=True, blank=True)
    longest_reception = models.IntegerField(null=True, blank=True)
    longest_td_reception = models.IntegerField(null=True, blank=True)
    yards_after_catch = models.IntegerField(null=True, blank=True)


class TacklesBoxscore(PlayerGameStatBase):
    tackles = models.IntegerField(default=0)
    assists = models.IntegerField(default=0)
    sacks = models.FloatField(default=0)
    sack_yards = models.IntegerField(default=0)
    qb_hits = models.IntegerField(default=0)
    tackles_for_loss = models.IntegerField(default=0)
    tackles_for_loss_yards = models.IntegerField(default=0)
    safeties = models.IntegerField(default=0)
    special_teams_tackles = models.IntegerField(default=0)
    special_teams_assists = models.IntegerField(default=0)
    special_teams_blocks = models.IntegerField(default=0)


class FumblesBoxscore(PlayerGameStatBase):
    fumbles = models.IntegerField(default=0)
    own_recoveries = models.IntegerField(default=0)
    own_recovery_yards = models.IntegerField(default=0)
    own_recovery_tds = models.IntegerField(default=0)
    opp_recoveries = models.IntegerField(default=0)
    opp_recovery_yards = models.IntegerField(default=0)
    opp_recovery_tds = models.IntegerField(default=0)
    forced_fumbles = models.IntegerField(default=0)
    out_of_bounds = models.IntegerField(default=0)


class FieldGoalsBoxscore(PlayerGameStatBase):
    attempts = models.IntegerField(default=0)
    made = models.IntegerField(default=0)
    blocked = models.IntegerField(default=0)
    yards = models.IntegerField(default=0)
    avg_yards = models.FloatField(null=True, blank=True)
    longest = models.IntegerField(null=True, blank=True)


class ExtraPointsBoxscore(PlayerGameStatBase):
    attempts = models.IntegerField(default=0)
    made = models.IntegerField(default=0)
    blocked = models.IntegerField(default=0)


class KickingBoxscore(PlayerGameStatBase):
    kickoffs = models.IntegerField(default=0)
    yards = models.IntegerField(default=0)
    touchbacks = models.IntegerField(default=0)
    inside_20 = models.IntegerField(default=0)
    out_of_bounds = models.IntegerField(default=0)
    to_endzone = models.IntegerField(default=0)
    return_yards = models.IntegerField(default=0)


class PuntingBoxscore(PlayerGameStatBase):
    attempts = models.IntegerField(default=0)
    yards = models.IntegerField(default=0)
    gross_avg = models.FloatField(null=True, blank=True)
    net_avg = models.FloatField(null=True, blank=True)
    blocked = models.IntegerField(default=0)
    longest = models.IntegerField(null=True, blank=True)
    touchbacks = models.IntegerField(default=0)
    inside_20 = models.IntegerField(default=0)
    return_yards = models.IntegerField(default=0)


class ReturnBoxscore(PlayerGameStatBase):
    """Covers both kick returns and punt returns."""

    return_type = models.CharField(max_length=12)  # "kick" or "punt"
    returns = models.IntegerField(default=0)
    yards = models.IntegerField(default=0)
    avg_yards = models.FloatField(null=True, blank=True)
    touchdowns = models.IntegerField(default=0)
    longest = models.IntegerField(null=True, blank=True)
    longest_td = models.IntegerField(null=True, blank=True)
    fair_catches = models.IntegerField(default=0)


class GameReplay(GamBaseModel):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="replays")
    replay_type = models.CharField(max_length=20, blank=True, default="")
    sub_type = models.CharField(max_length=80, blank=True, default="")
    title = models.CharField(max_length=500, blank=True, default="")
    description = models.TextField(blank=True, default="")
    duration = models.IntegerField(null=True, blank=True)  # seconds
    external_id = models.CharField(max_length=60, blank=True, default="")
    mcp_playback_id = models.CharField(max_length=40, blank=True, default="")
    publish_date = models.DateTimeField(null=True, blank=True)
    thumbnail_url = models.URLField(max_length=500, blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["game", "sub_type"]),
        ]

    def __str__(self):
        return f"{self.game} - {self.sub_type or self.title}"


# -------------------------
# Holdings (what you own)
# -------------------------


class Source(GamBaseModel):
    source_type = models.CharField(max_length=16, choices=SourceType.choices)
    name = models.CharField(
        max_length=140
    )  # "YouTube", "NFL+", "Paramount+", "DVD", "OTA DVR", etc.
    url = models.URLField(blank=True, default="")
    notes = models.TextField(blank=True, default="")

    def __str__(self) -> str:
        return f"{self.name} ({self.source_type})"


class Acquisition(GamBaseModel):
    source = models.ForeignKey(
        Source, on_delete=models.PROTECT, related_name="acquisitions"
    )
    acquired_on = models.DateField(default=timezone.now)
    cost_usd = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    rights = models.CharField(
        max_length=20, choices=Rights.choices, default=Rights.UNKNOWN
    )
    notes = models.TextField(blank=True, default="")

    # Optional: store path to receipt/proof in your filesystem
    proof_path = models.CharField(max_length=500, blank=True, default="")

    def __str__(self) -> str:
        return f"{self.source.name} on {self.acquired_on}"


class VideoAsset(GamBaseModel):
    """
    A single file (or a single primary artifact) representing one cut of one game.
    You can store multiple assets per game (full, condensed, all-22, etc.)
    and select a preferred/best-available copy for viewing.
    """

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="assets")
    acquisition = models.ForeignKey(
        Acquisition,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="assets",
    )

    asset_type = models.CharField(
        max_length=16, choices=AssetType.choices, default=AssetType.FULL
    )

    file_path = models.CharField(max_length=700)  # absolute or archive-relative
    container = models.CharField(max_length=16, blank=True, default="")  # mkv/mp4/ts
    video_codec = models.CharField(
        max_length=32, blank=True, default=""
    )  # h264/hevc/av1
    audio_codec = models.CharField(
        max_length=32, blank=True, default=""
    )  # aac/ac3/eac3/flac
    resolution_w = models.IntegerField(null=True, blank=True)
    resolution_h = models.IntegerField(null=True, blank=True)
    fps = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )  # 59.940, 29.970, etc.
    bitrate_kbps = models.IntegerField(null=True, blank=True)

    duration_seconds = models.IntegerField(null=True, blank=True)
    file_size_bytes = models.BigIntegerField(null=True, blank=True)

    language = models.CharField(max_length=16, blank=True, default="en")
    has_commercials = models.BooleanField(default=True)

    quality_tier = models.CharField(
        max_length=1, choices=QualityTier.choices, default=QualityTier.C
    )
    quality_notes = models.TextField(blank=True, default="")

    is_preferred = models.BooleanField(default=False)

    checksum_sha256 = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)

    # Helpful for browsing
    source_url = models.URLField(
        blank=True, default=""
    )  # link to reference page, VOD page, etc.

    class Meta:
        indexes = [
            models.Index(fields=["game", "asset_type"]),
            models.Index(fields=["quality_tier"]),
            models.Index(fields=["is_preferred"]),
        ]
        constraints = [
            # You can only have ONE preferred asset per (game, asset_type) OR per game overall.
            # Pick one rule. I recommend per game overall for viewing.
            models.UniqueConstraint(
                fields=["game"],
                condition=Q(is_preferred=True),
                name="uniq_preferred_asset_per_game",
            )
        ]

    def __str__(self) -> str:
        return f"{self.game} [{self.asset_type}] {self.quality_tier}"


class Tag(GamBaseModel):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self) -> str:
        return self.name


class AssetTag(GamBaseModel):
    asset = models.ForeignKey(
        VideoAsset, on_delete=models.CASCADE, related_name="tag_links"
    )
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="asset_links")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["asset", "tag"], name="uniq_asset_tag")
        ]

    def __str__(self) -> str:
        return f"{self.asset.game} - {self.tag}"


class GameCompleteness(GamBaseModel):
    class Status(models.TextChoices):
        MISSING = "MISSING", "Missing"
        PARTIAL = "PARTIAL", "Partial"
        COMPLETE = "COMPLETE", "Complete"
        COMPLETE_NEEDS_UPGRADE = "COMPLETE_NEEDS_UPGRADE", "Complete (Needs Upgrade)"

    game = models.ForeignKey(
        Game, on_delete=models.CASCADE, related_name="completeness"
    )
    scope = models.CharField(max_length=64)
    # examples: "NFL_ALL", "STEELERS_ALL", "UGA_ALL", "UGA_2010s"

    status = models.CharField(max_length=32, choices=Status.choices)
    best_full_quality_score = models.PositiveSmallIntegerField(null=True, blank=True)

    has_full = models.BooleanField(default=False)
    has_condensed = models.BooleanField(default=False)
    has_all22 = models.BooleanField(default=False)

    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["game", "scope"], name="uniq_game_scope_completeness"
            )
        ]
        indexes = [
            models.Index(fields=["scope", "status"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.game} [{self.scope}] → {self.status}"
