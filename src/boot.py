"""Application boot and initialization logic.

Extracted from src/main.py to reduce the 4000-line God Object.
Handles all service wiring, client init, and background task registration.
"""

import asyncio
import os
import logging

from telethon import TelegramClient, events
from telethon.sessions import StringSession

from src import config as src_config
from src.settings import settings
from src.database import Database
from src.controllers.message_controller import MessageController
from src.services.core.safe_responder import SafeResponder
from src.services.core.action_parser import ActionParser
from src.services.core.lead_scraper import LeadScraper
from src.services.core.advisor_agent import AdvisorAgent
from src.services.core.auto_lead_agent import AutoLeadAgent
from src.services.core.activity_monitor import ActivityMonitor
from src.services.core.audit_agent import AuditAgent
from src.services.core.sales_coach import SalesCoach
from src.services.core.crm_guard import CRMGuard
from src.services.core.admin_bot import AdminBot
from src.services.utils.access_manager import AccessManager
from src.services.core.session_manager import SessionManager
from src.services.core.meeting_scheduler import TelegramMeetingScheduler
from src.controllers.surgical_integration import get_surgical_integration
from src.services.core.amocrm_pipeline_config import FARMER_PIPELINE_ID, SALES_PIPELINE_ID
from src.services.core.workflow_manager import WorkflowManager
from src.context import app_ctx

logger = logging.getLogger(__name__)


def _parse_bool(val: str) -> bool:
    if not val:
        return False
    clean = val.replace("\ufeff", "").strip().lower()
    return clean in {"1", "true", "yes", "on"}


def _negotiation_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


async def _command_processor():
    """Processes commands from the API Server (e.g. sending messages)."""
    import src.api_server as api_module

    logger.info("[COMMANDS] API Command Processor started.")
    while True:
        try:
            item = await api_module.command_queue.get()
            cmd = item.get("cmd")
            logger.info(f"[COMMANDS] Received: {cmd}")

            if cmd == "send_message":
                u_id = item.get("user_id")
                txt = item.get("text")
                if app_ctx.client:
                    try:
                        await app_ctx.client.send_message(u_id, txt)
                        logger.info(f"[COMMANDS] Message sent to {u_id}")
                        await app_ctx.msg_controller.db.log_message(u_id, txt, is_ai=True)
                    except Exception as e:
                        logger.error(f"[COMMANDS] Failed to send msg to {u_id}: {e}")

            elif cmd == "audit":
                if app_ctx.audit_agent:
                    asyncio.create_task(app_ctx.audit_agent.run_full_audit())
                    logger.info("[COMMANDS] Full audit triggered.")

            api_module.command_queue.task_done()
        except Exception as e:
            logger.error(f"[COMMANDS] Processor error: {e}")
            await asyncio.sleep(1)


async def _crm_discipline_loop():
    while True:
        try:
            crm_guard = CRMGuard(
                amo=app_ctx.msg_controller.crm.amocrm,
                db=app_ctx.msg_controller.db,
                bot=None,
            )
            await crm_guard.check_discipline(pipeline_id=SALES_PIPELINE_ID)
            await crm_guard.check_discipline(pipeline_id=FARMER_PIPELINE_ID)
        except Exception as e:
            logger.error(f"[CRM_GUARD_LOOP] Error: {e}")
        await asyncio.sleep(7200)


