import asyncio
import inspect
import os
import sys
import logging
import base64
import json
import re
from datetime import datetime
from typing import Optional, Dict, Any

# [STABILITY] Windows and UTF-8 setup
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except OSError:
    pass

if os.name == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "src"))

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from src import config
from src.settings import settings
from src.database import Database
from src.services.core.safe_responder import SafeResponder
from src.services.core.action_parser import ActionParser
from src.services.core.lead_scraper import LeadScraper
from src.controllers.message_controller import MessageController
from src.services.core.advisor_agent import AdvisorAgent
from src.services.core.auto_lead_agent import AutoLeadAgent, detect_non_customer_context
from src.services.core.activity_monitor import ActivityMonitor
from src.services.core.audit_agent import AuditAgent
from src.services.core.sales_coach import SalesCoach
from src.services.core.crm_guard import CRMGuard
import uvicorn
from telethon import functions, types
import random
import time
from src.services.core.admin_bot import AdminBot
from src.services.core import auto_reply_gate
from src.services.core.folder_manager import FolderManager
from src.services.utils.voice_processor import VoiceProcessor
from src.services.utils.access_manager import AccessManager
from src.services.core.juma_notifier import JumaNotifier
from src.services.core.case_publisher import CasePublisher
from src.services.core.session_manager import SessionManager
from src.services.core.meeting_scheduler import TelegramMeetingScheduler
from src.controllers.surgical_integration import get_surgical_integration
from src.services.core.amocrm_pipeline_config import FARMER_PIPELINE_ID, SALES_PIPELINE_ID
from src.context import app_ctx
from src.handlers.income_workflow import (
    income_state_key as _income_state_key,
    income_gate_key as _income_gate_key,
    normalize_income_lookup as _normalize_income_lookup,
    detect_payment_type as _detect_payment_type,
    detect_payment_source as _detect_payment_source,
    format_person_mention as _format_person_mention,
    is_group_open_confirmation as _is_group_open_confirmation,
    is_finance_approval as _is_finance_approval,
    is_finance_rejection as _is_finance_rejection,
    resolve_finance_approver as _resolve_finance_approver,
    find_project_for_income as _find_project_for_income,
    count_income_records_for_project as _count_income_records_for_project,
    create_income_airtable_record as _create_income_airtable_record,
    save_income_workflow_state as _save_income_workflow_state,
    load_income_workflow_state as _load_income_workflow_state,
)
from src.handlers.kirim import (
    _kirim_celebration_key,
    _extract_income_amount,
    _format_income_amount_for_celebration,
    _sender_display_name,
    _looks_like_income_announcement,
    _is_kirim_topic_message,
)

# Global Managers
folder_manager: Optional[FolderManager] = None
voice_processor: Optional[VoiceProcessor] = None

# Loglarni sozlash
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
# Global service placeholders (initialized in main)
# New code should use app_ctx.* directly.
msg_controller = None
client = None
bot_client = None
lead_scraper = None
action_parser = None
advisor_agent = None
auto_lead_agent = None
safe_responder = None
activity_monitor = None
audit_agent = None
workflow_manager = None
access_manager = None
admin_bot = None
juma_notifier = None
session_manager = None
chat_bridge = None
BOT_TOKEN_STR = None
surgical_integration = None
evolution_scheduler = None
meeting_scheduler = None
oisha_brain = None
bot_messenger = None
agent_orchestrator = None
_health_api_server = None
_hisobchi_engine = None

# TN5 Group Config (env-configurable; fallback keeps legacy behavior)
TN5_GROUP_ID = (
    settings.CRM_GROUP_ID if settings.CRM_GROUP_ID is not None else -1003820339529
)
TN5_TOPIC_ID = (
    settings.CRM_TOPIC_ID if settings.CRM_TOPIC_ID is not None else 7
)  # Ishtirokchilar ma'lumotlari


