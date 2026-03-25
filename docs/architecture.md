# Architecture

GAM is a single Django app (`archive`) with a two-domain data model and a scraper-based
data ingestion pipeline.

## Data Model

### Catalog Domain

The catalog domain models the football world — leagues, teams, games, and their relationships.

#### League Structure

```
League -> Season -> Game
```

A **League** represents a competition (e.g., NFL, NCAA FBS) at a specific level of play
(High School, College, Professional). Each league contains **Seasons** identified by year,
and each season contains **Games**.

#### Teams and Franchises

```
Franchise -> Team (one-to-many, era-based)
Team -> TeamAffiliation -> OrgUnit
```

A **Franchise** groups era-specific **Team** records. For example, the "Cleveland Browns"
franchise might have team records for different eras separated by a hiatus. Each team
record has `era_start_date` and `era_end_date` fields.

**OrgUnit** models hierarchical organizational units — conferences, divisions, regions,
classifications, and league tiers. OrgUnits can nest via a self-referential `parent`
foreign key (e.g., AFC -> AFC North).

**TeamAffiliation** links a team to an OrgUnit with temporal scoping — either by `Season`
or by explicit date range (`start_date`/`end_date`). This supports tracking conference
realignment over time.

#### Venues

```
Venue <- TeamVenueOccupancy -> Team
```

**Venue** stores stadium information. **TeamVenueOccupancy** tracks which team plays at
which venue over time, supporting stadium moves and shared venues.

#### Games

A **Game** links two teams (home and away) within a season, with support for:

- Game classification (`GameType`: regular season, postseason, bowl, playoff, etc.)
- Neutral site games
- AP Poll rankings at game time
- Broadcast channel and overtime tracking

Each game can have detailed sub-records:

- **QuarterScore** — score by period (quarters and overtime)
- **Drive** — drive-level data (start/end position, plays, yards, time of possession)
- **Play** — individual play data (down, distance, description, scoring, red zone, NGS data)
- **PlayStat** — per-player stats on individual plays
- **Player boxscores** — game-level stats by category (passing, rushing, receiving, tackles, fumbles, field goals, extra points, kicking, punting, returns)
- **TeamStandingsSnapshot** — team standings at a specific week
- **GameReplay** — video replay/clip metadata

### Holdings Domain

The holdings domain tracks video assets you own and their provenance.

#### Asset Pipeline

```
Source -> Acquisition -> VideoAsset -> Game
```

A **Source** represents where content comes from (`SourceType`: streaming, YouTube, physical
media, DVR capture, file trade). An **Acquisition** records a purchase or transfer from a
source, including cost, rights, and proof of purchase.

A **VideoAsset** is a single file representing one cut of one game. It stores detailed
technical metadata:

- Container format, video/audio codecs
- Resolution, frame rate, bitrate
- File size and SHA-256 checksum
- Quality tier (A through D) with notes
- Asset type (full broadcast, condensed, coaches film, All-22, highlights, radio)

The `is_preferred` flag marks the best available asset per game (enforced as unique).

#### Tagging and Completeness

**Tag** and **AssetTag** provide flexible categorization of video assets.

**GameCompleteness** tracks coverage status per game within named scopes (e.g.,
`"NFL_ALL"`, `"STEELERS_ALL"`, `"UGA_ALL"`). Status values include missing, partial,
complete, and complete-needs-upgrade, along with flags for which asset types are available.

### Base Model

All models inherit from **GamBaseModel**, which provides two JSONFields:

- `bonus_data` — arbitrary supplemental data
- `external_ids` — league-specific identifiers (e.g., NFL.com smartId, teamId)

## Scrapers

Data ingestion uses a hierarchy of scrapers in `archive/scrapers/`:

### BaseScraper

Provides HTTP fetching with BeautifulSoup parsing and optional Playwright-based browser
rendering for JavaScript-heavy pages.

### NFLScraper

Fetches NFL team and game data using the [Griddy SDK](https://github.com/Thistle-Grow-Software/griddy-sdk-python).
Handles:

- Team creation with division affiliations
- Venue processing and team-venue occupancy
- Weekly game data gathering (drive charts, replays, standings, tagged videos)

### NFLDataIngestor

Transforms Griddy SDK data into Django model instances. Resolves teams by abbreviation,
smartId, or NFL ID, then creates:

- Game records with venue and score data
- Standings snapshots
- Player boxscores (all categories)
- Drive charts and play-by-play data
- Game replay metadata

### SportsRefCFBScraper

Scrapes NCAA FBS data from sports-reference.com:

- Team lists with conference affiliations
- Season schedules with game details
- Tracks FCS schools encountered but not in the database

### WikipediaCFBScraper

Supplements college football data from Wikipedia (currently a stub implementation).

## Enumerations

Models use Django `TextChoices` extensively:

| Enum | Values |
|---|---|
| `Level` | HS, COLLEGE, PRO, OTHER |
| `GameType` | REG, CONF, POST, BOWL, PLAYOFF, EXHIB, OTHER |
| `AssetType` | FULL, CONDENSED, COACHES, ALL22, HIGHLIGHTS, RADIO, OTHER |
| `SourceType` | STREAMING, YOUTUBE, PHYSICAL, DVR, FILE_TRADE, OTHER |
| `QualityTier` | A (Best), B (Very Good), C (Good), D (Filler) |
| `Rights` | PERSONAL_ONLY, SHAREABLE, UNKNOWN |
