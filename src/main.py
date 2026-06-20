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


def _income_state_key(message_id: int) -> str:
    return f"income_workflow:{message_id}"


def _income_gate_key(message_id: int) -> str:
    return f"income_workflow_gate:{message_id}"


def _kirim_celebration_key(chat_id: int, message_id: int) -> str:
    return f"kirim_celebration:{chat_id}:{message_id}"


def _normalize_income_lookup(text: str) -> str:
    normalized = re.sub(r"[^\w]+", " ", (text or "").lower(), flags=re.UNICODE)
    return " ".join(normalized.split())


def _extract_income_amount(text: str) -> Dict[str, Any]:
    lowered = (text or "").lower()
    currency = "USD" if ("$" in lowered or "usd" in lowered) else "UZS"
    matches = list(re.finditer(r"\d[\d\s,.]*", text or ""))
    if not matches:
        return {"raw": "noma'lum", "value": None, "currency": currency}

    raw_amount = max(matches, key=lambda match: len(match.group(0))).group(0).strip()
    if currency == "USD":
        cleaned = raw_amount.replace(" ", "").replace(",", ".")
        if cleaned.count(".") > 1:
            parts = cleaned.split(".")
            cleaned = "".join(parts[:-1]) + "." + parts[-1]
        try:
            value = float(cleaned)
        except ValueError:
            value = None
    else:
        cleaned = re.sub(r"[^\d]", "", raw_amount)
        value = int(cleaned) if cleaned else None

    return {"raw": raw_amount, "value": value, "currency": currency}


def _detect_payment_type(text: str, is_first_payment: bool) -> str:
    lowered = (text or "").lower()
    if "to'liq" in lowered or "toliq" in lowered or "full" in lowered:
        return "Oldindan to'liq" if is_first_payment else "Yakuniy"
    if "yakuniy" in lowered or "final" in lowered or "qoldiq" in lowered:
        return "Yakuniy"
    return "Avans" if is_first_payment else "Orada to'lov"


def _detect_payment_source(text: str) -> Optional[str]:
    lowered = (text or "").lower()
    if "naqd" in lowered or "cash" in lowered:
        return "Naqd"
    if "bank" in lowered or "hisob" in lowered:
        return "Bank hisobi"
    if "p2p" in lowered or "card" in lowered or "karta" in lowered:
        return "P2P card"
    return None


def _format_income_amount_for_celebration(amount: Dict[str, Any]) -> str:
    raw = str(amount.get("raw") or "").strip()
    if not raw or raw == "noma'lum":
        return "yangi kirim"

    lowered = raw.lower()
    if "$" in raw or "usd" in lowered:
        return raw
    if "so'm" in lowered or "sum" in lowered or "uzs" in lowered:
        return raw
    if (amount.get("currency") or "UZS") == "USD":
        return f"{raw} USD"
    return f"{raw} so'm"


def _sender_display_name(sender: Any) -> str:
    username = (getattr(sender, "username", None) or "").strip()
    if username:
        return username if username.startswith("@") else f"@{username}"

    full_name = " ".join(
        part
        for part in (
            getattr(sender, "first_name", None),
            getattr(sender, "last_name", None),
        )
        if part
    ).strip()
    return full_name or "Sotuvchi"


def _looks_like_income_announcement(text: str) -> bool:
    lowered = (text or "").lower().strip()
    if not lowered or lowered.startswith("/"):
        return False
    if _is_group_open_confirmation(lowered):
        return False

    # Questions and negations are status checks, not announcements
    if lowered.endswith("?"):
        return False
    negation_terms = (
        "bo'lmadi", "bolmadi", "kelmadi", "tushmadi",
        "yo'q", "yoq", "emas", "qilmadi", "bo'lmagan",
    )
    if any(term in lowered for term in negation_terms):
        return False
    if _is_finance_rejection(lowered):
        return False

    # Only congratulate when there is a confirmed numeric amount — bare keyword
    # mentions ("kirim bo'ldimi?", "to'lov haqida") are too ambiguous.
    amount = _extract_income_amount(text)
    return amount.get("value") is not None


def _format_person_mention(person: Optional[Dict[str, Any]], fallback: str) -> str:
    if not person:
        return fallback
    username = (person.get("username") or "").strip()
    if username:
        return username if username.startswith("@") else f"@{username}"
    user_id = person.get("user_id")
    name = person.get("name") or fallback
    if user_id:
        return f"<a href='tg://user?id={user_id}'>{name}</a>"
    return name


async def _resolve_finance_approver(db: Database) -> Optional[Dict[str, Any]]:
    for role_name in ("finance", "moliya", "accountant", "buxgalter"):
        person = await db.get_user_by_role(role_name)
        if person:
            return person

    owner_id = getattr(settings, "OWNER_ID", None) or getattr(config, "OWNER_ID", None)
    if owner_id:
        return {"user_id": owner_id, "name": "Owner", "username": None}
    return None


async def _find_project_for_income(message_text: str) -> Optional[Dict[str, Any]]:
    from src.services.core.airtable_sync import AirtableSync

    sync = AirtableSync()
    projects = await asyncio.to_thread(sync.get_projects)
    if not projects:
        return None

    normalized_text = _normalize_income_lookup(message_text)
    best_match = None
    best_score = 0.0

    for project in projects:
        fields = project.get("fields", {})
        project_name = AirtableSync._get_field(fields, "project_name", "") or ""
        normalized_name = _normalize_income_lookup(project_name)
        if len(normalized_name) < 4:
            continue

        if normalized_name in normalized_text:
            score = 2.0 + (len(normalized_name) / 1000)
        else:
            tokens = [token for token in normalized_name.split() if len(token) >= 4]
            if not tokens:
                continue
            hits = sum(1 for token in tokens if token in normalized_text)
            score = hits / len(tokens)

        if score > best_score:
            best_score = score
            best_match = {
                "record_id": project.get("id"),
                "project_name": project_name,
                "client_ids": fields.get("Mijoz nomi") or [],
                "seller_ids": fields.get("Seller") or [],
                "project_fields": fields,
            }

    return best_match if best_score >= 0.6 else None


async def _count_income_records_for_project(project_record_id: str) -> int:
    from src.services.core.airtable_sync import AirtableSync

    sync = AirtableSync()
    records = await asyncio.to_thread(sync.get_finance_records)
    count = 0
    for record in records:
        if record.get("_record_type") != "income":
            continue
        if project_record_id in (record.get("fields", {}).get("Loyiha nomi") or []):
            count += 1
    return count