_SHUTDOWN_DAEMON_TASK_NAMES = {
    "api_heartbeat",
    "background_monitor_task",
    "calendar_autoscan_loop",
    "command_processor",
    "crm_capacity_archiver_loop",
    "evolution_scheduler",
    "guest_bot_enable",
    "health_check_api",
    "oisha_brain_evolution",
    "shutdown_watcher",
    "telegram_group_access_probe_loop",
    "userbot_disconnect_watcher",
}

_SHUTDOWN_DAEMON_CORO_NAMES = {
    "_heartbeat_task",
    "_brain_evolution_loop",
    "_keepalive_loop",
    "_recv_loop",
    "_send_loop",
    "_update_loop",
    "ai_autopilot_loop",
    "background_crm_audit_task",
    "background_loop",
    "background_monitor_task",
    "background_scheduler",
    "calendar_autoscan_loop",
    "command_processor",
    "crm_capacity_archiver_loop",
    "crm_discipline_loop",
    "dm_lead_sync_task",
    "monitor_sessions",
    "run_health_check_api",
    "start_backlog_sync",
    "telegram_group_access_probe_loop",
}

_SHUTDOWN_DAEMON_CORO_SUFFIXES = {
    "AdminBot.start.<locals>.heartbeat",
    "EvolutionScheduler._run_loop",
    "LifespanOn.main",
    "MTProtoSender._keepalive_loop",
    "MTProtoSender._recv_loop",
    "MTProtoSender._send_loop",
    "UpdateMethods._update_loop",
}


def _is_shutdown_daemon_task(task: Any) -> bool:
    """Return whether a pending task is an infrastructure loop, not a handler."""
    task_name = getattr(task, "get_name", lambda: "")() or ""
    if task_name in _SHUTDOWN_DAEMON_TASK_NAMES:
        return True

    coro = getattr(task, "get_coro", lambda: None)()
    coro_name = getattr(coro, "__name__", "") or ""
    if coro_name in _SHUTDOWN_DAEMON_CORO_NAMES:
        return True

    coro_qualname = getattr(coro, "__qualname__", "") or ""
    return any(
        coro_qualname.endswith(suffix) for suffix in _SHUTDOWN_DAEMON_CORO_SUFFIXES
    )


def _shutdown_task_label(task: Any) -> str:
    """Build a secret-free task label for shutdown diagnostics."""
    task_name = getattr(task, "get_name", lambda: "")() or ""
    coro = getattr(task, "get_coro", lambda: None)()
    coro_qualname = getattr(coro, "__qualname__", "") or ""
    coro_name = getattr(coro, "__name__", "") or ""
    return f"{task_name}:{coro_qualname or coro_name or type(coro).__name__}"


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


_EXCLUDED_FOLDER_USER_CACHE: Dict[str, Any] = {"expires_at": 0.0, "user_ids": set()}
_EXCLUDED_FOLDER_CACHE_LOCK = asyncio.Lock()


def spawn_task(coro, name=None):
    """Create an asyncio task with semaphore limiting."""
    sem = app_ctx.task_semaphore
    if sem:
        async def _wrapped():
            async with sem:
                return await coro
        return asyncio.create_task(_wrapped(), name=name)
    return asyncio.create_task(coro, name=name)


def _userbot_private_replies_disabled() -> bool:
    return True


def _is_private_userbot_event(event: Any) -> bool:
    return bool(getattr(event, "is_private", False)) and not bool(
        getattr(event, "out", False)
    )


def _should_block_private_userbot_reply(event: Any) -> bool:
    return _userbot_private_replies_disabled() and _is_private_userbot_event(event)


