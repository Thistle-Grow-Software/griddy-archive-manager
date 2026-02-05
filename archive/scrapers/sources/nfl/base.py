from griddy.nfl import GriddyNFL

from archive.scrapers import BaseScraper


class NFLScraper(BaseScraper):
    def __init__(self, email: str, password: str):
        self.client = GriddyNFL(
            login_email=email, login_password=password, headless_login=True
        )
