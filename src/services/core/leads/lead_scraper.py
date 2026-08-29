"""
Facade for Lead Scraper.
Delegates to modular subpackage in src.services.core.leads.scraper.
"""
from src.services.core.leads.scraper import LeadScraper

__all__ = [
    "LeadScraper",
]
