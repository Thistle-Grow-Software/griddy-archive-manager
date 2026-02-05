import json

from django.core.management.base import BaseCommand

from archive.scrapers import SportsRefCFBScraper

class Command(BaseCommand):
    help = "Scrape reference sources to compile authoratative list of games."

    def add_arguments(self, parser):
        parser.add_argument("data_path", type=str)

    def handle(self, *args, **options):
        with open(options["data_path"], "r") as infile:
            games_data = json.load(infile)
        scraper = SportsRefCFBScraper(season=2025)
        print("Begin loading games data")
        games_list = scraper.load_games_from_scraped_json(games_data=games_data, create=True)

        print(games_list)
