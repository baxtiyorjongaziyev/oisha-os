import asyncio
import base64
from datetime import datetime
import json
import os
import re
import sys

# Force UTF-8 console output on Windows to avoid emoji-related crashes.
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError) as e:
    # Non-critical: console encoding failure won't stop the bot
    print(f"[INIT] Warning: Could not reconfigure console encoding: {e}")

# [STABILITY] Windows loop policy configuration
if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# [STABILITY] Create and set loop EARLY to support library imports that check for a loop
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Set project root and source directories to sys.path for backward compatibility
# and to support current mixed-import structure.
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "src"))
sys.path.append(os.path.join(os.getcwd(), "src", "services"))

import logging
from typing import Optional, Dict, Any, List
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from src.settings import settings
from src.database import Database
from src.services.core.safe_responder import SafeResponder
from src.services.core.action_parser import ActionParser
from src.services.core.lead_scraper import LeadScraper
from src.services.core.enterprise_reporter import EnterpriseReporter
from src.controllers.message_controller import MessageController
from src.services.utils.scouter import Scouter
from src.services.core.advisor_agent import AdvisorAgent
from src.services.core.auto_lead_agent import AutoLeadAgent
from src.services.core.activity_monitor import ActivityMonitor
from src.services.core.audit_agent import AuditAgent
import threading
import src.config as config
from src.services.core.session_manager import SessionManager
from src.services.core.chat_bridge import ChatBridge
from src.api_server import app as api_app
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



# Global Managers
folder_manager: Optional[FolderManager] = None
voice_processor: Optional[VoiceProcessor] = None

# Loglarni sozlash
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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

# TN5 Group Config (env-configurable; fallback keeps legacy behavior)
TN5_GROUP_ID = settings.CRM_GROUP_ID if settings.CRM_GROUP_ID is not None else -1003820339529
TN5_TOPIC_ID = settings.CRM_TOPIC_ID if settings.CRM_TOPIC_ID is not None else 7  # Ishtirokchilar ma'lumotlari


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
                logger.warning(f"[AUTH] Could not disconnect invalid userbot session: {disconnect_exc}")
            try:
                import src.api_server as api_module
                api_module.update_api_status("degraded", "Userbot session delegated to another runtime")
                api_module.set_runtime_context(userbot_authorized=False)
            except (ImportError, AttributeError) as api_exc:
                logger.warning(f"[AUTH] Could not update API status: {api_exc}")
            return False
        raise

    if await telegram_client.is_user_authorized():
        return True

    # [GOD MODE] If not on Cloud Run, allow interactive login to regenerate session
    cloud_control_plane = bool(os.getenv("K_SERVICE"))
    if not cloud_control_plane:
        logger.info("[AUTH] Interactive auth allowed for local runtime. Please follow the prompts in your terminal.")
        await telegram_client.start()
        if await telegram_client.is_user_authorized():
            # Export session string for the user convenient copy-pasting
            new_string = telegram_client.session.save()
            print("\n" + "="*50)
            print("🚀 [SUCCESS] NEW SESSION STRING GENERATED:")
            print(new_string)
            print("="*50 + "\n")
            return True

    logger.error("[AUTH] Userbot session missing or unauthorized. Interactive auth is disabled in cloud runtime.")


def _income_state_key(message_id: int) -> str:
    return f"income_workflow:{message_id}"


def _income_gate_key(message_id: int) -> str:
    return f"income_workflow_gate:{message_id}"


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


