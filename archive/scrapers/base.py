import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class BaseScraper:
    base_url = ""

    def _fetch_with_playwright(self, url: str) -> str:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            logger.info("Launching browser with playwright.")
            browser = playwright.firefox.launch(headless=True)

            page = browser.new_page()
            logger.info(f"Navigating to {url}")
            page.goto(url, wait_until="domcontentloaded")

            return page.content()


    def fetch_soup(self, sub_path: str, use_playwright: bool = False) -> BeautifulSoup:
        full_url = f"{self.base_url}{sub_path}"
        if use_playwright:
            text = self._fetch_with_playwright(url=full_url)
        else:
            response = requests.get(full_url)
            response.raise_for_status()
            text = response.text
        return BeautifulSoup(text)