async def _create_income_airtable_record(
    workflow: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    from src.services.core.airtable_sync import AirtableSync
    from src.time_utils import get_local_now

    project_id = workflow.get("project_id")
    if not project_id:
        return None

    project_fields = workflow.get("project_fields") or {}
    amount_value = workflow.get("amount_value")
    if amount_value is None:
        return None

    currency = workflow.get("currency") or "UZS"
    kurs = project_fields.get("Kurs") or 12000
    fields: Dict[str, Any] = {
        "Loyiha nomi": [project_id],
        "Valyuta": currency,
        "To'lov sanasi": get_local_now().strftime("%Y-%m-%d"),
        "To‘lov miqdori": amount_value,
        "Kurs": kurs,
        "To'lov turi": _detect_payment_type(
            workflow.get("source_text", ""), workflow.get("is_first_payment", False)
        ),
    }

    payment_source = _detect_payment_source(workflow.get("source_text", ""))
    if payment_source:
        fields["To'lov manbasi"] = payment_source
    if workflow.get("client_ids"):
        fields["Mijoz"] = workflow["client_ids"]
    if workflow.get("seller_ids"):
        fields["Seller"] = workflow["seller_ids"]

    sync = AirtableSync(table_name="Kirim")
    return await asyncio.to_thread(sync.create_record, fields)


async def _save_income_workflow_state(db: Database, payload: Dict[str, Any]) -> None:
    await db.set_state(
        _income_state_key(int(payload["original_message_id"])),
        json.dumps(payload, ensure_ascii=False),
    )
    gate_message_id = payload.get("gate_message_id")
    if gate_message_id:
        await db.set_state(
            _income_gate_key(int(gate_message_id)), int(payload["original_message_id"])
        )


async def _load_income_workflow_state(
    db: Database, reply_message_id: Optional[int]
) -> Optional[Dict[str, Any]]:
    if not reply_message_id:
        return None

    raw = await db.get_state(_income_state_key(int(reply_message_id)))
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    original_id = await db.get_state(_income_gate_key(int(reply_message_id)))
    if not original_id:
        return None

    raw = await db.get_state(_income_state_key(int(original_id)))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _is_group_open_confirmation(text: str) -> bool:
    lowered = (text or "").lower()
    keywords = (
        "guruh ochildi",
        "group opened",
        "group open",
        "gruppa ochildi",
        "mijoz bilan guruh",
        "client group",
    )
    return any(keyword in lowered for keyword in keywords) or "t.me/" in lowered


def _is_finance_approval(text: str) -> bool:
    lowered = (text or "").lower()
    keywords = (
        "tasdiq",
        "tasdiqlandi",
        "confirmed",
        "confirm",
        "ok",
        "okey",
        "tushdi",
        "tushgan",
    )
    return any(keyword in lowered for keyword in keywords)


def _is_finance_rejection(text: str) -> bool:
    lowered = (text or "").lower()
    keywords = (
        "rad",
        "reject",
        "rejected",
        "tasdiqlamadi",
        "tasdiqlanmadi",
        "xato",
        "xatolik",
        "tushmadi",
        "bekor",
    )
    return any(keyword in lowered for keyword in keywords)


def _is_kirim_topic_message(message: Any) -> bool:
    if not settings.TOPIC_KIRIM_ID:
        return False

    topic_id = settings.TOPIC_KIRIM_ID
    direct_reply_id = getattr(message, "reply_to_msg_id", None)
    reply_to = getattr(message, "reply_to", None)
    reply_top_id = getattr(message, "reply_to_top_id", None) or getattr(
        reply_to, "reply_to_top_id", None
    )
    forum_topic = getattr(reply_to, "forum_topic", False)

    return bool(
        direct_reply_id == topic_id
        or reply_top_id == topic_id
        or (forum_topic and direct_reply_id == topic_id)
    )


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
            except Exception:
                pass
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


# background_monitor_task() — the 5-minute scheduling loop — now lives in
# src/scheduler.py. boot.py spawns scheduler.background_monitor_task(); it
# reads runtime state (client, msg_controller, ...) from this module via `m.`.


# First definition of self_command_handler was merged into the main one below to avoid collision.


async def handle_new_message(event):
    """Barcha kiruvchi xabarlarni xavfsizlik va aqllilik bilan tahlil qilish."""

    # 0. Botning o'z ID sini olish (Sikl oldini olish uchun)
    me = await client.get_me()
    await safe_responder.update_me_id(me.id)

    # [PHASE 1.6] Advance per-chat checkpoint BEFORE any filtering.
    # We advance even for spam/skipped messages so boot_catchup doesn't
    # repeatedly re-replay the same skipped message after every restart.
    # Idempotent via MAX() semantics in update_chat_checkpoint.
    try:
        _cp_chat = getattr(event, "chat_id", None)
        _cp_msg = getattr(getattr(event, "message", None), "id", None) or getattr(
            event, "id", None
        )
        if _cp_chat and _cp_msg and msg_controller is not None:
            await msg_controller.db.update_chat_checkpoint(_cp_chat, _cp_msg)
    except Exception as _cp_exc:
        logger.debug(f"[CHECKPOINT] update skipped: {_cp_exc}")

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
        return

    # 1.6 Admin Commands
    if event.is_private and event.message.text.startswith("/"):
        if event.message.text == "/sync_backlog":
            await event.respond(
                "👸 Oisha-OS: O'tmishdagi (Backlog) xabarlarni skanerlashni boshladim... 👸🛡️"
            )
            # Run backlog sync in background
            asyncio.create_task(
                lead_scraper.sync_topic_to_contacts(
                    client=client,
                    group_id=TN5_GROUP_ID,
                    topic_id=TN5_TOPIC_ID,
                    limit=50,  # Enterprise backlog limit
                )
            )
            return

        if event.message.text == "/force_sync_all":
            await event.respond(
                "👸 Oisha-OS: Guruhning barcha a'zolarini ommaviy saqlash rejimini tasdiqladim!\nBu jarayon kunlab davom etishi mumkin. Orqa fonda (parallel) xavfsiz tezlikda saqlayman... 🐢🛡️"
            )
            # Run mass sync in background
            asyncio.create_task(
                lead_scraper.sync_all_group_members(
                    client=client, group_id=TN5_GROUP_ID
                )
            )
            return

        if event.message.text == "/efficiency":
            from src.services.core.airtable_sync import AirtableSync

            at_sync = AirtableSync()
            msg_controller.enterprise_reporter.airtable = at_sync

            report = (
                await msg_controller.enterprise_reporter.get_team_efficiency_report()
            )
            await event.respond(report, parse_mode="markdown")
            return

        if event.message.text == "/report":
            await event.respond("⏳ Oisha-OS: Kunlik hisobot (Reportagram) tayyorlanmoqda...")
            try:
                from src.services.core.crm_daily_report import CRMDailyReporter
                amocrm_client = None
                if msg_controller and getattr(msg_controller, "crm", None):
                    amocrm_client = getattr(msg_controller.crm, "amocrm", None)
                if not amocrm_client:
                    amocrm_client = get_surgical_integration().amocrm
                
                reporter = CRMDailyReporter(amocrm=amocrm_client)
                stats = await reporter.fetch_stats()
                prev = reporter._load_prev_stats()
                report_text = reporter.format_report(stats, prev)
                await event.respond(report_text)
            except Exception as e:
                await event.respond(f"❌ Xatolik yuz berdi: {e}")
            return

        if event.message.text == "/stats":
            await event.respond("⏳ Joriy statistika olinmoqda...")
            try:
                from src.services.core.crm_daily_report import CRMDailyReporter
                amocrm_client = None
                if msg_controller and getattr(msg_controller, "crm", None):
                    amocrm_client = getattr(msg_controller.crm, "amocrm", None)
                if not amocrm_client:
                    amocrm_client = get_surgical_integration().amocrm
                
                reporter = CRMDailyReporter(amocrm=amocrm_client)
                stats = await reporter.fetch_stats()
                text = (
                    f"📊 **Bugungi holat ({stats.date_label})**\n"
                    f"Tushgan: {stats.total_leads} lead\n"
                    f"Gaplashilgan: {stats.contacted} lead\n"
                    f"Sifatli: {stats.qualified} lead\n"
                    f"Muvaffaqiyatli (Won): {stats.won}\n"
                    f"Daromad: ${stats.revenue:,.0f}\n"
                    f"Pipeline qiymati: ${stats.pipeline_value:,.0f}"
                )
                await event.respond(text)
            except Exception as e:
                await event.respond(f"❌ Xatolik: {e}")
            return

        if event.message.text == "/history":
            try:
                from src.services.core.crm_daily_report import CRMDailyReporter
                reporter = CRMDailyReporter(amocrm=None)
                history = reporter.get_history(7)
                if not history:
                    await event.respond("📅 Tarix topilmadi. Hisobotlar hali keshga yozilmagan.")
                    return
                lines = ["📅 **So'nggi 7 kunlik hisobotlar tarixi:**"]
                for s in history:
                    lines.append(
                        f"• {s.date_label}: {s.total_leads} lead | {s.won} won | ${s.revenue:,.0f}"
                    )
                await event.respond("\n".join(lines))
            except Exception as e:
                await event.respond(f"❌ Xatolik: {e}")
            return

            from src.services.core.airtable_sync import AirtableSync

            at_sync = AirtableSync()
            projects = at_sync.get_projects()
            if not projects:
                await event.respond(
                    "👸 Oisha-OS: Hozircha aktiv loyihalar topilmadi. 🤷‍♀️"
                )
                return

            text = "🏗 **Aktiv Loyihalar (Airtable):**\n\n"
            for p in projects[:10]:
                f = p.get("fields", {})
                stage = f.get("Stage", "Nomalum")
                text += f"• {f.get('Project Name', 'Nomsiz')} — <b>{stage}</b>\n"
            await event.respond(text, parse_mode="html")
            return

        if event.message.text == "/audit":
            await event.respond(
                "👸 Oisha-OS: Oxirgi harakatlaringizni tahlil qilyapman, bir oz kutib turing... 👸📈📊"
            )
            report = await audit_agent.generate_audit_report(limit=100)
            await event.respond(report)
            return

        if event.message.text == "/audit_leads":
            await event.respond(
                "👸 Oisha-OS: Oxirgi 100 ta dialogni audit qilyapman, shaffoflik hisoboti tayyor bo'lishi bilan yuboraman... 👸🛡️"
            )

            audit_report = "👸 **Oisha-OS Lead Audit (Transparency Report)** 👸\n\n"
            async for dialog in client.iter_dialogs(limit=100):
                if not dialog.is_user or dialog.entity.bot:
                    continue

                name = getattr(dialog.entity, "first_name", "User")
                # Check messages
                messages = []
                async for msg in client.iter_messages(dialog.id, limit=5):
                    if msg.text:
                        messages.append(msg.text)

                if not messages:
                    continue

                lead_data = await auto_lead_agent.extract_lead_info(
                    "\n".join(reversed(messages)), {"id": dialog.id, "first_name": name}
                )

                if lead_data and lead_data.get("is_lead"):
                    audit_report += f"✅ **{name}** — Lead deb topildi. ({lead_data.get('business', 'Noʻmalum')})\n"
                else:
                    audit_report += f"❌ **{name}** — Shaxsiy/Irrelevant deb topildi.\n"

                if len(audit_report) > 3500:  # Telegram message limit
                    await event.respond(audit_report)
                    audit_report = ""

            if audit_report:
                await event.respond(audit_report)
            return

        if event.message.text.startswith("/find "):
            phone = event.message.text.split(" ", 1)[1].strip()
            await event.respond(
                f"🔍 **{phone}** raqamini butun Telegramdan qidiryapman... 👸🛡️"
            )
            user_data = await global_phone_lookup(phone)
            if user_data:
                username = (
                    f"@{user_data['username']}"
                    if user_data["username"]
                    else "Mavjud emas"
                )
                response = (
                    f"✅ **Foydalanuvchi topildi!**\n\n"
                    f"👤 **Ism:** {user_data['first_name']} {user_data['last_name'] or ''}\n"
                    f"🆔 **ID:** `{user_data['user_id']}`\n"
                    f"🔗 **Username:** {username}\n"
                    f"📱 **Raqam:** `{phone}`"
                )
                await event.respond(response)
            else:
                await event.respond(
                    "❌ **Afsus, foydalanuvchi topilmadi.**\n(Ehtimol, foydalanuvchi o'z maxfiylik sozlamalarida raqam orqali qidiruvni cheklagan bo'lishi mumkin)."
                )
            return

        if event.message.text == "/sync_today":
            await event.respond(
                "👸 Oisha-OS: Kecha va bugungi shaxsiy suhbatlarni (DM) skanerlashni boshladim... 👸🛡️"
            )
            # Run retro sync in background
            asyncio.create_task(
                lead_scraper.sync_private_dialogs(client=client, limit=100)
            )
            return

        if event.message.text == "/hunt":
            await event.respond(
                "👸 Oisha-OS: 2026-yildagi BARCHA shaxsiy yozishmalarni skanerlash boshlandi!\n"
                "🎯 Sifatli leadlar Team CRM topicga yuboriladi.\n"
                "⏳ Bu jarayon 10-30 daqiqa olishi mumkin..."
            )
            asyncio.create_task(
                lead_scraper.hunt_2026_leads(
                    client=client,
                    bot_client=bot_client,
                )
            )
            return

        if event.message.text == "/sync_history":
            await event.respond(
                "👸 Oisha-OS: O'tgan 1 yillik shaxsiy yozishmalarni (DM) bazaga kiritishni boshladim... 👸🛡️\nBu biroz vaqt olishi mumkin, orqa fonda xavfsiz ishlayman."
            )
            sync_service = HistoricalSyncService(msg_controller.db, client)
            asyncio.create_task(sync_service.start_backlog_sync(days=365))
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
    try:
        global _hisobchi_engine, handle_card_bot_message, handle_finance_group_reply, is_card_bot_sender  # noqa: PLW0603
        if "_hisobchi_engine" not in globals() or _hisobchi_engine is None:
            from src.services.core.finance.hisobchi_handlers import (
                handle_card_bot_message, handle_finance_group_reply, is_card_bot_sender,
            )
            from src.services.core.finance.hisobchi_engine import HisobchiEngine
            _hisobchi_engine = HisobchiEngine(msg_controller.db)

        if event.is_private and not event.out and is_card_bot_sender(sender):
            await handle_card_bot_message(event, client, _hisobchi_engine)
            return

        if not event.out and event.message.voice and voice_processor:
            from src.services.core.finance.hisobchi_handlers import _get_finance_config
            finance_group_id, _, _ = _get_finance_config()
            is_finance_chat = (finance_group_id is not None and event.chat_id == finance_group_id)
            is_auth_user = False
            if event.is_private:
                managers = getattr(settings, "SALES_MANAGER_IDS", [])
                sender_id = getattr(sender, "id", None)
                me = await client.get_me()
                is_auth_user = (sender_id is not None and (sender_id in managers or sender_id == me.id))
            if is_finance_chat or is_auth_user:
                from src.services.core.finance.hisobchi_handlers import process_finance_voice_message
                _was_voice_hisobchi = await process_finance_voice_message(
                    event, client, _hisobchi_engine, voice_processor
                )
                if _was_voice_hisobchi:
                    return

        if not event.is_private and not event.out and message_text:
            _was_hisobchi = await handle_finance_group_reply(event, client, _hisobchi_engine)
            if _was_hisobchi:
                return
    except Exception as _hisob_exc:
        logger.error("[HISOBCHI] Handler error: %s", _hisob_exc, exc_info=True)
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
        # Skanerlash (1.1, 1.2) - Now includes intent categorization
        lead_data = await auto_lead_agent.extract_lead_info(
            message_text, {"id": sender.id, "first_name": sender_name}
        )

        if lead_data:
            intent = lead_data.get("intent_category", "POTENTIAL")
            # [GOD MODE] Auto-Assign Folder
            if folder_manager:
                asyncio.create_task(folder_manager.assign_to_folder(sender.id, intent))

            if lead_data.get("is_lead") and not await msg_controller.db.is_crm_synced(
                event.sender_id
            ):
                logger.info(
                    f"[ELITE INTAKE] Yangi lid aniqlandi: {sender_name} (Intent: {intent})"
                )

                # Intent -> O'zbek label
                intent_label_map = {
                    "HOT_LEAD": "🔥 Qaynoq mijoz",
                    "WARM_LEAD": "♨️ Issiq mijoz",
                    "POTENTIAL": "🌱 Potensial mijoz",
                }
                intent_label = intent_label_map.get(intent, f"🔵 {intent}")

                # [GOD MODE] Save intent and data to DB
                await msg_controller.db.upsert_user(
                    sender.id,
                    sender_name,
                    username=getattr(sender, "username", None),
                    intent=intent,
                    region=lead_data.get("city"),
                    business_type=lead_data.get("activity"),
                    brand_name=lead_data.get("brand_name"),
                )

                # [GOD MODE] Smart Draft Suggestion (Using refined method)
                if intent == "HOT_LEAD" and admin_bot:
                    draft_prompt = (
                        f"Mijoz: {sender_name}\n"
                        f"Xabar: {event.message.text}\n\n"
                        "Baxtiyor aka nomidan ushbu mijozga do'stona, lekin professional javob loyihasini tayyorlang. "
                        "Unga yordam berishga tayyorligimizni va loyihasini o'rganib chiqishimizni ayting."
                    )
                    draft = await msg_controller.db.analyze_text_with_ai(draft_prompt)
                    await admin_bot.send_draft_for_approval(
                        sender.id, sender_name, draft
                    )

                # AmoCRM-da yaratish (1.3)
                # [TELETHON PHONE EXTRACTION] Try to get phone from sender or fetch full user info
                phone = lead_data.get("phone")
                if not phone and sender:
                    # First try direct attribute
                    phone = getattr(sender, "phone", None)

                    # If no phone and we have bot_client, try fetching full user entity
                    if not phone and bot_client:
                        try:
                            full_user = await bot_client.get_entity(sender.id)
                            phone = getattr(full_user, "phone", None)
                            if phone:
                                logger.info(
                                    f"📞 [PHONE] Telethon orqali raqam olindi: {sender.id}"
                                )
                        except Exception as e:
                            logger.debug(f"[PHONE] Telethon get_entity xato: {e}")

                if not phone:
                    phone = "Raqam yo'q"

                # [USERNAME EXTRACTION] Try to get username from sender or fetch full user info
                username = getattr(sender, "username", None)
                if not username and sender and bot_client:
                    # If no username and we have bot_client, try fetching full user entity
                    try:
                        # Re-use full_user if already fetched for phone
                        if "full_user" not in locals():
                            full_user = await bot_client.get_entity(sender.id)
                        username = getattr(full_user, "username", None)
                        if username:
                            logger.info(
                                f"[USERNAME] Telethon orqali username olindi: @{username}"
                            )
                    except Exception as e:
                        logger.debug(f"[USERNAME] Telethon get_entity xato: {e}")

                if not username:
                    username = "Username yo'q"

                username_str = (
                    f"@{username}" if username != "Username yo'q" else username
                )
                crm_sync = await msg_controller.crm.sync_lead(
                    user_id=sender.id,
                    name=f"DM Lead: {sender_name}",
                    phone=phone,
                    note=f"AI Tahlil: {lead_data.get('needs')}\nIntent: {intent}\nUser: {username_str}",
                )
                if crm_sync.get("success"):
                    await msg_controller.db.set_crm_synced(event.sender_id)

                # Elite Welcome (1.4)
                await welcome_manager.send_welcome(event.sender_id)

                # Admin-ni ogohlantirish
                sync_line = (
                    "✅ AmoCRM-ga saqlandi."
                    if crm_sync.get("success")
                    else f"⚠️ CRM sync xato: {crm_sync.get('error', 'nomaʼlum')}"
                )
                lead_notify_text = (
                    f"👸 **Yangi Lid aniqlandi!**\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 **Ism:** {sender_name}\n"
                    f"🔗 **Username:** {username_str}\n"
                    f"📞 **Raqam:** {phone}\n"
                    f"🎯 **Holat:** {intent_label}\n"
                    f"💬 **Xabar:** {(message_text or '')[:200]}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"{sync_line}"
                )
                if admin_bot:
                    await admin_bot.notify_lead(lead_notify_text)

                # [GOD MODE] HOT_LEAD bo'lsa CRM guruhiga ham yuborish
                if intent == "HOT_LEAD" and bot_client and TN5_GROUP_ID:
                    try:
                        await bot_client.send_message(
                            TN5_GROUP_ID, lead_notify_text, parse_mode="md"
                        )
                        logger.info(f"[HOT LEAD] CRM guruhiga yuborildi: {sender_name}")
                    except Exception as crm_notif_err:
                        logger.warning(
                            f"[HOT LEAD] CRM guruh notif xato: {crm_notif_err}"
                        )

    # [GOD MODE] Multi-Modal (Voice Note) Handling — Gemini STT + Surgical Assessment
    if event.is_private and not event.out and event.message.voice and voice_processor:
        logger.info(f"🎙️ [VOICE] New voice from {sender_name}...")
        try:
            temp_path = f"temp_voice_{event.id}.ogg"
            await client.download_media(event.message, file=temp_path)

            # --- Gemini multimodal STT + NegotiationAssessment ---
            try:
                from src.agents.negotiation_engine import transcribe_and_assess_audio

                with open(temp_path, "rb") as f:
                    audio_bytes = f.read()
                crm_status = ""
                if hasattr(msg_controller, "crm"):
                    try:
                        user_info = await msg_controller.db.get_user_info(
                            event.sender_id
                        )
                        phone = user_info.get("phone") if user_info else None
                        if phone:
                            crm_status = await msg_controller.crm.get_user_context(
                                phone
                            )
                    except Exception:
                        pass

                stt_result = await transcribe_and_assess_audio(
                    audio_bytes, mime_type="audio/ogg", crm_status=crm_status
                )
                transcript = stt_result.get("transcript", "")
                assessment = stt_result.get("assessment")

                if transcript:
                    admin_note = f"🎙️ **Ovozli xabar ({sender_name}):**\n\n{transcript}"
                    if assessment:
                        admin_note += (
                            f"\n\n🔍 **Assessment:** stage={assessment.stage} "
                            f"| intent={assessment.intent} "
                            f"| prob={assessment.close_probability:.0%}"
                        )
                    if admin_bot:
                        await admin_bot.notify_lead(admin_note)

                    # Route transcript through surgical negotiator (same as text)
                    if (
                        surgical_integration
                        and surgical_integration.should_use_surgical(
                            str(event.sender_id), transcript
                        )
                    ):
                        surgical_result = await surgical_integration.process_message(
                            str(event.sender_id),
                            transcript,
                            context={"source": "voice", "user_info": {}},
                        )
                        if surgical_result.get("mode") == "surgical":
                            voice_reply = surgical_result.get("response", "")
                            if voice_reply:
                                # [AUTO_REPLY_OFF] Gate tekshiruvi — off rejimida ovozga ham javob berilmaydi
                                _voice_decision = await auto_reply_gate.evaluate(
                                    msg_controller.db,
                                    is_mentioned=False,
                                    lead_score=0,
                                    message_text=transcript or "",
                                )
                                if _voice_decision.action == "send":
                                    await event.reply(voice_reply)
                                    logger.info(
                                        f"[VOICE→SURGICAL] Auto-replied to {sender_name}"
                                    )
                                else:
                                    logger.info(
                                        f"[VOICE→SURGICAL] Skipped reply (gate={_voice_decision.action})"
                                    )

            except Exception as stt_err:
                logger.warning(f"[VOICE] Gemini STT failed, fallback: {stt_err}")
                # Fallback: legacy voice_processor
                result = await voice_processor.transcribe(temp_path)
                if result and admin_bot:
                    await admin_bot.notify_lead(
                        f"🎙️ **Ovozli xabar ({sender_name}):**\n\n{result}"
                    )

            asyncio.create_task(voice_processor.cleanup(temp_path))
        except Exception as e:
            logger.error(f"[VOICE] Integration error: {e}")

    # [GOD MODE] Media/Document Sync
    if (
        event.is_private
        and not event.out
        and (event.message.photo or event.message.document)
    ):
        logger.info(f"📁 [MEDIA] New media from {sender_name}...")
        try:
            # Download
            media_path = await client.download_media(event.message)
            if media_path:
                # Upload to Google Drive (Background)
                def upload_drive():
                    return msg_controller.google.drive.upload_file(media_path)

                drive_link = await asyncio.to_thread(upload_drive)

                if drive_link:
                    # Notify Admin
                    if admin_bot:
                        type_str = "Rasm" if event.message.photo else "Hujjat"
                        await admin_bot.notify_lead(
                            f"📁 **Yangi {type_str} ({sender_name}):**\n🔗 [Google Drive Link]({drive_link})"
                        )

                # Cleanup local
                if os.path.exists(media_path):
                    os.remove(media_path)

        except Exception as e:
            logger.error(f"[MEDIA] Integration error: {e}")

    try:
        # 2.5 Tiered Auto-Reply Gate (shadow/vip_only/live + kill-switch)
        # Avval mention tekshiruvi — mention bo'lsa, gate'da short-circuit "send" qaytaradi.
        is_mentioned = False
        if event.message.text:
            me = await client.get_me()
            text_low = event.message.text.lower()
            me_username = (me.username or "").lower()
            is_mentioned = bool(me_username and f"@{me_username}" in text_low)

        # NOTE: lead_score=0 — Phase 3 scoring'gacha stub. VIP-only rejimida
        # score 0 bo'lsa avtomatik shadow'ga tushadi (xavfsiz default).
        decision = await auto_reply_gate.evaluate(
            msg_controller.db,
            is_mentioned=is_mentioned,
            lead_score=0,
            message_text=event.message.text or "",
        )
        logger.info(
            f"[AUTO_GATE] chat={chat_id} action={decision.action} reason={decision.reason} "
            f"mode={decision.effective_mode} kill={decision.kill_switch_on}"
        )

        if decision.action == "skip":
            return
        if decision.action == "escalate":
            if admin_bot:
                try:
                    await admin_bot.notify_lead(
                        f"🚨 **REVIEW kerak** chat=`{chat_id}` sender={sender_name}\n"
                        f"Sabab: `{decision.reason}`\n"
                        f"Matn: {(event.message.text or '')[:500]}"
                    )
                except Exception as notify_ex:
                    logger.warning(f"[AUTO_GATE] escalate notify failed: {notify_ex}")
            return
        # decision.action ∈ {"send", "shadow"} — pipeline davom etadi

        # 3. Odamdek tutilish (Delay + Typing...)
        # 3.1. Super-Analitika: Scouter orqali mijoz profilini tahlil qilish
        dosye = await scouter.get_user_dosye(sender.id)

        await safe_responder.prepare_to_reply(event, client)

        # 4. AI orqali javob tayyorlash
        # 4a. Surgical Negotiator (savdo so'rovlari uchun avtonom agent)
        ai_raw_response = None
        if surgical_integration and surgical_integration.should_use_surgical(
            str(sender.id), message_text or ""
        ):
            try:
                surgical_result = await surgical_integration.process_message(
                    user_id=str(sender.id),
                    message=message_text or "",
                    context={
                        "user_info": {
                            "first_name": getattr(sender, "first_name", ""),
                            "last_name": getattr(sender, "last_name", ""),
                            "username": getattr(sender, "username", ""),
                        },
                        "chat_id": chat_id,
                        "source": "telegram",
                    },
                )
                if surgical_result.get("mode") == "surgical":
                    ai_raw_response = surgical_result.get("response")
                    logger.info(
                        f"[SURGICAL] Autonomous response uid={sender.id} "
                        f"stage={surgical_result.get('deal_info', {}).get('stage')} "
                        f"prob={surgical_result.get('deal_info', {}).get('probability', 0):.0%}"
                    )
                    if surgical_result.get("deal_info", {}).get("probability", 1) < 0.2:
                        ai_raw_response = (
                            None  # Fallback to legacy for very uncertain cases
                        )
            except Exception as surg_ex:
                logger.warning(f"[SURGICAL] Fallback to legacy: {surg_ex}")

        # 4b. Legacy AI fallback yoki savdo bo'lmagan so'rovlar
        if not ai_raw_response:
            ai_raw_response = await msg_controller.get_response(
                user_id=sender.id,
                user_name=sender_name,
                message=message_text,
                context={
                    "chat_id": chat_id,
                    "is_group": not event.is_private,
                    "dosye": dosye,
                },
            )

        if ai_raw_response:
            # 5. Harakatlarni bajarish (Action Parsing)
            final_text = await action_parser.parse_and_execute(
                reply_text=ai_raw_response,
                sender_id=sender.id,
                sender_name=sender_name,
                username=getattr(sender, "username", "yoq"),
                saved_phone=None,
                context=None,
                is_business=False,
            )

            # 6. Javobni yuborish (gate decision'ga qarab)
            if final_text:
                if decision.action == "shadow":
                    # Shadow rejim: userga yubormaymiz — admin/owner'ga preview
                    if admin_bot:
                        try:
                            await admin_bot.notify_lead(
                                f"👁 **SHADOW PREVIEW** chat=`{chat_id}` sender={sender_name}\n"
                                f"Rejim: `{decision.effective_mode}` ({decision.reason})\n"
                                f"📥 User: {(event.message.text or '')[:300]}\n"
                                f"🤖 Bot draft: {final_text[:500]}"
                            )
                        except Exception as notify_ex:
                            logger.warning(
                                f"[AUTO_GATE] shadow notify failed: {notify_ex}"
                            )
                    try:
                        await msg_controller.db.log_message(
                            sender.id, final_text, is_ai=True
                        )
                    except Exception as log_ex:
                        logger.error(
                            f"[USERBOT] Failed to log AI reply (shadow): {log_ex}"
                        )
                    logger.info(f"[USERBOT] Shadow preview queued for chat {chat_id}")
                else:
                    # Live send (decision.action == 'send') — oldin rate-limit tekshirish
                    # Shaxsiy yozishmalar (DM) da hech qachon avtomatik javob yuborilmaydi
                    if event.is_private:
                        logger.info(
                            f"[USERBOT] Private DM autoreply blocked for chat {chat_id} ({sender_name})"
                        )
                    else:
                        limited, rl_reason = safe_responder.is_rate_limited(chat_id)
                        if limited:
                            logger.warning(
                                f"[USERBOT] Rate-limit skip chat={chat_id} reason={rl_reason}"
                            )
                            if admin_bot:
                                try:
                                    await admin_bot.notify_lead(
                                        f"⏱ **RATE-LIMIT skip** chat=`{chat_id}` reason=`{rl_reason}`\n"
                                        f"Matn tayyor edi, yuborilmadi (flood oldini olish)."
                                    )
                                except Exception:
                                    pass
                        else:
                            await event.respond(final_text)
                            try:
                                await msg_controller.db.log_message(
                                    sender.id, final_text, is_ai=True
                                )
                            except Exception as log_ex:
                                logger.error(f"[USERBOT] Failed to log AI reply: {log_ex}")
                            safe_responder.update_rate_limit(chat_id)
                            logger.info(f"[USERBOT] Replied successfully to {chat_id}")

    except Exception as e:
        logger.error(f"[USERBOT] Error while handling message: {e}")


async def sync_single_lead(event):
    """Single leadni avtomatik tahlil qilish va qo'shish."""
    # Shunchaki LeadScraper dagi markaziy logikadan foydalanamiz
    # Bu qayta ishlanganligini bazada tekshiradi va marklaydi
    if not event.message.text:
        return

    # Biz scraper metodini bitta xabar uchun ishlatamiz
    # Lekin iter_messages o'rniga to'g'ridan-to'g'ri parse qilamiz
    try:
        data = await lead_scraper.parse_intro_with_ai(event.message.text)

        # RELEVANCE FILTER
        if not data or not data.get("is_relevant"):
            reason = data.get("relevance_reason") if data else "AI Xatosi"
            logger.info(f"🚫 [SKIP] Relevant emas: {reason}")
            lead_scraper._mark_processed(
                event.id, TN5_GROUP_ID, status="irrelevant", reason=reason
            )
            return

        if data and data.get("phone"):
            phones = data.get("phone")
            if isinstance(phones, str):
                phones = [
                    p.strip()
                    for p in phones.replace(",", " ").replace("/", " ").split()
                    if p.strip()
                ]

            primary_phone = phones[0] if phones else None
            if not primary_phone:
                lead_scraper._mark_processed(
                    event.id, TN5_GROUP_ID, status="skipped", reason="No phone"
                )
                return

            sender = await event.get_sender()
            first_name = data.get("first_name")
            if not first_name or first_name.lower() == "unknown":
                first_name = getattr(sender, "first_name", None) or getattr(
                    sender, "username", "Unknown"
                )

            last_name = data.get("last_name") or getattr(sender, "last_name", "")

            # Unified naming
            full_name = lead_scraper.format_contact_name(
                first_name, last_name, is_tn5=True
            )
            bio = f"Biznes: {data.get('business', 'Noʻmalum')}\nEhtiyoj: {data.get('needs', 'Noʻmalum')}\n\n[AUTO-SYNCED]"

            # 1. Save to Google Contacts
            await msg_controller.google.save_contact(full_name, phones, notes=bio)

            # 2. Save to AmoCRM (Enterprise Automation)
            try:
                crm_sync = await msg_controller.crm.sync_lead(
                    user_id=event.sender_id,
                    name=full_name,
                    phone=primary_phone,
                    note=bio,
                )
                if crm_sync.get("success"):
                    logger.info(f"[ENTERPRISE] AmoCRM Lead created: {full_name}")
                else:
                    logger.warning(
                        f"[ENTERPRISE] AmoCRM Sync Error: {crm_sync.get('error')}"
                    )
            except Exception as amo_ex:
                logger.warning(f"[ENTERPRISE] AmoCRM Sync Error: {amo_ex}")

            # 3. Save to Telegram
            try:
                from telethon import functions

                await client(
                    functions.contacts.AddContactRequest(
                        id=event.sender_id,
                        first_name=full_name,  # Entire name in first_name for better visibility
                        last_name="",
                        phone=primary_phone,
                        add_phone_privacy_exception=True,
                    )
                )
            except Exception as e:
                logger.warning(f"TG Add Error: {e}")

            lead_scraper._mark_processed(event.id, TN5_GROUP_ID, status="synced")
            logger.info(f"✅ [ENTERPRISE SYNC OK] {full_name} avtomatik qo'shildi!")
    except Exception as e:
        logger.error(f"❌ [ENTERPRISE SYNC ERROR] {e}")


async def run_health_check_api() -> None:
    """Run the FastAPI health check server for Cloud Run compatibility.

    Handles port conflicts gracefully by logging warnings instead of crashing.
    """
    try:
        from src.api_server import app as api_app
    except ImportError:
        logger.error(
            "[API] Could not import api_app. Health check server will not start."
        )
        return

    config_uvicorn = uvicorn.Config(
        api_app,
        host="0.0.0.0",  # nosec
        port=int(os.environ.get("PORT", 8080)),
        log_level="info",
    )
    global _health_api_server
    server = uvicorn.Server(config_uvicorn)
    _health_api_server = server
    try:
        await server.serve()
    except SystemExit:
        logger.warning(
            "[API] Uvicorn port band (yoki server conflict). API server skip qilindi, bot davom etadi."
        )
    except OSError as e:
        logger.warning(f"[API] API server ishga tushmadi: {e}. Bot davom etadi.")
    finally:
        if _health_api_server is server:
            _health_api_server = None


async def stop_health_check_api(
    api_task: Optional[asyncio.Task], timeout_seconds: float = 5.0
) -> None:
    """Ask Uvicorn to finish its lifespan before the event loop is closed."""
    global _health_api_server
    server = _health_api_server
    if server is not None:
        server.should_exit = True

    if api_task is not None and not api_task.done():
        try:
            await asyncio.wait_for(
                asyncio.shield(api_task),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning("[SHUTDOWN] API server exceeded shutdown deadline; forcing.")
            api_task.cancel()
            await asyncio.gather(api_task, return_exceptions=True)

    _health_api_server = None


async def safe_ai_call(
    client,
    prompt,
    system_instruction=None,
    model=None,
    mime_type=None,
    retries=3,
):
    """Surrogate for safe_ai_call providing backward compatibility for old imports."""
    from src.utils.ai_utils import safe_ai_call as _actual_call

    return await _actual_call(
        client, prompt, system_instruction, model, mime_type, retries
    )


async def run_autonomous_advice(chat_id, sender_name, message_text):
    """Background worker to provide strategic advice without blocking regular message handling."""
    global advisor_agent, client
    if not _env_enabled("ENABLE_SHADOW_ADVISOR"):
        return
    if not advisor_agent or not client:
        return

    try:
        # History for context (optimized limit for autonomous mode)
        messages = []
        async for msg in client.iter_messages(chat_id, limit=7):
            s_name = "Mijoz" if msg.incoming else "Siz (Baxtiyor)"
            messages.append(f"[{s_name}]: {msg.text or ''}")

        history_context = "\n".join(reversed(messages))

        advice = await advisor_agent.analyze_and_advise(
            chat_id=chat_id,
            message_text=message_text,
            history_context=history_context,
            sender_name=sender_name,
        )

        if advice and await advisor_agent.should_notify(chat_id, 0, advice):
            header = f"👸 **Oisha-OS Strategik Maslahati** (Suhbat: {sender_name})\n\n"
            await client.send_message("me", header + advice)

            if "[" in advice and "]" in advice:
                await action_parser.parse_and_execute(
                    reply_text=advice,
                    sender_id=chat_id,
                    sender_name=sender_name,
                    username="yoq",
                    saved_phone=None,
                    context={"chat_id": "me"},
                    is_business=False,
                )

        # [SELF-LEARNING] Extract lessons from this conversation
        if evolution_scheduler and history_context:
            await evolution_scheduler.on_conversation_end(
                conversation=history_context,
                client_type="lead",
                outcome="advice_given" if advice else "no_action",
                manager_name=sender_name,
                chat_id=chat_id,
            )
    except Exception as e:
        logger.error(f"[ADVISOR] Background advice error: {e}")


async def shadow_advisor_handler(event):
    """Event-driven shadow advisor for real-time monitoring."""
    if not _env_enabled("ENABLE_SHADOW_ADVISOR"):
        return
    if _should_block_private_userbot_reply(event):
        logger.info("[ADVISOR] Personal DM ignored by policy chat=%s", event.chat_id)
        return
    if event.out or not event.is_private or not event.message.text:
        return

    sender = await event.get_sender()
    if getattr(sender, "bot", False):
        logger.info(
            f"[ADVISOR] Bot chat ignored: {getattr(sender, 'id', event.chat_id)}"
        )
        return

    sender_name = getattr(sender, "first_name", "User")
    await run_autonomous_advice(event.chat_id, sender_name, event.message.text)


_crm_audit_running = False


async def self_command_handler(event):
    """Handle commands from the owner in 'Saved Messages'."""
    if not event.message.text:
        return
    cmd = event.message.text.lower().strip()

    if cmd.startswith("/dashboard"):
        stats = await msg_controller.db.get_today_stats()
        msg = (
            "📊 **OISHA ROI DASHBOARD**\n"
            f"📅 Bugun: {datetime.now().strftime('%d-%m-%Y')}\n\n"
            f"👤 **Yangi lidlar:** {stats['leads_found']} ta\n"
            f"💬 **Sinxron chatlar:** {stats['messages_synced']} ta\n"
            f"👥 **Kontaktlar (Mass):** {stats['contacts_added']} ta\n"
            f"🤝 **DM Lidar:** {stats['private_chats']} ta\n\n"
            "✅ *Oisha hozirda fonda muvaffaqiyatli ishlamoqda.*"
        )
        await event.respond(msg)
    elif cmd.startswith("/lead_cockpit") or cmd.startswith("/pipeline"):
        from src.services.core.lead_operating_system import LeadOperatingSystem
        lead_os = LeadOperatingSystem(msg_controller, msg_controller.db)
        report = await lead_os.render_cockpit_report(limit=12, lookback_hours=72)
        await event.respond(report, parse_mode="HTML")
    elif cmd.startswith("/status"):
        await event.respond("🟢 **Oisha Engine:** Active\n🛰 **Server:** GCP Cloud Run")
    elif cmd.startswith("/report"):
        await event.respond("⏳ Oisha-OS: Kunlik hisobot (Reportagram) tayyorlanmoqda...")
        try:
            from src.services.core.crm_daily_report import CRMDailyReporter
            amocrm_client = None
            if msg_controller and getattr(msg_controller, "crm", None):
                amocrm_client = getattr(msg_controller.crm, "amocrm", None)
            if not amocrm_client:
                amocrm_client = get_surgical_integration().amocrm
            
            reporter = CRMDailyReporter(amocrm=amocrm_client)
            stats = await reporter.fetch_stats()
            prev = reporter._load_prev_stats()
            report_text = reporter.format_report(stats, prev)
            await event.respond(report_text)
        except Exception as e:
            await event.respond(f"❌ Xatolik yuz berdi: {e}")
    elif cmd.startswith("/stats"):
        await event.respond("⏳ Joriy statistika olinmoqda...")
        try:
            from src.services.core.crm_daily_report import CRMDailyReporter
            amocrm_client = None
            if msg_controller and getattr(msg_controller, "crm", None):
                amocrm_client = getattr(msg_controller.crm, "amocrm", None)
            if not amocrm_client:
                amocrm_client = get_surgical_integration().amocrm
            
            reporter = CRMDailyReporter(amocrm=amocrm_client)
            stats = await reporter.fetch_stats()
            text = (
                f"📊 **Bugungi holat ({stats.date_label})**\n"
                f"Tushgan: {stats.total_leads} lead\n"
                f"Gaplashilgan: {stats.contacted} lead\n"
                f"Sifatli: {stats.qualified} lead\n"
                f"Muvaffaqiyatli (Won): {stats.won}\n"
                f"Daromad: ${stats.revenue:,.0f}\n"
                f"Pipeline qiymati: ${stats.pipeline_value:,.0f}"
            )
            await event.respond(text)
        except Exception as e:
            await event.respond(f"❌ Xatolik: {e}")
    elif cmd.startswith("/history"):
        try:
            from src.services.core.crm_daily_report import CRMDailyReporter
            reporter = CRMDailyReporter(amocrm=None)
            history = reporter.get_history(7)
            if not history:
                await event.respond("📅 Tarix topilmadi. Hisobotlar hali keshga yozilmagan.")
                return
            lines = ["📅 **So'nggi 7 kunlik hisobotlar tarixi:**"]
            for s in history:
                lines.append(
                    f"• {s.date_label}: {s.total_leads} lead | {s.won} won | ${s.revenue:,.0f}"
                )
            await event.respond("\n".join(lines))
        except Exception as e:
            await event.respond(f"❌ Xatolik: {e}")
    elif cmd.startswith("/junk_audit"):
        if msg_controller and msg_controller.enterprise_reporter:
            await event.respond(
                "🧹 **CRM Audit boshlandi...**\nOisha 'bekorchi' sdelkalarni qidirmoqda. Iltimos, kuting... ⏳"
            )
            try:
                report = await msg_controller.enterprise_reporter.get_junk_leads_report(
                    limit=250
                )
                # Split report if too long
                if len(report) > 4000:
                    for chunk in [
                        report[i : i + 4000] for i in range(0, len(report), 4000)
                    ]:
                        await event.respond(chunk)
                else:
                    await event.respond(report)
            except Exception as e:
                logger.error(f"[COMMAND] /junk_audit error: {e}", exc_info=True)
                await event.respond(f"❌ **Auditda xato:** {str(e)}")
        else:
            await event.respond("❌ **Xato:** EnterpriseReporter topilmadi.")
    elif cmd.startswith("/stagnant"):
        if msg_controller and msg_controller.enterprise_reporter:
            await event.respond("🔍 **Stagnatsiya tahlili boshlandi...**")
            try:
                alert = (
                    await msg_controller.enterprise_reporter.get_stagnant_leads_alert()
                )
                if alert:
                    await event.respond(alert)
                else:
                    await event.respond(
                        "✅ **Hammasi joyida:** Hozircha 24 soatdan oshgan stagnant lidlar yo'q."
                    )
            except Exception as e:
                logger.error(f"[COMMAND] /stagnant error: {e}", exc_info=True)
                await event.respond(f"❌ **Xato:** {str(e)}")
        else:
            await event.respond("❌ **Xato:** EnterpriseReporter topilmadi.")
    elif cmd.startswith("/calendar_scan"):
        if not meeting_scheduler:
            await event.respond("❌ Calendar scanner hali ishga tushmagan.")
            return
        await event.respond("📅 Telegram chatlardan uchrashuvlarni qidiryapman...")
        try:
            result = await meeting_scheduler.scan_recent_dialogs(
                client,
                dialog_limit=_negotiation_int("CALENDAR_SCAN_DIALOG_LIMIT", 80),
                message_limit=_negotiation_int("CALENDAR_SCAN_MESSAGE_LIMIT", 12),
                max_age_hours=_negotiation_int("CALENDAR_SCAN_MAX_AGE_HOURS", 72),
            )
            await event.respond(
                "📅 Calendar scan yakunlandi:\n"
                f"Tekshirildi: {result.get('scanned', 0)} chat\n"
                f"Yaratildi: {result.get('created', 0)} uchrashuv\n"
                f"Eski/noaniq o'tkazildi: {result.get('skipped_old', 0)}\n"
                f"Xato: {result.get('errors', 0)}"
            )
        except Exception as exc:
            logger.error(f"[COMMAND] /calendar_scan error: {exc}", exc_info=True)
            await event.respond(f"❌ Calendar scan xatosi: {type(exc).__name__}")
    elif cmd.startswith("/sync_cases") or cmd.startswith("/sync_portfolio"):
        parts = cmd.split()
        limit_val = 30
        if len(parts) > 1 and parts[1].isdigit():
            limit_val = int(parts[1])
            
        await event.respond(
            f"🚀 **Backlog portfolio sinxronizatsiyasi boshlandi...**\n"
            f"`@{settings.JONBRANDING_CHANNEL}` kanalidan so'nggi {limit_val} ta xabarni tekshirib, portfolio keyslarini aniqlayman va CMS'ga yuklayman. Iltimos, kuting... ⏳"
        )
        try:
            from src.services.core.case_publisher import CasePublisher
            publisher = CasePublisher(client=event.client)
            
            target = settings.JONBRANDING_CHANNEL.strip().lower()
            
            scanned = 0
            published = 0
            skipped = 0
            
            async for msg in event.client.iter_messages(target, limit=limit_val):
                scanned += 1
                if not msg.text:
                    skipped += 1
                    continue

                try:
                    success = await publisher.process_message(msg)
                    if success:
                        published += 1
                    else:
                        skipped += 1
                except Exception as pe:
                    logger.error(f"[CRAWL COMMAND] Error processing message {msg.id}: {pe}")
                    skipped += 1

                # Safe delay
                await asyncio.sleep(2.5)
                
            await event.respond(
                f"🏁 **Portfolio keys sinxronizatsiyasi muvaffaqiyatli yakunlandi!**\n\n"
                f"📊 **Statistika:**\n"
                f"• Skanner qilindi: {scanned} ta xabar\n"
                f"• Yuklandi (CMS): {published} ta keys\n"
                f"• O'tkazib yuborildi: {skipped} ta xabar"
            )
        except Exception as e:
            logger.error(f"[COMMAND] /sync_cases error: {e}", exc_info=True)
            await event.respond(f"❌ **Sinxronizatsiyada xatolik:** {str(e)}")
    elif cmd.startswith("/sync_archive"):
        parts = cmd.split()
        limit = 30
        if len(parts) > 1:
            try:
                limit = int(parts[1])
            except ValueError:
                pass

        await event.respond(f"🧹 **AmoCRM limitsizlantirish va arxivlash boshlandi...**\nBatch limiti: {limit} ta bitim. Iltimos, kuting... ⏳")
        try:
            from src.services.core.crm_archiver import CRMArchiver
            archiver = CRMArchiver()
            await archiver.init_tables()

            # 1. Fetch all stagnant leads
            stagnant = await archiver.get_stagnant_leads(max_stagnant_days=21)
            if not stagnant:
                await event.respond("✅ **Hammasi joyida:** Hozircha arxivlash uchun stagnant bitimlar mavjud emas.")
                return

            targets = stagnant[:limit]
            await event.respond(f"🎯 **Arxivlash uchun {len(targets)} ta bitim tanlandi.** Arxivlash va outreach xabarlar generatsiya qilinmoqda...")

            processed_count = 0
            failed_count = 0

            for lead in targets:
                try:
                    res = await archiver.archive_lead(lead, dry_run=False)
                    if res.get("success"):
                        processed_count += 1
                    else:
                        failed_count += 1
                except Exception as ex:
                    failed_count += 1
                    logger.error(f"[SYNC ARCHIVE] Lead {lead.get('id')} error: {ex}")

            # Send rich Uzbek KPI report of reclaimed capacity
            active_leads = await archiver.fetch_all_active_leads()
            active_count = len(active_leads)

            report = (
                f"🏁 **ARXIVLASH VA OUTREACH HISOBOTI**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ **Muvaffaqiyatli arxivlandi:** {processed_count} ta bitim\n"
                f"❌ **Xatoliklar:** {failed_count} ta\n"
                f"📦 **Qolgan faol bitimlar:** {active_count} / 500 limit\n"
                f"📊 **Yangi bandlik darajasi:** {(active_count / 500) * 100:.1f}%\n"
                f"💡 *Barcha arxivlangan bitimlar Turso Cloud bazasiga 100% xavfsiz saqlandi va 3 bosqichli Uzbek outreach kampaniyalari generatsiya qilindi!*"
            )
            await event.respond(report)
        except Exception as e:
            logger.error(f"[COMMAND] /sync_archive error: {e}", exc_info=True)
            await event.respond(f"❌ **Arxivlashda xatolik yuz berdi:** {str(e)}")
    elif cmd.startswith("/contacts_audit"):
        global _crm_audit_running
        if _crm_audit_running:
            await event.respond("⚠️ **Audit allaqachon fonda ishlamoqda!**\nHisobot olish uchun `/contacts_report` yozing.")
            return

        parts = cmd.split()
        limit_val = 500
        force_val = False
        if len(parts) > 1:
            for part in parts[1:]:
                if part.isdigit():
                    limit_val = int(part)
                elif part.lower() == "force":
                    force_val = True

        await event.respond(
            f"🔍 **AmoCRM Kontaktlar Auditi boshlandi...**\n"
            f"🎯 Maqsad: {limit_val} ta bitimni tahlil qilish (force={force_val}).\n"
            f"Fonda ishlamoqda, tugagandan so'ng xabar beraman. Progressni ko'rish: `/contacts_report` ⏳"
        )

        async def run_audit_task():
            global _crm_audit_running
            _crm_audit_running = True
            try:
                amocrm_client = None
                if msg_controller and getattr(msg_controller, "crm", None):
                    amocrm_client = getattr(msg_controller.crm, "amocrm", None)
                if not amocrm_client:
                    amocrm_client = get_surgical_integration().amocrm

                db_instance = msg_controller.db
                tg_client = client

                from src.services.core.crm_contacts_auditor import CRMContactsAuditor
                auditor = CRMContactsAuditor(
                    amocrm=amocrm_client,
                    db=db_instance,
                    tg_client=tg_client,
                )

                async def progress_cb(current, total, stats):
                    cats_str = "\n".join(
                        f"• {k}: {v} ta" for k, v in stats["categories"].items()
                    )
                    progress_msg = (
                        f"📈 **CRM Audit Progress ({current}/{total})**\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"Tahlil qilindi: {stats['processed']} ta\n"
                        f"O'tkavib yuborildi (avval qilingan): {stats['skipped']} ta\n\n"
                        f"**Toifalar bo'yicha:**\n{cats_str}"
                    )
                    try:
                        await event.respond(progress_msg)
                    except Exception as err:
                        logger.error(f"[AUDITOR CALLBACK] Failed to send progress: {err}")

                stats = await auditor.run_audit(
                    limit=limit_val, progress_callback=progress_cb, force=force_val
                )

                cats_str = "\n".join(
                    f"• {k}: {v} ta" for k, v in stats["categories"].items()
                )
                final_msg = (
                    f"🏁 **CRM AUDIT YAKUNLANDI!**\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"Jami tekshirildi: {stats['total_leads']} ta bitim\n"
                    f"Tahlil qilindi: {stats['processed']} ta\n"
                    f"O'tkazib yuborildi: {stats['skipped']} ta\n\n"
                    f"**Toifalar bo'yicha yakuniy natijalar:**\n{cats_str}\n\n"
                    f"💡 *Batafsil hisobot matnini olish uchun `/contacts_report` deb yozing.*"
                )
                await event.respond(final_msg)

            except Exception as e:
                logger.error(f"[AUDITOR TASK] Failed: {e}", exc_info=True)
                try:
                    await event.respond(f"❌ **Audit jarayonida xatolik yuz berdi:** {str(e)}")
                except Exception:
                    pass
            finally:
                _crm_audit_running = False

        asyncio.create_task(run_audit_task())
    elif cmd.startswith("/contacts_report"):
        await event.respond("📊 **Audit hisoboti tayyorlanmoqda...**")
        try:
            import inspect
            async def _local_maybe_await(value):
                if inspect.isawaitable(value):
                    return await value
                return value

            db_instance = msg_controller.db
            conn = await db_instance.get_connection()
            
            # Ensure table exists
            await _local_maybe_await(
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS crm_contacts_audit (
                        lead_id INTEGER PRIMARY KEY,
                        lead_name TEXT,
                        contact_id INTEGER,
                        contact_name TEXT,
                        phone TEXT,
                        username TEXT,
                        telegram_user_id INTEGER,
                        call_summary TEXT,
                        telegram_history TEXT,
                        category TEXT,
                        explanation TEXT,
                        audited_at TEXT
                    )
                    """
                )
            )
            await _local_maybe_await(conn.commit())
            
            cursor = await _local_maybe_await(conn.execute("SELECT COUNT(*), category FROM crm_contacts_audit GROUP BY category"))
            rows = await _local_maybe_await(cursor.fetchall())
            
            total_audited = 0
            cats = {
                "Mijoz": 0,
                "Shaxsiy": 0,
                "Kandidat": 0,
                "Hamkor/Jamoa": 0,
                "Boshqa": 0
            }
            for count, cat in rows:
                if cat in cats:
                    cats[cat] = count
                total_audited += count

            if total_audited == 0:
                await event.respond("📊 **Hozircha audit natijalari mavjud emas.**\nAuditni boshlash uchun `/contacts_audit` yozing.")
                return

            cursor = await _local_maybe_await(conn.execute(
                "SELECT lead_id, contact_name, category, phone, username FROM crm_contacts_audit ORDER BY audited_at DESC LIMIT 5"
            ))
            latest_rows = await _local_maybe_await(cursor.fetchall())
            latest_lines = []
            for lid, name, cat, phone, username in latest_rows:
                tg_info = f" (@{username})" if username else ""
                phone_info = f" ({phone})" if phone else ""
                latest_lines.append(f"• [ID {lid}] {name}{phone_info}{tg_info} ➔ **{cat}**")
            
            latest_str = "\n".join(latest_lines) if latest_lines else "Topilmadi"

            report = (
                f"📊 **CRM KONTAKTLAR AUDITI HISOBOTI**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"Jami audit qilingan: {total_audited} ta kontakt\n\n"
                f"**Toifalar bo'yicha taqsimot:**\n"
                f"• Mijoz: {cats['Mijoz']} ta ({(cats['Mijoz']/total_audited)*100:.1f}%)\n"
                f"• Shaxsiy: {cats['Shaxsiy']} ta ({(cats['Shaxsiy']/total_audited)*100:.1f}%)\n"
                f"• Kandidat: {cats['Kandidat']} ta ({(cats['Kandidat']/total_audited)*100:.1f}%)\n"
                f"• Hamkor/Jamoa: {cats['Hamkor/Jamoa']} ta ({(cats['Hamkor/Jamoa']/total_audited)*100:.1f}%)\n"
                f"• Boshqa: {cats['Boshqa']} ta ({(cats['Boshqa']/total_audited)*100:.1f}%)\n\n"
                f"**So'nggi tahlil qilingan 5 ta kontakt:**\n{latest_str}\n\n"
                f"💡 *Jarayonni qaytadan boshlash uchun `/contacts_reset` yozishingiz mumkin.*"
            )
            await event.respond(report)
        except Exception as e:
            logger.error(f"[COMMAND] /contacts_report error: {e}", exc_info=True)
            await event.respond(f"❌ **Hisobot tayyorlashda xato:** {str(e)}")
    elif cmd.startswith("/contacts_reset"):
        await event.respond("⏳ **Audit ma'lumotlari tozalanmoqda...**")
        try:
            import inspect
            async def _local_maybe_await(value):
                if inspect.isawaitable(value):
                    return await value
                return value

            db_instance = msg_controller.db
            conn = await db_instance.get_connection()
            
            # Ensure table exists
            await _local_maybe_await(
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS crm_contacts_audit (
                        lead_id INTEGER PRIMARY KEY,
                        lead_name TEXT,
                        contact_id INTEGER,
                        contact_name TEXT,
                        phone TEXT,
                        username TEXT,
                        telegram_user_id INTEGER,
                        call_summary TEXT,
                        telegram_history TEXT,
                        category TEXT,
                        explanation TEXT,
                        audited_at TEXT
                    )
                    """
                )
            )
            await _local_maybe_await(conn.commit())
            
            await _local_maybe_await(conn.execute("DELETE FROM crm_contacts_audit"))
            await _local_maybe_await(conn.commit())
            await event.respond("✅ **Audit ma'lumotlari muvaffaqiyatli tozalandi!**\nEndi `/contacts_audit` orqali yangi audit boshlashingiz mumkin.")
        except Exception as e:
            logger.error(f"[COMMAND] /contacts_reset error: {e}", exc_info=True)
            await event.respond(f"❌ **Tozalashda xatolik yuz berdi:** {str(e)}")

    # ── ERP KOMANDALAR ─────────────────────────────────────────────────────
    elif cmd.startswith("/erp") or cmd.startswith("/moliya") or cmd.startswith("/jamoa") \
            or cmd.startswith("/loyihalar") or cmd.startswith("/loyiha_qosh") \
            or cmd.startswith("/xarajat"):
        try:
            from src.services.core.finance.erp_handlers import (
                cmd_erp_holat, cmd_moliya, cmd_jamoa, cmd_loyihalar,
                cmd_erp_salomatlik, cmd_qo_shish_loyiha, cmd_xarajat_qosh,
                ERP_HELP_TEXT,
            )
            db = msg_controller.db

            if cmd.startswith("/erp_holat"):
                await cmd_erp_holat(event, db)
            elif cmd.startswith("/erp_salomatlik"):
                await cmd_erp_salomatlik(event, db)
            elif cmd.startswith("/moliya"):
                parts = cmd.split()
                period = parts[1] if len(parts) > 1 else None
                await cmd_moliya(event, db, period)
            elif cmd.startswith("/jamoa"):
                parts = cmd.split()
                period = parts[1] if len(parts) > 1 else None
                await cmd_jamoa(event, db, period)
            elif cmd.startswith("/loyiha_qosh"):
                # /loyiha_qosh Sarlavha | Mijoz | 5000000 | 2025-07-01
                args = cmd[len("/loyiha_qosh"):].strip().split("|")
                if len(args) >= 4:
                    try:
                        budget = int(args[2].strip())
                    except ValueError:
                        await event.respond("❌ Byudjet raqam bo'lishi kerak. Namuna: /loyiha_qosh Sarlavha | Mijoz | 5000000 | 2025-07-01")
                        return
                    await cmd_qo_shish_loyiha(event, db, args[0].strip(), args[1].strip(),
                                              budget, args[3].strip())
                else:
                    await event.respond("❌ Format: /loyiha_qosh Sarlavha | Mijoz | Byudjet | Muddat")
            elif cmd.startswith("/xarajat"):
                # /xarajat kategoriya | tavsif | miqdor
                args = cmd[len("/xarajat"):].strip().split("|")
                if len(args) >= 3:
                    try:
                        amount = int(args[2].strip())
                    except ValueError:
                        await event.respond("❌ Miqdor raqam bo'lishi kerak. Namuna: /xarajat ofis | Printer qog'oz | 150000")
                        return
                    await cmd_xarajat_qosh(event, db, args[0].strip(), args[1].strip(), amount)
                else:
                    await event.respond("❌ Format: /xarajat kategoriya | tavsif | miqdor")
            elif cmd.startswith("/loyihalar"):
                await cmd_loyihalar(event, db)
            elif cmd == "/erp_help":
                await event.respond(ERP_HELP_TEXT, parse_mode="markdown")
            elif cmd.startswith("/erp"):
                await cmd_erp_holat(event, db)
        except Exception as e:
            logger.error(f"[ERP COMMAND] {cmd} error: {e}", exc_info=True)
            await event.respond(f"❌ ERP xatolik: {e}")

    # ── TAHLIL KOMANDA ─────────────────────────────────────────────────────
    elif cmd.startswith("/tahlil"):
        await event.respond("⏳ So'nggi qo'ng'iroqlar tahlil qilinmoqda...")
        try:
            from src.services.core.call_analyzer import CallAnalyzer
            from src.services.core.crm_note_approval import CRMNoteApprovalService
            parts = cmd.split()
            limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 3
            analyzer = CallAnalyzer(
                amocrm=msg_controller.crm.amocrm,
                db=msg_controller.db,
            )
            owner_id = getattr(settings, "OWNER_ID", None)
            if owner_id:
                analyzer.approval_service = CRMNoteApprovalService(
                    amocrm_client=msg_controller.crm.amocrm,
                    owner_telegram_id=int(owner_id),
                    bot_client=bot_client,
                )
            result = await analyzer.analyze_recent_calls(limit=limit, write=True)
            if isinstance(result, dict):
                analyzed = result.get("calls_processed", 0)
                total = result.get("leads_scanned", 0)
                await event.respond(
                    f"✅ {analyzed}/{total} qo'ng'iroq tahlil qilindi.\n"
                    f"Tasdiqlash so'rovlari yuborildi — ✅ yoki ✏️ bosing."
                )
            else:
                await event.respond(f"✅ Tahlil tugadi: {result}")
        except Exception as e:
            logger.error(f"[COMMAND] /tahlil error: {e}", exc_info=True)
            await event.respond(f"❌ Tahlil xatoligi: {e}")


async def activity_monitor_handler(event):
    """Log outgoing activities for auditing."""
    if not _env_enabled("ENABLE_ACTIVITY_MONITOR"):
        return
    if activity_monitor:
        await activity_monitor.log_event(event)


async def crm_note_callback_handler(event):
    """CRM note tasdiqlash/tahrirlash inline tugmalari uchun callback handler."""
    try:
        data = event.data.decode("utf-8") if isinstance(event.data, bytes) else event.data
        if not (data.startswith("crm_approve:") or data.startswith("crm_edit:")):
            return
        from src.services.core.crm_note_approval import handle_callback
        await handle_callback(data, event)
    except Exception as e:
        logger.error(f"[CRM_CALLBACK] Xatolik: {e}", exc_info=True)


async def crm_edit_text_handler(event):
    """Captures follow-up text message after user clicked ✏️ Tahrirlash."""
    try:
        from src.services.core.crm_note_approval import pop_pending_edit, handle_callback
        approve_key = pop_pending_edit(event.sender_id)
        if not approve_key:
            return
        # Don't consume bot commands as note text — restore edit state and pass through
        if event.raw_text and event.raw_text.startswith("/"):
            from src.services.core.crm_note_approval import push_pending_edit
            push_pending_edit(event.sender_id, approve_key)
            return
        edit_key = approve_key.replace("crm_approve:", "crm_edit:", 1)
        ok = await handle_callback(edit_key, event, new_text=event.raw_text)
        if ok:
            raise events.StopPropagation
    except events.StopPropagation:
        raise
    except Exception as e:
        logger.error(f"[CRM_EDIT] Xatolik: {e}", exc_info=True)


async def meeting_scheduler_handler(event):
    """Create Google Calendar events from clear Telegram meeting agreements."""
    if not meeting_scheduler:
        return
    try:
        await meeting_scheduler.process_event(event, client)
    except Exception as exc:
        logger.warning(f"[MEETING] Scheduler skipped: {type(exc).__name__}: {exc}")


def _negotiation_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


async def case_publisher_handler(event):
    """Listen to @jonbranding channel messages and process/publish design cases."""
    if not settings.ENABLE_CASE_PUBLISHER:
        return

    try:
        chat = await event.get_chat()
        chat_username = getattr(chat, "username", None)
        chat_id = event.chat_id

        target = settings.JONBRANDING_CHANNEL.strip().lower()

        is_match = False
        if chat_username and chat_username.lower() == target:
            is_match = True
        elif target.startswith("-100") and str(chat_id) == target:
            is_match = True
        elif str(chat_id) == target:
            is_match = True

        if not is_match:
            return

        logger.info(
            f"[CASE_HANDLER] New message in target channel '{target}': msg_id={event.id}"
        )

        publisher = CasePublisher(client=event.client)
        asyncio.create_task(publisher.process_message(event.message))

    except Exception as e:
        logger.error(f"[CASE_HANDLER] Error in handler: {e}")


async def negotiation_agent_handler(event):
    """Safe autonomous negotiation for allowed Telegram messages."""
    if not _env_enabled("ENABLE_AI_NEGOTIATION"):
        return
    if _should_block_private_userbot_reply(event):
        logger.info(
            "[NEGOTIATION] Personal DM ignored by policy chat=%s", event.chat_id
        )
        return
    if event.out or not event.is_private or not getattr(event.message, "text", None):
        return

    message_date = getattr(event.message, "date", None)
    max_age = _negotiation_int("NEGOTIATION_MAX_MESSAGE_AGE_SECS", 600)
    if message_date and time.time() - message_date.timestamp() > max_age:
        return

    sender = await event.get_sender()
    if getattr(sender, "bot", False):
        return
    if safe_responder and await safe_responder.is_team_member(
        event.sender_id, getattr(sender, "username", None)
    ):
        return
    if await _is_personal_folder_sender(sender):
        logger.info(f"[NEGOTIATION] Personal/family folder skip chat={event.chat_id}")
        return

    text = (event.message.text or "").strip()
    if not text or text.startswith("/"):
        return
    non_customer_reason = detect_non_customer_context(text)
    if non_customer_reason:
        logger.info(
            f"[NEGOTIATION] Non-customer context skip chat={event.chat_id} reason={non_customer_reason}"
        )
        return

    chat_id = event.chat_id
    db = msg_controller.db
    last_msg_key = f"negotiation:last_msg:{chat_id}"
    if str(await db.get_state(last_msg_key, "")) == str(event.id):
        return
    await db.set_state(last_msg_key, event.id)

    reply_delay = _negotiation_int("NEGOTIATION_REPLY_DELAY_SECS", 8)
    if reply_delay > 0:
        await asyncio.sleep(reply_delay)
        latest = await client.get_messages(chat_id, limit=1)
        if latest and latest[0].id != event.id:
            return

    now = time.time()
    cooldown = _negotiation_int("NEGOTIATION_COOLDOWN_SECS", 120)
    last_reply_key = f"negotiation:last_reply_at:{chat_id}"
    try:
        last_reply_at = float(await db.get_state(last_reply_key, "0") or 0)
    except (TypeError, ValueError):
        last_reply_at = 0.0
    if now - last_reply_at < cooldown:
        logger.info(f"[NEGOTIATION] Cooldown skip chat={chat_id}")
        return

    day = time.strftime("%Y-%m-%d", time.localtime(now))
    daily_key = f"negotiation:daily_count:{chat_id}:{day}"
    try:
        daily_count = int(await db.get_state(daily_key, "0") or 0)
    except (TypeError, ValueError):
        daily_count = 0
    daily_limit = _negotiation_int("NEGOTIATION_DAILY_LIMIT", 25)
    if daily_count >= daily_limit:
        logger.info(f"[NEGOTIATION] Daily limit skip chat={chat_id}")
        return

    sender_name = getattr(sender, "first_name", "Mijoz")
    username = getattr(sender, "username", None)

    sender_profile = {"id": sender.id, "first_name": sender_name, "username": username}
    try:
        known_customer = await db.is_crm_synced(sender.id)
    except Exception:
        known_customer = False

    lead_data = None
    try:
        lead_data = await auto_lead_agent.extract_lead_info(text, sender_profile)
    except Exception as exc:
        logger.warning(
            f"[NEGOTIATION] Lead classification failed chat={chat_id}: {type(exc).__name__}"
        )

    if not known_customer and not (lead_data and lead_data.get("is_lead")):
        intent = (lead_data or {}).get("intent_category", "NO_SIGNAL")
        logger.info(
            f"[NEGOTIATION] Non-customer/no-lead skip chat={chat_id} intent={intent}"
        )
        return

    try:
        await db.log_message(sender.id, text, is_ai=False)
    except Exception as exc:
        logger.debug(f"[NEGOTIATION] Incoming log skipped: {exc}")

    try:
        if (
            lead_data
            and lead_data.get("is_lead")
            and not await db.is_crm_synced(sender.id)
        ):
            phone = (
                lead_data.get("phone") or getattr(sender, "phone", None) or "Raqam yo'q"
            )
            await msg_controller.crm.sync_lead(
                user_id=sender.id,
                name=f"DM Lead: {sender_name}",
                phone=phone,
                note=f"AI negotiation intake\nIntent: {lead_data.get('intent_category')}\nEhtiyoj: {lead_data.get('needs')}\nTelegram: @{username or 'yoq'}",
            )
            await db.set_crm_synced(sender.id)
    except Exception as exc:
        logger.warning(
            f"[NEGOTIATION] CRM intake skipped chat={chat_id}: {type(exc).__name__}"
        )

    high_risk_terms = ("shikoyat", "qaytarish", "advokat", "sud", "aldadi", "firibgar")
    if any(term in text.lower() for term in high_risk_terms):
        final_text = (
            "Xabaringizni qabul qildim. Bu masalani e'tibor bilan ko'rib chiqish kerak, "
            "shuning uchun Baxtiyor akaga yetkazaman va sizga aniq javob bilan qaytamiz."
        )
    else:
        try:
            final_text = await msg_controller.get_response(
                user_id=sender.id,
                user_name=sender_name,
                message=text,
                context={
                    "source": "autonomous_negotiation",
                    "policy": "Be concise, warm, professional. Ask one clear next-step question. Do not overpromise discounts, deadlines, or legal guarantees.",
                    "telegram_username": username,
                },
            )
        except Exception as exc:
            logger.warning(
                f"[NEGOTIATION] AI response fallback chat={chat_id}: {type(exc).__name__}"
            )
            final_text = (
                "Assalomu alaykum! Xabaringizni oldim. Loyihangiz bo'yicha to'g'ri yo'naltirishim uchun "
                "faoliyatingiz, asosiy maqsadingiz va sizga qulay bog'lanish vaqtini yozib yuboring."
            )

    final_text = (final_text or "").strip()
    if not final_text:
        return
    if len(final_text) > 1200:
        final_text = final_text[:1190].rstrip() + "..."

    async with client.action(chat_id, "typing"):
        await asyncio.sleep(1)
    sent = await event.respond(final_text)
    await db.set_state(last_reply_key, int(now))
    await db.set_state(daily_key, daily_count + 1)
    await db.set_state(f"negotiation:last_sent_msg:{chat_id}", getattr(sent, "id", ""))
    try:
        await db.log_message(sender.id, final_text, is_ai=True)
    except Exception as exc:
        logger.debug(f"[NEGOTIATION] Outgoing log skipped: {exc}")
    logger.info(f"[NEGOTIATION] Replied chat={chat_id} msg={event.id}")


async def kirim_topic_handler(event):
    """Team guruhidagi Kirim topicda sotuvchi kirim e'lon qilsa tabriklaydi."""
    if not settings.TEAM_GROUP_ID or not settings.TOPIC_KIRIM_ID:
        return
    if event.chat_id != settings.TEAM_GROUP_ID:
        return
    if not _is_kirim_topic_message(event.message):
        return

    text = (getattr(event.message, "message", None) or getattr(event.message, "text", None) or "").strip()
    if not _looks_like_income_announcement(text):
        return

    sender = await event.get_sender()
    if getattr(sender, "bot", False):
        return

    db = msg_controller.db if msg_controller else None
    if not db:
        logger.warning("[KIRIM] DB unavailable; celebration skipped.")
        return

    state_key = _kirim_celebration_key(int(event.chat_id), int(event.id))
    if await db.get_state(state_key):
        return
    await db.set_state(state_key, "started")

    seller_name = _sender_display_name(sender)
    amount_label = _format_income_amount_for_celebration(_extract_income_amount(text))
    try:
        if advisor_agent:
            celebration = await advisor_agent.generate_sales_celebration(seller_name, amount_label)
        else:
            celebration = ""
    except Exception as exc:
        logger.warning(f"[KIRIM] AI celebration fallback: {type(exc).__name__}")
        celebration = ""

    if not celebration:
        celebration = (
            f"{seller_name}, tabriklaymiz!\n\n"
            f"Yangi kirim: {amount_label}.\n"
            "Zo'r natija. Mijoz ishonchini kelishuvga aylantirish oson ish emas. "
            "Shu tempni ushlab turamiz!"
        )
    elif seller_name not in celebration:
        celebration = f"{seller_name}, {celebration}"

    try:
        await _send_kirim_celebration(event, celebration)
        await db.set_state(state_key, "done")
        logger.info(f"[KIRIM] Celebration sent chat={event.chat_id} msg={event.id} seller={seller_name}")
    except Exception as exc:
        await db.set_state(state_key, f"failed:{type(exc).__name__}")
        logger.error(f"[KIRIM] Celebration send failed: {exc}", exc_info=True)


async def _send_kirim_celebration(event, celebration: str) -> None:
    """Prefer the bot head, then use the listening userbot when group access is absent."""
    if bot_client:
        try:
            await bot_client.send_message(
                settings.TEAM_GROUP_ID,
                celebration,
                reply_to=event.id,
                link_preview=False,
            )
            return
        except Exception as exc:
            logger.warning(
                "[KIRIM] Bot-token send failed (%s); using userbot reply fallback.",
                type(exc).__name__,
            )
    await event.reply(celebration, link_preview=False)


async def _brain_evolution_loop():
    """Runs OishaBrain.evolve() every 6 hours to self-diagnose agent failures."""
    await asyncio.sleep(300)  # 5-minute boot delay
    while True:
        try:
            if oisha_brain:
                result = await oisha_brain.evolve(task="routine_health_check")
                logger.info(
                    f"[BRAIN] Evolution cycle done: priority={result.get('priority')} "
                    f"component={result.get('affected_component')}"
                )
        except Exception as exc:
            logger.error(f"[BRAIN] Evolution loop error: {exc}")
        await asyncio.sleep(21600)  # 6 hours


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
