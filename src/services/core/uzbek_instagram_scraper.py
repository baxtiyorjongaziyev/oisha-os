"""
Facade for Uzbek Instagram Scraper.
Delegates to modular subpackage in src.services.core.instagram.
"""
from src.services.core.instagram.models import InstagramProfile
from src.services.core.instagram.real_scraper import InstagramScraperReal
from src.services.core.instagram.browser_scraper import InstagramScraperBrowser

__all__ = [
    "InstagramProfile",
    "InstagramScraperReal",
    "InstagramScraperBrowser",
]
