# Griddy Archive Manager

Griddy Archive Manager (GAM) is a Django 6.0+ application for cataloging and managing
football game video archives across multiple levels of play — High School, College,
and Professional.

## What It Does

GAM organizes football data into two domains:

**Catalog** — tracks what exists in the football world:

- Leagues, seasons, and games
- Teams with franchise history and era tracking
- Organizational hierarchies (conferences, divisions) with realignment support
- Venues and team occupancy history
- Game-level detail: drives, plays, player boxscores, standings snapshots

**Holdings** — tracks what you own:

- Video assets with codec-level quality metadata
- Acquisition records (source, cost, rights)
- Coverage completeness tracking per game and scope
- Flexible tagging system

## Data Ingestion

GAM populates its catalog through a hierarchy of scrapers:

- **NFL.com** — game data, drive charts, play-by-play, boxscores, replays, and standings via the [Griddy SDK](https://github.com/Thistle-Grow-Software/griddy-sdk-python)
- **Sports-Reference** — NCAA FBS schedules and team data
- **Wikipedia** — supplemental college football data

## Getting Started

See the [Getting Started](getting-started.md) guide for installation and setup instructions.

## Architecture

See the [Architecture](architecture.md) page for a detailed description of the data model and scraper hierarchy.

## API Authentication

The Griddy API supports two auth paths: short-lived Clerk-issued JWTs for end-user apps, and long-lived API keys for SDK and machine-to-machine access. Start with the [API Authentication overview](auth/index.md) to pick the right one, then follow the guide:

- [JWT (End-User Apps)](auth/jwt.md) — for browser-driven access where a real user signs in.
- [API Keys (SDK / M2M)](auth/api-keys.md) — for backend, CI, and SDK integrations.
- [Permissions](auth/permissions.md) — the catalog of permission strings, identical for both paths.
- [Errors & Troubleshooting](auth/errors.md) — what `401` vs `403` mean, common causes, and a debugging walkthrough.