async def _create_income_airtable_record(workflow: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
        "To'lov turi": _detect_payment_type(workflow.get("source_text", ""), workflow.get("is_first_payment", False)),
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
        await db.set_state(_income_gate_key(int(gate_message_id)), int(payload["original_message_id"]))


async def _load_income_workflow_state(db: Database, reply_message_id: Optional[int]) -> Optional[Dict[str, Any]]:
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
    reply_top_id = getattr(message, "reply_to_top_id", None) or getattr(reply_to, "reply_to_top_id", None)
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
    if not msg_controller: return
    try:
        contact = await msg_controller.crm.amocrm.get_contact_by_phone(phone)
        if contact:
            await msg_controller.crm.amocrm.add_contact_note(contact['id'], block_text)
            logger.info(f"[ENTERPRISE SYNC] Block pushed for {user_id}")
        else:
            logger.warning(f"[ENTERPRISE SYNC] Contact not found for {user_id} ({phone})")
    except Exception as e:
        logger.error(f"[ENTERPRISE SYNC ERROR] Push failed: {e}")

# Global Search State (Memory-based for simplicity)
last_deep_search_time = 0

async def global_phone_lookup(phone: str) -> Optional[Dict[str, Any]]:
    """Butun Telegramdan raqam orqali qidirib topish (Xavfsiz rejimda)."""
    # Raqamni tozalash
    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    if not clean_phone.startswith('998'): 
        # Agar O'zbekiston raqami bo'lsa va + bo'lmasa, qo'shib qo'yamiz
        if len(clean_phone) == 9: clean_phone = '998' + clean_phone

    try:
        # 1. Vaqtinchalik kontakt yaratish
        contact = types.InputPhoneContact(
            client_id=random.randrange(-2**63, 2**63),
            phone=clean_phone,
            first_name='Oisha Search',
            last_name=''
        )
        
        # 2. Import so'rovi
        result = await client(functions.contacts.ImportContactsRequest(contacts=[contact]))
        
        if result.users:
            user = result.users[0]
            user_data = {
                "user_id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name
            }
            
            # 3. Bazaga saqlab qo'yamiz (Keyingi safar tekin bo'lishi uchun)
            await msg_controller.db.upsert_user(
                user_id=user.id,
                first_name=user.first_name,
                username=user.username,
                phone=clean_phone,
                last_name=user.last_name
            )
            
            # 4. Kontaktni darhol o'chirib tashlaymiz
            try:
                await client(functions.contacts.DeleteContactsRequest(id=[user.id]))
            except:
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
        await client.send_message('me', message)
    except Exception as e:
        logger.error(f"[NOTIFY ERROR] {e}")

async def background_monitor_task() -> None:
    """Barcha korporativ monitoring vazifalarini fonda ishga tushirish (AmoCRM + Airtable).
    
    Runs indefinitely with 5-minute intervals between checks.
    Handles errors gracefully and continues operation.
    """
    from src.services.core.proactive_worker import (
        check_amocrm_stagnation,
        check_airtable_deadlines,
        send_overdue_nudges,
        check_airtable_stagnation,
        check_client_journey_excellence,
    )
    from src.services.core.lead_operating_system import LeadOperatingSystem
    from src.time_utils import get_local_now, is_quiet_hours
    
    logger.info("[MONITOR] Boshlandi (Interval: 5 daqiqa)")
    
    while True:
        try:
            now = get_local_now()

            if is_quiet_hours(now):
                logger.debug("[MONITOR] Quiet hours active. Automatic notifications are paused.")
                await asyncio.sleep(300)
                continue
            
            # 1. Stagnatsiya va Deadline tekshirish
            await check_amocrm_stagnation()
            await check_airtable_stagnation()
            await check_client_journey_excellence()
            await check_airtable_deadlines()

            if msg_controller:
                if not hasattr(background_monitor_task, "_lead_os"):
                    background_monitor_task._lead_os = LeadOperatingSystem(msg_controller, msg_controller.db)
                last_cycle_at = getattr(background_monitor_task, "_lead_cycle_at", None)
                if not last_cycle_at or (now - last_cycle_at).total_seconds() >= 900:
                    await background_monitor_task._lead_os.review_recent_active_leads(
                        limit=12,
                        lookback_hours=72,
                        execute_actions=True,
                    )
                    background_monitor_task._lead_cycle_at = now

                if now.hour in [10, 14, 18, 22] and now.minute == 0:
                    today_str = now.strftime('%Y-%m-%d')
                    job_key = f"lead_reengagement_{now.hour}_{today_str}"
                    if not hasattr(background_monitor_task, '_sent_jobs'):
                        background_monitor_task._sent_jobs = set()
                    if job_key not in background_monitor_task._sent_jobs:
                        await background_monitor_task._lead_os.run_reengagement_cycle(limit=8)
                        background_monitor_task._sent_jobs.add(job_key)

            # 3. Shaxsiy eslatmalar (17:00 da - faqat bir marta)
            if now.hour == 17 and now.minute == 0:
                # Bir marta yuborishni tekshirish
                today_str = now.strftime('%Y-%m-%d')

            # 3. Shaxsiy eslatmalar (17:00 da - faqat bir marta)
            if now.hour == 17 and now.minute == 0:
                # Bir marta yuborishni tekshirish
                today_str = now.strftime('%Y-%m-%d')
                job_key = f"overdue_nudges_{today_str}"
                if not hasattr(background_monitor_task, '_sent_jobs'):
                    background_monitor_task._sent_jobs = set()
                if job_key not in background_monitor_task._sent_jobs:
                    await send_overdue_nudges()
                    background_monitor_task._sent_jobs.add(job_key)

            # 4. Har 4 soatda "Hushyor" xabari (13:00, 17:00, 21:00 - faqat bir marta)
            if now.hour in [13, 17, 21] and now.minute == 0:
                # Bir marta yuborishni tekshirish
                today_str = now.strftime('%Y-%m-%d')
                job_key = f"status_notify_{now.hour}_{today_str}"
                if not hasattr(background_monitor_task, '_sent_jobs'):
                    background_monitor_task._sent_jobs = set()
                if job_key not in background_monitor_task._sent_jobs:
                    await notify_admin("👸 **Oisha OS: Tizim nazoratda**\nAmoCRM, Airtable va Lead-Scraper barqaror ishlamoqda.")
                    background_monitor_task._sent_jobs.add(job_key)

            # 5. [ALWAYS ONLINE] Keep-alive pulse
            if client:
                try:
                    await client(functions.account.UpdateStatusRequest(offline=False))
                    logger.debug("[HEARTBEAT] Account status set to ONLINE")
                except Exception as e:
                    logger.warning(f"[HEARTBEAT] Failed to update status: {e}")

            # Intervalni 5 daqiqaga tushirdik (300 soniya)
            await asyncio.sleep(300)
        except Exception as e:
            logger.error(f"[MONITOR ERROR] {e}")
            await asyncio.sleep(60)

async def self_command_handler(event):
    """'Saved Messages' dagi buyruqlarni (self-chat) va Baxtiyor akani o'z xabarlarini tahlil qilish."""
    if not event.message.text: return
    cmd = event.message.text.lower().strip()
    if cmd.startswith('/dashboard'):
        stats = await msg_controller.db.get_today_stats()
        msg = f"📊 **OISHA ROI DASHBOARD**\n📅 Bugun: {datetime.now().strftime('%d-%m-%Y')}\n\n👤 Yangi lidlar: {stats['leads_found']}\n💬 Sinxron: {stats['messages_synced']}\n"
        await event.respond(msg)
    elif cmd.startswith('/lead_cockpit') or cmd.startswith('/pipeline'):
        from src.services.core.lead_operating_system import LeadOperatingSystem

        lead_os = LeadOperatingSystem(msg_controller, msg_controller.db)
        report = await lead_os.render_cockpit_report(limit=12, lookback_hours=72)
        await event.respond(report, parse_mode="HTML")
    elif cmd.startswith('/status'):
        await event.respond("🟢 **TIZIM HOLATI:** Active (GCP Master)")

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
        _cp_msg = getattr(getattr(event, "message", None), "id", None) or getattr(event, "id", None)
        if _cp_chat and _cp_msg and msg_controller is not None:
            await msg_controller.db.update_chat_checkpoint(_cp_chat, _cp_msg)
    except Exception as _cp_exc:
        logger.debug(f"[CHECKPOINT] update skipped: {_cp_exc}")

    # 1. Spamdan himoya va Guruh filtrini tekshirish
    if not await safe_responder.should_respond(event):
        return
    
    # 1.5 Real-time Lead Sync (Automatic for TN5 Topic 7)
    if event.chat_id == TN5_GROUP_ID and getattr(event.message.reply_to, 'reply_to_msg_id', None) == TN5_TOPIC_ID:
        logger.info(f"[ENTERPRISE SYNC] New lead detected from Topic 7! MessageID: {event.id}")
        # Run sync in parallel using the unified LeadScraper logic
        asyncio.create_task(sync_single_lead(event))
        return 

    # 1.6 Admin Commands
    if event.is_private and event.message.text.startswith('/'):
        if event.message.text == '/sync_backlog':
            await event.respond("👸 Oisha-OS: O'tmishdagi (Backlog) xabarlarni skanerlashni boshladim... 👸🛡️")
            # Run backlog sync in background
            asyncio.create_task(lead_scraper.sync_topic_to_contacts(
                client=client, 
                group_id=TN5_GROUP_ID, 
                topic_id=TN5_TOPIC_ID,
                limit=50 # Enterprise backlog limit
            ))
            return
            
        if event.message.text == '/force_sync_all':
            await event.respond("👸 Oisha-OS: Guruhning barcha a'zolarini ommaviy saqlash rejimini tasdiqladim!\nBu jarayon kunlab davom etishi mumkin. Orqa fonda (parallel) xavfsiz tezlikda saqlayman... 🐢🛡️")
            # Run mass sync in background
            asyncio.create_task(lead_scraper.sync_all_group_members(
                client=client, 
                group_id=TN5_GROUP_ID
            ))
            return
            
        if event.message.text == '/efficiency' or event.message.text == '/report':
            from src.services.core.airtable_sync import AirtableSync
            at_sync = AirtableSync()
            msg_controller.enterprise_reporter.airtable = at_sync
            
            report = await msg_controller.enterprise_reporter.get_team_efficiency_report()
            await event.respond(report, parse_mode='markdown')
            return
            
            from src.services.core.airtable_sync import AirtableSync
            at_sync = AirtableSync()
            projects = at_sync.get_projects()
            if not projects:
                await event.respond("👸 Oisha-OS: Hozircha aktiv loyihalar topilmadi. 🤷‍♀️")
                return
            
            text = "🏗 **Aktiv Loyihalar (Airtable):**\n\n"
            for p in projects[:10]:
                f = p.get('fields', {})
                stage = f.get('Stage', 'Nomalum')
                text += f"• {f.get('Project Name', 'Nomsiz')} — <b>{stage}</b>\n"
            await event.respond(text, parse_mode='html')
            return
            
        if event.message.text == '/audit':
            await event.respond("👸 Oisha-OS: Oxirgi harakatlaringizni tahlil qilyapman, bir oz kutib turing... 👸📈📊")
            report = await audit_agent.generate_audit_report(limit=100)
            await event.respond(report)
            return

        if event.message.text == '/audit_leads':
            await event.respond("👸 Oisha-OS: Oxirgi 100 ta dialogni audit qilyapman, shaffoflik hisoboti tayyor bo'lishi bilan yuboraman... 👸🛡️")
            
            audit_report = "👸 **Oisha-OS Lead Audit (Transparency Report)** 👸\n\n"
            async for dialog in client.iter_dialogs(limit=100):
                if not dialog.is_user or dialog.entity.bot: continue
                
                name = getattr(dialog.entity, 'first_name', 'User')
                # Check messages
                messages = []
                async for msg in client.iter_messages(dialog.id, limit=5):
                    if msg.text: messages.append(msg.text)
                
                if not messages: continue
                
                lead_data = await auto_lead_agent.extract_lead_info("\n".join(reversed(messages)), {"id": dialog.id, "first_name": name})
                
                if lead_data and lead_data.get("is_lead"):
                    audit_report += f"✅ **{name}** — Lead deb topildi. ({lead_data.get('business', 'Noʻmalum')})\n"
                else:
                    audit_report += f"❌ **{name}** — Shaxsiy/Irrelevant deb topildi.\n"
                
                if len(audit_report) > 3500: # Telegram message limit
                    await event.respond(audit_report)
                    audit_report = ""
            
            if audit_report:
                await event.respond(audit_report)
            return

        if event.message.text.startswith('/find '):
            phone = event.message.text.split(' ', 1)[1].strip()
            await event.respond(f"🔍 **{phone}** raqamini butun Telegramdan qidiryapman... 👸🛡️")
            user_data = await global_phone_lookup(phone)
            if user_data:
                username = f"@{user_data['username']}" if user_data['username'] else "Mavjud emas"
                response = (
                    f"✅ **Foydalanuvchi topildi!**\n\n"
                    f"👤 **Ism:** {user_data['first_name']} {user_data['last_name'] or ''}\n"
                    f"🆔 **ID:** `{user_data['user_id']}`\n"
                    f"🔗 **Username:** {username}\n"
                    f"📱 **Raqam:** `{phone}`"
                )
                await event.respond(response)
            else:
                await event.respond("❌ **Afsus, foydalanuvchi topilmadi.**\n(Ehtimol, foydalanuvchi o'z maxfiylik sozlamalarida raqam orqali qidiruvni cheklagan bo'lishi mumkin).")
            return

        if event.message.text == '/sync_today':
            await event.respond("👸 Oisha-OS: Kecha va bugungi shaxsiy suhbatlarni (DM) skanerlashni boshladim... 👸🛡️")
            # Run retro sync in background
            asyncio.create_task(lead_scraper.sync_private_dialogs(
                client=client, 
                limit=100
            ))
            return

            if event.message.text == '/sync_history':
                await event.respond("👸 Oisha-OS: O'tgan 1 yillik shaxsiy yozishmalarni (DM) bazaga kiritishni boshladim... 👸🛡️\nBu biroz vaqt olishi mumkin, orqa fonda xavfsiz ishlayman.")
                sync_service = HistoricalSyncService(msg_controller.db, client)
                asyncio.create_task(sync_service.start_backlog_sync(days=365))
                return
    
    # 2. Xabar matnini olish
    message_text = event.message.message
    chat_id = event.chat_id
    sender = await event.get_sender()
    sender_name = getattr(sender, 'first_name', 'User')

    logger.info(f"[USERBOT] Processing message from {sender_name} in {chat_id}: {message_text[:50]}...")

    if event.is_private and not event.out and message_text:
        try:
            await msg_controller.db.log_message(sender.id, message_text, is_ai=False)
            
            # [AUTONOMOUS ADVISOR] Real-time Analysis
            asyncio.create_task(run_autonomous_advice(chat_id, sender_name, message_text))
            
        except Exception as log_ex:
            logger.error(f"[USERBOT] Failed to log incoming message: {log_ex}")

    # 3. New Message Logic (Elite Intake)
    if event.is_private and not event.out and not getattr(sender, 'bot', False):
        # Skanerlash (1.1, 1.2) - Now includes intent categorization
        lead_data = await auto_lead_agent.extract_lead_info(message_text, {"id": sender.id, "first_name": sender_name})
        
        if lead_data:
            intent = lead_data.get("intent_category", "POTENTIAL")
            # [GOD MODE] Auto-Assign Folder
            if folder_manager:
                asyncio.create_task(folder_manager.assign_to_folder(sender.id, intent))
            
            if lead_data.get("is_lead") and not await msg_controller.db.is_crm_synced(event.sender_id):
                logger.info(f"[ELITE INTAKE] Yangi lid aniqlandi: {sender_name} (Intent: {intent})")
                
                # Intent -> O'zbek label
                intent_label_map = {
                    "HOT_LEAD":   "🔥 Qaynoq mijoz",
                    "WARM_LEAD":  "♨️ Issiq mijoz",
                    "POTENTIAL":  "🌱 Potensial mijoz",
                }
                intent_label = intent_label_map.get(intent, f"🔵 {intent}")

                # [GOD MODE] Save intent and data to DB
                await msg_controller.db.upsert_user(
                    sender.id, 
                    sender_name, 
                    username=getattr(sender, 'username', None), 
                    intent=intent,
                    region=lead_data.get('city'),
                    business_type=lead_data.get('activity'),
                    brand_name=lead_data.get('brand_name'),
                )
                
                # [GOD MODE] Smart Draft Suggestion (Using refined method)
                if intent == 'HOT_LEAD' and admin_bot:
                    draft_prompt = (
                        f"Mijoz: {sender_name}\n"
                        f"Xabar: {event.message.text}\n\n"
                        "Baxtiyor aka nomidan ushbu mijozga do'stona, lekin professional javob loyihasini tayyorlang. "
                        "Unga yordam berishga tayyorligimizni va loyihasini o'rganib chiqishimizni ayting."
                    )
                    draft = await msg_controller.db.analyze_text_with_ai(draft_prompt)
                    await admin_bot.send_draft_for_approval(sender.id, sender_name, draft)

                # AmoCRM-da yaratish (1.3)
                # [TELETHON PHONE EXTRACTION] Try to get phone from sender or fetch full user info
                phone = lead_data.get('phone')
                if not phone and sender:
                    # First try direct attribute
                    phone = getattr(sender, 'phone', None)
                    
                    # If no phone and we have bot_client, try fetching full user entity
                    if not phone and bot_client:
                        try:
                            full_user = await bot_client.get_entity(sender.id)
                            phone = getattr(full_user, 'phone', None)
                            if phone:
                                logger.info(f"📞 [PHONE] Telethon orqali raqam olindi: {sender.id}")
                        except Exception as e:
                            logger.debug(f"[PHONE] Telethon get_entity xato: {e}")
                
                if not phone:
                    phone = "Raqam yo'q"
                
                # [USERNAME EXTRACTION] Try to get username from sender or fetch full user info
                username = getattr(sender, 'username', None)
                if not username and sender and bot_client:
                    # If no username and we have bot_client, try fetching full user entity
                    try:
                        # Re-use full_user if already fetched for phone
                        if 'full_user' not in locals():
                            full_user = await bot_client.get_entity(sender.id)
                        username = getattr(full_user, 'username', None)
                        if username:
                            logger.info(f"[USERNAME] Telethon orqali username olindi: @{username}")
                    except Exception as e:
                        logger.debug(f"[USERNAME] Telethon get_entity xato: {e}")
                
                if not username:
                    username = "Username yo'q"
                
                username_str = f"@{username}" if username != "Username yo'q" else username
                crm_sync = await msg_controller.crm.sync_lead(
                    user_id=sender.id,
                    name=f"DM Lead: {sender_name}",
                    phone=phone,
                    note=f"AI Tahlil: {lead_data.get('needs')}\nIntent: {intent}\nUser: {username_str}"
                )
                if crm_sync.get("success"):
                    await msg_controller.db.set_crm_synced(event.sender_id)
                
                # Elite Welcome (1.4)
                await welcome_manager.send_welcome(event.sender_id)
                
                # Admin-ni ogohlantirish
                sync_line = "✅ AmoCRM-ga saqlandi." if crm_sync.get("success") else f"⚠️ CRM sync xato: {crm_sync.get('error', 'nomaʼlum')}"
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
                if intent == 'HOT_LEAD' and bot_client and TN5_GROUP_ID:
                    try:
                        await bot_client.send_message(
                            TN5_GROUP_ID,
                            lead_notify_text,
                            parse_mode="md"
                        )
                        logger.info(f"[HOT LEAD] CRM guruhiga yuborildi: {sender_name}")
                    except Exception as crm_notif_err:
                        logger.warning(f"[HOT LEAD] CRM guruh notif xato: {crm_notif_err}")


    # [GOD MODE] Multi-Modal (Voice Note) Handling
    if event.is_private and not event.out and event.message.voice and voice_processor:
        logger.info(f"🎙️ [VOICE] New voice from {sender_name}...")
        try:
            temp_path = f"temp_voice_{event.id}.ogg"
            await client.download_media(event.message, file=temp_path)
            
            # AI Transcription
            result = await voice_processor.transcribe(temp_path)
            if result:
                # Notify Admin
                if admin_bot:
                    await admin_bot.notify_lead(f"🎙️ **Ovozli xabar ({sender_name}):**\n\n{result}")
                
                # Update AmoCRM Note if lead
                if await msg_controller.db.is_crm_synced(event.sender_id):
                    # We don't have lead ID here, but create_lead with same phone should handle it or just notify.
                    # For now, notification to Admin is the primary 'God Mode' feature.
                    pass
            
            # Cleanup
            asyncio.create_task(voice_processor.cleanup(temp_path))
        except Exception as e:
            logger.error(f"[VOICE] Integration error: {e}")

    # [GOD MODE] Media/Document Sync
    if event.is_private and not event.out and (event.message.photo or event.message.document):
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
                        await admin_bot.notify_lead(f"📁 **Yangi {type_str} ({sender_name}):**\n🔗 [Google Drive Link]({drive_link})")
                    
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
            is_mentioned = (me_username and f"@{me_username}" in text_low) or "oisha" in text_low

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
        
        # 4. AI orqali javob tayyorlash (Gemini 2.0 Flash)
        ai_raw_response = await msg_controller.get_response(
            user_id=sender.id,
            user_name=sender_name,
            message=message_text,
            context={
                'chat_id': chat_id, 
                'is_group': not event.is_private,
                'dosye': dosye
            }
        )

        if ai_raw_response:
            # 5. Harakatlarni bajarish (Action Parsing)
            final_text = await action_parser.parse_and_execute(
                reply_text=ai_raw_response,
                sender_id=sender.id,
                sender_name=sender_name,
                username=getattr(sender, 'username', 'yoq'),
                saved_phone=None,
                context=None,
                is_business=False
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
                            logger.warning(f"[AUTO_GATE] shadow notify failed: {notify_ex}")
                    try:
                        await msg_controller.db.log_message(sender.id, final_text, is_ai=True)
                    except Exception as log_ex:
                        logger.error(f"[USERBOT] Failed to log AI reply (shadow): {log_ex}")
                    logger.info(f"[USERBOT] Shadow preview queued for chat {chat_id}")
                else:
                    # Live send (decision.action == 'send') — oldin rate-limit tekshirish
                    limited, rl_reason = safe_responder.is_rate_limited(chat_id)
                    if limited:
                        logger.warning(f"[USERBOT] Rate-limit skip chat={chat_id} reason={rl_reason}")
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
                            await msg_controller.db.log_message(sender.id, final_text, is_ai=True)
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
    if not event.message.text: return
    
    # Biz scraper metodini bitta xabar uchun ishlatamiz
    # Lekin iter_messages o'rniga to'g'ridan-to'g'ri parse qilamiz
    try:
        data = await lead_scraper.parse_intro_with_ai(event.message.text)
        
        # RELEVANCE FILTER
        if not data or not data.get('is_relevant'):
            reason = data.get('relevance_reason') if data else 'AI Xatosi'
            logger.info(f"🚫 [SKIP] Relevant emas: {reason}")
            lead_scraper._mark_processed(event.id, TN5_GROUP_ID, status='irrelevant', reason=reason)
            return

        if data and data.get('phone'):
            phones = data.get('phone')
            if isinstance(phones, str):
                phones = [p.strip() for p in phones.replace(',', ' ').replace('/', ' ').split() if p.strip()]
            
            primary_phone = phones[0] if phones else None
            if not primary_phone:
                lead_scraper._mark_processed(event.id, TN5_GROUP_ID, status='skipped', reason='No phone')
                return

            sender = await event.get_sender()
            first_name = data.get('first_name')
            if not first_name or first_name.lower() == 'unknown':
                first_name = getattr(sender, 'first_name', None) or getattr(sender, 'username', 'Unknown')
            
            last_name = data.get('last_name') or getattr(sender, 'last_name', '')
            
            # Unified naming
            full_name = lead_scraper.format_contact_name(first_name, last_name, is_tn5=True)
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
                    logger.warning(f"[ENTERPRISE] AmoCRM Sync Error: {crm_sync.get('error')}")
            except Exception as amo_ex:
                logger.warning(f"[ENTERPRISE] AmoCRM Sync Error: {amo_ex}")
            
            # 3. Save to Telegram
            try:
                from telethon import functions
                await client(functions.contacts.AddContactRequest(
                    id=event.sender_id,
                    first_name=full_name, # Entire name in first_name for better visibility
                    last_name="",
                    phone=primary_phone,
                    add_phone_privacy_exception=True
                ))
            except Exception as e:
                logger.warning(f"TG Add Error: {e}")
            
            lead_scraper._mark_processed(event.id, TN5_GROUP_ID, status='synced')
            logger.info(f"✅ [ENTERPRISE SYNC OK] {full_name} avtomatik qo'shildi!")
    except Exception as e:
        logger.error(f"❌ [ENTERPRISE SYNC ERROR] {e}")

async def run_health_check_api() -> None:
    """Run the FastAPI health check server for Cloud Run compatibility.
    
    Handles port conflicts gracefully by logging warnings instead of crashing.
    """
    config_uvicorn = uvicorn.Config(api_app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), log_level="info")
    server = uvicorn.Server(config_uvicorn)
    try:
        await server.serve()
    except SystemExit:
        logger.warning("[API] Uvicorn port band (yoki server conflict). API server skip qilindi, bot davom etadi.")
    except OSError as e:
        logger.warning(f"[API] API server ishga tushmadi: {e}. Bot davom etadi.")


async def safe_ai_call(client, prompt, system_instruction=None, model="gemini-2.0-flash", mime_type=None, retries=3):
    """Surrogate for safe_ai_call providing backward compatibility for old imports."""
    from src.utils.ai_utils import safe_ai_call as _actual_call
    return await _actual_call(client, prompt, system_instruction, model, mime_type, retries)

async def run_autonomous_advice(chat_id, sender_name, message_text):
    """Background worker to provide strategic advice without blocking regular message handling."""
    global advisor_agent, client
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
            sender_name=sender_name
        )

        if advice and await advisor_agent.should_notify(chat_id, 0, advice):
            header = f"👸 **Oisha-OS Strategik Maslahati** (Suhbat: {sender_name})\n\n"
            await client.send_message('me', header + advice)
            
            if "[" in advice and "]" in advice:
                 await action_parser.parse_and_execute(
                    reply_text=advice,
                    sender_id=chat_id,
                    sender_name=sender_name,
                    username="yoq",
                    saved_phone=None,
                    context={'chat_id': 'me'},
                    is_business=False
                  )
    except Exception as e:
        logger.error(f"[ADVISOR] Background advice error: {e}")

