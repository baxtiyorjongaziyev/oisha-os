"""
Facade for Airtable Sync Service.
Delegates to modular subpackage in src.services.core.airtable.
"""
import time
from src.services.core.airtable import AirtableOAuth, AirtableSync

__all__ = [
    "AirtableOAuth",
    "AirtableSync",
    "time",
]
