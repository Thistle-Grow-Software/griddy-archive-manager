import json
from typing import Optional

import djclick as click
from griddy.nfl.models import SeasonTypeEnum

from archive.scrapers import NFLScraper
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
def nfl(
    season: int,
    week: int,
    season_type: SeasonTypeEnum = "REG",
    login_email: Optional[str] = None,
    login_password: Optional[str] = None,
    creds: Optional[str] = None,
    headless: Optional[bool] = False,
    output_file: Optional[str] = None,
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
    game_data = scraper.gather_all_data_for_week(
        season=season, week=week, season_type=season_type, as_json=True
    )
    games = list(game_data.values())
    for idx, game in enumerate(games):
        with open(f"archive/fixtures/complete_game_{idx+1}.json", "w") as outfile:
            json.dump(game, outfile, indent=4, cls=DateTimeEncoder)
    else:
        click.echo(game_data)
