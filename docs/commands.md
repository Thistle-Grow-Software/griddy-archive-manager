# Management Commands

GAM provides several Django management commands for data ingestion and exploration.
Commands built with [django-click](https://github.com/GaretJax/django-click) use a
subcommand pattern; standard Django commands use positional arguments.

## scrape_games

The primary data ingestion command. Built with django-click as a command group with
two subcommands: `nfl` and `cfb`.

### scrape_games nfl

Scrape NFL game data from NFL.com using the Griddy SDK.

```bash
uv run manage.py scrape_games nfl --season 2024 --min-week 1 --max-week 18 --store-db
```

**Options:**

| Option | Type | Required | Description |
|---|---|---|---|
| `--season` | int | Yes | NFL season year |
| `--week` | int | No | Specific week number |
| `--season-type` | REG/POST | No | Season type (default: `REG`) |
| `--min-week` | int | No | Minimum week number (for range scraping) |
| `--max-week` | int | No | Maximum week number (for range scraping) |
| `--login-email` | str | No | NFL.com email for authentication |
| `--login-password` | str | No | NFL.com password for authentication |
| `--creds` | str | No | Path to credentials JSON file |
| `--headless` | flag | No | Use headless browser for login |
| `--output-file` | str | No | Path to write JSON output |
| `--store-db` | flag | No | Store data in the database (default: dry run) |

**Behavior:**

- Iterates over the week range (`min-week` to `max-week`)
- For each week, fetches game details including drive charts, replays, standings, and tagged videos
- With `--store-db`: creates/updates `Game`, boxscore, drive, play, standings, and replay records
- Without `--store-db`: writes raw JSON to fixture files
- With `--output-file`: also writes JSON output alongside database storage

**Prerequisites:**

- `League` and `Season` records must exist in the database for the target season
- NFL.com authentication credentials (via options or environment variables)

### scrape_games cfb

Scrape NCAA FBS game data from sports-reference.com.

```bash
uv run manage.py scrape_games cfb 2024 --store-db
```

**Arguments:**

| Argument | Type | Description |
|---|---|---|
| `season` | int | Season year |

**Options:**

| Option | Type | Description |
|---|---|---|
| `--output-file` | str | Path to write scraped game data as JSON |
| `--store-db` | flag | Store data in the database (default: dry run) |

**Behavior:**

- Fetches the season schedule from sports-reference.com
- Extracts game rows and parses team/score/date information
- With `--store-db`: creates `Game` records in the database
- Without `--store-db`: parses and validates games without persisting (dry run)
- Reports FCS schools encountered that are not in the database
- Reports games that failed to process

## scrapegames

Legacy Django management command for loading previously scraped game data from JSON files.

```bash
uv run manage.py scrapegames "NCAA - FBS" 2024 --data_path games.json
```

**Arguments:**

| Argument | Type | Description |
|---|---|---|
| `league` | str | League name (e.g., `"NCAA - FBS"`) |
| `season` | int | Season year |

**Options:**

| Option | Type | Description |
|---|---|---|
| `--week` | int | Specific week number |
| `--data_path` | str | Path to a JSON file containing scraped game data |

**Behavior:**

- Loads game data from the specified JSON file
- Currently supports `"NCAA - FBS"` (uses `SportsRefCFBScraper.load_games_from_scraped_json`)
- NFL support is stubbed but not yet implemented

## scrapenflteams

Load NFL team data from a JSON file into the database.

```bash
uv run manage.py scrapenflteams nfl_teams.json
```

**Arguments:**

| Argument | Type | Description |
|---|---|---|
| `data_path` | str | Path to a JSON file containing NFL team data |

**Behavior:**

- Reads the JSON file containing NFL team data (as returned by the Griddy SDK)
- Skips conference-level entries (AFC, NFC) and teams that already exist
- For each new team, creates `Team`, `Venue`, `TeamVenueOccupancy`, and division `TeamAffiliation` records via `NFLScraper.create_db_object()`

## sandbox

Development and exploration commands for comparing NFL API data structures. Built with
django-click as a command group.

### sandbox comparison

Compare schema differences between old and modern NFL API endpoints.

```bash
uv run manage.py sandbox comparison --fetch --creds-file creds.json
```

**Options:**

| Option | Type | Description |
|---|---|---|
| `--fetch` | flag | Pull live data from NFL.com (otherwise reads cached JSON) |
| `--email` | str | NFL.com email |
| `--password` | str | NFL.com password |
| `--creds-file` | str | Path to credentials JSON file |

**Behavior:**

- Compares `weekly_game_details` schema between a 2015 and 2016 game
- Generates `all_reg_keys.json`, `combined_pro_info.json`, and `missing_keys.json`
- Without `--fetch`: reads previously cached JSON files and converts keys to snake_case

### sandbox boxscore_comparison

Compare historic vs. modern boxscore data structures.

```bash
uv run manage.py sandbox boxscore_comparison --fetch --creds-file creds.json
```

**Options:**

| Option | Type | Description |
|---|---|---|
| `--fetch` | flag | Pull live data from NFL.com |
| `--email` | str | NFL.com email |
| `--password` | str | NFL.com password |
| `--creds-file` | str | Path to credentials JSON file |

**Behavior:**

- Compares historic game details, live stats, and historical stats endpoints
- Compares against modern pro API endpoints (boxscore, game center, playlist)
- Generates `historic_game_info.json` and `pro_game_info.json`
