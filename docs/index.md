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
