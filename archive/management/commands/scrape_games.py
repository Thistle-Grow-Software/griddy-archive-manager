import json
from typing import Optional

import djclick as click
from griddy.nfl.models import SeasonTypeEnum

from archive.models import League, Season
from archive.scrapers import NFLDataIngestor, NFLScraper, SportsRefCFBScraper
from archive.utils import DateTimeEncoder


@click.group()
def scrape_games():
    """Scrape game data"""
    pass


@scrape_games.command()
@click.option("--season", type=int, required=True)
@click.option("--week", type=int)
@click.option("--season-type", type=click.Choice(["REG", "POST"]), default="REG")
@click.option("--login-email", type=str)
@click.option("--login-password", type=str)
@click.option("--creds", type=str)
@click.option("--headless", default=False, is_flag=True, flag_value=True)
@click.option("--output-file", type=str)
@click.option(
    "--store-db", default=False, is_flag=True, help="Store data in the database"
)
@click.option("--min-week", type=int)
@click.option("--max-week", type=int)
def nfl(
    season: int,
    week: int,
    season_type: SeasonTypeEnum = "REG",
    login_email: Optional[str] = None,
    login_password: Optional[str] = None,
    creds: Optional[str] = None,
    headless: Optional[bool] = False,
    output_file: Optional[str] = None,
    store_db: Optional[bool] = False,
    min_week: Optional[int] = None,
    max_week: Optional[int] = None,
):
    click.echo(f"Season: {season}")
    click.echo(f"Week: {week}")
    click.echo(f"Min Week: {min_week}")
    click.echo(f"Max Week: {max_week}")
    click.echo(f"Season Type: {season_type}")
    click.echo(f"Login Email: {login_email}")
    click.echo(f"Login password: {login_password}")
    click.echo(f"Creds: {creds}")
    click.echo(f"Headless: {headless}")

    scraper = NFLScraper(
        login_email=login_email,
        login_password=login_password,
        creds=creds,
        headless_login=headless,
        year=season,
    )

    for week in range(min_week, max_week + 1):
        if store_db:
            click.echo("Fetching data (Pydantic models) for DB storage...")
            game_data = scraper.gather_all_data_for_week(
                season=season, week=week, season_type=season_type, as_json=False
            )

            league = League.objects.get(short_name="NFL")
            season_obj = Season.objects.get(league=league, year=season)

            ingestor = NFLDataIngestor(league=league, season=season_obj)
            games = ingestor.ingest_week(week_data=game_data, week=week)
            click.echo(f"Stored {len(games)} games in the database.")

            if output_file:
                json_data = scraper._cast_to_json(data=game_data)
                games_list = list(json_data.values())
                for idx, game in enumerate(games_list):
                    with open(f"{output_file}_{idx+1}.json", "w") as outfile:
                        json.dump(game, outfile, indent=4, cls=DateTimeEncoder)
                click.echo(f"Also wrote {len(games_list)} JSON files.")
        else:
            game_data = scraper.gather_all_data_for_week(
                season=season, week=week, season_type=season_type, as_json=True
            )
            games = list(game_data.values())
            for idx, game in enumerate(games):
                with open(
                    f"archive/fixtures/complete_game_{idx+1}.json", "w"
                ) as outfile:
                    json.dump(game, outfile, indent=4, cls=DateTimeEncoder)
            else:
                click.echo(game_data)


@scrape_games.command()
@click.argument("season", type=int)
@click.option("--output-file", type=str, help="Path to write scraped game data as JSON")
@click.option(
    "--store-db", default=False, is_flag=True, help="Store data in the database"
)
def cfb(
    season: int,
    output_file: Optional[str] = None,
    store_db: Optional[bool] = False,
):
    """Scrape NCAA FBS game data from sports-reference.com for a given SEASON year."""
    click.echo(f"Scraping NCAA FBS games for the {season} season...")

    scraper = SportsRefCFBScraper(league_short_name="NCAA - FBS", season=season)

    click.echo("Fetching season schedule from sports-reference.com...")
    scraper.fetch_season_table(season=season)

    click.echo("Extracting game rows from schedule...")
    games_data = scraper.extract_game_rows_from_schedule()
    click.echo(f"Found {len(games_data)} games in the schedule.")

    if store_db:
        created_games = scraper.load_games_from_scraped_json(
            games_data=games_data, create=True
        )
        click.echo(f"Stored {len(created_games)} games in the database.")
    else:
        game_objects = scraper.load_games_from_scraped_json(
            games_data=games_data, create=False
        )
        click.echo(f"Parsed {len(game_objects)} games (dry run, not stored).")

    if output_file:
        with open(output_file, "w") as outfile:
            json.dump(games_data, outfile, indent=4, cls=DateTimeEncoder)
        click.echo(f"Wrote scraped data to {output_file}")

    if scraper.failed_games:
        click.echo(f"\n{len(scraper.failed_games)} games failed to process.")
    if scraper.fcs_schools:
        click.echo(
            f"{len(scraper.fcs_schools)} FCS schools encountered (not in DB): "
            f"{', '.join(sorted(scraper.fcs_schools))}"
        )
