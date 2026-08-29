"""
Telegram contact lookup, direct chat history, and shared group discovery mixin.
"""
import asyncio
import logging
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from telethon import functions, types
from src.services.core.crm.auditor.db_storage import normalize_phone

logger = logging.getLogger(__name__)


class TelegramHistoryMixin:
    """Handles Telegram user lookup, direct chat messages, and group chat analysis."""

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
                            logger.debug("[CRM_AUDIT] Failed to clean up imported contact after phone lookup", exc_info=True)
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
