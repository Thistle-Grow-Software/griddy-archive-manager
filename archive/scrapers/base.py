import requests
from bs4 import BeautifulSoup


class BaseScraper:
    base_url = ""

    def fetch_soup(self, sub_path: str) -> BeautifulSoup:
        full_url = f"{self.base_url}{sub_path}"
        response = requests.get(full_url)
        response.raise_for_status()
        return BeautifulSoup(response.text)
