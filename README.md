# Griddy Archive Manager

A Django 6.0+ application for cataloging and managing football game video archives across multiple levels of play (High School, College, Professional).

## Overview

Griddy Archive Manager (GAM) tracks games, teams, venues, and video assets using a two-domain data model:

- **Catalog** — what exists: leagues, seasons, games, teams, venues, and organizational hierarchies (conferences, divisions)
- **Holdings** — what you own: sources, acquisitions, video assets with detailed codec/quality metadata, and coverage tracking

The application ingests game data from NFL.com (via the [Griddy SDK](https://github.com/Thistle-Grow-Software/griddy-sdk-python)), Sports-Reference, and Wikipedia using a hierarchy of scrapers, and exposes all data through the Django admin interface.

## Quick Start

### Prerequisites

- Python 3.14+
- PostgreSQL
- [uv](https://docs.astral.sh/uv/) for dependency management
- AWS CodeArtifact access (for the `griddy` SDK dependency)

### Installation

```bash
# Clone the repository
git clone https://github.com/Thistle-Grow-Software/all-things-griddy.git
cd all-things-griddy/griddy-archive-manager

# Install dependencies
uv sync

# Set required environment variables
export PG_HOST=localhost
export PG_PORT=5432
export PG_DB_NAME=griddy
export PG_USER=your_user
export PG_PASSWORD=your_password

# Apply database migrations
uv run manage.py migrate

# Create a superuser for the admin interface
uv run manage.py createsuperuser

# Start the development server
uv run manage.py runserver
```

The admin interface is available at `http://localhost:8000/admin/`.

### Environment Variables

| Variable | Description |
|---|---|
| `PG_HOST` | PostgreSQL host |
| `PG_PORT` | PostgreSQL port |
| `PG_DB_NAME` | PostgreSQL database name |
| `PG_USER` | PostgreSQL user |
| `PG_PASSWORD` | PostgreSQL password |
| `GRIDDY_NFL_EMAIL` | NFL.com email for authenticated scraping |
| `GRIDDY_NFL_PASSWORD` | NFL.com password for authenticated scraping |
| `MEDIA_ROOT` | Directory for uploaded media files (team logos, etc.) |
| `AWS_CODEARTIFACT_TOKEN` | Authentication token for AWS CodeArtifact |

## Architecture

### Two-Domain Data Model

**Catalog domain** — game metadata and organizational structure:

```
League -> Season -> Game (home_team / away_team -> Team)
Team -> TeamAffiliation -> OrgUnit (conferences, divisions -- hierarchical via parent)
Franchise -> Team (groups era-specific team records)
Venue <- TeamVenueOccupancy -> Team
```

`TeamAffiliation` supports temporal scoping by `Season` or date range to track conference realignment. `Franchise` groups multiple `Team` eras (e.g., the Baltimore Ravens franchise includes its current and historical team records).

**Holdings domain** — asset management:

```
Source -> Acquisition -> VideoAsset -> Game
Tag <- AssetTag -> VideoAsset
GameCompleteness -> Game (coverage tracking per named scope)
```

`VideoAsset` stores detailed codec and quality metadata (resolution, bitrate, FPS, SHA-256 checksums). `GameCompleteness` tracks coverage status per game within named scopes (e.g., `"NFL_ALL"`, `"STEELERS_ALL"`).

### Scrapers

Data ingestion is handled by a hierarchy of scrapers in `archive/scrapers/`:

- **`BaseScraper`** — HTTP fetching with BeautifulSoup and optional Playwright browser support
- **`NFLScraper`** — fetches NFL team and game data via the Griddy SDK; creates teams, venues, and affiliations
- **`NFLDataIngestor`** — transforms Griddy SDK game data into Django model instances (games, drives, plays, boxscores, standings, replays)
- **`SportsRefCFBScraper`** — scrapes NCAA FBS schedules and team data from sports-reference.com
- **`WikipediaCFBScraper`** — scrapes college football data from Wikipedia

## Documentation

Documentation is built with [Zensical](https://zensical.org/) (Material theme) and [mkdocstrings](https://mkdocstrings.github.io/) for API reference generation.

```bash
# Install doc dependencies
uv sync --group docs

# Serve docs locally
uv run zensical serve
```

## Development

```bash
# Install all dependencies
uv sync --all-groups

# Run tests
uv run pytest

# Lint and format
uv run ruff check --fix .
uv run ruff format .
```

## License

Copyright 2026 Thistle Grow Software. All rights reserved.
