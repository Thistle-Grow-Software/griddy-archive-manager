from django.core.management.base import BaseCommand


class ScrapeGames(BaseCommand):
    help = "Scrape reference sources to compile authoratative list of games."

    def handle(self, *args, **options):
        pass