async def shadow_advisor_handler(event):
    """Event-driven shadow advisor for real-time monitoring."""
    if not event.is_private or not event.message.text:
        return
    
    sender = await event.get_sender()
    sender_name = getattr(sender, 'first_name', 'User')
    await run_autonomous_advice(event.chat_id, sender_name, event.message.text)

async def self_command_handler(event):
    """Handle commands from the owner in 'Saved Messages'."""
    if not event.message.text: return
    cmd = event.message.text.lower().strip()
    
    if cmd.startswith('/dashboard'):
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
    elif cmd.startswith('/status'):
        await event.respond("🟢 **Oisha Engine:** Active\n🛰 **Server:** GCP Cloud Run")

async def activity_monitor_handler(event):
    """Log outgoing activities for auditing."""
    if activity_monitor:
        await activity_monitor.log_event(event)

async def main():
    """Botlarni ishga tushirish (Userbot + Admin Bot)."""
    global msg_controller, client, bot_client, lead_scraper, action_parser
    from src.services.core.historical_sync import HistoricalSyncService
    global advisor_agent, auto_lead_agent, safe_responder, activity_monitor, audit_agent
    global workflow_manager, access_manager, admin_bot, session_manager, chat_bridge, BOT_TOKEN_STR, juma_notifier

    print("🚀 Oisha-OS Tizimi tayyorlanmoqda (Dual-Head Architecture)...")

    _restore_cloud_artifacts()
    
    # 1. Credentials, Foundations & Database
    api_keys = {
        "gemini": settings.GEMINI_API_KEY.get_secret_value(),
        "deepseek": settings.DEEPSEEK_API_KEY.get_secret_value() if settings.DEEPSEEK_API_KEY else None
    }
    
    # [AUDIT: RESTORATION] Centralized DB instance for global consistency
    db = Database()
    await db.init_instance()
    msg_controller = MessageController(api_keys=api_keys, db=db)
    
    cloud_control_plane = bool(os.getenv("K_SERVICE"))
    enable_cloud_userbot = os.getenv("ENABLE_CLOUD_USERBOT", "").strip().lower() in {"1", "true", "yes", "on"}
    force_control_plane_only = os.getenv("CLOUD_RUN_CONTROL_PLANE_ONLY", "").strip().lower() in {"1", "true", "yes", "on"}
    
    # [REANIMATION] Force-enable Telegram runtime on Cloud Run.
    # The 'Control-plane' delegation is currently breaking Oisha's autonomous polling.
    cloud_control_plane_only = False # force_control_plane_only or (cloud_control_plane and not enable_cloud_userbot)

    # [GOD MODE] Authorized Session Discovery
    session_string = os.environ.get("USERBOT_SESSION_STRING", "").strip()
    
    if session_string:
        logger.info("[AUTH] Using USERBOT_SESSION_STRING for authentication.")
        client = TelegramClient(
            StringSession(session_string),
            settings.API_ID,
            settings.API_HASH,
            device_model="Oisha Enterprise v2",
            system_version="Windows 11 Agent"
        )
    elif cloud_control_plane:
        # Fallback for cloud environments where StringSession might be preferred but empty initially
        logger.warning("[AUTH] Cloud environment detected but USERBOT_SESSION_STRING is empty. Attempting ephemeral session.")
        client = TelegramClient(
            StringSession(),
            settings.API_ID,
            settings.API_HASH,
            device_model="Oisha Enterprise Control Plane",
            system_version="Cloud Run"
        )
    else:
        # Final fallback to standard path, though we cleaned these up.
        # This allows the bot to prompt for login if run interactively.
        SESSION_PATH = 'data/oisha_user_active'
        logger.info(f"[AUTH] No session string found. Using file-based path: {SESSION_PATH}")
        client = TelegramClient(
            SESSION_PATH,
            settings.API_ID,
            settings.API_HASH,
            device_model="Oisha Enterprise v2",
            system_version="Windows 11 Agent"
        )
    
    # Head 2: Main Bot (Public interface and Admin Dashboard)
    # [PHASE 1.5] Use StringSession so Cloud Run ephemeral disk does not lose
    # bot DC cache on every revision rollover. BOT_SESSION_STRING env is
    # optional — if set (via GCP Secret Manager), Telethon reuses it; otherwise
    # a fresh in-memory session is created on each boot (bot tokens auto-auth,
    # so the only cost is a few seconds of extra DC handshake).
    BOT_TOKEN = settings.BOT_TOKEN.get_secret_value()
    _bot_session_string = os.environ.get("BOT_SESSION_STRING", "").strip()
    if _bot_session_string:
        logger.info("[AUTH] Reusing BOT_SESSION_STRING for bot-token head.")
        _bot_session = StringSession(_bot_session_string)
    else:
        logger.info("[AUTH] No BOT_SESSION_STRING — creating fresh StringSession for bot-token head.")
        _bot_session = StringSession()
    bot_client = TelegramClient(_bot_session, settings.API_ID, settings.API_HASH)
    BOT_TOKEN_STR = BOT_TOKEN
    juma_notifier = JumaNotifier(client=client, db=db)

    # 3. Services initialization (Safe inside loop)
    lead_scraper = LeadScraper(
        google_service=msg_controller.google, 
        db=msg_controller.db, 
        client=client,
        amocrm=msg_controller.crm.amocrm,
        message_controller=msg_controller
    )

    action_parser = ActionParser(
        db=msg_controller.db,
        gcontacts=msg_controller.google.contacts,
        gcalendar=msg_controller.google.calendar,
        invoicer=None,
        amocrm=msg_controller.crm.amocrm,
        config=config,
        lead_scraper=lead_scraper
    )

    advisor_agent = AdvisorAgent(api_key=api_keys["gemini"], db=msg_controller.db, action_parser=action_parser)
    auto_lead_agent = AutoLeadAgent(api_key=api_keys["gemini"])
    safe_responder = SafeResponder()
    
    from src.services.core.workflow_manager import WorkflowManager
    activity_monitor = ActivityMonitor(db=msg_controller.db)
    audit_agent = AuditAgent(api_key=api_keys["gemini"], db=msg_controller.db)
    
    workflow_manager = WorkflowManager(crm=msg_controller.crm.amocrm, db=msg_controller.db, client=client)
    access_manager = AccessManager(owner_id=config.OWNER_ID)
    logger.info(f"🚀 [INIT] OWNER_ID Config: {config.OWNER_ID}")
    logger.info(f"🚀 [INIT] Is 150074828 Owner?: {access_manager.get_role(150074828) == 'OWNER'}")
    
    # [ENTERPRISE: UI] Register AdminBot on the Bot Client.
    # This provides the dashboard to the user via the main bot.
    admin_bot = AdminBot(
        bot_client=bot_client, 
        user_client=client, 
        db=msg_controller.db, 
        msg_controller=msg_controller, 
        access_manager=access_manager,
        team_group_id=settings.TEAM_GROUP_ID
    )
    from src.services.utils.welcome_manager import WelcomeManager
    welcome_manager = WelcomeManager(client=client)
    
    lead_scraper.notify_callback = admin_bot.notify_lead

    from src.services.core.workflow_orchestrator import WorkflowOrchestrator
    orchestrator = WorkflowOrchestrator(
        amocrm=msg_controller.crm.amocrm,
        airtable=msg_controller.crm.airtable,
        notify_callback=admin_bot.notify_lead,
        team_group_id=settings.TEAM_GROUP_ID,
        advisor_agent=advisor_agent
    )
    
    session_manager = SessionManager(sync_callback=push_block_to_amocrm)
    chat_bridge = ChatBridge(amocrm_subdomain=config.AMOCRM_SUBDOMAIN, amocrm_token=msg_controller.crm.amocrm.access_token or "")

    # [WAZZUP KILLER] Bridge Telegram & DB to API Server for the AmoCRM Widget
    import src.api_server as api_module
    api_module.user_client = None
    api_module.db_instance = msg_controller.db
    api_module.set_runtime_context(
        service_name=os.getenv("K_SERVICE") or "oisha-main",
        canonical_entrypoint="src/main.py",
        state_backend=db.get_backend_name(),
        state_db_path=msg_controller.db.db_path,
        scheduler_mode="persistent",
        quiet_hours_enabled=True,
        userbot_authorized=None,
    )

    async def _heartbeat_task():
        while True:
            try:
                api_module.mark_heartbeat()
            except Exception as e:  # defensive - never crash the loop
                logger.debug(f"[HEARTBEAT] tick error: {e}")
            await asyncio.sleep(15)

    api_module.mark_heartbeat()
    asyncio.create_task(_heartbeat_task(), name="api_heartbeat")
    # [REANIMATION] Decouple health-check from startup sequence to ensure Cloud Run marks revision as healthy early.
    asyncio.create_task(run_health_check_api(), name="health_check_api")
    
    api_module.set_runtime_context(


    # Cloud Run is the health/API control-plane. The personal Telegram userbot
    # must run only on the VM, otherwise Telegram revokes the shared session.
    if cloud_control_plane_only:
        api_module.set_runtime_context(
            state_backend=db.get_backend_name(),
            state_db_path=msg_controller.db.db_path,
            scheduler_mode="control-plane",
            userbot_authorized=False,
        )
        api_module.update_api_status("online", "Control plane active; Telegram runtime delegated to VM")
        logger.info("[CLOUD] Control-plane mode active; Telegram runtime delegated to VM.")
        await asyncio.Event().wait()


    # 3. Userbotni (Shaxsiy akkaunt) ishga tushirish
    userbot_ready = await _connect_user_client(client)
    api_module.set_runtime_context(
        state_backend=db.get_backend_name(),
        state_db_path=msg_controller.db.db_path,
        userbot_authorized=userbot_ready,
    )
    if not userbot_ready:
        api_module.user_client = None
        if BOT_TOKEN_STR:
            try:
                await bot_client.start(bot_token=BOT_TOKEN_STR)
            except Exception as bot_exc:
                logger.error(f"[AUTH] Bot-token head startup failed in degraded mode: {bot_exc}")
                bot_client = None
        api_module.update_api_status("degraded", "Userbot features are disabled")
        logger.error("[AUTH] Runtime is alive for health checks, but userbot features are disabled.")
        await asyncio.Event().wait()

    api_module.user_client = client
    
    # [GOD MODE] Initialize Managers
    global folder_manager, voice_processor
    folder_manager = FolderManager(client)
    voice_processor = VoiceProcessor(api_key=settings.GEMINI_API_KEY.get_secret_value())
    
    # 4. Botni ishga tushirish
    if BOT_TOKEN_STR:
        try:
            await bot_client.start(bot_token=BOT_TOKEN_STR)
            # [PHASE 1.5] Persist bot session string hint so Owner can save it
            # as BOT_SESSION_STRING secret, eliminating re-handshake on deploy.
            if not _bot_session_string:
                try:
                    _dumped = bot_client.session.save()
                    if _dumped:
                        # Log length only — never log the full session string
                        # (it's an auth credential). Owner can retrieve via
                        # /bot_session_export admin command if needed.
                        logger.info(
                            f"[AUTH] Bot StringSession ready ({len(_dumped)} chars). "
                            "Owner: use /bot_session_export in admin bot to copy into "
                            "BOT_SESSION_STRING secret."
                        )
                except Exception as dump_exc:
                    logger.debug(f"[AUTH] Could not dump bot session: {dump_exc}")
        except Exception as bot_exc:
            logger.error(f"[AUTH] Bot-token head startup failed: {bot_exc}")
            bot_client = None
    api_module.update_api_status("online", "Canonical runtime active")

    # 5. Background Tasks
    asyncio.create_task(session_manager.monitor_sessions())
    asyncio.create_task(orchestrator.background_loop(interval_minutes=15))
    
    # [STABILITY] Registrating event handlers AFTER client initialization
    client.add_event_handler(handle_new_message, events.NewMessage)
    client.add_event_handler(self_command_handler, events.NewMessage(chats='me'))
    client.add_event_handler(shadow_advisor_handler, events.NewMessage(incoming=True))
    client.add_event_handler(shadow_advisor_handler, events.NewMessage(outgoing=True)) # Bi-directional Shadow Advisor
    client.add_event_handler(activity_monitor_handler, events.NewMessage(outgoing=True))
    
    # Register handlers for the Bot Token head
    if bot_client:
        bot_client.add_event_handler(handle_new_message, events.NewMessage)

    # [PHASE 1.6] Boot-time missed-messages catch-up.
    # Fire-and-forget: runs in background so we don't block startup of other
    # services. If catch-up takes longer than its internal 90s budget it will
    # self-terminate and the remaining tail will be picked up by the next
    # restart (at-least-once semantics, idempotent via chat_checkpoints).
    async def _run_catchup():
        try:
            from src.services.core.boot_catchup import catch_up_missed_messages
            stats = await catch_up_missed_messages(
                client=client,
                db=msg_controller.db,
                handle_new_message=handle_new_message,
            )
            if stats.get("messages"):
                logger.info(f"[BOOT] Catch-up replayed {stats['messages']} missed message(s) across {stats['chats']} chat(s).")
        except Exception as exc:
            logger.warning(f"[BOOT] Catch-up failed: {exc}")

    asyncio.create_task(_run_catchup())

    # [GOD MODE] User Presence Tracker (Nudge Alerts)
    @client.on(events.UserUpdate)
    async def presence_handler(event):
        if event.online:
            user_id = event.user_id
            # 1. Check if user is a HOT_LEAD
            user_info = await msg_controller.db.get_user_info(user_id)
            intent = user_info.get("intent") if user_info else None
            
            if intent == 'HOT_LEAD':
                # 2. Check if we need to nudge (last msg was from user and > 5 mins ago)
                logger.info(f"🔥 [NUDGE] Hot Lead online: {user_id}")
                # We could fetch last message from DB or TG
                # For high-performance, we notify the admin immediately
                if admin_bot:
                    name = (await client.get_entity(user_id)).first_name
                    await admin_bot.notify_lead(f"🔥 **HOT LEAD ONLINE!**\n👤 {name} hozir onlayn. Uni suhbatga tortishning ayni vaqti! 👸🛡️")

    # [STABILITY] Registrating event handlers AFTER client initialization
        if settings.TEAM_GROUP_ID:
            @bot_client.on(events.NewMessage(pattern='/team'))
            async def team_audit_handler(event):
                """Guruhda taniqlik a'zolarni ko'rsatish."""
                logger.info(f"👸 [TEAM AUDIT] Command from {event.chat_id}")
                from src.database import Database
                db = Database()
                async with await db.get_connection() as conn:
                    async with conn.execute(
                        "SELECT user_id, first_name, username, role FROM users WHERE role IS NOT NULL"
                    ) as cursor:
                        members = await cursor.fetchall()
                
                if not members:
                    await event.respond("👸 **Oisha:** Hozircha hech qanday xodimni tanimayapman. Ularga role biriktirish kerak.")
                    return
                
                msg = "👸 **Taniqlik xodimlarimiz:**\n\n"
                for mid, name, uname, role in members:
                    tag = f"@{uname}" if uname else f"<a href='tg://user?id={mid}'>{name}</a>"
                    msg += f"• {tag} — <i>{role}</i>\n"
                
                await event.respond(msg, parse_mode='html')
            
            @bot_client.on(events.NewMessage(pattern='/topic_info'))
            async def topic_info_handler(event):
                """Guruhdagi Topic ID raqamini aniqlash uchun."""
                chat_id = event.chat_id
                thread_id = event.message.reply_to_msg_id
                
                msg = (
                    f"👸 **Mavzu ma'lumotlari:**\n\n"
                    f"🔹 **Group ID:** `{chat_id}`\n"
                    f"🔸 **Topic ID (Thread):** `{thread_id or 'General (Asosiy)'}`\n\n"
                    f"💡 Ushbu Topic ID-ni `.env` faylida sozlash uchun foydalaning."
                )
                await event.respond(msg)
            
            @bot_client.on(events.NewMessage(pattern='/task'))
            async def task_command_handler(event):
                """Vazifani tahlil qilish va yaratish."""
                logger.info(f"👸 [TASK] Command from {event.chat_id}")
                # AI tahlilini PTB botga yoki ichki handlerga yo'naltirish
                # Hozircha oddiy tasdiq va AI Assistant orqali tahlilni boshlaymiz
                await event.respond("👸 **Oisha:** Vazifa qabul qilindi. AI assistant tahlil qilmoqda... 👸🛡️")
                
                # Import here to avoid circular imports
                from src.services.debug.userbot_legacy import task_command
                # Create a mock update/context if needed, or just run the logic
                # For simplicity, we assume the PTB bot in userbot_legacy is also running and will pick this up
                # If not, we could implement a unified handler here.

            @bot_client.on(events.NewMessage(pattern='/audit'))
            async def audit_command_handler(event):
                """Jamoa va loyihalarni real raqamlarda audit qilish."""
                sender = await event.get_sender()
                if getattr(sender, 'id', 0) != settings.OWNER_ID:
                    await event.respond("👸 **Oisha:** Bu maxfiy audit hisoboti faqat Baxtiyor aka uchun. 👸🛡️")
                    return
                
                logger.info(f"👸 [AUDIT] Running real performance audit for Owner...")
                await event.respond("👸 **Oisha:** Real raqamlarni yig'yapman, bir soniya... 👸🛡️")
                
                try:
                    audit_text = await msg_controller.enterprise_reporter.get_real_numbers_audit()
                    await event.respond(audit_text, parse_mode='markdown')
                except Exception as e:
                    logger.error(f"👸 [AUDIT ERROR] {e}")
                    await event.respond(f"👸 **Xatolik:** Hisobatni tayyorlashda muammo yuz berdi: {e}")

            @bot_client.on(events.NewMessage(chats=settings.TEAM_GROUP_ID))
            async def team_group_handler(event):
                sender = await event.get_sender()
                if getattr(sender, "bot", False):
                    return

                text = (event.raw_text or "").strip()
                normalized = text.lower()

                report_type = None
                if normalized.startswith(("plan:", "reja:", "#plan", "#reja")):
                    report_type = "morning_plan"
                elif normalized.startswith(("result:", "natija:", "#result", "#natija")):
                    report_type = "evening_result"

                if report_type:
                    await msg_controller.db.upsert_user(
                        sender.id,
                        first_name=getattr(sender, "first_name", "Xodim"),
                        username=getattr(sender, "username", None),
                    )
                    await msg_controller.db.save_team_report(
                        user_id=sender.id,
                        report_type=report_type,
                        content=text,
                    )
                    report_label = "PLAN" if report_type == "morning_plan" else "NATIJA"
                    await event.reply(f"✅ {report_label} qabul qilindi.")
                    return

                # Faqat mention bo'lganda yoki savol berilganda javob beramiz
                if event.mentioned:
                    logger.info(f"👸 [TEAM ASSISTANT] Mentioned in group {event.chat_id}")
                    # AdvisorAgent orqali aqlli javob tayyorlash
                    response = await advisor_agent.generate_advice(event.text)
                    await event.respond(f"👸 **Oisha Assistant:**\n\n{response}")
            
            # [NEW] Kirim (Inflow) Celebration Listener
            if settings.TOPIC_KIRIM_ID:
                @bot_client.on(events.NewMessage(chats=settings.TEAM_GROUP_ID))
                async def kirim_celebration_handler(event):
                    if not _is_kirim_topic_message(event.message):
                        return

                    sender = await event.get_sender()
                    if getattr(sender, "bot", False):
                        return

                    text = (event.raw_text or "").strip()
                    lowered = text.lower()
                    reply_to_id = getattr(event.message, "reply_to_msg_id", None)
                    workflow = await _load_income_workflow_state(db, reply_to_id)

                    if workflow:
                        finance_approver = workflow.get("finance_approver")
                        finance_user_id = (finance_approver or {}).get("user_id")
                        finance_mention = _format_person_mention(finance_approver, "finance")
                        sender_name = getattr(sender, "first_name", "Xodim")

                        if workflow.get("status") in {"confirmed", "rejected"}:
                            return

                        if _is_group_open_confirmation(text):
                            if not workflow.get("requires_client_group"):
                                await event.reply("ℹ️ Bu kirim uchun mijoz guruhi majburiy bosqich emas.")
                                return

                            workflow["client_group_confirmed"] = True
                            workflow["client_group_confirmed_by"] = sender.id
                            workflow["client_group_confirmation_text"] = text
                            workflow["status"] = "awaiting_finance"
                            await _save_income_workflow_state(db, workflow)
                            await event.reply(
                                f"✅ Mijoz bilan guruh ochilgani qayd qilindi. "
                                f"{finance_mention}, endi tushumni tekshirib <code>tasdiq</code> yoki <code>rad</code> deb yozing.",
                                parse_mode="html",
                            )
                            return

                        if _is_finance_rejection(text):
                            if sender.id != finance_user_id and sender.id != settings.OWNER_ID:
                                await event.reply(
                                    f"⚠️ Bu kirim bo‘yicha rad qarorini faqat {finance_mention} yoki owner bera oladi.",
                                    parse_mode="html",
                                )
                                return

                            workflow["status"] = "rejected"
                            workflow["finance_rejected_by"] = sender.id
                            workflow["finance_rejection_text"] = text
                            await _save_income_workflow_state(db, workflow)
                            await event.reply(
                                f"❌ Finance bu kirimni tasdiqlamadi. {sender_name} sababni yozib, qayta yuboring."
                            )
                            return

                        if _is_finance_approval(text):
                            if sender.id != finance_user_id and sender.id != settings.OWNER_ID:
                                await event.reply(
                                    f"⚠️ Bu kirimni faqat {finance_mention} yoki owner tasdiqlaydi.",
                                    parse_mode="html",
                                )
                                return

                            if workflow.get("requires_client_group") and not workflow.get("client_group_confirmed"):
                                await event.reply(
                                    "❗ Bu loyiha uchun birinchi kirim. Avval mijoz bilan guruh ochilganini tasdiqlang, keyin finance tasdiqlaydi."
                                )
                                return

                            if not workflow.get("project_id"):
                                await event.reply(
                                    "⚠️ Loyiha avtomatik aniqlanmadi. Kirimni Airtablega yozishdan oldin loyiha nomini aniq ko‘rsatib qayta yuboring."
                                )
                                return

                            record = await _create_income_airtable_record(workflow)
                            if not record:
                                await event.reply(
                                    "⚠️ Finance tasdig‘i olindi, lekin Airtablega yozishda xatolik chiqdi. Logni tekshiraman."
                                )
                                return

                            workflow["status"] = "confirmed"
                            workflow["finance_approved"] = True
                            workflow["finance_approved_by"] = sender.id
                            workflow["finance_approval_text"] = text
                            workflow["airtable_record_id"] = record.get("id")
                            await _save_income_workflow_state(db, workflow)

                            project_name = workflow.get("project_name") or "noma'lum loyiha"
                            await event.reply(
                                f"✅ Kirim finance tomonidan tasdiqlandi va Airtablega yozildi.\n"
                                f"📁 Loyiha: {project_name}\n"
                                f"🧾 Kirim ID: <code>{record.get('id', 'nomaʼlum')}</code>",
                                parse_mode="html",
                            )
                            return

                    is_inflow = re.search(r"\d+", text) and any(
                        kw in lowered for kw in ["$", "som", "so'm", "sum", "usd", "uzs", "kirim", "to'lov", "tulov"]
                    )
                    if not is_inflow:
                        return

                    sender_id = sender.id
                    if sender_id == settings.OWNER_ID:
                        logger.info(f"👸 [KIRIM] Owner ({sender_id}) reported inflow. Quietly logging.")
                        return

                    first_name = getattr(sender, "first_name", "Xodim")
                    amount_info = _extract_income_amount(text)
                    amount_str = amount_info.get("raw") or "noma'lum"
                    logger.info(f"👸 [KIRIM] Generating AI celebration for {first_name} for {amount_str}...")

                    try:
                        celebration_text = await advisor_agent.generate_sales_celebration(
                            manager_name=first_name,
                            amount=amount_str,
                        )
                    except Exception as e:
                        logger.error(f"👸 [CELEBRATION ERROR] AI failed: {e}")
                        celebration_text = (
                            f"🎉 <b>BARAKALLA, {first_name}!</b>\n\n"
                            "Sizni ajoyib natija bilan tabriklaymiz."
                        )

                    await event.reply(celebration_text, parse_mode="html")

                    project_match = await _find_project_for_income(text)
                    is_first_payment = False
                    if project_match and project_match.get("record_id"):
                        is_first_payment = (await _count_income_records_for_project(project_match["record_id"])) == 0

                    finance_approver = await _resolve_finance_approver(db)
                    finance_mention = _format_person_mention(finance_approver, "finance")
                    seller_mention = _format_person_mention(
                        {
                            "user_id": sender.id,
                            "name": first_name,
                            "username": getattr(sender, "username", None),
                        },
                        first_name,
                    )

                    workflow = {
                        "original_message_id": event.message.id,
                        "source_chat_id": event.chat_id,
                        "source_text": text,
                        "sender_id": sender.id,
                        "sender_name": first_name,
                        "sender_username": getattr(sender, "username", None),
                        "amount_raw": amount_info.get("raw"),
                        "amount_value": amount_info.get("value"),
                        "currency": amount_info.get("currency"),
                        "project_id": (project_match or {}).get("record_id"),
                        "project_name": (project_match or {}).get("project_name"),
                        "client_ids": (project_match or {}).get("client_ids") or [],
                        "seller_ids": (project_match or {}).get("seller_ids") or [],
                        "project_fields": (project_match or {}).get("project_fields") or {},
                        "is_first_payment": is_first_payment,
                        "requires_client_group": bool(is_first_payment and project_match),
                        "client_group_confirmed": False,
                        "finance_approver": finance_approver,
                        "status": "awaiting_client_group" if is_first_payment and project_match else "awaiting_finance",
                    }

                    instructions = []
                    if project_match:
                        instructions.append(f"📁 Loyiha: <b>{project_match['project_name']}</b>")
                    else:
                        instructions.append("⚠️ Loyiha avtomatik aniqlanmadi. Keyingi tasdiqdan oldin loyiha nomini aniq yozing.")

                    if workflow["requires_client_group"]:
                        instructions.append(
                            "🚪 Bu loyiha uchun <b>birinchi kirim</b>. Mijoz bilan alohida guruh ochilgani tasdiqlanmasdan finance bu kirimni yopmaydi."
                        )
                        instructions.append(
                            f"{seller_mention}, shu threadda <code>guruh ochildi</code> deb yozing yoki guruh linkini yuboring."
                        )
                        instructions.append(
                            f"{finance_mention}, guruh tasdig‘idan keyin <code>tasdiq</code> yoki <code>rad</code> deb yozing."
                        )
                    else:
                        instructions.append(
                            f"{finance_mention}, tushumni tekshirib shu threadda <code>tasdiq</code> yoki <code>rad</code> deb yozing."
                        )

                    gate_message = await event.reply(
                        "\n".join(instructions),
                        parse_mode="html",
                        link_preview=False,
                    )
                    workflow["gate_message_id"] = gate_message.id
                    await _save_income_workflow_state(db, workflow)

                    logger.info(
                        f"👸 [KIRIM] Workflow created for {first_name}; project={workflow.get('project_name')} "
                        f"first_payment={workflow.get('is_first_payment')}"
                    )
    
    print("✅ Userbot ulandi va xabarlarni eshita boshladi!")

    # 4. Admin Botni ishga tushirish (on bot_client)
    if admin_bot and bot_client:
        await admin_bot.start()
        print(f"✅ Oisha Admin Bot (Bot Token-da) faollashtirildi.")

    # [ENTERPRISE] Auto-run Mass Sync
    if getattr(settings, 'AUTORUN_MASS_SYNC', False):
        logger.info("[ENTERPRISE] 👸 Oisha-OS: 'Loyiha TN5' kontaktlarini ommaviy saqlash jarayoni boshlandi... 👸🛡️")
        asyncio.create_task(lead_scraper.sync_all_group_members(
            client=client, 
            group_id=TN5_GROUP_ID,
            limit=500
        ))

    # [ENTERPRISE] Background Monitor
    asyncio.create_task(background_monitor_task())
    
    # [GOD MODE] Periodic tasks (Juma, Maintenance)
    async def background_scheduler():
        while True:
            try:
                await juma_notifier.check_and_send()
            except Exception as e:
                logger.error(f"[SCHEDULER] Task Error: {e}")
            await asyncio.sleep(600) # Check every 10 mins
    
    asyncio.create_task(background_scheduler())
    
    # [ENTERPRISE] Periodic DM Lead Sync (Personal Account)
    async def dm_lead_sync_task():
        while True:
            try:
                logger.info("👸 [DM SYNC] Starting periodic private dialogs analysis...")
                await lead_scraper.sync_private_dialogs(client, limit=50)
            except Exception as e:
                logger.error(f"[DM SYNC ERROR] {e}")
            await asyncio.sleep(900) # Run every 15 mins
    
    asyncio.create_task(dm_lead_sync_task())

    # [PHASE 1.4] Graceful SIGTERM drain for Cloud Run revision rollover.
    # Cloud Run sends SIGTERM with a 30s grace period; we drain in-flight
    # handlers for up to 25s, then disconnect cleanly so the new revision
    # (already warm via min-instances=1) takes over with zero message loss.
    _shutdown_event = asyncio.Event()

    def _on_sigterm():
        logger.warning("[SHUTDOWN] SIGTERM received — beginning graceful drain.")
        _shutdown_event.set()

    import signal as _signal
    try:
        loop.add_signal_handler(_signal.SIGTERM, _on_sigterm)
        loop.add_signal_handler(_signal.SIGINT, _on_sigterm)
        logger.info("[SHUTDOWN] SIGTERM/SIGINT handlers installed.")
    except NotImplementedError:
        # Windows asyncio does not support add_signal_handler for these.
        logger.info("[SHUTDOWN] Signal handlers unavailable on this platform (Windows).")

    async def _graceful_drain():
        """Called once SIGTERM fires. Drains in-flight tasks, then disconnects."""
        drain_deadline = 25.0
        logger.info(f"[SHUTDOWN] Draining in-flight tasks for up to {drain_deadline}s...")
        current = asyncio.current_task()
        pending = [
            t for t in asyncio.all_tasks(loop=asyncio.get_running_loop())
            if t is not current and not t.done()
        ]
        # Filter out the long-lived background loops (heartbeat, scheduler, etc.)
        # — we only want to wait for message-handler tasks. Heuristic: tasks
        # whose coroutine is not one of our known daemon coroutines.
        daemon_names = {
            "_heartbeat_task", "background_scheduler", "dm_lead_sync_task",
            "background_monitor_task", "background_loop", "monitor_sessions",
            "background_crm_audit_task",
        }
        drainable = []
        for t in pending:
            coro = getattr(t, "get_coro", lambda: None)()
            name = getattr(coro, "__name__", "") or ""
            if name in daemon_names:
                continue
            drainable.append(t)
        if drainable:
            logger.info(f"[SHUTDOWN] Waiting on {len(drainable)} in-flight handler task(s).")
            done, still_pending = await asyncio.wait(drainable, timeout=drain_deadline)
            if still_pending:
                logger.warning(f"[SHUTDOWN] {len(still_pending)} task(s) exceeded drain deadline; forcing.")
        else:
            logger.info("[SHUTDOWN] No in-flight handler tasks to drain.")
        # Disconnect Telegram clients
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

    logger.info("✅ Oisha-OS: All High-Performance Agents are Online & Ready!")

    # Main client loop — race run_until_disconnected against SIGTERM.
    disc_task = asyncio.create_task(client.run_until_disconnected(), name="userbot_disconnect_watcher")
    shutdown_task = asyncio.create_task(_shutdown_event.wait(), name="shutdown_watcher")
    done, pending = await asyncio.wait(
        {disc_task, shutdown_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    if shutdown_task in done:
        await _graceful_drain()
        for t in pending:
            t.cancel()
    else:
        # Client disconnected naturally (e.g. AUTH_KEY_DUPLICATED).
        logger.warning("[SHUTDOWN] Telegram client disconnected unexpectedly.")
        shutdown_task.cancel()

if __name__ == "__main__":
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("👸 Oisha-OS: To'xtatildi (KeyboardInterrupt).")
    except Exception as e:
        logger.critical(f"👸 Oisha-OS: Fatal Error: {e}", exc_info=True)
    finally:
        loop.close()
        print("Stopping bot...")
