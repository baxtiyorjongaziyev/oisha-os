"""
AmoCRM Contacts Auditor Service.
Audits leads/contacts by reading call histories and Telegram chat logs,
then classifies them using Gemini.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import random
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests  # type: ignore
from src.settings import settings
from src.services.utils.gemini_fallback import generate_content_with_fallback

try:
    from google import genai
    from google.genai import types as genai_types
except Exception:
    genai = None
    genai_types = None

try:
    from telethon import functions, types
except Exception:
    functions = None
    types = None

logger = logging.getLogger("crm_contacts_auditor")


def normalize_phone(phone: Optional[str]) -> str:
    """Normalize phone strings to +<digits> for matching."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 9:
        digits = "998" + digits
    return f"+{digits}"


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class CRMContactsAuditor:
    """Audits and classifies amoCRM deals/contacts using call notes and Telegram logs."""

    def __init__(
        self,
        amocrm: Any,
        db: Any,
        tg_client: Any,
        gemini_api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.amocrm = amocrm
        self.db = db
        self.tg_client = tg_client
        self.model_name = (
            model_name
            or os.getenv("GEMINI_CRM_AUDIT_MODEL")
            or settings.GEMINI_CALL_MODEL
        )
        
        # Load Gemini client
        api_key = (gemini_api_key or settings.GEMINI_API_KEY.get_secret_value()).strip()
        self.genai_client = None
        if api_key and genai is not None:
            try:
                self.genai_client = genai.Client(api_key=api_key)
                logger.info("[AUDITOR] Gemini client initialized.")
            except Exception as e:
                logger.warning("[AUDITOR] Gemini client init failed: %s", e)

        # Dialogs cache for group lookup optimization
        self._dialogs_cache = None
        self._dialogs_cache_time = None

    async def init_db(self) -> None:
        """Create crm_contacts_audit table in the database."""
        if not self.db:
            logger.warning("[AUDITOR] No DB instance, skipping table creation.")
            return
        
        try:
            conn = await self.db.get_connection()
            await _maybe_await(
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
            await _maybe_await(conn.commit())
            
            # Add new columns if they don't exist
            try:
                await _maybe_await(conn.execute("ALTER TABLE crm_contacts_audit ADD COLUMN detailed_summary TEXT"))
            except Exception:
                pass
            try:
                await _maybe_await(conn.execute("ALTER TABLE crm_contacts_audit ADD COLUMN task_text TEXT"))
            except Exception:
                pass
            await _maybe_await(conn.commit())
            
            logger.info("[AUDITOR] crm_contacts_audit table initialized successfully.")
        except Exception as e:
            logger.error("[AUDITOR] Database initialization failed: %s", e)

    async def is_lead_audited(self, lead_id: int) -> bool:
        """Check if a lead has already been audited."""
        if not self.db:
            return False
        try:
            conn = await self.db.get_connection()
            cursor = await _maybe_await(
                conn.execute(
                    "SELECT 1 FROM crm_contacts_audit WHERE lead_id = ? LIMIT 1",
                    (lead_id,)
                )
            )
            row = await _maybe_await(cursor.fetchone())
            return row is not None
        except Exception as e:
            logger.error("[AUDITOR] Failed to check audited state for lead %s: %s", lead_id, e)
            return False

    async def save_audit_result(
        self,
        lead_id: int,
        lead_name: str,
        contact_id: Optional[int],
        contact_name: str,
        phone: str,
        username: str,
        telegram_user_id: Optional[int],
        call_summary: str,
        telegram_history: str,
        category: str,
        explanation: str,
        detailed_summary: Optional[str] = None,
        task_text: Optional[str] = None,
    ) -> None:
        """Persist audit result to database."""
        if not self.db:
            return
        try:
            conn = await self.db.get_connection()
            now = datetime.now(timezone.utc).isoformat()
            await _maybe_await(
                conn.execute(
                    """
                    INSERT OR REPLACE INTO crm_contacts_audit
                        (lead_id, lead_name, contact_id, contact_name, phone, username,
                         telegram_user_id, call_summary, telegram_history, category,
                         explanation, detailed_summary, task_text, audited_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        lead_id,
                        lead_name,
                        contact_id,
                        contact_name,
                        phone,
                        username,
                        telegram_user_id,
                        call_summary,
                        telegram_history,
                        category,
                        explanation,
                        detailed_summary,
                        task_text,
                        now,
                    ),
                )
            )
            await _maybe_await(conn.commit())
            logger.info("[AUDITOR] Audit saved: lead_id=%s contact=%s category=%s", lead_id, contact_name, category)
        except Exception as e:
            logger.error("[AUDITOR] Failed to save audit to DB for lead %s: %s", lead_id, e)

    async def fetch_recent_leads(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Fetch leads page-by-page from AmoCRM."""
        leads: List[Dict[str, Any]] = []
        page = 1
        
        logger.info("[AUDITOR] Fetching leads detailed from AmoCRM (limit=%s)...", limit)
        while len(leads) < limit:
            url = f"{self.amocrm.base_url}/api/v4/leads"
            req_limit = min(250, limit - len(leads))
            params = {
                "limit": req_limit,
                "page": page,
                "with": "contacts",
            }
            try:
                # Runs AmoCRM API request with auth handles
                response = await self.amocrm._request_with_auth(
                    requests.get, url, params=params, timeout=30
                )
                if response.status_code == 200:
                    data = response.json()
                    page_leads = data.get("_embedded", {}).get("leads", [])
                    if not page_leads:
                        break
                    leads.extend(page_leads)
                    if len(page_leads) < req_limit:
                        break
                    page += 1
                else:
                    logger.error("[AUDITOR] Failed to fetch leads page %s: status=%s", page, response.status_code)
                    break
            except Exception as e:
                logger.error("[AUDITOR] Exception in fetch_recent_leads on page %s: %s", page, e)
                break
                
        logger.info("[AUDITOR] Total leads fetched: %s", len(leads))
        return leads[:limit]

    async def get_contact_phone_and_username(self, contact_id: int) -> Tuple[str, str]:
        """Fetch contact details from AmoCRM and extract phone & telegram username."""
        phone = ""
        username = ""
        try:
            # get_contact_details is synchronous in AmoCRMSync, run in thread
            contact_details = await asyncio.to_thread(
                self.amocrm.get_contact_details, contact_id
            )
            if contact_details:
                for field in contact_details.get("custom_fields_values") or []:
                    code = str(field.get("field_code") or "").upper()
                    name = str(field.get("field_name") or "").upper()
                    
                    # Phone
                    if code == "PHONE":
                        for val in field.get("values") or []:
                            if val.get("value"):
                                phone = str(val.get("value"))
                                break
                    
                    # Telegram Username
                    if "TELEGRAM" in name or "TELEGRAM" in code or "TG" in code or "USERNAME" in code:
                        for val in field.get("values") or []:
                            if val.get("value"):
                                username = str(val.get("value")).replace("@", "").strip()
                                break
        except Exception as e:
            logger.error("[AUDITOR] Failed to get contact details for ID %s: %s", contact_id, e)
            
        return phone, username

    async def get_or_lookup_telegram_user(
        self, phone: str, username: str
    ) -> Tuple[Optional[int], str]:
        """Look up user on Telegram using username first, then phone number fallback."""
        if not self.tg_client or (functions is None or types is None):
            return None, username

        telegram_user_id = None
        resolved_username = username

        # 1. Try to resolve via username
        if resolved_username:
            try:
                entity = await self.tg_client.get_entity(resolved_username)
                if entity:
                    telegram_user_id = entity.id
                    resolved_username = getattr(entity, "username", resolved_username) or resolved_username
                    return telegram_user_id, resolved_username
            except Exception as e:
                logger.debug("[AUDITOR] Username resolve failed for %s: %s", resolved_username, e)

        # 2. Try to resolve via phone number
        norm_phone = normalize_phone(phone)
        if norm_phone:
            try:
                clean_phone = norm_phone.replace("+", "")
                contact = types.InputPhoneContact(
                    client_id=random.randrange(-(2**63), 2**63),
                    phone=clean_phone,
                    first_name="Oisha Audit",
                    last_name="",
                )
                result = await self.tg_client(
                    functions.contacts.ImportContactsRequest(contacts=[contact])
                )
                users = getattr(result, "users", None) or []
                if users:
                    user = users[0]
                    telegram_user_id = getattr(user, "id", None)
                    resolved_username = getattr(user, "username", resolved_username) or resolved_username
                    
                    # Clean contact immediately to prevent contacts list cluttering
                    if telegram_user_id:
                        try:
                            await self.tg_client(
                                functions.contacts.DeleteContactsRequest(id=[int(telegram_user_id)])
                            )
                        except Exception:
                            pass
            except Exception as e:
                logger.warning("[AUDITOR] Phone lookup failed for %s: %s", norm_phone, e)

        return telegram_user_id, resolved_username

    async def get_telegram_chat_history(
        self, telegram_user_id: int, limit: int = 20
    ) -> str:
        """Fetch last 20 messages of the chat history with this user."""
        if not self.tg_client or not telegram_user_id:
            return ""

        try:
            messages: List[str] = []
            async for msg in self.tg_client.iter_messages(
                int(telegram_user_id), limit=limit
            ):
                text = str(getattr(msg, "text", "") or "").strip()
                if not text:
                    continue
                role = "Men (Userbot)" if getattr(msg, "out", False) else "Mijoz"
                date_str = msg.date.strftime("%Y-%m-%d %H:%M") if msg.date else ""
                messages.append(f"[{date_str}] {role}: {text}")
                
            return "\n".join(reversed(messages))
        except Exception as e:
            logger.debug("[AUDITOR] Failed to fetch Telegram chat history for %s: %s", telegram_user_id, e)
            return ""

    async def get_telegram_history_and_unanswered(
        self, telegram_user_id: int, limit: int = 20
    ) -> Tuple[str, bool, str]:
        """Fetch chat history and check if the latest message is unanswered."""
        if not self.tg_client or not telegram_user_id:
            return "", False, ""

        try:
            msgs = []
            async for msg in self.tg_client.iter_messages(
                int(telegram_user_id), limit=limit
            ):
                msgs.append(msg)
                
            is_unanswered = False
            duration_str = ""
            if msgs:
                latest_msg = msgs[0]
                if not getattr(latest_msg, "out", False):
                    is_unanswered = True
                    delta = datetime.now(timezone.utc) - latest_msg.date
                    hours = delta.total_seconds() / 3600
                    if hours < 1:
                        duration_str = f"{int(delta.total_seconds() / 60)} daqiqa avval"
                    else:
                        duration_str = f"{int(hours)} soat avval"

            formatted_msgs = []
            for msg in reversed(msgs):
                text = str(getattr(msg, "text", "") or "").strip()
                if not text:
                    continue
                role = "Men (Userbot)" if getattr(msg, "out", False) else "Mijoz"
                date_str = msg.date.strftime("%Y-%m-%d %H:%M") if msg.date else ""
                formatted_msgs.append(f"[{date_str}] {role}: {text}")
                
            return "\n".join(formatted_msgs), is_unanswered, duration_str
        except Exception as e:
            logger.debug("[AUDITOR] Failed to fetch Telegram chat history with metadata for %s: %s", telegram_user_id, e)
            return "", False, ""

    async def get_cached_group_dialogs(self) -> List[Any]:
        """Fetch and cache recent group/channel dialogs to avoid Telegram rate limits."""
        now = datetime.now()
        if self._dialogs_cache is not None and self._dialogs_cache_time is not None:
            if (now - self._dialogs_cache_time).total_seconds() < 300:  # 5 minutes cache
                return self._dialogs_cache

        if not self.tg_client:
            return []

        try:
            # Fetch last 200 dialogs (covers active project groups)
            dialogs = await self.tg_client.get_dialogs(limit=200)
            group_dialogs = []
            for d in dialogs:
                if d.is_group or d.is_channel:
                    group_dialogs.append(d)
            self._dialogs_cache = group_dialogs
            self._dialogs_cache_time = now
            logger.info("[AUDITOR] Cached %d group/channel dialogs.", len(group_dialogs))
            return group_dialogs
        except Exception as e:
            logger.error("[AUDITOR] Failed to fetch or cache group dialogs: %s", e)
            return []

    def extract_keywords(self, lead_name: str, contact_name: str) -> List[str]:
        """Extract search keywords from lead name and contact name for group lookups."""
        words = []

        def clean_and_split(text: Optional[str]) -> List[str]:
            if not text:
                return []
            # Replace common punctuation/symbols with spaces
            text_clean = re.sub(r"[^\w\s-]", " ", text)
            return text_clean.split()

        all_words = clean_and_split(lead_name) + clean_and_split(contact_name)

        stop_words = {
            "smm", "branding", "brending", "dizayn", "design", "sayt", "site",
            "logo", "mchj", "ooo", "group", "guruh", "ltd", "co", "uz", "uzb",
            "agency", "agentligi", "va", "bilan", "nomalum", "bitim", "kontakt",
            "mijoz", "shaxsiy", "kandidat", "hamkor", "jamoa", "boshqa", "tg",
            "telegram", "tel", "phone", "username", "id", "lead", "contact",
            "company", "kompaniya", "firm", "firma", "web", "website", "tahlil",
            "audit", "saved", "messages",
            # Honorifics are shared by many unrelated project groups and must
            # never be used as customer identity evidence.
            "aka", "opa", "ustoz", "janob", "xon", "jon", "bro",
        }

        for w in all_words:
            w_low = w.lower().strip()
            # Filter out short terms, numbers, and stop words
            if len(w_low) > 2 and w_low not in stop_words and not w_low.isdigit():
                words.append(w_low)

        return list(set(words))

    async def find_shared_group_chats(
        self, lead_name: str, contact_name: str, telegram_user_id: Optional[int]
    ) -> List[Tuple[Any, str]]:
        """
        Find group chats shared with the customer.
        First matches group title with keywords, then checks if telegram_user_id is in the group.
        """
        if not self.tg_client:
            return []

        # Group history is sensitive customer data. A title keyword alone is
        # not identity proof, so never attach group context without a resolved
        # Telegram account that can be verified as a participant.
        if not telegram_user_id:
            logger.info(
                "[AUDITOR] Skipping group lookup: Telegram identity is unresolved "
                "for lead=%s contact=%s.",
                lead_name,
                contact_name,
            )
            return []

        keywords = self.extract_keywords(lead_name, contact_name)
        if not keywords:
            return []

        group_dialogs = await self.get_cached_group_dialogs()
        matched = []

        for d in group_dialogs:
            title = getattr(d, "name", "") or ""
            title_lower = title.lower()
            title_tokens = set(re.findall(r"[\w-]+", title_lower))

            # Whole-token matching prevents short/common fragments from
            # associating one client's project group with another deal.
            is_match = any(kw in title_tokens for kw in keywords)

            if is_match:
                is_member = False
                try:
                    # Successful permission lookup is the minimum identity
                    # evidence required before reading a project's history.
                    await self.tg_client.get_permissions(d.entity, telegram_user_id)
                    is_member = True
                except Exception as e:
                    logger.info(
                        "[AUDITOR] Group candidate rejected because membership "
                        "could not be verified: group=%s user_id=%s error=%s",
                        title,
                        telegram_user_id,
                        str(e)[:200],
                    )
                if is_member:
                    matched.append((d.entity, title))

        return matched

    async def get_group_chat_history(self, group_entity: Any, limit: int = 15) -> str:
        """Fetch last limit messages from the group chat."""
        if not self.tg_client or not group_entity:
            return ""

        try:
            messages = []
            async for msg in self.tg_client.iter_messages(group_entity, limit=limit):
                text = str(getattr(msg, "text", "") or "").strip()
                if not text:
                    continue
                sender = await msg.get_sender()
                sender_name = "Noma'lum"
                if sender:
                    first = getattr(sender, "first_name", "") or ""
                    last = getattr(sender, "last_name", "") or ""
                    username = getattr(sender, "username", "")
                    sender_name = f"{first} {last}".strip()
                    if username:
                        sender_name += f" (@{username})"
                date_str = msg.date.strftime("%Y-%m-%d %H:%M") if msg.date else ""
                messages.append(f"[{date_str}] {sender_name}: {text}")
            return "\n".join(reversed(messages))
        except Exception as e:
            logger.debug("[AUDITOR] Failed to fetch group history: %s", e)
            return ""

    async def get_group_chat_history_and_unanswered(
        self, group_entity: Any, limit: int = 15
    ) -> Tuple[str, bool, str]:
        """Fetch group history and check if the latest message is from the customer."""
        if not self.tg_client or not group_entity:
            return "", False, ""

        try:
            msgs = []
            async for msg in self.tg_client.iter_messages(group_entity, limit=limit):
                msgs.append(msg)

            is_unanswered = False
            duration_str = ""
            if msgs:
                latest_msg = msgs[0]
                if not getattr(latest_msg, "out", False):
                    is_unanswered = True
                    delta = datetime.now(timezone.utc) - latest_msg.date
                    hours = delta.total_seconds() / 3600
                    if hours < 1:
                        duration_str = f"{int(delta.total_seconds() / 60)} daqiqa avval"
                    else:
                        duration_str = f"{int(hours)} soat avval"

            formatted_msgs = []
            for msg in reversed(msgs):
                text = str(getattr(msg, "text", "") or "").strip()
                if not text:
                    continue
                sender = await msg.get_sender()
                sender_name = "Noma'lum"
                if sender:
                    first = getattr(sender, "first_name", "") or ""
                    last = getattr(sender, "last_name", "") or ""
                    username = getattr(sender, "username", "")
                    sender_name = f"{first} {last}".strip()
                    if username:
                        sender_name += f" (@{username})"
                date_str = msg.date.strftime("%Y-%m-%d %H:%M") if msg.date else ""
                formatted_msgs.append(f"[{date_str}] {sender_name}: {text}")
                
            return "\n".join(formatted_msgs), is_unanswered, duration_str
        except Exception as e:
            logger.debug("[AUDITOR] Failed to fetch group history with metadata: %s", e)
            return "", False, ""

    def serialize_lead_details(self, lead: Dict[str, Any]) -> str:
        """Serialize AmoCRM lead/deal parameters to pass to Gemini."""
        details = []
        details.append(f"Bitim ID: {lead.get('id')}")
        details.append(f"Bitim Nomi: {lead.get('name')}")
        details.append(f"Narxi: {lead.get('price')} UZS")

        created_at = lead.get("created_at")
        if created_at:
            try:
                date_str = datetime.fromtimestamp(int(created_at), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
                details.append(f"Yaratilgan sana: {date_str}")
            except Exception:
                pass

        closed_at = lead.get("closed_at")
        if closed_at:
            try:
                date_str = datetime.fromtimestamp(int(closed_at), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
                details.append(f"Yopilgan sana: {date_str}")
            except Exception:
                pass

        details.append(f"Mas'ul xodim ID (Responsible User): {lead.get('responsible_user_id')}")
        details.append(f"Status (Pipeline Stage) ID: {lead.get('status_id')}")
        details.append(f"Voronka (Pipeline) ID: {lead.get('pipeline_id')}")
        
        loss_reason = lead.get("loss_reason_id")
        if loss_reason:
            details.append(f"Muvaffaqiyatsizlik sababi ID (Loss Reason): {loss_reason}")

        # Tags
        tags = lead.get("_embedded", {}).get("tags", []) or lead.get("tags", [])
        tag_names = [t.get("name") for t in tags if isinstance(t, dict) and t.get("name")]
        if tag_names:
            details.append(f"Teglar: {', '.join(tag_names)}")

        # Custom Fields
        cfs = lead.get("custom_fields_values") or []
        cf_details = []
        for cf in cfs:
            name = cf.get("field_name") or cf.get("field_code") or "Noma'lum maydon"
            vals = [str(v.get("value")) for v in cf.get("values") or [] if v.get("value") is not None]
            if vals:
                cf_details.append(f"- {name}: {', '.join(vals)}")
        if cf_details:
            details.append("Qo'shimcha maydonlar:\n" + "\n".join(cf_details))

        return "\n".join(details)

    async def get_lead_tasks(self, lead_id: int) -> List[Dict[str, Any]]:
        """Fetch tasks (both active and completed) for a specific lead."""
        tasks = []
        for is_completed in [0, 1]:
            url = f"{self.amocrm.base_url}/api/v4/tasks"
            params = {
                "filter[entity_id]": lead_id,
                "filter[entity_type]": "leads",
                "filter[is_completed]": is_completed
            }
            try:
                response = await self.amocrm._request_with_auth(
                    requests.get, url, params=params, timeout=30
                )
                if response.status_code == 200:
                    data = response.json()
                    page_tasks = data.get("_embedded", {}).get("tasks", [])
                    tasks.extend(page_tasks)
            except Exception as e:
                logger.error("[AUDITOR] Failed to fetch tasks for lead %s (is_completed=%s): %s", lead_id, is_completed, e)
        return tasks

    def serialize_tasks(self, tasks: List[Dict[str, Any]]) -> str:
        """Convert lead tasks history and comments into structured string."""
        if not tasks:
            return "Bitimda vazifalar tarixi mavjud emas."
        lines = []
        for t in tasks:
            status = "Bajarilgan" if t.get("is_completed") else "Faol"
            created = ""
            if t.get("created_at"):
                try:
                    created = datetime.fromtimestamp(int(t.get("created_at")), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass
            text = t.get("text") or "Tavsifsiz vazifa"
            result_info = ""
            if t.get("is_completed") and t.get("result"):
                res_text = t.get("result", {}).get("text") or "Izohsiz"
                result_info = f" | Bajarilish izohi (javobi): {res_text}"
            
            lines.append(f"- [{status}] Yaratilgan: {created} | Vazifa: {text}{result_info}")
        return "\n".join(lines)

    def is_duplicate_task(self, new_task_text: str, existing_tasks: List[Dict[str, Any]]) -> bool:
        """Check if new_task_text is similar to any existing active or completed task."""
        if not new_task_text:
            return False
            
        def clean_text(t: str) -> str:
            # Lowercase, keep letters/numbers, strip
            t_clean = re.sub(r"[^\w\s]", "", t.lower())
            t_clean = t_clean.replace("oisha-os keyingi qadam", "").strip()
            t_clean = t_clean.replace("oishaos", "").strip()
            return t_clean
            
        new_cleaned = clean_text(new_task_text)
        if not new_cleaned:
            return False
            
        new_words = set(new_cleaned.split())
        if not new_words:
            return False
            
        for t in existing_tasks:
            ext_text = t.get("text") or ""
            ext_cleaned = clean_text(ext_text)
            if not ext_cleaned:
                continue
                
            # Exact match check
            if new_cleaned == ext_cleaned or new_cleaned in ext_cleaned or ext_cleaned in new_cleaned:
                return True
                
            # Word overlap check (e.g. if 70% of words overlap)
            ext_words = set(ext_cleaned.split())
            if not ext_words:
                continue
            intersection = new_words.intersection(ext_words)
            smaller_len = min(len(new_words), len(ext_words))
            if smaller_len > 0 and len(intersection) / smaller_len > 0.7:
                return True
                
        return False

    async def get_call_notes_and_transcripts(
        self, lead_id: int, phone: str
    ) -> Tuple[str, str]:
        """Get processed transcripts/summaries from db or AmoCRM lead notes."""
        transcript = ""
        summary = ""

        # 1. Search locally/Turso DB for processed calls
        if self.db:
            try:
                conn = await self.db.get_connection()
                cursor = await _maybe_await(
                    conn.execute(
                        """
                        SELECT transcript, summary FROM call_analyses 
                        WHERE lead_id = ? OR (caller_phone = ? AND caller_phone != '')
                        ORDER BY analyzed_at DESC LIMIT 1
                        """,
                        (lead_id, phone),
                    )
                )
                row = await _maybe_await(cursor.fetchone())
                if row:
                    transcript, summary = row
                    if transcript or summary:
                        logger.info("[AUDITOR] Found existing call analysis in DB for lead %s.", lead_id)
                        return transcript, summary
            except Exception as e:
                logger.debug("[AUDITOR] DB call lookup failed: %s", e)

        # 2. Look for existing Oisha call notes in AmoCRM
        try:
            notes = await _maybe_await(self.amocrm.get_lead_notes(lead_id))
            for note in notes or []:
                text = str((note.get("params") or {}).get("text") or "")
                # If this is Oisha call tahlili note, grab the text
                if "Oisha-OS: Qo'ng'iroq tahlili" in text or "Qo'ng'iroq tahlili" in text:
                    summary = text
                    logger.info("[AUDITOR] Found existing call note in AmoCRM for lead %s.", lead_id)
                    break
                    
            # 3. Fallback to basic call notes summary if no transcripts found
            if not summary:
                call_lines = []
                for note in notes or []:
                    note_type = str(note.get("note_type") or "").lower()
                    if note_type in ("call_in", "call_out", "phone_call"):
                        params = note.get("params") or {}
                        duration = params.get("duration", 0)
                        direction = "Kiruvchi" if note_type == "call_in" else "Chiquvchi"
                        created_at = note.get("created_at")
                        date_str = ""
                        if created_at:
                            try:
                                date_str = datetime.fromtimestamp(int(created_at)).strftime("%Y-%m-%d %H:%M")
                            except Exception:
                                pass
                        call_lines.append(f"Qo'ng'iroq ({date_str}): {direction}, davomiyligi={duration}s")
                
                if call_lines:
                    summary = "Mavjud qo'ng'iroqlar tarixi:\n" + "\n".join(call_lines)
        except Exception as e:
            logger.error("[AUDITOR] Failed to get call notes from AmoCRM for lead %s: %s", lead_id, e)

        return transcript, summary

    async def get_lead_notes_history(self, lead_id: int) -> str:
        """Fetch and serialize recent text comments/notes for the lead to help classification."""
        try:
            notes = await _maybe_await(self.amocrm.get_lead_notes(lead_id))
            if not notes:
                return "Izohlar tarixi bo'sh."
            
            lines = []
            for note in notes[:15]:  # Limit to last 15 notes
                note_type = str(note.get("note_type") or "").lower()
                text = str((note.get("params") or {}).get("text") or "").strip()
                if not text:
                    continue
                
                # Skip Oisha's own long audit and duplicate warnings to avoid context pollution
                if "Oisha-OS: Bitim va Suhbatlar Mukammal Tahlili" in text or "Oisha-OS: Qo'ng'iroq tahlili" in text or "Oisha-OS Eslatma:" in text or "Oisha-OS Telegram Draft:" in text:
                    continue
                
                created_at = note.get("created_at")
                date_str = ""
                if created_at:
                    try:
                        date_str = datetime.fromtimestamp(int(created_at)).strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        pass
                
                lines.append(f"[{date_str}] ({note_type}): {text}")
            
            if not lines:
                return "Izohlar tarixi bo'sh."
            return "\n".join(lines)
        except Exception as e:
            logger.error("[AUDITOR] Failed to get notes history for lead %s: %s", lead_id, e)
            return "Izohlar tarixi olinmadi (xatolik)."

    async def classify_contact(
        self,
        lead_name: str,
        contact_name: str,
        phone: str,
        username: str,
        call_summary: str,
        telegram_history: str,
        lead_details: str = "",
        group_history: str = "",
        tasks_history: str = "",
        notes_history: str = "",
        telegram_unanswered_info: str = "",
    ) -> Tuple[str, str, str, str, str]:  # Return (category, explanation, detailed_summary, task_text, telegram_draft_reply)
        """Use Gemini to classify the contact and generate conclusion, follow-up task, and draft reply."""
        if not self.genai_client:
            return "Boshqa", "Gemini API sozlanmagan. Standart toifa 'Boshqa' deb tanlandi.", "", "", ""

        context = {
            "lead_name": lead_name,
            "contact_name": contact_name,
            "phone": phone,
            "username": username,
            "call_summary_or_transcript": call_summary[:2000],
            "telegram_history": telegram_history[:3000],
            "lead_details": lead_details[:2000],
            "group_history": group_history[:3000],
            "tasks_history": tasks_history[:2000],
            "notes_history": notes_history[:3000],
            "telegram_unanswered_info": telegram_unanswered_info,
        }

        prompt = (
            "Siz Oisha-OS Surgical Agent tizimining aloqalarni tahlil qilish va saralash xizmatining bir bo'lagisiz. "
            "Sizga amoCRM dagi bitim nomi, bitimning to'liq har bir maydoni (field), bitimdagi izohlar va eslatmalar tarixi (notes_history), kontakt ma'lumotlari, qo'ng'iroq yozuvlari tahlili/tarixi, "
            "Telegram shaxsiy va guruh yozishmalari tarixi, amoCRM bitimidagi vazifalar (zadachalar) tarixi hamda ularga berilgan javoblar/izohlar, "
            "va Telegram chatlaridagi javobsiz qolib ketgan suhbatlar holati taqdim etiladi.\n\n"
            "Sizning vazifangiz taqdim etilgan barcha ma'lumotlarni, jumladan sdelkaning har bir fieldini, vazifalar va ularning bajarilish javoblarini, ayniqsa notes_history dagi izohlarni chuqur tahlil qilib, quyidagi natijalarni ishlab chiqish:\n\n"
            "1. **Tasniflash (category)**: Kontaktni quyidagi 5 ta toifadan faqat bittasiga tasniflash:\n"
            "   - Mijoz: Brending, SMM, sayt yaratish, dizayn kabi xizmatlarimizni so'ragan, sotib olgan, narxi yoki tijorat taklifi bilan qiziqqan har qanday shaxs.\n"
            "   - Shaxsiy: Shaxsiy oila a'zolari, do'stlar yoki biznesga mutlaqo aloqasi bo'lmagan shaxsiy masaladagi suhbatdoshlar.\n"
            "   - Kandidat: Ish so'rab kelganlar, rezyume (CV) tashlaganlar, vakansiya yoki amaliyot haqida so'raganlar.\n"
            "   - Hamkor/Jamoa: Jamoamiz a'zolari (xodimlar), hamkorlar yoki birgalikda ish olib borayotgan tashqi hamkorlar.\n"
            "   - Boshqa: Spam qo'ng'iroqlar, xato tushganlar, yoki suhbat tarixi bo'sh bo'lgan va aniq toifaga kirmaydigan kontaktlar. SHUNINGDEK, agar notes_history da mijoz bo'lmaganligi, puli qaytarilganligi yoki bitim bekor qilinganligi (masalan, 'mijozimiz emas', 'ishlab bo'lmaydi', 'pulini qaytarganmiz', 'junk', 'reject') aniq yozilgan bo'lsa, uni Boshqa toifasiga kiriting.\n\n"
            "2. **Tasniflash sababi (explanation)**: Qisqa va londa o'zbek tilida (lotin alifbosida) tasniflash sababi.\n\n"
            "3. **Mukammal Tahlil Xulosasi (detailed_summary)**: Har bir mijozning ma'lumotlarini (Telefon qo'ng'iroqlari, Telegram shaxsiy va guruh yozishmalari, sdelka maydonlari, vazifalar tarixi va ularning bajarilish izohlari) to'liq tahlil qilib, o'zbek tilida (lotin alifbosida) professional biznes-konsalting ohangida yozilgan mukammal xulosa. \n"
            "Xulosaning oxiriga har doim va faqat haqiqiy faol mijozlar uchun quyidagi maslahatni qo'shing:\n"
            "   '💡 Menejerga maslahat: Vazifa bajarilgach, uni amoCRMda \"Bajarildi\" deb belgilang va bajarilish izohini yozing. Oisha boti bajarilgan vazifalar tarixi va izohlarini to'liq tahlil qiladi va qayta takroriy vazifa yaratilishining oldini oladi.'\n\n"
            "4. **Keyingi Qadam Vazifasi (next_step_task)**: Mas'ul menejer uchun keyingi qadam bo'yicha aniq vazifa matni. \n"
            "   - **MUHIM QOIDA (Takroriy vazifalarni oldini olish va bekorchi bitimlar)**:\n"
            "     - Agar bitimdagi izohlar yoki eslatmalar (notes_history) ichida 'mijozimiz emas', 'ishlamaymiz', 'pulini qaytarganmiz', 'ishlab bo'lmaydi', 'junk' yoki shunga o'xshash mijoz bo'lmaganligi yoki bitim tugatilganligi haqidagi ma'lumotlar mavjud bo'lsa, keyingi qadam vazifasini mutlaqo yozmang (bo'sh satr '' qoldiring).\n"
            "     - Agar keyingi qadam vazifasi taqdim etilgan vazifalar tarixida (tasks_history) allaqachon bajarilgan bo'lsa yoki hozirda faol bo'lsa, xuddi shu vazifani qaytadan yaratishni tavsiya qilmang. Buning o'rniga yangi mantiqiy vazifa yozing.\n"
            "     - Agar bitim toifasi 'Boshqa' (Other) deb saralansa va faol biznes vazifasi talab etilmasa, keyingi qadam vazifasini bo'sh satr ('') qoldiring.\n"
            "     - Telegram javobsiz xabarlar: Agar 'telegram_unanswered_info' maydoni mijozning xabari javobsiz qolganini ko'rsatsa, birinchi navbatda Telegramda mijozga javob yozish vazifasini qo'ying.\n"
            "     - Agar mutlaqo yangi vazifa qo'yish shart bo'lmasa yoki barcha ishlar yakunlangan bo'lsa, 'next_step_task' maydonini bo'sh satr ('') qoldiring.\n\n"
            "5. **Telegram Draft Reply (telegram_draft_reply)**: Mijozning shaxsiy Telegramdagi oxirgi javobsiz xabariga taklif qilinayotgan javob matni (o'zbek tilida, lotin alifbosida, samimiy va professional ohangda). Agar shaxsiy Telegram chatida mijozning xabari javobsiz qolgan bo'lsa, ushbu maydonga tahminiy javob matnini yozing. Userbot buni shaxsiy chatda avtomatik ravishda qoralama (draft) qilib qo'yadi. Agar javobsiz xabar bo'lmasa, bo'sh satr ('') qaytaring.\n\n"
            "Javobni quyidagi JSON formatida qaytaring, boshqa hech qanday qo'shimcha tushuntirish va markdown belgilari (masalan, ```json) yozmang:\n"
            "{\n"
            '  "category": "Mijoz|Shaxsiy|Kandidat|Hamkor/Jamoa|Boshqa",\n'
            '  "explanation": "Tasniflash sababi...",\n'
            '  "detailed_summary": "Tahlil xulosasi...",\n'
            '  "next_step_task": "Menejer uchun vazifa...",\n'
            '  "telegram_draft_reply": "Taklif etiladigan javob matni..."\n'
            "}\n\n"
            f"Kontekst JSON:\n{json.dumps(context, ensure_ascii=False, default=str)}"
        )

        try:
            kwargs = {"model": self.model_name, "contents": [prompt]}
            if genai_types is not None:
                kwargs["config"] = genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                )

            # Using generate_content_with_fallback for resiliency
            response, _ = await generate_content_with_fallback(
                self.genai_client,
                primary_model=self.model_name,
                contents=kwargs["contents"],
                config=kwargs.get("config"),
                env_name="GEMINI_CRM_AUDIT_FALLBACK_MODELS",
                log_prefix="[AUDITOR_GEMINI]",
            )
            text = str(getattr(response, "text", "") or "").strip()

            # Parse JSON safely
            data = {}
            if text:
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    # Try regex match
                    match = re.search(r"\{.*\}", text, re.DOTALL)
                    if match:
                        data = json.loads(match.group(0))

            category = data.get("category")
            explanation = data.get("explanation", "Sabab taqdim etilmadi.")
            detailed_summary = data.get("detailed_summary", f"Tizim tomonidan avtomatik tahlil: {explanation}")
            next_step_task = data.get("next_step_task", "Mijoz bilan bog'lanib, holatni aniqlashtiring.")
            telegram_draft_reply = data.get("telegram_draft_reply", "")

            valid_categories = {"Mijoz", "Shaxsiy", "Kandidat", "Hamkor/Jamoa", "Boshqa"}
            if category not in valid_categories:
                category = "Boshqa"

            return category, explanation, detailed_summary, next_step_task, telegram_draft_reply
        except Exception as e:
            logger.error("[AUDITOR] Gemini classification/analysis failed: %s", e)

            # Rules-based fallback if Gemini fails
            lowered_history = (telegram_history + " " + call_summary + " " + group_history + " " + notes_history).lower()
            category = "Boshqa"
            if any(w in lowered_history for w in ("mijozimiz emas", "ishlab bo'lmaydi", "pulini qaytar", "not a client", "junk")):
                category = "Boshqa"
                next_step_task = ""
            elif any(w in lowered_history for w in ("rezyume", "resume", "cv", "ishga", "vakansiya", "amaliyot")):
                category = "Kandidat"
                next_step_task = ""
            elif any(w in lowered_history for w in ("branding", "brending", "narxi", "narx", "site", "sayt", "logo", "smm", "dizayn")):
                category = "Mijoz"
                next_step_task = "Mijoz bilan bog'lanib, keyingi kelishuvlarni aniqlashtiring."
            else:
                next_step_task = "Mijoz bilan bog'lanib, keyingi kelishuvlarni aniqlashtiring."

            explanation = f"Xatolik tufayli qoida bo'yicha saralandi (Fallback): {str(e)}"
            detailed_summary = f"Mijoz va uning yozishmalari tahlili xatolik tufayli yakunlanmadi. Aloqa toifasi: {category}."

            return category, explanation, detailed_summary, next_step_task, ""

    async def audit_lead_by_data(self, lead: Dict[str, Any], force: bool = False) -> Optional[str]:
        """Audit and classify a single AmoCRM lead data dictionary."""
        lead_id = lead.get("id")
        if not lead_id:
            return None

        if not force and await self.is_lead_audited(int(lead_id)):
            return "skipped"

        lead_name = lead.get("name") or "Noma'lum Bitim"
        contacts = lead.get("_embedded", {}).get("contacts", []) or lead.get("contacts", [])
        
        contact_id = None
        contact_name = "Noma'lum Kontakt"
        phone = ""
        username = ""
        
        if contacts:
            contact_id = contacts[0].get("id")
            contact_name = contacts[0].get("name") or contact_name
            if contact_id:
                phone, username = await self.get_contact_phone_and_username(int(contact_id))

        # Lookup Telegram Account & chat history
        telegram_user_id = None
        telegram_history = ""
        is_unanswered_tg = False
        tg_unanswered_duration = ""
        if phone or username:
            telegram_user_id, username = await self.get_or_lookup_telegram_user(phone, username)
            if telegram_user_id:
                telegram_history, is_unanswered_tg, tg_unanswered_duration = await self.get_telegram_history_and_unanswered(telegram_user_id, limit=20)

        # Lookup Shared Group Chats & histories
        group_history_parts = []
        is_unanswered_group = False
        group_unanswered_duration = ""
        try:
            shared_groups = await self.find_shared_group_chats(lead_name, contact_name, telegram_user_id)
            for group_entity, group_title in shared_groups:
                g_hist, g_unanswered, g_duration = await self.get_group_chat_history_and_unanswered(group_entity, limit=15)
                if g_hist:
                    group_history_parts.append(f"--- Guruh: {group_title} ---\n{g_hist}")
                    if g_unanswered:
                        is_unanswered_group = True
                        group_unanswered_duration = g_duration
        except Exception as group_err:
            logger.warning("[AUDITOR] Error fetching shared group chats for lead %s: %s", lead_id, group_err)

        group_history = "\n\n".join(group_history_parts)

        # Determine Telegram unanswered status info
        telegram_unanswered_info = ""
        if is_unanswered_tg:
            telegram_unanswered_info += f"Mijoz shaxsiy telegramda oxirgi xabarni yozgan ({tg_unanswered_duration}) va javob berilmagan. "
        if is_unanswered_group:
            telegram_unanswered_info += f"Mijoz loyiha guruhida oxirgi xabarni yozgan ({group_unanswered_duration}) va javob berilmagan."
        if not telegram_unanswered_info:
            telegram_unanswered_info = "Barcha Telegram xabarlariga javob berilgan."

        # Fetch and serialize Lead Tasks
        existing_tasks = await self.get_lead_tasks(int(lead_id))
        tasks_history = self.serialize_tasks(existing_tasks)

        # Serialize Lead details
        lead_details = self.serialize_lead_details(lead)

        # Lookup call notes/transcripts
        _, call_summary = await self.get_call_notes_and_transcripts(int(lead_id), phone)

        # Fetch notes history (comments) from AmoCRM
        notes_history = await self.get_lead_notes_history(int(lead_id))

        # Classify and analyze via Gemini
        category, explanation, detailed_summary, next_step_task, telegram_draft_reply = await self.classify_contact(
            lead_name=lead_name,
            contact_name=contact_name,
            phone=phone,
            username=username,
            call_summary=call_summary,
            telegram_history=telegram_history,
            lead_details=lead_details,
            group_history=group_history,
            tasks_history=tasks_history,
            notes_history=notes_history,
            telegram_unanswered_info=telegram_unanswered_info,
        )

        # Save to DB
        await self.save_audit_result(
            lead_id=int(lead_id),
            lead_name=lead_name,
            contact_id=contact_id,
            contact_name=contact_name,
            phone=phone,
            username=username,
            telegram_user_id=telegram_user_id,
            call_summary=call_summary,
            telegram_history=telegram_history + ("\n\n" + group_history if group_history else ""),
            category=category,
            explanation=explanation,
            detailed_summary=detailed_summary,
            task_text=next_step_task,
        )

        # Add note to AmoCRM lead
        if detailed_summary:
            try:
                full_note_text = f"🤖 **Oisha-OS: Bitim va Suhbatlar Mukammal Tahlili**\n\n{detailed_summary}"
                await asyncio.to_thread(self.amocrm.add_lead_note, int(lead_id), full_note_text)
                logger.info("[AUDITOR] Added audit note to AmoCRM for lead %s.", lead_id)
            except Exception as note_err:
                logger.error("[AUDITOR] Failed to add audit note to AmoCRM for lead %s: %s", lead_id, note_err)

        # Save draft in Telegram if unanswered
        if telegram_user_id and is_unanswered_tg and telegram_draft_reply:
            try:
                draft_text = telegram_draft_reply.strip()
                await self.tg_client.edit_draft(int(telegram_user_id), draft_text)
                logger.info("[AUDITOR] Saved draft reply in Telegram for user %s: %s", telegram_user_id, draft_text[:50])
                
                # Add note to AmoCRM that a draft reply has been saved
                try:
                    draft_note = f"🤖 **Oisha-OS Telegram Draft:**\nMijozning shaxsiy Telegramdagi oxirgi javobsiz xabariga userbot orqali taklif etilgan javob qoralama (draft) sifatida saqlandi:\n\n\"{draft_text}\"\n\n*(Menejer ushbu javobni tahrirlashi yoki o'zgartirmasdan shaxsiy Telegram orqali yuborishi mumkin)*"
                    await asyncio.to_thread(self.amocrm.add_lead_note, int(lead_id), draft_note)
                except Exception:
                    pass
            except Exception as draft_err:
                logger.error("[AUDITOR] Failed to save draft in Telegram for user %s: %s", telegram_user_id, draft_err)

        # Create task in AmoCRM (with duplication prevention)
        if next_step_task:
            next_step_task_clean = next_step_task.strip()
            # Double check duplication logic
            is_dup = self.is_duplicate_task(next_step_task_clean, existing_tasks)
            if is_dup:
                logger.info("[AUDITOR] Skipped creating duplicate task for lead %s: %s", lead_id, next_step_task_clean)
                try:
                    dup_note = f"🤖 **Oisha-OS Eslatma:**\nKeyingi qadam vazifasi ('{next_step_task_clean}') bitimda allaqachon faol yoki bajarilganligi sababli takroran yaratilmadi."
                    await asyncio.to_thread(self.amocrm.add_lead_note, int(lead_id), dup_note)
                except Exception:
                    pass
            else:
                try:
                    responsible_user_id = lead.get("responsible_user_id")
                    # Calculate tomorrow at 18:00 local time (GMT+5 offset)
                    tz_offset = timezone(timedelta(hours=5))
                    now_gmt5 = datetime.now(tz_offset)
                    tomorrow_gmt5 = now_gmt5 + timedelta(days=1)
                    tomorrow_18_gmt5 = tomorrow_gmt5.replace(hour=18, minute=0, second=0, microsecond=0)
                    complete_till = int(tomorrow_18_gmt5.timestamp())

                    task_text = f"🤖 Oisha-OS Keyingi Qadam:\n{next_step_task_clean}"
                    await self.amocrm.create_task(
                        element_id=int(lead_id),
                        text=task_text,
                        complete_till=complete_till,
                        responsible_user_id=responsible_user_id,
                    )
                    logger.info("[AUDITOR] Created follow-up task in AmoCRM for lead %s (responsible: %s).", lead_id, responsible_user_id)
                except Exception as task_err:
                    logger.error("[AUDITOR] Failed to create follow-up task in AmoCRM for lead %s: %s", lead_id, task_err)

        # Tag lead in AmoCRM automatically
        try:
            add_tag = getattr(self.amocrm, "add_lead_tag", None)
            if callable(add_tag):
                await _maybe_await(add_tag(int(lead_id), category))
                logger.info("[AUDITOR] Auto-tagged lead %s as '%s' in AmoCRM.", lead_id, category)
        except Exception as tag_err:
            logger.warning("[AUDITOR] Failed to tag lead %s as '%s' in AmoCRM: %s", lead_id, category, tag_err)

        return category

    async def run_audit(
        self,
        limit: int = 500,
        progress_callback: Optional[callable] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Main entry point. Fetches and audits leads, updates progress."""
        await self.init_db()
        
        leads = await self.fetch_recent_leads(limit=limit)
        stats = {
            "total_leads": len(leads),
            "processed": 0,
            "skipped": 0,
            "categories": {
                "Mijoz": 0,
                "Shaxsiy": 0,
                "Kandidat": 0,
                "Hamkor/Jamoa": 0,
                "Boshqa": 0,
            },
        }

        for idx, lead in enumerate(leads):
            lead_id = lead.get("id")
            if not lead_id:
                continue

            try:
                result = await self.audit_lead_by_data(lead, force=force)
                if result == "skipped":
                    stats["skipped"] += 1
                elif result:
                    stats["processed"] += 1
                    stats["categories"][result] = stats["categories"].get(result, 0) + 1
                
                # Sleep between requests to avoid rate limits
                await asyncio.sleep(1.0)
            except Exception as e:
                logger.error("[AUDITOR] Error auditing lead %s: %s", lead_id, e, exc_info=True)
                stats["processed"] += 1
                stats["categories"]["Boshqa"] += 1

            # Progress callback every 10 leads
            if progress_callback and (idx + 1) % 10 == 0:
                try:
                    await progress_callback(idx + 1, len(leads), stats)
                except Exception as cb_err:
                    logger.error("[AUDITOR] Progress callback error: %s", cb_err)

        # Final progress callback
        if progress_callback:
            try:
                await progress_callback(len(leads), len(leads), stats)
            except Exception:
                pass

        return stats


