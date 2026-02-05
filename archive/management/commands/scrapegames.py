import json
import logging

from django.core.management.base import BaseCommand

from archive.scrapers import SportsRefCFBScraper

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Scrape reference sources to compile authoratative list of games."

    def add_arguments(self, parser):
        parser.add_argument("data_path", type=str)

    def handle(self, *args, **options):
        with open(options["data_path"]) as infile:
            games_data = json.load(infile)
        scraper = SportsRefCFBScraper(season=2025)
        logger.info("Begin loading games data")
        games_list = scraper.load_games_from_scraped_json(
            games_data=games_data, create=True
        )

        logger.info("Loaded %s games", len(games_list))
        logger.debug("Games list: %s", games_list)
