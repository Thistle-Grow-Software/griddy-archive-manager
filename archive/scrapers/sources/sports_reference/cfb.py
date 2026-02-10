import logging
import re
import time
from datetime import date, datetime
from random import uniform
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup, Tag
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

from archive.models import Game, League, Season, Team
from archive.scrapers.base import BaseScraper
from archive.utils import numberify

logger = logging.getLogger(__name__)


class SportsRefCFBScraper(BaseScraper):
    base_url = "https://www.sports-reference.com"
    date_format_string = "%b %d, %Y"
    time_format_string = "%I:%M %p"

    def __init__(
        self, league_short_name: str = "NCAA - FBS", season: int | None = None
    ):
        self.soup: BeautifulSoup | Tag | None = None
        self.league = League.objects.get(short_name=league_short_name)

        if season is None:
            season = date.today().year

        self.season = Season.objects.get(league=self.league, year=season)
        self.fcs_schools = set()
        self.failed_games = []
        self.processed_games = set()

    def parse_team_row(self, row: Tag) -> dict:
        team_data = {}
        for cell in row.find_all("td"):
            if cell["data-stat"] == "school_name":
                anchor = cell.find("a")
                team_data["sports_ref_path"] = anchor["href"]

            team_data[cell["data-stat"]] = cell.get_text(strip=True)
        return numberify(data=team_data)

    def extract_list_of_all_cfb_teams(
        self, team_idx: str = "/cfb/schools/index.html"
    ) -> list[dict]:
        soup = self.fetch_soup(sub_path=team_idx)
        schools_table = soup.find("table", id="schools")

        body_rows = [
            row
            for row in schools_table.find("tbody").find_all("tr")
            if "thead" not in row.get("class", [])
        ]

        return [self.parse_team_row(row=row) for row in body_rows]

    def extract_team_details(self) -> list[dict]:

        existing_team_names = Team.objects.values_list("name", flat=True)

        logger.info("Compiling team details")
        all_teams = self.extract_list_of_all_cfb_teams()
        logger.info("Successfully extracted list of teams")

        cur_count = 1
        total_teams = len(all_teams)
        for team in all_teams:
            logger.info(
                f"Processing team {team['school_name']} ({cur_count} of {total_teams})"
            )

            if team["school_name"] not in existing_team_names:
                logger.debug(
                    f"{team['school_name']} is not among the list of current teams. Skipping."
                )
                continue

            team.update(
                self.extract_additional_team_details(team_path=team["sports_ref_path"])
            )
            time.sleep(uniform(2.5, 3.5))
            cur_count += 1

        return all_teams

    def extract_additional_team_details(self, team_path: str) -> dict:
        supp_data = {}

        soup = self.fetch_soup(sub_path=team_path)
        image_tag = soup.find("img", class_="teamlogo")
        supp_data["logo_url"] = image_tag["src"]

        logger.debug("Successfully extracted logo URL")

        team_info = soup.find("div", id="info")
        try:
            supp_data.update(self.extract_venue_info(team_info=team_info))
        except AttributeError:
            logger.warning("No venue information available.")

        return supp_data

    def extract_venue_info(self, team_info: Tag) -> dict:
        logger.debug("Extracting Venue information")
        stadium_label = team_info.find(
            "strong", string=lambda s: "stadium" in s.lower()
        )
        venue_text = stadium_label.next_sibling.get_text(strip=True)

        # When this works properly, we will get a list with two elements:
        # The stadium's name, and capacity
        venue_parts = venue_text.replace(")", "").split(" (cap. ")
        venue_data = {
            "name": venue_parts[0],
            "capacity": int(venue_parts[1].replace(",", "")),
        }
        location_label = team_info.find(
            "strong", string=lambda s: "location" in s.lower()
        )
        location_text = location_label.next_sibling.get_text(strip=True)
        location_parts = location_text.split(",")
        venue_data["city"] = location_parts[0].strip()
        venue_data["state"] = location_parts[1].strip()

        return venue_data

    def fetch_season_table(self, season: int):
        full_url = f"{self.base_url}/cfb/years/{season}-schedule.html"
        response = requests.get(full_url)
        response.raise_for_status()

        full_soup = BeautifulSoup(response.text)
        self.soup = full_soup.find(id="schedule")

    def extract_game_rows_from_schedule(self) -> list[dict]:
        data = []
        body_rows = self.soup.find("tbody").find_all("tr")

        for row in body_rows:
            if row["class"] == ["thead"]:
                continue

            row_data = {}
            for cell in row.find_all("td"):
                key = cell["data-stat"]
                value = cell.get_text(strip=True)
                row_data[key] = value

                if key == "date_game":
                    anchor_tag = cell.find("a")
                    row_data["boxscore_path"] = anchor_tag["href"]
                elif key == "winner_school_name":
                    anchor_tag = cell.find("a")
                    row_data["winning_team_path"] = anchor_tag["href"]
                elif key == "loser_school_name":
                    anchor_tag = cell.find("a")
                    row_data["losing_team_path"] = anchor_tag["href"]

            header_cell = row.find("th")
            # Maps "ranker": i where i is the game number
            row_data[header_cell["data-stat"]] = header_cell.get_text(strip=True)

            data.append(row_data)

        return data

    def _determine_game_type(self, game_notes: str) -> str:
        if "bowl" in game_notes.lower():
            return "BOWL"
        elif "college football playoff" in game_notes.lower():
            return "PLAYOFF"
        else:
            return "REG"

    def _parse_team_name_for_rank(self, team_name: str) -> tuple[str | None, Team]:
        match = re.search(r"\((\d{1,2})\)", team_name)
        rank = int(match.group(1)) if match else None
        name = re.sub(r"\(\d{1,2}\)", "", team_name).strip()

        try:
            team_obj = Team.objects.get(Q(name=name) | Q(alternate_name=name))
        except ObjectDoesNotExist:
            self.fcs_schools.add(name)
            raise

        return rank, team_obj

    def _extract_game_team_info(self, game_data: dict):
        teams_info = {}

        winner_is_away = game_data["game_location"] == "@"
        if winner_is_away:
            away_team_name = game_data["winner_school_name"]
            teams_info["final_away_score"] = game_data["winner_points"]
            home_team_name = game_data["loser_school_name"]
            teams_info["final_home_score"] = game_data["loser_points"]

        else:
            away_team_name = game_data["loser_school_name"]
            teams_info["final_away_score"] = game_data["loser_points"]
            home_team_name = game_data["winner_school_name"]
            teams_info["final_home_score"] = game_data["winner_points"]

        ap_rank_away, away_team = self._parse_team_name_for_rank(
            team_name=away_team_name
        )
        ap_rank_home, home_team = self._parse_team_name_for_rank(
            team_name=home_team_name
        )

        teams_info["ap_rank_away"] = ap_rank_away
        teams_info["away_team"] = away_team
        teams_info["ap_rank_home"] = ap_rank_home
        teams_info["home_team"] = home_team

        return teams_info

    def transform_sports_ref_json(self, game_data: dict) -> Game:
        transformed_data = {
            "league": self.league,
            "season": self.season,
            "date_local": date.strptime(
                game_data["date_game"], self.date_format_string
            ),
            "kickoff_time_local": datetime.strptime(
                game_data["time_game"], self.time_format_string
            )
            .replace(tzinfo=ZoneInfo("US/Eastern"))
            .time(),
            "week": game_data["week_number"],
            "game_type": self._determine_game_type(game_data["notes"]),
            "competition_name": game_data["notes"],
            "neutral_site": game_data["game_location"] == "N",
            "external_ids": {
                "sports_reference": game_data["boxscore_path"].split("/")[-1]
            },
            "notes": game_data["notes"],
            "ordinal": game_data["ranker"],
            **self._extract_game_team_info(game_data=game_data),
        }
        if not transformed_data["neutral_site"]:
            transformed_data["venue"] = transformed_data["home_team"].current_venue

        return Game(**transformed_data)

    def load_games_from_scraped_json(
        self, games_data: list[dict], create: bool = False
    ):
        game_objects = []
        for gd in games_data:
            if gd["ranker"] in self.processed_games:
                logger.debug(f"Already processed game {gd['ranker']}. Skipping")
                continue
            try:
                game_objects.append(self.transform_sports_ref_json(game_data=gd))
                self.processed_games.add(gd["ranker"])
            except ObjectDoesNotExist:
                self.failed_games.append(gd)
        if create:
            return Game.objects.bulk_create(game_objects)
        else:
            return game_objects
