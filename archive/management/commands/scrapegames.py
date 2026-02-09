import json
import logging

from django.core.management.base import BaseCommand

from archive.scrapers import SportsRefCFBScraper

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Scrape reference sources to compile authoratative list of games."

    def add_arguments(self, parser):
        parser.add_argument("league", type=str)
        parser.add_argument("season", type=int)
        parser.add_argument("--week", type=int)
        parser.add_argument("--data_path", type=str)

    def handle(self, *args, **options):
        from pprint import pprint

        print("\n\noptions:")
        pprint(options, indent=4)

        league_short_name = options["league"]
        season = options["season"]
        week = options.get("week")

        match league_short_name:
            case "NCAA - FBS":
                with open(options["data_path"]) as infile:
                    games_data = json.load(infile)
                scraper = SportsRefCFBScraper(season=2025)
                self.stdout.write("Begin loading games data")
                logger.info(f"Loading games data from {options['data_path']}")
                games_list = scraper.load_games_from_scraped_json(
                    games_data=games_data, create=True
                )

                self.stdout.write(
                    self.style.SUCCESS(f"Successfully loaded {len(games_list)} games")
                )
                logger.info(f"Created {len(games_list)} game objects")

            case "NFL":
                pass