async def _crm_capacity_archiver_loop():
    await asyncio.sleep(60)
    while True:
        try:
            logger.info("[ARCHIVER_LOOP] Active AmoCRM capacity check starting...")
            from src.services.core.crm_archiver import CRMArchiver

            archiver = CRMArchiver(
                amocrm=app_ctx.msg_controller.crm.amocrm,
                db=app_ctx.msg_controller.db,
            )
            await archiver.init_tables()
            active_leads = await archiver.fetch_all_active_leads()
            active_count = len(active_leads)
            logger.info(f"[ARCHIVER_LOOP] Active sdelkas: {active_count} / 500 limit")

            if active_count >= 480:
                logger.warning(
                    f"[ARCHIVER_LOOP] Active sdelkas count {active_count} exceeds threshold of 480! Autocleaning..."
                )
                stagnant = await archiver.get_stagnant_leads(max_stagnant_days=21)
                if stagnant:
                    targets = stagnant[:30]
                    processed = 0
                    for lead in targets:
                        try:
                            res = await archiver.archive_lead(lead, dry_run=False)
                            if res.get("success"):
                                processed += 1
                        except Exception as ex:
                            logger.error(f"[ARCHIVER_LOOP] Error archiving lead {lead.get('id')}: {ex}")
                    logger.info(f"[ARCHIVER_LOOP] Autocleanup complete. Archived {processed} leads.")
                else:
                    logger.info("[ARCHIVER_LOOP] No stagnant leads found.")
        except Exception as e:
            logger.error(f"[ARCHIVER_LOOP] Error in capacity archiver loop: {e}")
        await asyncio.sleep(21600)


async def _ai_autopilot_loop():
    await asyncio.sleep(15)
    from src.services.core.telegram_task_creator import TelegramTaskCreator
    from src.services.core.call_analyzer import CallAnalyzer
    from src.services.core.ambassador_journey import AmbassadorJourneyManager
    from src.services.utils.voice_processor import VoiceProcessor

    gemini_key = None
    if app_ctx.msg_controller:
        gemini_key = getattr(app_ctx.msg_controller, "api_keys", {}).get("gemini")
    if not gemini_key:
        logger.warning("[AUTOPILOT] Gemini key missing — AI Autopilot loop disabled.")
        return

    voice_proc = VoiceProcessor(api_key=gemini_key)
    task_creator = TelegramTaskCreator(
        amocrm=app_ctx.msg_controller.crm.amocrm,
        db=app_ctx.msg_controller.db,
        user_client=app_ctx.client,
        voice_processor=voice_proc,
        gemini_api_key=gemini_key,
    )
    call_analyzer = CallAnalyzer(
        amocrm=app_ctx.msg_controller.crm.amocrm,
        db=app_ctx.msg_controller.db,
    )
    ambassador_manager = AmbassadorJourneyManager(
        amocrm=app_ctx.msg_controller.crm.amocrm,
        db=app_ctx.msg_controller.db,
        user_client=app_ctx.client,
        gemini_api_key=gemini_key,
    )

    logger.info("[AUTOPILOT] AI Autopilot loop started.")
    while True:
        try:
            logger.info("[AUTOPILOT] Running periodic AI Autopilot cycle...")
            try:
                leads = await app_ctx.msg_controller.crm.amocrm.get_leads_detailed(limit=30)
                if leads and isinstance(leads, list):
                    for lead in leads:
                        if task_creator.blocks_dialogue_analysis():
                            break
                        lead_id = lead.get("id")
                        if not lead_id:
                            continue
                        phone = None
                        contacts = lead.get("_embedded", {}).get("contacts", []) or lead.get("contacts", [])
                        for contact in contacts:
                            fields = contact.get("custom_fields_values") or []
                            for field in fields:
                                if str(field.get("field_code", "")).upper() == "PHONE":
                                    vals = field.get("values") or []
                                    if vals:
                                        phone = str(vals[0].get("value", ""))
                                        break
                            if phone:
                                break
                        phone_getter = getattr(app_ctx.msg_controller.crm.amocrm, "get_primary_contact_phone", None)
                        if not phone and callable(phone_getter):
                            phone = await phone_getter(lead)
                        if phone:
                            await task_creator.create_amocrm_tasks_from_chat(
                                phone_or_username=phone, lead_id=int(lead_id), limit=15
                            )
            except Exception as tg_err:
                logger.error(f"[AUTOPILOT] Telegram Task Creator error: {tg_err}")

            try:
                await call_analyzer.analyze_recent_calls(limit=30)
            except Exception as call_err:
                logger.error(f"[AUTOPILOT] Call Analyzer error: {call_err}")

            try:
                await ambassador_manager.sync_won_leads_to_ambassadors(limit=30)
                await ambassador_manager.process_scheduled_touchpoints()
            except Exception as amb_err:
                logger.error(f"[AUTOPILOT] Ambassador Journey error: {amb_err}")

            logger.info("[AUTOPILOT] AI Autopilot cycle completed.")
        except Exception as exc:
            logger.error(f"[AUTOPILOT] Critical error in autopilot loop: {exc}")
        await asyncio.sleep(900)


