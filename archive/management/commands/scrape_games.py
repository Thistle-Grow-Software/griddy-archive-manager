import json
from typing import Optional

import djclick as click
from griddy.nfl.models import SeasonTypeEnum

from archive.models import League, Season
from archive.scrapers import NFLDataIngestor, NFLScraper
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
):
    click.echo(f"Season: {season}")
    click.echo(f"Week: {week}")
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
    )

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
            with open(f"archive/fixtures/complete_game_{idx+1}.json", "w") as outfile:
                json.dump(game, outfile, indent=4, cls=DateTimeEncoder)
        else:
            click.echo(game_data)
