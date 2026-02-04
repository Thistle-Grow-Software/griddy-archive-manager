from django.core.management.base import BaseCommand
from django.db.models import Q

from archive.models import Team, OrgUnit, TeamAffiliation
from archive.scrapers import CFBTeamScraper, get_conf_short_name

class Command(BaseCommand):
    help = "Scrape reference sources to compile authoratative list of games."

    def add_arguments(self, parser):
        parser.add_argument("html_file", type=str)

    def handle(self, *args, **options):
        html_path = options["html_file"]
        scraper = CFBTeamScraper(html_path=html_path)
        team_data = scraper.extract_all_team_data()

        for td in team_data:
            print(f"Creating team object for {td['school']}")
            team, created = Team.objects.get_or_create(name=td["school"],
                        short_name="",
                        city=td["city"],
                        state=td["state"],
                        country="US",
                        school_name=td["school_name"],
                        mascot=td["nickname"])

            if created:
                print(f"Created new team object in database")

            print(f"Looking up Conference: {td['current_conference']}")

            conference = OrgUnit.objects.get(short_name=get_conf_short_name(td["current_conference"]))

            print(f"Adding {team} to {conference}")
            affiliation = TeamAffiliation(team=team, org_unit=conference)
            affiliation.save()
