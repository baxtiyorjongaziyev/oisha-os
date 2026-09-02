"""
Domain agents, tools and managers initialization.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

import src.config as src_config
from src.services.core.advisor_agent import AdvisorAgent
from src.services.core.auto_lead_agent import AutoLeadAgent
from src.services.core.leads.scraper.scraper import LeadScraper
from src.services.core.meetings.scheduler import TelegramMeetingScheduler
from src.services.core.sales_coach import SalesCoach
from src.controllers.surgical_integration import get_surgical_integration
from src.bootstrap.helpers import _surgical_send
from src.context import app_ctx
from src.services.core.action_parser import ActionParser
from src.services.utils.access_manager import AccessManager
from src.services.core.activity_monitor import ActivityMonitor
from src.services.core.admin_bot import AdminBot
from src.services.core.amocrm_alert_forwarder import AmoCrmAlertForwarder
from src.services.core.audit_agent import AuditAgent
from src.services.core.safe_responder import SafeResponder
from src.services.core.telegram.session_manager import SessionManager
from src.services.core.workflow_manager import WorkflowManager
from src.services.core.juma_notifier import JumaNotifier
from src.entrypoint.crm_push import push_block_to_amocrm
from src.settings import settings

logger = logging.getLogger("OishaBootstrap")


def init_domain_agents(
    api_keys: Dict[str, Any],
    msg_controller: Any,
    client: Any,
    bot_client: Any,
    bot_runtime: Any,
    m: Any,
) -> Dict[str, Any]:
    juma_notifier = JumaNotifier(client=client, db=msg_controller.db)
    lead_scraper = LeadScraper(
        google_service=msg_controller.google, db=msg_controller.db,
        client=client, amocrm=msg_controller.crm.amocrm,
        message_controller=msg_controller,
    )
    action_parser = ActionParser(
        db=msg_controller.db, gcontacts=msg_controller.google.contacts,
        gcalendar=msg_controller.google.calendar, invoicer=None,
        amocrm=msg_controller.crm.amocrm, config=src_config, lead_scraper=lead_scraper,
    )
    meeting_scheduler = TelegramMeetingScheduler(
        db=msg_controller.db, gcalendar=msg_controller.google.calendar,
        admin_notifier=None, amocrm=msg_controller.crm.amocrm,
    )
    advisor_agent = AdvisorAgent(api_key=api_keys["gemini"], db=msg_controller.db, action_parser=action_parser)
    auto_lead_agent = AutoLeadAgent(api_key=api_keys["gemini"])
    meeting_scheduler.lead_detector = auto_lead_agent
    SalesCoach(ai_provider=auto_lead_agent)
    safe_responder = SafeResponder()

    surgical_integration = get_surgical_integration()
    try:
        surgical_integration.negotiator = __import__(
            "src.agents.surgical_negotiator", fromlist=["get_surgical_negotiator"]
        ).get_surgical_negotiator(
            db=msg_controller.db, amocrm=msg_controller.crm.amocrm, send_fn=_surgical_send,
        )
        surgical_integration.enabled = False
    except Exception as surg_init_exc:
        surgical_integration.negotiator = None
        surgical_integration.enabled = False
        logger.warning(f"[SURGICAL] Disabled: {type(surg_init_exc).__name__}")
    surgical_integration.autonomy_threshold = getattr(settings, "AUTONOMY_THRESHOLD", 0.55)

    activity_monitor = ActivityMonitor(db=msg_controller.db)
    audit_agent = AuditAgent(api_key=api_keys["gemini"], db=msg_controller.db)

    evolution_scheduler = None
    if not settings.RUN_USERBOT_ONLY:
        from src.services.core.evolution_scheduler import EvolutionScheduler
        evolution_scheduler = EvolutionScheduler(
            db=msg_controller.db,
            gemini_api_key=api_keys["gemini"],
            bot_client=bot_runtime,
            owner_id=settings.OWNER_ID,
        )
        asyncio.create_task(evolution_scheduler.start(), name="evolution_scheduler")

    workflow_manager = WorkflowManager(crm=msg_controller.crm, db=msg_controller.db, client=client)
    access_manager = AccessManager(owner_id=src_config.OWNER_ID)
    AmoCrmAlertForwarder(user_client=client, bot_runtime=bot_runtime).setup_handlers()

    admin_bot = AdminBot(
        bot_client=bot_client, user_client=client, db=msg_controller.db,
        msg_controller=msg_controller, access_manager=access_manager,
        team_group_id=settings.TEAM_GROUP_ID,
        bot_runtime=bot_runtime,
    )

    if meeting_scheduler:
        meeting_scheduler.admin_notifier = admin_bot
    from src.services.utils.welcome_manager import WelcomeManager
    app_ctx.welcome_manager = WelcomeManager(client=client)
    from src.services.utils.scouter import Scouter
    app_ctx.scouter = Scouter(api_key=api_keys.get("gemini"), db=msg_controller.db)
    lead_scraper.notify_callback = admin_bot.notify_lead

    from src.services.core.workflow_orchestrator import WorkflowOrchestrator
    WorkflowOrchestrator(
        amocrm=msg_controller.crm.amocrm, airtable=msg_controller.crm.airtable,
        notify_callback=admin_bot.notify_lead, team_group_id=settings.TEAM_GROUP_ID,
        advisor_agent=advisor_agent,
    )

    session_manager = SessionManager(sync_callback=push_block_to_amocrm)
    if hasattr(m, "session_manager"):
        m.session_manager = session_manager
    asyncio.create_task(session_manager.monitor_sessions())

    return {
        "juma_notifier": juma_notifier,
        "lead_scraper": lead_scraper,
        "action_parser": action_parser,
        "meeting_scheduler": meeting_scheduler,
        "advisor_agent": advisor_agent,
        "auto_lead_agent": auto_lead_agent,
        "safe_responder": safe_responder,
        "surgical_integration": surgical_integration,
        "activity_monitor": activity_monitor,
        "audit_agent": audit_agent,
        "evolution_scheduler": evolution_scheduler,
        "workflow_manager": workflow_manager,
        "access_manager": access_manager,
        "admin_bot": admin_bot,
        "session_manager": session_manager,
    }