async def _brain_evolution_loop():
    await asyncio.sleep(300)
    while True:
        try:
            if app_ctx.oisha_brain:
                result = await app_ctx.oisha_brain.evolve(task="routine_health_check")
                logger.info(
                    f"[BRAIN] Evolution cycle done: priority={result.get('priority')} "
                    f"component={result.get('affected_component')}"
                )
        except Exception as exc:
            logger.error(f"[BRAIN] Evolution loop error: {exc}")
        await asyncio.sleep(21600)


async def _surgical_send(user_id: int, text: str):
    from src.main import _userbot_private_replies_disabled
    if _userbot_private_replies_disabled():
        logger.info("[SURGICAL] Proactive private send blocked by policy.")
        return
    try:
        if app_ctx.client:
            await app_ctx.client.send_message(user_id, text)
    except Exception as exc:
        logger.warning(f"[SURGICAL] Proactive send failed uid={user_id}: {exc}")


async def boot_application():
    """Initialize all services, clients, and background tasks."""
    global msg_controller, client, bot_client, lead_scraper, action_parser
    global advisor_agent, auto_lead_agent, safe_responder, activity_monitor, audit_agent
    global workflow_manager, access_manager, admin_bot, session_manager, chat_bridge, BOT_TOKEN_STR, juma_notifier
    global surgical_integration, evolution_scheduler
    global meeting_scheduler
    global oisha_brain, bot_messenger, agent_orchestrator

    import src.main as m

    # [ENTERPRISE] Anti-Local Execution Lock
    runtime_name = os.getenv("OISHA_RUNTIME", "").strip().lower()
    is_cloud = (
        os.getenv("K_SERVICE")
        or os.getenv("RUNNING_IN_CLOUD") == "1"
        or runtime_name in {"vm_service", "oracle_vm", "production"}
    )
    allow_local = os.getenv("ALLOW_LOCAL_RUN") == "1"
    if not is_cloud and not allow_local:
        print("\n" + "!" * 60)
        print("[SECURITY LOCK] Oisha-OS Local Execution is DISABLED.")
        print("Set ALLOW_LOCAL_RUN=1 to override on dev machine.")
        print("!" * 60 + "\n")
        return

    app_ctx.task_semaphore = asyncio.Semaphore(50)
    print("Oisha-OS Tizimi tayyorlanmoqda (Dual-Head Architecture)...")

    # Early health check
    health_api_task = asyncio.create_task(m.run_health_check_api(), name="health_check_api")
    asyncio.create_task(_command_processor(), name="command_processor")
    m._restore_cloud_artifacts()

    # Credentials & Database
    api_keys = {
        "gemini": settings.GEMINI_API_KEY.get_secret_value(),
        "deepseek": settings.DEEPSEEK_API_KEY.get_secret_value() if settings.DEEPSEEK_API_KEY else None,
        "aws_access_key": settings.AWS_ACCESS_KEY_ID.get_secret_value() if settings.AWS_ACCESS_KEY_ID else None,
        "aws_secret_key": settings.AWS_SECRET_ACCESS_KEY.get_secret_value() if settings.AWS_SECRET_ACCESS_KEY else None,
        "aws_region": settings.AWS_REGION,
        "bedrock_model_id": settings.BEDROCK_MODEL_ID,
    }
    db = Database()
    await db.init_instance()
    # Hisobchi AI tables
    from src.services.core.hisobchi_schema import init_hisobchi_tables
    await init_hisobchi_tables(db)
    logger.info("[HISOBCHI] Database schema is ready.")
    msg_controller = MessageController(api_keys=api_keys, db=db)

    cloud_control_plane = bool(os.getenv("K_SERVICE"))
    enable_cloud_userbot = _parse_bool(os.getenv("ENABLE_CLOUD_USERBOT", ""))
    force_control_plane_only = _parse_bool(os.getenv("CLOUD_RUN_CONTROL_PLANE_ONLY", ""))
    cloud_control_plane_only = force_control_plane_only or (cloud_control_plane and not enable_cloud_userbot)

    # Telegram Client init
    if cloud_control_plane_only:
        client = TelegramClient(
            StringSession(), settings.API_ID, settings.API_HASH,
            device_model="Oisha Enterprise Control Plane", system_version="Cloud Run",
        )
    else:
        session_string = os.environ.get("USERBOT_SESSION_STRING", "").strip()
        if session_string:
            client = TelegramClient(
                StringSession(session_string), settings.API_ID, settings.API_HASH,
                device_model="Oisha Enterprise v2", system_version="Windows 11 Agent",
            )
        elif cloud_control_plane:
            client = TelegramClient(
                StringSession(), settings.API_ID, settings.API_HASH,
                device_model="Oisha Enterprise Control Plane", system_version="Cloud Run",
            )
        else:
            client = TelegramClient(
                "data/oisha_user_active", settings.API_ID, settings.API_HASH,
                device_model="Oisha Enterprise v2", system_version="Windows 11 Agent",
            )

    # Bot Client init
    BOT_TOKEN = settings.BOT_TOKEN.get_secret_value()
    _bot_session_string = os.environ.get("BOT_SESSION_STRING", "").strip()
    _bot_session = StringSession(_bot_session_string) if _bot_session_string else StringSession()
    bot_client = TelegramClient(_bot_session, settings.API_ID, settings.API_HASH)
    BOT_TOKEN_STR = BOT_TOKEN
    juma_notifier = m.JumaNotifier(client=client, db=db)

    # Services
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

    # Background discipline loop
    asyncio.create_task(_crm_discipline_loop())
    asyncio.create_task(_crm_capacity_archiver_loop(), name="crm_capacity_archiver_loop")
    asyncio.create_task(_ai_autopilot_loop())

    # Surgical negotiator
    surgical_integration = get_surgical_integration()
    try:
        surgical_integration.negotiator = __import__(
            "src.agents.surgical_negotiator", fromlist=["get_surgical_negotiator"]
        ).get_surgical_negotiator(
            db=msg_controller.db, amocrm=msg_controller.crm.amocrm, send_fn=_surgical_send,
        )
        surgical_integration.enabled = getattr(settings, "SURGICAL_MODE", False)
    except Exception as surg_init_exc:
        surgical_integration.negotiator = None
        surgical_integration.enabled = False
        logger.warning(f"[SURGICAL] Disabled: {type(surg_init_exc).__name__}")
    surgical_integration.autonomy_threshold = getattr(settings, "AUTONOMY_THRESHOLD", 0.55)

    activity_monitor = ActivityMonitor(db=msg_controller.db)
    audit_agent = AuditAgent(api_key=api_keys["gemini"], db=msg_controller.db)

    from src.services.core.evolution_scheduler import EvolutionScheduler
    evolution_scheduler = EvolutionScheduler(db=msg_controller.db, gemini_api_key=api_keys["gemini"])
    asyncio.create_task(evolution_scheduler.start(), name="evolution_scheduler")

    workflow_manager = WorkflowManager(crm=msg_controller.crm.amocrm, db=msg_controller.db, client=client)
    access_manager = AccessManager(owner_id=src_config.OWNER_ID)

    # Admin Bot
    admin_bot = AdminBot(
        bot_client=bot_client, user_client=client, db=msg_controller.db,
        msg_controller=msg_controller, access_manager=access_manager,
        team_group_id=settings.TEAM_GROUP_ID,
    )
    if meeting_scheduler:
        meeting_scheduler.admin_notifier = admin_bot
    from src.services.utils.welcome_manager import WelcomeManager
    WelcomeManager(client=client)
    lead_scraper.notify_callback = admin_bot.notify_lead

    from src.services.core.workflow_orchestrator import WorkflowOrchestrator
    WorkflowOrchestrator(
        amocrm=msg_controller.crm.amocrm, airtable=msg_controller.crm.airtable,
        notify_callback=admin_bot.notify_lead, team_group_id=settings.TEAM_GROUP_ID,
        advisor_agent=advisor_agent,
    )

    session_manager = SessionManager(sync_callback=m.push_block_to_amocrm)

    # API server wiring
    import src.api_server as api_module
    api_module.user_client = client
    api_module.db_instance = msg_controller.db
    api_module.msg_controller = msg_controller
    api_module.action_parser = action_parser
    api_module.set_runtime_context(
        service_name=os.getenv("K_SERVICE") or "oisha-main",
        canonical_entrypoint="src/main.py",
        state_backend=db.get_backend_name(),
        state_db_path=msg_controller.db.db_path,
        scheduler_mode="persistent", quiet_hours_enabled=True, userbot_authorized=None,
    )

    async def _heartbeat_task():
        while True:
            try:
                api_module.mark_heartbeat()
            except Exception as e:
                logger.debug(f"[HEARTBEAT] tick error: {e}")
            await asyncio.sleep(15)

    api_module.mark_heartbeat()
    asyncio.create_task(_heartbeat_task(), name="api_heartbeat")

    if cloud_control_plane_only:
        api_module.set_runtime_context(
            state_backend=db.get_backend_name(), state_db_path=msg_controller.db.db_path,
            scheduler_mode="control-plane", userbot_authorized=False,
        )
        api_module.update_api_status("online", "Control plane active; Telegram runtime delegated to VM")
        logger.info("[CLOUD] Control-plane mode active.")
        await asyncio.Event().wait()
        return

    # Userbot connection
    userbot_ready = await m._connect_user_client(client)
    api_module.set_runtime_context(
        state_backend=db.get_backend_name(), state_db_path=msg_controller.db.db_path,
        userbot_authorized=userbot_ready,
    )
    if not userbot_ready:
        api_module.user_client = None
        if BOT_TOKEN_STR:
            try:
                await bot_client.start(bot_token=BOT_TOKEN_STR)
            except Exception as bot_exc:
                logger.error(f"[AUTH] Bot-token head startup failed: {bot_exc}")
                bot_client = None
        if admin_bot and bot_client:
            try:
                admin_bot.user_client = None
                await admin_bot.start()
                logger.info("[BOT_ONLY] Admin bot started without userbot.")
            except Exception as admin_exc:
                logger.error(f"[BOT_ONLY] Admin bot startup failed: {admin_exc}", exc_info=True)
        api_module.update_api_status("degraded", "Bot-token mode active; userbot needs re-login")
        asyncio.create_task(m.background_monitor_task(), name="background_monitor_task")
        await asyncio.Event().wait()
        return

    from src.services.core.tool_adapters import configure_userbot_group_fallback
    configure_userbot_group_fallback(client)
    asyncio.create_task(m.background_monitor_task(), name="background_monitor_task")
    logger.info("[MONITOR] Persistent CRM/Airtable scheduler registered.")

    # Bot-token head startup
    if BOT_TOKEN_STR and bot_client:
        try:
            await bot_client.start(bot_token=BOT_TOKEN_STR)

            from src.services.core.telegram_ai_features import (
                BOT_API_10_ALLOWED_UPDATES, TelegramBotAPI10Client, TelegramBotAPILongPoller,
            )

            tg_ai_client = TelegramBotAPI10Client(BOT_TOKEN_STR)
            webhook_url = os.getenv("WEBHOOK_URL")
            webhook_secret = settings.TELEGRAM_WEBHOOK_SECRET.get_secret_value() if settings.TELEGRAM_WEBHOOK_SECRET else None
            if webhook_url and webhook_secret:
                webhook_path = f"{webhook_url.rstrip('/')}/webhook/telegram-ai"
                logger.info("[BOT API 10] Setting authenticated webhook.")
                asyncio.create_task(
                    tg_ai_client.set_webhook(webhook_path, secret_token=webhook_secret, allowed_updates=BOT_API_10_ALLOWED_UPDATES),
                    name="telegram_bot_api_webhook_setup",
                )
                api_module.set_telegram_ai_ingress_status(mode="webhook", active=True)
            else:
                async def _dispatch_bot_api_update(update):
                    return await api_module.process_telegram_ai_update(update)

                poller = TelegramBotAPILongPoller(BOT_TOKEN_STR, _dispatch_bot_api_update)
                asyncio.create_task(poller.run(), name="telegram_bot_api_long_poll")
                api_module.set_telegram_ai_ingress_status(mode="long_poll", active=True)
                logger.info("[BOT API 10] Long-poll receiver started.")

            if admin_bot:
                admin_bot.user_client = client
                await admin_bot.start()
            logger.info("[BOT] Bot-token head and AdminBot handlers started.")

            # OishaBrain
            from src.services.core.agent_brain import OishaBrain
            oisha_brain = OishaBrain(
                db=msg_controller.db, gemini_api_key=api_keys["gemini"],
                bot_token=BOT_TOKEN_STR, owner_id=getattr(src_config, "OWNER_ID", None),
            )
            asyncio.create_task(_brain_evolution_loop(), name="oisha_brain_evolution")
            logger.info("[BRAIN] OishaBrain initialized.")

            # BotMessenger
            from src.services.core.bot_to_bot import BotMessenger
            bot_messenger = BotMessenger(bot_client=bot_client, userbot_client=client)
            logger.info("[BOT2BOT] BotMessenger initialized.")

            # AgentOrchestrator
            from src.services.core.agent_orchestrator import get_orchestrator
            agent_orchestrator = get_orchestrator(
                agent_registry={"advisor": advisor_agent, "audit": audit_agent},
                bot_messenger=bot_messenger, db=msg_controller.db,
            )
            logger.info("[ORCHESTRATOR] AgentOrchestrator initialized.")

            # Guest bot
            from src.services.core.guest_bot import GuestBotHandler, enable_guest_queries
            _guest_handler = GuestBotHandler(bot_client=bot_client, message_controller=msg_controller)
            _guest_handler.register()
            asyncio.create_task(enable_guest_queries(bot_client), name="guest_bot_enable")
            logger.info("[GUEST_BOT] GuestBotHandler registered.")

        except Exception as bot_exc:
            logger.error(f"[BOT] Bot-token head startup failed: {bot_exc}", exc_info=True)

    # Event handlers — sync to both main module globals and app_ctx
    m.client = client
    m.bot_client = bot_client
    m.msg_controller = msg_controller
    m.lead_scraper = lead_scraper
    m.action_parser = action_parser
    m.advisor_agent = advisor_agent
    m.auto_lead_agent = auto_lead_agent
    m.safe_responder = safe_responder
    m.activity_monitor = activity_monitor
    m.audit_agent = audit_agent
    m.workflow_manager = workflow_manager
    m.access_manager = access_manager
    m.admin_bot = admin_bot
    m.juma_notifier = juma_notifier
    m.session_manager = session_manager
    m.surgical_integration = surgical_integration
    m.evolution_scheduler = evolution_scheduler
    m.meeting_scheduler = meeting_scheduler
    m.oisha_brain = oisha_brain
    m.bot_messenger = bot_messenger
    m.agent_orchestrator = agent_orchestrator
    m.BOT_TOKEN_STR = BOT_TOKEN_STR
    m.health_api_server = None

    # Sync to app_ctx for new code
    app_ctx.client = client
    app_ctx.bot_client = bot_client
    app_ctx.msg_controller = msg_controller
    app_ctx.lead_scraper = lead_scraper
    app_ctx.action_parser = action_parser
    app_ctx.advisor_agent = advisor_agent
    app_ctx.auto_lead_agent = auto_lead_agent
    app_ctx.safe_responder = safe_responder
    app_ctx.activity_monitor = activity_monitor
    app_ctx.audit_agent = audit_agent
    app_ctx.workflow_manager = workflow_manager
    app_ctx.access_manager = access_manager
    app_ctx.admin_bot = admin_bot
    app_ctx.juma_notifier = juma_notifier
    app_ctx.session_manager = session_manager
    app_ctx.surgical_integration = surgical_integration
    app_ctx.evolution_scheduler = evolution_scheduler
    app_ctx.meeting_scheduler = meeting_scheduler
    app_ctx.oisha_brain = oisha_brain
    app_ctx.bot_messenger = bot_messenger
    app_ctx.agent_orchestrator = agent_orchestrator
    app_ctx.bot_token_str = BOT_TOKEN_STR

    # Register event handlers on client
    from src.services.core.hisobchi_engine import HisobchiEngine
    from src.services.core.hisobchi_handlers import (
        backfill_card_bot_messages,
        handle_card_bot_message,
        handle_finance_group_reply,
        is_card_bot_sender,
    )

    hisobchi_engine = HisobchiEngine(msg_controller.db)
    m._hisobchi_engine = hisobchi_engine

    async def _hisobchi_event_handler(event):
        """Handle finance events before generic bot/spam filters can drop them."""
        try:
            sender = await event.get_sender()
            if event.is_private and not event.out and is_card_bot_sender(sender):
                await handle_card_bot_message(event, client, hisobchi_engine)
                raise events.StopPropagation
            if not event.is_private and not event.out:
                if await handle_finance_group_reply(event, client, hisobchi_engine):
                    raise events.StopPropagation
        except events.StopPropagation:
            raise
        except Exception as exc:
            logger.error("[HISOBCHI] Dedicated handler failed: %s", exc, exc_info=True)

    client.add_event_handler(
        _hisobchi_event_handler,
        events.NewMessage(incoming=True),
    )
    client.add_event_handler(m.handle_new_message, events.NewMessage(incoming=True))

    if settings.TEAM_GROUP_ID and settings.TOPIC_KIRIM_ID:
        client.add_event_handler(
            m.kirim_topic_handler,
            events.NewMessage(chats=settings.TEAM_GROUP_ID),
        )
        logger.info(f"[KIRIM] Listener active team={settings.TEAM_GROUP_ID} topic={settings.TOPIC_KIRIM_ID}")

    client.add_event_handler(m.case_publisher_handler, events.NewMessage(incoming=True))
    client.add_event_handler(m.negotiation_agent_handler, events.NewMessage(incoming=True))
    client.add_event_handler(m.shadow_advisor_handler, events.NewMessage(incoming=True))
    client.add_event_handler(m.activity_monitor_handler, events.NewMessage(outgoing=True))
    client.add_event_handler(m.meeting_scheduler_handler, events.NewMessage(incoming=True))
    client.add_event_handler(m.meeting_scheduler_handler, events.NewMessage(outgoing=True))
    client.add_event_handler(m.self_command_handler, events.NewMessage(chats="me"))
    client.add_event_handler(m.handle_new_message, events.NewMessage(incoming=True))
    logger.info("[EVENTS] Safe userbot handlers registered.")

    asyncio.create_task(
        backfill_card_bot_messages(client, hisobchi_engine),
        name="hisobchi_card_backfill",
    )

    # Group access probe
    async def telegram_group_access_probe_loop():
        await asyncio.sleep(5)
        while True:
            delay_seconds = _negotiation_int("TELEGRAM_GROUP_PROBE_INTERVAL_SECS", 3600)
            try:
                snapshot = await api_module.refresh_userbot_group_access_snapshot(client)
                readable_groups = sum(1 for e in snapshot.get("groups", {}).values() if e.get("readable"))
                readable_topics = sum(1 for e in snapshot.get("topics", {}).values() if e.get("readable"))
                logger.info("[TELEGRAM PROBE] status=%s readable_groups=%s readable_topics=%s", snapshot.get("status"), readable_groups, readable_topics)
                if snapshot.get("status") != "ok":
                    delay_seconds = min(delay_seconds, _negotiation_int("TELEGRAM_GROUP_PROBE_RETRY_SECS", 60))
            except Exception as exc:
                logger.warning("[TELEGRAM PROBE] Failed: %s", type(exc).__name__)
                delay_seconds = min(delay_seconds, _negotiation_int("TELEGRAM_GROUP_PROBE_RETRY_SECS", 60))
            await asyncio.sleep(delay_seconds)

    asyncio.create_task(telegram_group_access_probe_loop(), name="telegram_group_access_probe_loop")

    # Calendar autoscan
    async def calendar_autoscan_loop():
        await asyncio.sleep(_negotiation_int("CALENDAR_SCAN_BOOT_DELAY_SECS", 60))
        while True:
            try:
                if meeting_scheduler and os.getenv("ENABLE_CALENDAR_AUTOSCAN", "1").strip().lower() not in {"0", "false", "no", "off"}:
                    result = await meeting_scheduler.scan_recent_dialogs(
                        client,
                        dialog_limit=_negotiation_int("CALENDAR_SCAN_DIALOG_LIMIT", 80),
                        message_limit=_negotiation_int("CALENDAR_SCAN_MESSAGE_LIMIT", 12),
                        max_age_hours=_negotiation_int("CALENDAR_SCAN_MAX_AGE_HOURS", 72),
                    )
                    logger.info(f"[MEETING SCAN] {result}")
            except Exception as exc:
                logger.warning(f"[MEETING SCAN] Autoscan failed: {type(exc).__name__}: {exc}")
            await asyncio.sleep(_negotiation_int("CALENDAR_SCAN_INTERVAL_SECS", 900))

    asyncio.create_task(calendar_autoscan_loop(), name="calendar_autoscan_loop")

    # Graceful shutdown
    _shutdown_event = asyncio.Event()

    def _on_sigterm():
        logger.warning("[SHUTDOWN] SIGTERM received — beginning graceful drain.")
        _shutdown_event.set()

    import signal as _signal
    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(_signal.SIGTERM, _on_sigterm)
        loop.add_signal_handler(_signal.SIGINT, _on_sigterm)
        logger.info("[SHUTDOWN] SIGTERM/SIGINT handlers installed.")
    except NotImplementedError:
        logger.info("[SHUTDOWN] Signal handlers unavailable on this platform (Windows).")

    async def _graceful_drain():
        drain_deadline = 25.0
        logger.info(f"[SHUTDOWN] Draining in-flight tasks for up to {drain_deadline}s...")
        current = asyncio.current_task()
        pending = [t for t in asyncio.all_tasks(loop=asyncio.get_running_loop()) if t is not current and not t.done()]
        drainable = [t for t in pending if not m._is_shutdown_daemon_task(t)]
        if drainable:
            logger.info(f"[SHUTDOWN] Waiting on {len(drainable)} in-flight handler task(s).")
            done, still_pending = await asyncio.wait(drainable, timeout=drain_deadline)
            if still_pending:
                logger.warning(f"[SHUTDOWN] {len(still_pending)} task(s) exceeded drain deadline.")
        try:
            await client.disconnect()
            logger.info("[SHUTDOWN] Userbot client disconnected.")
        except Exception as e:
            logger.warning(f"[SHUTDOWN] Userbot disconnect error: {e}")
        if bot_client is not None:
            try:
                await bot_client.disconnect()
                logger.info("[SHUTDOWN] Bot client disconnected.")
            except Exception as e:
                logger.warning(f"[SHUTDOWN] Bot disconnect error: {e}")
        try:
            await msg_controller.db.close()
            logger.info("[SHUTDOWN] DB closed.")
        except Exception as e:
            logger.warning(f"[SHUTDOWN] DB close error: {e}")
        await m.stop_health_check_api(health_api_task)
        logger.info("[SHUTDOWN] API server stopped.")

    api_module.update_api_status("online", "Userbot, Telegram bot, and persistent scheduler are active")
    logger.info("Oisha-OS userbot runtime is online and ready.")

    disc_task = asyncio.create_task(client.run_until_disconnected(), name="userbot_disconnect_watcher")
    shutdown_task = asyncio.create_task(_shutdown_event.wait(), name="shutdown_watcher")
    done, pending = await asyncio.wait({disc_task, shutdown_task}, return_when=asyncio.FIRST_COMPLETED)
    if shutdown_task in done:
        await _graceful_drain()
        for t in pending:
            t.cancel()
    else:
        logger.warning("[SHUTDOWN] Telegram client disconnected unexpectedly.")
        shutdown_task.cancel()
