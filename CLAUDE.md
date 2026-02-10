# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Griddy Archive Manager (GAM) is a Django 6.0+ application for cataloging and managing football game video archives. It tracks games, teams, venues, and video assets across multiple football levels (High School, College, Professional). The project is in early development (v0.1.0).

- **Python 3.14+**, managed with **uv**
- **PostgreSQL** database (name: `griddy`)
- Single Django app: `archive`

## Environment Variables

The following environment variables are of particular interest to this project:
- `GRIDDY_NFL_EMAIL` - Email to use in `GriddyNFL` when authenticating with email + password
- `GRIDDY_NFL_PASSWORD` - Password to use in `GriddyNFL` when authenticating with email + password
- `PG_HOST`, `PG_PORT`, `PG_DB_NAME`, `PG_USER`, `PG_PASSWORD` - Postgres connection values
- - `MEDIA_ROOT` - Directory for uploaded media files (team logos, etc.)
- `AWS_CODEARTIFACT_TOKEN` - Authentication token used for interacting with AWS CodeArtifact PyPi repository
- `UV_INDEX_PRIVATE_REGISTRY_USERNAME` - Username used by `uv` when interacting with CodeArtifact
- `UV_INDEX_PRIVATE_REGISTRY_PASSWORD` - Same value as `AWS_CODEARTIFACT_TOKEN`, used by `uv` to interact with CodeArtifact

## Custom Shell Functions and Aliases (from ~/.bashrc)
- `artifact-token` - Initializes necessary authentication info for interacting with AWS CodeArtifact. Usage: `artifact-token`
- `gam` - Navigates to the project directory, sets project specific env vars, and invokes `artifact-token`. Usage: `gam`
- `uvrm` - A quality of life shortcut for `uv run manage.py`. Usage: `uvrm <management command>`. Example: `uvrm makemigrations` to make Django migrations
- `tgf-format` - Runs `isort` and `black` _in the current directory_. Usage: `tgf-format`

## Common Commands

```bash
# Dependencies
uv sync                              # Install/sync dependencies from uv.lock

# Database
uvrm makemigrations      # Generate migrations after model changes
uvrm migrate             # Apply migrations


# Server
uvrm runserver           # Start dev server (admin at /admin/)

# Shell
uvrm shell              # Django shell (uses IPython)
uvrm shell_plus         # Enhanced shell via django-extensions (auto-imports models)

# Management commands
uvrm scrapegames <html_file>  # Import teams/affiliations from scraped HTML

# Tests
uvrm test                # Run all tests
uvrm test archive        # Run archive app tests
uvrm test archive.tests.TestClassName.test_method  # Single test
```

## Git Conventions

- **Always run `tgf-format` before committing.** A pre-commit hook enforces this, but if committing manually, run it first.
- Use **Conventional Commits** for all commit messages.
- **Deriving the GitHub issue number:** Check the current branch name. If it contains a number, that number is the GitHub issue number. If the branch has no number, there is no associated issue.

### Commit messages

- Always include `GAM` in the scope.
- If there is an associated issue: `feat(GAM #42): add player stats endpoint`
- If there is no associated issue: `feat(GAM): add player stats endpoint`
- Valid types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `ci`, `style`, `perf`, `build`
- Keep the subject line under 72 characters. Add a body for non-trivial changes.

### Pull requests (via `gh pr create`)

- PR title follows the same format as commit messages:
  - `feat(GAM #42): add player stats endpoint`
- If there is an associated issue, append `Closes #<issue num>` as the last line of the PR body.

### Examples

Branch: `feature/42-player-stats`
→ Issue number: 42
→ Commit: `feat(GAM #42): add player stats endpoint`
→ PR title: `feat(GAM #42): add player stats endpoint`
→ PR body ends with: `Closes #42`

Branch: `refactor/cleanup-api-client`
→ No issue number
→ Commit: `refactor(GAM): extract API client into separate module`
→ PR title: `refactor(GAM): extract API client into separate module`
→ PR body: no `Closes` line


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
