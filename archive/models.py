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

class League(models.Model):
    short_name = models.CharField(max_length=10, unique=True)
    long_name = models.CharField(max_length=120, unique=True)
    level = models.CharField(max_length=16, choices=Level.choices, default=Level.OTHER)
    country = models.CharField(max_length=2, default="US")  # ISO-3166-1 alpha-2
    notes = models.TextField(blank=True, default="")

    def __str__(self) -> str:
        return self.short_name


class Season(models.Model):
    league = models.ForeignKey(League, on_delete=models.PROTECT, related_name="seasons")
    year = models.IntegerField()  # e.g. 2025
    label = models.CharField(max_length=40, blank=True, default="")  # "2025", "2024-25", etc.
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["league", "year"], name="uniq_season_league_year")
        ]

    def __str__(self) -> str:
        return f"{self.league.name} {self.label or self.year}"


class Team(models.Model):
    """
    Single table across all levels/leagues.
    League-specific org concepts (conference/division/classification/etc.)
    should be modeled via TeamAffiliation (below).
    """
    name = models.CharField(max_length=140)           # "Georgia", "Pittsburgh Steelers"
    alternate_name = models.CharField(max_length=140, null=True)
    short_name = models.CharField(max_length=40, blank=True, default="")  # "UGA", "PIT"
    city = models.CharField(max_length=80, blank=True, default="")
    state = models.CharField(max_length=60, blank=True, default="")
    country = models.CharField(max_length=2, default="US")
    # Useful for HS + college:
    school_name = models.CharField(max_length=160, blank=True, default="")
    mascot = models.CharField(max_length=80, blank=True, default="")

    # Optional JSON for ids like espn/team id, sportsref slug, etc.
    external_ids = models.JSONField(blank=True, default=dict)

    logo = models.ImageField(upload_to="teams/logos/", null=True)
    primary_color = models.CharField(max_length=6, null=True)
    secondary_color = models.CharField(max_length=6, null=True)
    tertiary_color = models.CharField(max_length=6, null=True)

    class Meta:
        # Not truly unique globally, but this helps reduce duplicates.
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["short_name"]),
        ]

    @property
    def current_venue(self):
        today = timezone.now().date()
        occupancy = (
            self.venue_occupancies
            .filter(Q(end_date__isnull=True) | Q(end_date__gte=today))
            .order_by("-start_date")
            .select_related("venue")
            .first()
        )
        return occupancy.venue if occupancy else None

    def __str__(self) -> str:
        return self.name


class OrgUnit(models.Model):
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

    league = models.ForeignKey(League, on_delete=models.PROTECT, related_name="org_units")
    short_name = models.CharField(max_length=10)
    long_name = models.CharField(max_length=120)
    org_type = models.CharField(max_length=20, choices=OrgType.choices, default=OrgType.OTHER)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["league", "org_type", "short_name"], name="uniq_orgunit_scope")
        ]
        indexes = [
            models.Index(fields=["league", "org_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.league.short_name}: {self.short_name} ({self.org_type})"


class TeamAffiliation(models.Model):
    """
    Many-to-many between Team and OrgUnit with optional season scoping.
    Supports realignment over time.
    """
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="affiliations")
    org_unit = models.ForeignKey(OrgUnit, on_delete=models.PROTECT, related_name="team_links")

    # Option A: attach to a Season (simple)
    season = models.ForeignKey(Season, null=True, blank=True, on_delete=models.PROTECT, related_name="team_affiliations")

    # Option B: date range (more precise, optional)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["team", "org_unit", "season"],
                name="uniq_team_orgunit_season"
            )
        ]


class Venue(models.Model):
    name = models.CharField(max_length=160)
    city = models.CharField(max_length=80, blank=True, default="")
    state = models.CharField(max_length=60, blank=True, default="")
    country = models.CharField(max_length=2, default="US")
    capacity = models.IntegerField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name", "city", "state"],
                name="uniq_venue_city_state"
            )
        ]

    def __str__(self) -> str:
        return self.name


class TeamVenueOccupancy(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="venue_occupancies")
    venue = models.ForeignKey(Venue, on_delete=models.PROTECT, related_name="team_occupancies")

    start_date = models.DateField(null=True)
    end_date = models.DateField(null=True)


