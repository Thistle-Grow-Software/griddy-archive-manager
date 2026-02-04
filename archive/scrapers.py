import re
import requests
import time

from random import uniform
from typing import List, Dict

from bs4 import BeautifulSoup, Tag

from archive.models import Team

class BaseScraper:
    base_url = ""

    def fetch_soup(self, sub_path: str) -> BeautifulSoup:
        full_url = f"{self.base_url}{sub_path}"
        response = requests.get(full_url)
        response.raise_for_status()
        return BeautifulSoup(response.text)


def numberify(data: Dict):
    for key, value in data.items():
        try:
            value = int(value)
        except ValueError:
            try:
                value = float(value)
            except ValueError:
                value = value
        data[key] = value
    return data

class SportsRefScraper(BaseScraper):
    base_url = "https://www.sports-reference.com"
    def __init__(self):
        self.soup = None
        self.header_values = None

    def parse_team_row(self, row: Tag) -> Dict:
        team_data = {}
        for cell in row.find_all("td"):
            if cell["data-stat"] == "school_name":
                anchor = cell.find("a")
                team_data["sports_ref_path"] = anchor["href"]

            team_data[cell["data-stat"]] = cell.get_text(strip=True)
        return numberify(data=team_data)

    def extract_list_of_all_cfb_teams(self, team_idx: str = "/cfb/schools/index.html") -> List[Dict]:
        soup = self.fetch_soup(sub_path=team_idx)
        schools_table = soup.find("table", id="schools")
        header_cells = schools_table.find("thead").find_all("tr")[-1].find_all("th")
        self.header_values = [h["data-stat"] for h in header_cells]

        body_rows = [row for row in schools_table.find("tbody").find_all("tr")
                     if "thead" not in row.get("class", [])]

        return [self.parse_team_row(row=row) for row
                in body_rows]

    def extract_venue_info(self, team_info: Tag) -> Dict:
        print("Extracting Venue information")
        stadium_label = team_info.find("strong", string=lambda s: "stadium" in s.lower())
        venue_text = stadium_label.next_sibling.get_text(strip=True)

        # When this works properly, we will get a list with two elements:
        # The stadium's name, and capacity
        venue_parts = venue_text.replace(")", "").split(" (cap. ")
        venue_data = {
            "name": venue_parts[0],
            "capacity": int(venue_parts[1].replace(",", ""))
        }
        location_label = team_info.find("strong", string=lambda s: "location" in s.lower())
        location_text = location_label.next_sibling.get_text(strip=True)
        location_parts = location_text.split(",")
        venue_data["city"] = location_parts[0].strip()
        venue_data["state"] = location_parts[1].strip()

        return venue_data

    def extract_additional_team_details(self, team_path: str) -> Dict:
        supp_data = {}

        soup = self.fetch_soup(sub_path=team_path)
        image_tag = soup.find("img", class_="teamlogo")
        supp_data["logo_url"] = image_tag["src"]

        print("Successfully extracted logo URL")

        team_info = soup.find("div", id="info")
        try:
            supp_data.update(self.extract_venue_info(team_info=team_info))
        except AttributeError:
            print("No venue information available.")

        return supp_data

    def compile_team_details(self) -> List[Dict]:

        existing_team_names = Team.objects.values_list("name", flat=True)

        print("Compiling team details")
        all_teams = self.extract_list_of_all_cfb_teams()
        print("Successfully extracted list of teams")

        cur_count = 1
        total_teams = len(all_teams)
        for team in all_teams:
            print(f"\n\n\n===== Processing team {team['school_name']} =====")
            print(f"No. {cur_count} of {total_teams}")

            if team["school_name"] not in existing_team_names:
                print(f"{team['school_name']} is not among the list of current teams. Skipping.")
                continue

            team.update(self.extract_additional_team_details(team_path=team["sports_ref_path"]))
            time.sleep(uniform(2.5, 3.5))
            cur_count += 1

        return all_teams


class CFBScraper(BaseScraper):
    base_url = "https://www.sports-reference.com"

    def __init__(self):
        self.soup: BeautifulSoup | Tag | None = None

    def fetch_season_table(self, season: int):
        full_url = f"{self.base_url}/cfb/years/{season}-schedule.html"
        response = requests.get(full_url)
        response.raise_for_status()

        full_soup = BeautifulSoup(response.text)
        self.soup = full_soup.find(id="schedule")

    def extract_schedule_rows(self) -> List[Dict]:
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


def get_conf_short_name(name):
    short_name = ""
    match name:
        case "Mountain West":
            short_name = "MWC"
        case "MAC":
            short_name = "MAC"
        case "SEC":
            short_name = "SEC"
        case "Sun Belt":
            short_name = "SBC"
        case "Big 12":
            short_name = "Big 12"
        case "American":
            short_name = "American"
        case "ACC":
            short_name = "ACC"
        case "CUSA":
            short_name = "CUSA"
        case "Big Ten":
            short_name = "Big Ten"
        case "Pac-12":
            short_name = "Pac-12"
        case "Independent":
            short_name = "Ind"
        case _:
            short_name = name
    return short_name

class CFBTeamScraper(BaseScraper):
    def __init__(self, html_path: str):
        with open(html_path, "r") as infile:
            self.soup = BeautifulSoup(infile, features="html.parser")
        self.team_table = self._extract_teams_table()
        self.column_headers = ["school",
                               "nickname",
                               "city",
                               "state",
                               "enrollment",
                               "current_conference",
                               "former_conferences",
                               "first_year",
                               "joined_fbs",
                               "first_joined_fbs",
                               "left_fbs"]

    def _extract_teams_table(self):
        return self.soup.find("table", class_="wikitable sortable jquery-tablesorter")

    def _extract_formal_name(self, cell: Tag) -> str:
        formal_name = None

        anchor = cell.find("a")
        if anchor:
            formal_name = anchor["title"]

        return formal_name

    def process_row(self, row: Tag) -> Dict:
        cells = row.find_all("td")
        team_data = {"school_name": self._extract_formal_name(cell=cells[0])}

        row_values = [re.sub(r"\[[a-z]+\]", "", c.get_text(strip=True))
                      for c in cells]
        team_data.update(dict(zip(self.column_headers, row_values)))


        return team_data

    def extract_all_team_data(self):
        return [self.process_row(row=row)
                for row in self.team_table.find("tbody").find_all("tr")]



