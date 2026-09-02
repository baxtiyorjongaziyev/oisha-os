"""
LeadScraper main engine composing group, dialog, and base scraping mixins.
"""
from __future__ import annotations

import os
import logging
from typing import Any, Dict, List, Optional, Set

from google import genai

from src.settings import settings
from src.services.core.leads.scraper.base import BaseScraperMixin
from src.services.core.leads.scraper.dialog_sync import DialogSyncMixin
from src.services.core.leads.scraper.group_sync import GroupSyncMixin

logger = logging.getLogger("LeadScraper")


class LeadScraper(BaseScraperMixin, GroupSyncMixin, DialogSyncMixin):
    """
    Telegram guruhlar va dialoglardan yangi lidlarni qirqib olib (scraping),
    AmoCRM ga to'g'ri 'Yangi Lid' yoki 'Mijoz' qilib kirituvchi tizim.
    """

    def __init__(
        self,
        google_service,
        db,
        client=None,
        amocrm=None,
        notify_callback=None,
        message_controller=None,
    ):
        self.google = google_service
        self.db = db
        self.client = client
        self.amocrm = amocrm
        self.notify_callback = notify_callback
        self.message_controller = message_controller

        # Configure Gemini with modern SDK
        self.genai_client = genai.Client(
            api_key=settings.GEMINI_API_KEY.get_secret_value()
        )
        self.model_name = os.getenv("GEMINI_LEAD_SCRAPER_MODEL", settings.GEMINI_CALL_MODEL)