class Game(models.Model):
    league = models.ForeignKey(League, on_delete=models.PROTECT, related_name="games")
    season = models.ForeignKey(Season, on_delete=models.PROTECT, related_name="games")
    ordinal = models.IntegerField(null=True)
    date_local = models.DateField()
    kickoff_time_local = models.TimeField(null=True, blank=True)

    week = models.IntegerField(null=True)
    game_type = models.CharField(max_length=16, choices=GameType.choices, default=GameType.REG)
    competition_name = models.CharField(max_length=160, blank=True, default="")  # "Rose Bowl", "SEC Championship", etc.

    neutral_site = models.BooleanField(default=False)
    venue = models.ForeignKey(Venue, null=True, blank=True, on_delete=models.PROTECT, related_name="games")

    home_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="home_games")
    away_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="away_games")

    final_home_score = models.IntegerField(null=True, blank=True)
    final_away_score = models.IntegerField(null=True, blank=True)
    overtime_periods = models.IntegerField(null=True, blank=True)

    # Rankings at game time (AP Poll, per your requirement)
    ap_rank_home = models.IntegerField(null=True, blank=True)
    ap_rank_away = models.IntegerField(null=True, blank=True)

    notes = models.TextField(blank=True, default="")

    # External identifiers to avoid duplicates when importing later.
    external_ids = models.JSONField(blank=True, default=dict)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~Q(home_team=models.F("away_team")), name="chk_home_away_distinct"),
            # This helps dedupe "same league/season/date/teams" games.
            models.UniqueConstraint(
                fields=["league", "season", "date_local", "home_team", "away_team"],
                name="uniq_game_identity_basic"
            ),
        ]
        indexes = [
            models.Index(fields=["league", "season", "date_local"]),
            models.Index(fields=["home_team", "date_local"]),
            models.Index(fields=["away_team", "date_local"]),
        ]

    def __str__(self) -> str:
        return f"{self.date_local} {self.away_team} @ {self.home_team}"


# -------------------------
# Holdings (what you own)
# -------------------------

class Source(models.Model):
    source_type = models.CharField(max_length=16, choices=SourceType.choices)
    name = models.CharField(max_length=140)  # "YouTube", "NFL+", "Paramount+", "DVD", "OTA DVR", etc.
    url = models.URLField(blank=True, default="")
    notes = models.TextField(blank=True, default="")

    def __str__(self) -> str:
        return f"{self.name} ({self.source_type})"


class Acquisition(models.Model):
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name="acquisitions")
    acquired_on = models.DateField(default=timezone.now)
    cost_usd = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    rights = models.CharField(max_length=20, choices=Rights.choices, default=Rights.UNKNOWN)
    notes = models.TextField(blank=True, default="")

    # Optional: store path to receipt/proof in your filesystem
    proof_path = models.CharField(max_length=500, blank=True, default="")

    def __str__(self) -> str:
        return f"{self.source.name} on {self.acquired_on}"


class VideoAsset(models.Model):
    """
    A single file (or a single primary artifact) representing one cut of one game.
    You can store multiple assets per game (full, condensed, all-22, etc.)
    and select a preferred/best-available copy for viewing.
    """
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="assets")
    acquisition = models.ForeignKey(Acquisition, null=True, blank=True, on_delete=models.PROTECT, related_name="assets")

    asset_type = models.CharField(max_length=16, choices=AssetType.choices, default=AssetType.FULL)

    file_path = models.CharField(max_length=700)  # absolute or archive-relative
    container = models.CharField(max_length=16, blank=True, default="")  # mkv/mp4/ts
    video_codec = models.CharField(max_length=32, blank=True, default="")  # h264/hevc/av1
    audio_codec = models.CharField(max_length=32, blank=True, default="")  # aac/ac3/eac3/flac
    resolution_w = models.IntegerField(null=True, blank=True)
    resolution_h = models.IntegerField(null=True, blank=True)
    fps = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)  # 59.940, 29.970, etc.
    bitrate_kbps = models.IntegerField(null=True, blank=True)

    duration_seconds = models.IntegerField(null=True, blank=True)
    file_size_bytes = models.BigIntegerField(null=True, blank=True)

    language = models.CharField(max_length=16, blank=True, default="en")
    has_commercials = models.BooleanField(default=True)

    quality_tier = models.CharField(max_length=1, choices=QualityTier.choices, default=QualityTier.C)
    quality_notes = models.TextField(blank=True, default="")

    is_preferred = models.BooleanField(default=False)

    checksum_sha256 = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)

    # Helpful for browsing
    source_url = models.URLField(blank=True, default="")  # link to reference page, VOD page, etc.

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
                name="uniq_preferred_asset_per_game"
            )
        ]

    def __str__(self) -> str:
        return f"{self.game} [{self.asset_type}] {self.quality_tier}"


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self) -> str:
        return self.name


class AssetTag(models.Model):
    asset = models.ForeignKey(VideoAsset, on_delete=models.CASCADE, related_name="tag_links")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="asset_links")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["asset", "tag"], name="uniq_asset_tag")
        ]


class GameCompleteness(models.Model):
    class Status(models.TextChoices):
        MISSING = "MISSING", "Missing"
        PARTIAL = "PARTIAL", "Partial"
        COMPLETE = "COMPLETE", "Complete"
        COMPLETE_NEEDS_UPGRADE = "COMPLETE_NEEDS_UPGRADE", "Complete (Needs Upgrade)"

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="completeness")
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
                fields=["game", "scope"],
                name="uniq_game_scope_completeness"
            )
        ]
        indexes = [
            models.Index(fields=["scope", "status"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.game} [{self.scope}] → {self.status}"