def _folder_exclusion_enabled() -> bool:
    return os.getenv("ENABLE_PERSONAL_FOLDER_EXCLUSION", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _excluded_folder_keywords() -> tuple[str, ...]:
    raw = os.getenv(
        "PERSONAL_FOLDER_KEYWORDS", "oila,family,shaxsiy,personal,do'st,dost,friends"
    )
    return tuple(item.strip().lower() for item in raw.split(",") if item.strip())


def _dialog_filter_title(dialog_filter: Any) -> str:
    title = getattr(dialog_filter, "title", "")
    if isinstance(title, str):
        return title
    return getattr(title, "text", str(title or ""))


def _peer_user_id(peer: Any) -> Optional[int]:
    return getattr(peer, "user_id", None) or getattr(peer, "userId", None)


async def _excluded_folder_user_ids() -> set[int]:
    now = time.time()
    async with _EXCLUDED_FOLDER_CACHE_LOCK:
        if _EXCLUDED_FOLDER_USER_CACHE["expires_at"] > now:
            return set(_EXCLUDED_FOLDER_USER_CACHE["user_ids"])

        user_ids: set[int] = set()
        try:
            raw_filters = await client(functions.messages.GetDialogFiltersRequest())
            filters = getattr(raw_filters, "filters", raw_filters)
            keywords = _excluded_folder_keywords()
            for dialog_filter in filters or []:
                title = _dialog_filter_title(dialog_filter).lower()
                if not title or not any(keyword in title for keyword in keywords):
                    continue
                for attr in ("include_peers", "pinned_peers"):
                    for peer in getattr(dialog_filter, attr, []) or []:
                        user_id = _peer_user_id(peer)
                        if user_id:
                            user_ids.add(int(user_id))
        except Exception as exc:
            logger.warning(
                f"[FOLDER_GUARD] Could not inspect Telegram folders: {type(exc).__name__}"
            )

        ttl = _negotiation_int("PERSONAL_FOLDER_CACHE_SECS", 600)
        _EXCLUDED_FOLDER_USER_CACHE["expires_at"] = now + ttl
        _EXCLUDED_FOLDER_USER_CACHE["user_ids"] = user_ids
        return set(user_ids)


async def _is_personal_folder_sender(sender: Any) -> bool:
    if not _folder_exclusion_enabled() or not sender:
        return False
    sender_id = getattr(sender, "id", None)
    if sender_id is None:
        return False
    return int(sender_id) in await _excluded_folder_user_ids()


def _restore_cloud_artifacts() -> None:
    """Materialize Cloud Run secrets into runtime files when provided."""
    os.makedirs("data", exist_ok=True)

    session_b64 = os.environ.get("USERBOT_SESSION_B64")
    session_path = os.path.join("data", "userbot_session.session")
    if session_b64 and not os.path.exists(session_path):
        try:
            with open(session_path, "wb") as fh:
                fh.write(base64.b64decode(session_b64))
            logger.info("[CLOUD] Restored userbot session from secret.")
        except Exception as exc:
            logger.error(f"[CLOUD] Failed to restore userbot session: {exc}")

    amocrm_token_json = os.environ.get("AMOCRM_TOKEN_JSON")
    amocrm_token_path = os.path.join("data", "amocrm_token.json")
    if amocrm_token_json and not os.path.exists(amocrm_token_path):
        try:
            with open(amocrm_token_path, "w", encoding="utf-8") as fh:
                fh.write(amocrm_token_json)
            logger.info("[CLOUD] Restored AmoCRM token file from secret.")
        except Exception as exc:
            logger.error(f"[CLOUD] Failed to restore AmoCRM token file: {exc}")

    service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    creds_path = os.environ.get("GSHEET_CREDS_FILE", "service_account.json")
    if service_account_json and not os.path.exists(creds_path):
        try:
            with open(creds_path, "w", encoding="utf-8") as fh:
                fh.write(service_account_json)
            logger.info(f"[CLOUD] Restored Google credentials file at {creds_path}.")
        except Exception as exc:
            logger.error(f"[CLOUD] Failed to restore Google credentials file: {exc}")


async def _connect_user_client(telegram_client: TelegramClient) -> bool:
    if os.environ.get("CLOUD_RUN_CONTROL_PLANE_ONLY") == "1":
        logger.info("[AUTH] Skipping userbot login: CLOUD_RUN_CONTROL_PLANE_ONLY=1")
        return False

    """Connect the userbot without ever falling back to interactive auth.
    
    Args:
        telegram_client: The Telethon client instance to connect
        
    Returns:
        bool: True if authorized, False otherwise
    """
    try:
        await telegram_client.connect()
    except Exception as exc:
        error_fingerprint = f"{type(exc).__name__} {exc}".upper()
        duplicate_markers = (
            "AUTH_KEY_DUPLICATED",
            "AUTHKEYDUPLICATEDERROR",
            "AUTHORIZATION KEY",
            "USED UNDER TWO DIFFERENT IP",
        )
        if any(marker in error_fingerprint for marker in duplicate_markers):
            logger.error("[AUTH] Userbot session is already in use by another runtime.")
            try:
                await telegram_client.disconnect()
            except Exception as disconnect_exc:
                logger.warning(
                    f"[AUTH] Could not disconnect invalid userbot session: {disconnect_exc}"
                )
            try:
                import src.api_server as api_module

                api_module.update_api_status(
                    "degraded", "Userbot session delegated to another runtime"
                )
                api_module.set_runtime_context(userbot_authorized=False)
            except (ImportError, AttributeError) as api_exc:
                logger.warning(f"[AUTH] Could not update API status: {api_exc}")
            return False
        raise

    if await telegram_client.is_user_authorized():
        return True

    # Only an explicit local terminal may prompt for Telegram login.
    # Production VMs run under systemd, so prompting there causes EOFError
    # and makes health checks pass briefly before the process dies.
    cloud_control_plane = bool(os.getenv("K_SERVICE"))
    interactive_auth_allowed = (
        os.getenv("ALLOW_LOCAL_RUN") == "1"
        and sys.stdin is not None
        and sys.stdin.isatty()
    )
    if not cloud_control_plane and interactive_auth_allowed:
        logger.info(
            "[AUTH] Interactive auth allowed for local runtime. Please follow the prompts in your terminal."
        )
        await telegram_client.start()
        if await telegram_client.is_user_authorized():
            # Export session string for the user convenient copy-pasting
            new_string = telegram_client.session.save()
            print("\n" + "=" * 50)
            print("🚀 [SUCCESS] NEW SESSION STRING GENERATED:")
            print(new_string)
            print("=" * 50 + "\n")
            return True

    logger.error(
        "[AUTH] Userbot session missing or unauthorized. Interactive auth is disabled in cloud runtime."
    )
    return False


# Callbacks and Helper Functions (defined after globals)
async def push_block_to_amocrm(user_id: int, phone: str, block_text: str) -> None:
    """Callback for SessionManager to flush a block of messages.

    Args:
        user_id: The Telegram user ID
        phone: User's phone number
        block_text: The message block to push to AmoCRM
    """
    global msg_controller
    if not msg_controller:
        return
    try:
        contact_result = msg_controller.crm.amocrm.get_contact_by_phone(phone)
        contact = (
            await contact_result
            if inspect.isawaitable(contact_result)
            else contact_result
        )
        if contact:
            note_result = msg_controller.crm.amocrm.add_contact_note(
                contact["id"], block_text
            )
            if inspect.isawaitable(note_result):
                await note_result
            logger.info(f"[ENTERPRISE SYNC] Block pushed for {user_id}")
        else:
            logger.warning(
                f"[ENTERPRISE SYNC] Contact not found for {user_id} ({phone})"
            )
    except Exception as e:
        logger.error(f"[ENTERPRISE SYNC ERROR] Push failed: {e}")


# Global Search State (Memory-based for simplicity)
last_deep_search_time = 0


async def global_phone_lookup(phone: str) -> Optional[Dict[str, Any]]:
    """Butun Telegramdan raqam orqali qidirib topish (Xavfsiz rejimda)."""
    # Raqamni tozalash
    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    if not clean_phone.startswith("998"):
        # Agar O'zbekiston raqami bo'lsa va + bo'lmasa, qo'shib qo'yamiz
        if len(clean_phone) == 9:
            clean_phone = "998" + clean_phone

    try:
        # 1. Vaqtinchalik kontakt yaratish
        contact = types.InputPhoneContact(
            client_id=random.randrange(-(2**63), 2**63),
            phone=clean_phone,
            first_name="Oisha Search",
            last_name="",
        )

        # 2. Import so'rovi
        result = await client(
            functions.contacts.ImportContactsRequest(contacts=[contact])
        )

        if result.users:
            user = result.users[0]
            user_data = {
                "user_id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
            }

            # 3. Bazaga saqlab qo'yamiz (Keyingi safar tekin bo'lishi uchun)
            await msg_controller.db.upsert_user(
                user_id=user.id,
                first_name=user.first_name,
                username=user.username,
                phone=clean_phone,
                last_name=user.last_name,
            )

            # 4. Kontaktni darhol o'chirib tashlaymiz
            try:
                await client(functions.contacts.DeleteContactsRequest(id=[user.id]))
            except Exception as exc:
                logger.debug("[GLOBAL SEARCH] Contact delete failed: %s", exc)
            return user_data

        return None
    except Exception as e:
        logger.error(f"[GLOBAL SEARCH ERROR] {e}")
        return None


async def notify_admin(message: str, client: TelegramClient) -> None:
    """Admin (baxtiyorjon) ga muhim xabar yuborish.

    Args:
        message: The message text to send
        client: The Telethon client instance
    """
    try:
        await client.send_message("me", message)
    except Exception as e:
        logger.error(f"[NOTIFY ERROR] {e}")


async def background_monitor_task() -> None:
    """Barcha korporativ monitoring vazifalarini fonda ishga tushirish — wrapper."""
    from src.schedulers.background_monitor import BackgroundMonitor

    monitor = BackgroundMonitor(
        msg_controller=msg_controller,
        client=client,
        juma_notifier=juma_notifier,
        settings=settings,
        get_surgical_integration=get_surgical_integration,
        TN5_GROUP_ID=TN5_GROUP_ID,
    )
    await monitor.run()


# First definition of self_command_handler was merged into the main one below to avoid collision.


async def handle_new_message(event):
    """Barcha kiruvchi xabarlarni xavfsizlik va aqllilik bilan tahlil qilish."""
    from src.api.live_monitor import broadcast_event

    # 0. Botning o'z ID sini olish (Sikl oldini olish uchun)
    me = await client.get_me()
    await safe_responder.update_me_id(me.id)

    # Broadcast: incoming message
    sender = await event.get_sender()
    sender_name = getattr(sender, "first_name", "User")
    msg_text = (event.message.message or "")[:200]
    chat_title = getattr(event.chat, "title", None) or sender_name
    await broadcast_event({
        "type": "message",
        "chat_id": event.chat_id,
        "chat_name": chat_title,
        "sender": sender_name,
        "text": msg_text,
        "is_private": event.is_private,
        "message_id": event.id,
    })

    # [PHASE 1.6] Advance per-chat checkpoint BEFORE any filtering.
    from src.handlers.message_handler import advance_checkpoint
    await advance_checkpoint(event, msg_controller)

    if _should_block_private_userbot_reply(event):
        logger.info("[USERBOT] Personal DM ignored by policy chat=%s", event.chat_id)
        return

    # 1. Spamdan himoya va Guruh filtrini tekshirish
    if not await safe_responder.should_respond(event):
        return

    # 1.5 Real-time Lead Sync (Automatic for TN5 Topic 7)
    if (
        event.chat_id == TN5_GROUP_ID
        and getattr(event.message.reply_to, "reply_to_msg_id", None) == TN5_TOPIC_ID
    ):
        logger.info(
            f"[ENTERPRISE SYNC] New lead detected from Topic 7! MessageID: {event.id}"
        )
        # Run sync in parallel using the unified LeadScraper logic
        asyncio.create_task(sync_single_lead(event))
        await broadcast_event({"type": "sync", "text": f"Lead sync boshlandi: {event.id}", "chat_id": event.chat_id})
        return

    # 1.6 Admin Commands
    from src.handlers.message_handler import process_admin_commands
    if await process_admin_commands(
        event,
        client=client,
        bot_client=bot_client,
        msg_controller=msg_controller,
        settings=settings,
        meeting_scheduler=meeting_scheduler,
        get_surgical_integration=get_surgical_integration,
        _negotiation_int=_negotiation_int,
        lead_scraper=lead_scraper,
        audit_agent=audit_agent,
        auto_lead_agent=auto_lead_agent,
        admin_bot=admin_bot,
        TN5_GROUP_ID=TN5_GROUP_ID,
        TN5_TOPIC_ID=TN5_TOPIC_ID,
    ):
        return

    # 2. Xabar matnini olish
    message_text = event.message.message
    chat_id = event.chat_id
    sender = await event.get_sender()
    sender_name = getattr(sender, "first_name", "User")
    non_customer_reason = detect_non_customer_context(message_text)
    personal_folder_sender = await _is_personal_folder_sender(sender)

    logger.info(
        f"[USERBOT] Processing message from {sender_name} in {chat_id}: {message_text[:50]}..."
    )

    # ── HISOBCHI AI: Card bot xabarlari ──────────────────────────────────
    from src.handlers.message_handler import process_hisobchi
    if await process_hisobchi(
        event,
        client=client,
        sender=sender,
        message_text=message_text,
        msg_controller=msg_controller,
        voice_processor=voice_processor,
        settings=settings,
    ):
        await broadcast_event({"type": "system", "text": f"Hisobchi AI qayta ishladi: {sender_name}", "chat_id": event.chat_id})
        return
    # ─────────────────────────────────────────────────────────────────────

    if event.is_private and not event.out and message_text:
        try:
            await msg_controller.db.log_message(sender.id, message_text, is_ai=False)

            # [AUTONOMOUS ADVISOR] Real-time Analysis
            asyncio.create_task(
                run_autonomous_advice(chat_id, sender_name, message_text)
            )

        except Exception as log_ex:
            logger.error(f"[USERBOT] Failed to log incoming message: {log_ex}")

    # 3. New Message Logic (Elite Intake)
    if personal_folder_sender:
        logger.info(f"[ELITE INTAKE] Personal/family folder skipped: {sender_name}")
    elif non_customer_reason:
        logger.info(
            f"[ELITE INTAKE] Non-customer context skipped: {sender_name} reason={non_customer_reason}"
        )
    elif event.is_private and not event.out and not getattr(sender, "bot", False):
        from src.handlers.message_handler import process_elite_intake
        await process_elite_intake(
            event,
            sender=sender,
            message_text=message_text,
            sender_name=sender_name,
            msg_controller=msg_controller,
            auto_lead_agent=auto_lead_agent,
            folder_manager=folder_manager,
            admin_bot=admin_bot,
            bot_client=bot_client,
            welcome_manager=welcome_manager,
            TN5_GROUP_ID=TN5_GROUP_ID,
        )

    # [GOD MODE] Multi-Modal (Voice Note) Handling — Gemini STT + Surgical Assessment
    if event.is_private and not event.out and event.message.voice and voice_processor:
        from src.handlers.message_handler import process_voice
        await process_voice(
            event,
            client=client,
            sender=sender,
            sender_name=sender_name,
            msg_controller=msg_controller,
            voice_processor=voice_processor,
            admin_bot=admin_bot,
            surgical_integration=surgical_integration,
            auto_reply_gate=auto_reply_gate,
        )

    # [GOD MODE] Media/Document Sync
    if (
        event.is_private
        and not event.out
        and (event.message.photo or event.message.document)
    ):
        from src.handlers.message_handler import process_media
        await process_media(
            event,
            client=client,
            sender_name=sender_name,
            msg_controller=msg_controller,
            admin_bot=admin_bot,
        )

    # 2.5 Tiered Auto-Reply Gate (shadow/vip_only/live + kill-switch)
    from src.handlers.message_handler import process_ai_reply
    await process_ai_reply(
        event,
        client=client,
        sender=sender,
        chat_id=chat_id,
        sender_name=sender_name,
        message_text=message_text,
        msg_controller=msg_controller,
        auto_reply_gate=auto_reply_gate,
        safe_responder=safe_responder,
        scouter=scouter,
        surgical_integration=surgical_integration,
        action_parser=action_parser,
        admin_bot=admin_bot,
    )
    await broadcast_event({"type": "reply", "text": f"AI reply jo'natildi: {sender_name}", "chat_id": chat_id})


async def sync_single_lead(event):
    """Single leadni avtomatik tahlil qilish va qo'shish — wrapper for backward compat."""
    from src.handlers.lead_sync import sync_single_lead as _impl
    await _impl(
        event,
        client=client,
        lead_scraper=lead_scraper,
        msg_controller=msg_controller,
        TN5_GROUP_ID=TN5_GROUP_ID,
    )


async def run_health_check_api() -> None:
    """Run the FastAPI health check server for Cloud Run compatibility."""
    from src.api.health import run_health_check_api as _impl
    await _impl()


async def stop_health_check_api(
    api_task: Optional[asyncio.Task], timeout_seconds: float = 5.0
) -> None:
    """Ask Uvicorn to finish its lifespan before the event loop is closed."""
    from src.api.health import stop_health_check_api as _impl
    await _impl(api_task, timeout_seconds)



async def run_autonomous_advice(chat_id, sender_name, message_text):
    """Background worker to provide strategic advice — wrapper for backward compat."""
    from src.handlers.shadow_advisor import run_autonomous_advice as _impl
    await _impl(
        chat_id,
        sender_name,
        message_text,
        advisor_agent=advisor_agent,
        client=client,
        action_parser=action_parser,
        evolution_scheduler=evolution_scheduler,
    )


# Import handlers from src/handlers/
from src.handlers import (
    shadow_advisor_handler,
    activity_monitor_handler,
    crm_note_callback_handler,
    crm_edit_text_handler,
    meeting_scheduler_handler,
    case_publisher_handler,
    negotiation_agent_handler,
    kirim_topic_handler,
)


_crm_audit_running = False


# Import command modules to register them
from src.commands import get_command_handler
from src.commands import dashboard as _cmd_dashboard
from src.commands import crm as _cmd_crm
from src.commands import calendar as _cmd_calendar
from src.commands import sync as _cmd_sync
from src.commands import erp as _cmd_erp
from src.commands import analysis as _cmd_analysis


async def self_command_handler(event):
    """Handle commands from the owner in 'Saved Messages'."""
    from src.api.live_monitor import broadcast_event
    if not event.message.text:
        return
    cmd = event.message.text.lower().strip()

    handler, prefix = get_command_handler(cmd)
    if handler:
        await broadcast_event({"type": "command", "text": f"Buyruq: {cmd}", "chat_id": "saved_messages"})
        ctx = {
            "msg_controller": msg_controller,
            "client": client,
            "bot_client": bot_client,
            "settings": settings,
            "meeting_scheduler": meeting_scheduler,
            "get_surgical_integration": get_surgical_integration,
            "_negotiation_int": _negotiation_int,
        }
        await handler(event, **ctx)
        return

    # Command not found — do nothing


def _negotiation_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default





async def _brain_evolution_loop():
    """Runs OishaBrain.evolve() every 6 hours to self-diagnose agent failures."""
    from src.schedulers.brain_evolution import brain_evolution_loop as _impl
    await _impl(oisha_brain=oisha_brain)


async def main():
    """Botlarni ishga tushirish (Userbot + Admin Bot)."""
    from src.boot import boot_application
    await boot_application()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👸 Oisha-OS: To'xtatildi (KeyboardInterrupt).")
    except Exception as e:
        logger.critical(f"👸 Oisha-OS: Fatal Error: {e}", exc_info=True)
    finally:
        print("Stopping bot...")
