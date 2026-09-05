"""
Main CRMContactsAuditor class composed of modular mixins.
"""
import logging
import os
from typing import Optional

from src.services.core.crm.auditor.db_storage import (
    DatabaseStorageMixin,
)
from src.services.core.crm.auditor.telegram_history import TelegramHistoryMixin
from src.services.core.crm.auditor.tasks_notes import TasksNotesMixin
from src.services.core.crm.auditor.classifier import ClassifierMixin

logger = logging.getLogger(__name__)


class CRMContactsAuditor(
    DatabaseStorageMixin,
    TelegramHistoryMixin,
    TasksNotesMixin,
    ClassifierMixin,
):
    """
    Surgical CRM & Multi-channel Contact Auditor.
    Audits AmoCRM leads, cross-references Telegram direct & group chats,
    detects unanswered messages, duplicates, and missing next steps.
    """

    def __init__(
        self,
        amocrm=None,
        telegram_client=None,
        gemini_api_key: Optional[str] = None,
        db_path: str = "data/crm_contacts_audit.db",
        bot_client=None,
    ):
        self.amocrm = amocrm
        self.telegram = telegram_client
        self.bot_client = bot_client
        self.gemini_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.db_path = db_path
        self._group_dialogs_cache: list = []
        self._cache_timestamp: float = 0.0
        self._cache_ttl: float = 300.0
