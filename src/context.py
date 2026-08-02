from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from telethon import TelegramClient
    from src.controllers.message_controller import MessageController
    from src.services.core.safe_responder import SafeResponder
    from src.services.core.action_parser import ActionParser
    from src.services.core.leads.lead_scraper import LeadScraper
    from src.services.core.advisor_agent import AdvisorAgent
    from src.services.core.auto_lead_agent import AutoLeadAgent
    from src.services.core.activity_monitor import ActivityMonitor
    from src.services.core.audit_agent import AuditAgent
    from src.services.core.folder_manager import FolderManager
    from src.services.utils.voice_processor import VoiceProcessor
    from src.services.utils.access_manager import AccessManager
    from src.services.core.admin_bot import AdminBot
    from src.services.core.juma_notifier import JumaNotifier
    from src.services.core.telegram.session_manager import SessionManager
    from src.services.core.meeting_scheduler import TelegramMeetingScheduler
    from src.services.core.workflow_manager import WorkflowManager


logger = logging.getLogger(__name__)


def _telegram_salescoach_enabled() -> bool:
    raw = os.getenv("TELEGRAM_SALESCOACH_ENABLED")
    if raw is None:
        from src.settings import settings

        return bool(getattr(settings, "TELEGRAM_SALESCOACH_ENABLED", False))
    return raw.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@dataclass
class ApplicationContext:
    """Centralized context for all global Oisha-OS services."""

    msg_controller: Optional[MessageController] = None
    client: Optional[TelegramClient] = None
    bot_client: Optional[TelegramClient] = None
    bot_runtime: Optional[Any] = None
    lead_scraper: Optional[LeadScraper] = None
    action_parser: Optional[ActionParser] = None
    advisor_agent: Optional[AdvisorAgent] = None
    auto_lead_agent: Optional[AutoLeadAgent] = None
    safe_responder: Optional[SafeResponder] = None
    activity_monitor: Optional[ActivityMonitor] = None
    audit_agent: Optional[AuditAgent] = None
    workflow_manager: Optional[WorkflowManager] = None
    access_manager: Optional[AccessManager] = None
    admin_bot: Optional[AdminBot] = None
    admin_aiogram_dispatcher: Optional[Any] = None
    aiogram_bot_head: Optional[Any] = None
    juma_notifier: Optional[JumaNotifier] = None
    session_manager: Optional[SessionManager] = None
    telegram_session_manager: Optional[Any] = None
    userbot_group_fallback: Optional[Any] = None
    surgical_integration: Optional[Any] = None
    evolution_scheduler: Optional[Any] = None
    meeting_scheduler: Optional[TelegramMeetingScheduler] = None
    oisha_brain: Optional[Any] = None
    bot_messenger: Optional[Any] = None
    agent_orchestrator: Optional[Any] = None
    folder_manager: Optional[FolderManager] = None
    voice_processor: Optional[VoiceProcessor] = None
    health_api_server: Optional[Any] = None
    bot_token_str: Optional[str] = None
    welcome_manager: Optional[Any] = None
    scouter: Optional[Any] = None

    # Telegram SalesCoach runtime. All fields stay None unless the explicit
    # TELEGRAM_SALESCOACH_ENABLED feature flag is enabled on the Oracle VM.
    salescoach_sync: Optional[Any] = None
    telegram_salescoach: Optional[Any] = None
    telegram_salescoach_store: Optional[Any] = None
    salescoach_task_writer: Optional[Any] = None
    telegram_salescoach_install_task: Optional[Any] = None

    # Runtime state
    crm_audit_running: bool = False
    last_heartbeat: Optional[float] = None
    excluded_folder_cache: Dict[str, Any] = field(default_factory=dict)

    # Concurrency controls
    task_semaphore: Optional[Any] = None

    def __setattr__(self, name: str, value: Any) -> None:
        object.__setattr__(self, name, value)
        if name not in {"client", "msg_controller", "bot_runtime"}:
            return
        self._maybe_schedule_telegram_salescoach_install()

    def _maybe_schedule_telegram_salescoach_install(self) -> None:
        """Install after canonical boot wiring, without changing legacy main.py."""
        if not _telegram_salescoach_enabled():
            return
        if getattr(self, "telegram_salescoach", None) is not None:
            return
        existing = getattr(self, "telegram_salescoach_install_task", None)
        if existing is not None and not existing.done():
            return
        if (
            getattr(self, "client", None) is None
            or getattr(self, "msg_controller", None) is None
            or getattr(self, "bot_runtime", None) is None
        ):
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        from src.services.core.telegram_salescoach_runtime import (
            install_telegram_salescoach,
        )

        task = loop.create_task(
            install_telegram_salescoach(self),
            name="telegram_salescoach_install",
        )
        object.__setattr__(self, "telegram_salescoach_install_task", task)

        def _finished(completed: asyncio.Task[Any]) -> None:
            try:
                completed.result()
            except Exception as exc:
                logger.warning(
                    "Telegram SalesCoach install failed: %s",
                    type(exc).__name__,
                )
            finally:
                object.__setattr__(self, "telegram_salescoach_install_task", None)

        task.add_done_callback(_finished)


app_ctx = ApplicationContext()
