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
| `CLERK_JWKS_URL` | Clerk JWKS endpoint Django fetches public signing keys from |
| `CLERK_ISSUER` | Clerk Frontend API URL — must equal the `iss` claim on every token |
| `CLERK_AUDIENCE` | API identifier Clerk stamps into the `aud` claim |
| `CLERK_AUTHORIZED_PARTIES` | Comma-separated origins allowed in the `azp` claim |
| `CLERK_SECRET_KEY` | Server-side Clerk Backend API key (loaded from AWS Secrets Manager in deployed envs) |
| `R2_BUCKET` | Cloudflare R2 bucket the `package_hls` pipeline uploads HLS output to |
| `R2_ENDPOINT_URL` | R2 S3-compatible endpoint (`https://<account-id>.r2.cloudflarestorage.com`) |
| `R2_ACCESS_KEY_ID` | R2 access key ID (from AWS Secrets Manager in deployed envs) |
| `R2_SECRET_ACCESS_KEY` | R2 secret access key (from AWS Secrets Manager in deployed envs) |
| `HLS_SOURCE_ROOTS` | Colon-separated league source trees `package_hls` walks by default |

See `.env.example` for development defaults.

## Authentication

GAM uses [Clerk](https://clerk.com/)-issued JWTs for API authentication, verified via
the JWKS-based `JWKSAuthentication` class registered as DRF's
`DEFAULT_AUTHENTICATION_CLASSES`. The auth class itself is IdP-agnostic — it reads
generic `JWKS_URL`, `JWT_AUDIENCE`, `JWT_ISSUER`, and `JWT_AUTHORIZED_PARTIES`
settings; `gam/settings.py` is the single place that names Clerk as the provider.

### Smoke-testing against the dev Clerk instance

1. Ensure `.env` is populated from `.env.example`. The dev `CLERK_JWKS_URL`,
   `CLERK_ISSUER`, and `CLERK_AUDIENCE` already point at the shared
   `casual-earwig-79` dev instance.
2. Mint a token from a real Clerk session. Two options:
   - **Account Portal** — open `https://casual-earwig-79.accounts.dev`, sign in
     as a test user (provisioned in TGF-314), and copy the `__session` cookie
     value from the browser DevTools.
   - **Dashboard impersonation** — Clerk Dashboard → Users → pick a user →
     "Impersonate user" → grab the session token.
3. Paste the token into [jwt.io](https://jwt.io) and confirm `aud` matches your
   `CLERK_AUDIENCE` and `iss` matches `CLERK_ISSUER`.
4. Hit the API:

   ```bash
   uv run manage.py runserver
   curl -H "Authorization: Bearer <token>" \
        http://127.0.0.1:8000/api/v1/leagues/
   ```

   A 200 confirms end-to-end token validation. A 401 with
   `{"detail": "Invalid authorized party."}` means your token's `azp` is not in
   `CLERK_AUTHORIZED_PARTIES` (likely the portal origin differs from
   `http://localhost:3000`).

### Local JWKS harness (no Clerk required)

For tests and offline dev, `scripts/local_jwks_server.py` boots a local JWKS
server and emits a signed token. Leave `CLERK_AUTHORIZED_PARTIES` blank to
skip the `azp` check when using the harness.

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
