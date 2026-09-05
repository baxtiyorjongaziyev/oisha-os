"""
TelegramSalesCoachStore main class composing schema and analysis operations mixins.
"""
from __future__ import annotations

import logging
from typing import Any

from src.database_pool import db_pool
from src.services.core.salescoach_store.schema import SchemaMixin
from src.services.core.salescoach_store.analysis_ops import AnalysisOpsMixin

logger = logging.getLogger("TelegramSalesCoachStore")


class TelegramSalesCoachStore(SchemaMixin, AnalysisOpsMixin):
    """
    SQLite / Turso storage for Telegram sales coach analysis audits.
    """

    def __init__(self, db: Any = None):
        self.db = db if db is not None else db_pool
