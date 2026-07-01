from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from telethon import TelegramClient
from src.controllers.message_controller import MessageController
from src.services.core.safe_responder import SafeResponder
from src.services.core.action_parser import ActionParser
from src.services.core.lead_scraper import LeadScraper
from src.services.core.advisor_agent import AdvisorAgent
from src.services.core.auto_lead_agent import AutoLeadAgent
from src.services.core.activity_monitor import ActivityMonitor
from src.services.core.audit_agent import AuditAgent
from src.services.core.folder_manager import FolderManager
from src.services.utils.voice_processor import VoiceProcessor
from src.services.utils.access_manager import AccessManager
from src.services.core.admin_bot import AdminBot
from src.services.core.juma_notifier import JumaNotifier
from src.services.core.session_manager import SessionManager
from src.services.core.meeting_scheduler import TelegramMeetingScheduler
from src.services.core.workflow_manager import WorkflowManager


@dataclass
class ApplicationContext:
    """Centralized context for all global Oisha-OS services."""

    msg_controller: Optional[MessageController] = None
    client: Optional[TelegramClient] = None
    bot_client: Optional[TelegramClient] = None
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
    juma_notifier: Optional[JumaNotifier] = None
    session_manager: Optional[SessionManager] = None
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

    # Runtime state
    crm_audit_running: bool = False
    last_heartbeat: Optional[float] = None
    excluded_folder_cache: Dict[str, Any] = field(default_factory=dict)

    # Concurrency controls
    task_semaphore: Optional[Any] = None  # asyncio.Semaphore


app_ctx = ApplicationContext()
