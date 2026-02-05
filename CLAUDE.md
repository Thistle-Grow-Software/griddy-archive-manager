# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Griddy Archive Manager (GAM) is a Django 6.0+ application for cataloging and managing football game video archives. It tracks games, teams, venues, and video assets across multiple football levels (High School, College, Professional). The project is in early development (v0.1.0).

- **Python 3.14+**, managed with **uv**
- **PostgreSQL** database (name: `griddy`)
- Single Django app: `archive`

## Common Commands

```bash
# Dependencies
uv sync                              # Install/sync dependencies from uv.lock

# Database
python manage.py migrate             # Apply migrations
python manage.py makemigrations      # Generate migrations after model changes

# Server
python manage.py runserver           # Start dev server (admin at /admin/)

# Shell
python manage.py shell              # Django shell (uses IPython)
python manage.py shell_plus         # Enhanced shell via django-extensions (auto-imports models)

# Management commands
python manage.py scrapegames <html_file>  # Import teams/affiliations from scraped HTML

# Tests
python manage.py test                # Run all tests
python manage.py test archive        # Run archive app tests
python manage.py test archive.tests.TestClassName.test_method  # Single test
```

## Environment Variables

Required for database connection:
- `PG_USER`, `PG_PASSWORD`, `PG_HOST`, `PG_PORT`

Optional:
- `MEDIA_ROOT` - Directory for uploaded media files (team logos, etc.)

## Architecture

### Two-Domain Data Model

The `archive` app models split into two conceptual domains:

**Catalog (what exists)** - League/game metadata:
- `League` -> `Season` -> `Game` (with `home_team`/`away_team` FKs to `Team`)
- `Team` -> `TeamAffiliation` -> `OrgUnit` (conferences, divisions, regions - hierarchical via `parent`)
- `TeamAffiliation` supports temporal scoping (by `Season` or date range) to track realignment
- `Venue` linked to `Game`
- `GameCompleteness` tracks coverage status per game within named scopes (e.g., "NFL_ALL", "STEELERS_ALL")

**Holdings (what you own)** - Asset management:
- `Source` (streaming, YouTube, physical, DVR, etc.) -> `Acquisition` (purchase record) -> `VideoAsset`
- `VideoAsset` linked to `Game` with detailed codec/quality metadata and SHA-256 checksums
- `Tag`/`AssetTag` for flexible asset categorization

### Scrapers (`archive/scrapers.py`)

Hierarchy of scrapers for populating catalog data from sports-reference.com:
- `BaseScraper` - generic HTTP + BeautifulSoup base
- `SportsRefScraper` - CFB team extraction with rate limiting
- `CFBScraper` - season schedule extraction
- `CFBTeamScraper` - local HTML file parsing (used by `scrapegames` command)

### Key Enumerations

Models use TextChoices extensively: `Level` (HS/COLLEGE/PRO), `GameType` (REG/POST/BOWL/PLAYOFF...), `AssetType` (FULL/CONDENSED/ALL22...), `QualityTier` (A-D), `SourceType`, `OrgType`, `Rights`, `GameCompletenessStatus`.

### URL Routing

Currently admin-only (`/admin/`). Debug toolbar enabled in development.
