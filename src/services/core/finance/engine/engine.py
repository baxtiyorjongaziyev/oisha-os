"""
HisobchiEngine main class composing rules, transactions, and reports mixins.
"""
from __future__ import annotations

import logging
from typing import Any

from src.database_pool import db_pool
from src.services.core.finance.hisobchi_schema import ensure_hisobchi_db
from src.services.core.finance.accounting_period import (
    DEFAULT_TRACKING_START_DATE,
    parse_tracking_start_date,
)
from src.services.core.finance.engine.rules import RulesLearningMixin
from src.services.core.finance.engine.transactions import TransactionsMixin
from src.services.core.finance.engine.reports import ReportsMixin

logger = logging.getLogger(__name__)


class HisobchiEngine(RulesLearningMixin, TransactionsMixin, ReportsMixin):
    """
    Hisobchi moliyaviy tranzaksiyalarni boshqarish va avtomatik kategoriyalash dvigateli.
    """

    def __init__(
        self,
        db=None,
        gs_store: Any = None,
        tracking_start_date: str = DEFAULT_TRACKING_START_DATE,
    ) -> None:
        self._gs = gs_store
        self._tracking_start_date = parse_tracking_start_date(tracking_start_date)
        self._db = ensure_hisobchi_db(
            db if db is not None else db_pool
        )
