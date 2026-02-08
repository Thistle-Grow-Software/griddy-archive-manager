import logging
from datetime import date

logger = logging.getLogger(__name__)

from archive.models import OrgUnit, Team, TeamAffiliation, TeamVenueOccupancy, Venue
from archive.scrapers import BaseScraper
from archive.utils import get_content_file_from_url


class NFLScraper(BaseScraper):
    logo_format_instructions = "h_144,w_144,q_auto,f_auto,dpr_2.0"

    def transform_team_data(self, nfl_data: dict) -> dict:
        griddy_data = {
            "name": nfl_data["name"],
            "alternate_name": nfl_data["fullName"],
            "short_name": nfl_data["abbr"],
            "city": nfl_data["city"],
            # TODO: For some reason th NFL just stores the city value in cityState
            "state": nfl_data["cityState"],
            "country": "US",
            "mascot": nfl_data["nickname"],
            "external_ids": {
                "nfl.com": {
                    "slug": nfl_data["slug"],
                    "smartId": nfl_data["smartId"],
                    "teamId": nfl_data["teamId"],
                }
            },
            "primary_color": nfl_data["primaryColor"].replace("#", ""),
            "secondary_color": nfl_data["secondaryColor"].replace("#", ""),
            "tertiary_color": nfl_data["tertiaryColor"].replace("#", ""),
            "additional_colors": {
                "altColor": nfl_data["altColor"],
                "darkColor": nfl_data["darkColor"],
            },
            "logo": nfl_data["logo"].format(
                formatInstructions=self.logo_format_instructions
            ),
        }

        addl_data = {
            key: nfl_data[key]
            for key in [
                "conference",
                "division",
                "domain",
                "isProBowl",
                "nick",
                "season",
                "stadiumName",
                "teamSiteTicketUrl",
                "teamSitUrl",
                "teamType",
                "ticketPhoneNumber",
                "yearFound",
            ]
            if key in nfl_data
        }
        griddy_data["bonus_data"] = addl_data

        return griddy_data

    def _create_division_affiliation(self, team: Team, div_str: str):
        division = OrgUnit.objects.get(long_name=div_str)
        ta = TeamAffiliation(
            team=team, org_unit=division, start_date=date(year=2002, month=9, day=5)
        )
        ta.save()

    def create_db_object(self, raw_data):
        logger.info(f"Creating team for {raw_data['name']}")
        team_data = self.transform_team_data(nfl_data=raw_data)
        logger.info("Transformed data")
        logo_url = team_data.pop("logo")
        team = Team(**team_data)
        team.save()
        logger.info(f"Saved team to disk. ID={team.id}")
        team.logo.save(
            f"{raw_data['slug']}.png", get_content_file_from_url(logo_url), save=True
        )
        logger.info("Saved logo to disk")

        self._create_division_affiliation(
            team=team,
            div_str=raw_data["division"]["full_name"].replace(" Division", ""),
        )
        logger.info("Created division affiliation")
        self.create_team_venue_occupancy(team=team, venue_name=raw_data["stadiumName"])
        logger.info("Created team occupancy record")

    def process_venue(self, venue_data: dict):
        venue = Venue.objects.filter(name=venue_data["name"]).first()
        if venue is None:
            venue = Venue(
                name=venue_data.pop("name"),
                city=venue_data.pop("city"),
                state=venue_data.pop("territory", ""),
                country=venue_data.pop("country"),
                external_ids={"nfl": {"id": venue_data.pop("id")}},
                bonus_data=venue_data,
            )
            venue.save()
        return venue

    def create_team_venue_occupancy(self, team: Team, venue_name: str):
        venue = Venue.objects.filter(name=venue_name).first()
        if venue is None:
            return
        tvo = TeamVenueOccupancy(team=team, venue=venue)
        tvo.save()
