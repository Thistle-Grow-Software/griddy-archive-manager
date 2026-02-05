import re

from bs4 import BeautifulSoup, Tag

from archive.scrapers.base import BaseScraper

fbs_columns = [
    "school",
    "nickname",
    "city",
    "state",
    "enrollment",
    "current_conference",
    "former_conferences",
    "first_year",
    "joined_fbs",
    "first_joined_fbs",
    "left_fbs",
]

fcs_columns = [
    "team",
    "name",
    "school",
    "city",
    "state",
    "program_established",
    "first_fcs_season",
    "conference",
]


class WikipediaCFBScraper(BaseScraper):
    def __init__(self, html_path: str, subdivision: str = "fbs"):
        with open(html_path) as infile:
            self.soup = BeautifulSoup(infile, features="html.parser")
        self.team_table = self._extract_teams_table()
        self.subdivision = subdivision
        self.column_headers = fbs_columns if subdivision == "fbs" else fcs_columns

    def _extract_teams_table(self):
        return self.soup.find("table", class_="wikitable sortable jquery-tablesorter")

    def _extract_formal_name(self, cell: Tag) -> str:
        formal_name = None

        anchor = cell.find("a")
        if anchor:
            formal_name = anchor["title"]

        return formal_name

    def process_row(self, row: Tag) -> dict:
        cells = row.find_all("td")
        team_data = {}
        if self.subdivision == "fbs":
            team_data["school_name"] = self._extract_formal_name(cells[0])

        row_values = [re.sub(r"\[[a-z]+\]", "", c.get_text(strip=True)) for c in cells]
        team_data.update(dict(zip(self.column_headers, row_values)))
        print("ARMADILLO", self.column_headers)
        print("BADGER", row_values)
        from pprint import pprint

        pprint(team_data)

        if self.subdivision == "fcs":
            team_data["nickname"] = team_data.pop("name")
            team_data["name"] = team_data.pop("team")
            team_data["school_name"] = team_data.pop("school")

        return team_data

    def extract_all_team_data(self):
        return [
            self.process_row(row=row)
            for row in self.team_table.find("tbody").find_all("tr")
        ]
