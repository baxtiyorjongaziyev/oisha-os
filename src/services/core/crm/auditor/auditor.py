"""
Main CRMContactsAuditor class composed of modular mixins.
"""
import logging
import os
from typing import Any, Optional

try:
    from google import genai
except ImportError:
    genai = None

from src.services.core.crm.auditor.db_storage import DatabaseStorageMixin
from src.services.core.crm.auditor.telegram_history import TelegramHistoryMixin
from src.services.core.crm.auditor.tasks_notes import TasksNotesMixin
from src.services.core.crm.auditor.classifier import ClassifierMixin
from src.services.core.crm.auditor.temperature import TemperatureMixin

logger = logging.getLogger(__name__)


class CRMContactsAuditor(
    DatabaseStorageMixin,
    TelegramHistoryMixin,
    TasksNotesMixin,
    ClassifierMixin,
    TemperatureMixin,
):
    """
    Surgical CRM & Multi-channel Contact Auditor.
    Audits AmoCRM leads, cross-references Telegram direct & group chats,
    detects unanswered messages, duplicates, and missing next steps.
    """

    def __init__(
        self,
        amocrm: Any = None,
        telegram_client: Any = None,
        gemini_api_key: Optional[str] = None,
        db_path: str = "data/crm_contacts_audit.db",
        bot_client: Any = None,
        *,
        db: Any = None,
        tg_client: Any = None,
        model_name: Optional[str] = None,
    ):
        resolved_tg = tg_client if tg_client is not None else telegram_client
        self.amocrm = amocrm
        self.db = db
        self.telegram = resolved_tg
        self.tg_client = resolved_tg
        self.bot_client = bot_client
        raw_key = gemini_api_key or os.getenv("GEMINI_API_KEY") or ""
        if hasattr(raw_key, "get_secret_value"):
            raw_key = raw_key.get_secret_value()
        self.gemini_key = str(raw_key or "").strip()
        self.model_name = model_name or os.getenv("GEMINI_CRM_AUDIT_MODEL") or "gemini-2.5-flash"
        self.genai_client = None
        if self.gemini_key and genai is not None:
            try:
                self.genai_client = genai.Client(api_key=self.gemini_key)
            except Exception as exc:
                logger.warning("[AUDITOR] Gemini client init skipped: %s", exc)
        self.db_path = db_path
        self._group_dialogs_cache: list = []
        self._dialogs_cache: Optional[list] = None
        self._dialogs_cache_time: Any = None
        self._cache_timestamp: float = 0.0
        self._cache_ttl: float = 300.0
