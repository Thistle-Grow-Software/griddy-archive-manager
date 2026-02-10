import json
import logging

from django.core.management.base import BaseCommand

from archive.models import Team
from archive.scrapers import NFLScraper

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("data_path", type=str)

    def handle(self, *args, **options):
        with open(options["data_path"]) as infile:
            nfl_team_data = json.load(infile)

        scraper = NFLScraper()

        logger.info("Begin loading NFL teams")

        for team_data in nfl_team_data:
            if (
                team_data["abbr"] in ["AFC", "NFC"]
                or Team.objects.filter(name=team_data["fullName"]).exists()
            ):
                continue
            scraper.create_db_object(raw_data=team_data)
