import requests

from typing import List, Dict

from bs4 import BeautifulSoup, Tag

class BaseScraper:
    base_url = ""

    def fetch_soup(self, sub_path: str) -> BeautifulSoup:
        full_url = f"{self.base_url}{sub_path}"
        response = requests.get(full_url)
        response.raise_for_status()
        return BeautifulSoup(response.text)


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


class CFBTeamScraper(BaseScraper):
    def __init__(self, team_path: str):
        self.soup = self.fetch_soup(sub_path=team_path)
