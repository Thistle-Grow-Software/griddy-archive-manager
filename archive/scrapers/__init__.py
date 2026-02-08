from .base import BaseScraper
from .sources.nfl.base import NFLScraper
from .sources.sports_reference.cfb import SportsRefCFBScraper
from .sources.wikipedia.cfb import WikipediaCFBScraper

__all__ = ["BaseScraper", "NFLScraper", "SportsRefCFBScraper", "WikipediaCFBScraper"]
