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
import random
import re
from datetime import datetime, timezone
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
                         explanation, audited_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            messages: List[Dict[str, Any]] = []
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

    async def classify_contact(
        self,
        lead_name: str,
        contact_name: str,
        phone: str,
        username: str,
        call_summary: str,
        telegram_history: str,
    ) -> Tuple[str, str]:
        """Use Gemini to classify the contact into one of five categories."""
        if not self.genai_client:
            return "Boshqa", "Gemini API sozlanmagan. Standart toifa 'Boshqa' deb tanlandi."

        context = {
            "lead_name": lead_name,
            "contact_name": contact_name,
            "phone": phone,
            "username": username,
            "call_summary_or_transcript": call_summary[:2000],
            "telegram_history": telegram_history[:3000],
        }

        prompt = (
            "Siz Oisha-OS Surgical Agent tizimining aloqalarni tahlil qilish va saralash xizmatining bir bo'lagisiz. "
            "Sizga amoCRM dagi bitim nomi, kontakt ma'lumotlari, qo'ng'iroq yozuvlari tahlili/tarixi hamda "
            "Telegram userbot suhbatlari tarixi taqdim etiladi.\n\n"
            "Sizning vazifangiz suhbatlar natijasiga ko'ra ushbu kontaktni quyidagi 5 ta toifadan faqat bittasiga tasniflash:\n"
            "1. Mijoz: Brending, SMM, sayt yaratish, dizayn kabi xizmatlarimizni so'ragan, sotib olgan, narxi yoki tijorat taklifi "
            "bilan qiziqqan har qanday shaxs.\n"
            "2. Shaxsiy: Shaxsiy oila a'zolari, do'stlar yoki biznesga mutlaqo aloqasi bo'lmagan shaxsiy masaladagi suhbatdoshlar.\n"
            "3. Kandidat: Ish so'rab kelganlar, rezyume (CV) tashlaganlar, vakansiya yoki amaliyot haqida so'raganlar.\n"
            "4. Hamkor/Jamoa: Jamoamiz a'zolari (xodimlar), hamkorlar yoki birgalikda ish olib borayotgan tashqi hamkorlar.\n"
            "5. Boshqa: Spam qo'ng'iroqlar, xato tushganlar, yoki suhbat tarixi bo'sh bo'lgan va aniq toifaga kirmaydigan kontaktlar.\n\n"
            "Javobni quyidagi JSON formatida qaytaring, hech qanday qo'shimcha tushuntirish yozmang:\n"
            "{\n"
            '  "category": "Mijoz|Shaxsiy|Kandidat|Hamkor/Jamoa|Boshqa",\n'
            '  "explanation": "Qisqa va londa o\'zbek tilida tasniflash sababi (sdelka nomi, telefon va telegram suhbatidan olingan dalillar asosida)."\n'
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
            
            valid_categories = {"Mijoz", "Shaxsiy", "Kandidat", "Hamkor/Jamoa", "Boshqa"}
            if category not in valid_categories:
                category = "Boshqa"
                
            return category, explanation
        except Exception as e:
            logger.error("[AUDITOR] Gemini classification failed: %s", e)
            
            # Rules-based fallback if Gemini fails
            lowered_history = (telegram_history + " " + call_summary).lower()
            if any(w in lowered_history for w in ("rezyume", "resume", "cv", "ishga", "vakansiya", "amaliyot")):
                return "Kandidat", "Kandidat so'zlari topilganligi sababli qoida bo'yicha saralandi (Fallback)."
            elif any(w in lowered_history for w in ("branding", "brending", "narxi", "narx", "site", "sayt", "logo", "smm", "dizayn")):
                return "Mijoz", "Mijoz so'zlari topilganligi sababli qoida bo'yicha saralandi (Fallback)."
            return "Boshqa", "Xatolik tufayli standart toifaga tushdi: " + str(e)

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
        if phone or username:
            telegram_user_id, username = await self.get_or_lookup_telegram_user(phone, username)
            if telegram_user_id:
                telegram_history = await self.get_telegram_chat_history(telegram_user_id, limit=20)

        # Lookup call notes/transcripts
        _, call_summary = await self.get_call_notes_and_transcripts(int(lead_id), phone)

        # Classify via Gemini
        category, explanation = await self.classify_contact(
            lead_name=lead_name,
            contact_name=contact_name,
            phone=phone,
            username=username,
            call_summary=call_summary,
            telegram_history=telegram_history,
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
            telegram_history=telegram_history,
            category=category,
            explanation=explanation,
        )

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
