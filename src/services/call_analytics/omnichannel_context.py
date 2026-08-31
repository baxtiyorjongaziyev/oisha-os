"""
Omnichannel Context Extractor for Call Intelligence.

Aggregates AmoCRM Lead & Contact Custom Fields and Telegram Chat History
to enrich AI Call Analysis with full 360-degree client context.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class OmnichannelContext:
    """Structured context combining CRM lead fields, contact data, and Telegram history."""

    def __init__(
        self,
        lead_id: int,
        lead_name: str = "",
        price: int = 0,
        status_name: str = "",
        pipeline_name: str = "",
        responsible_user: str = "",
        tags: Optional[List[str]] = None,
        custom_fields: Optional[Dict[str, str]] = None,
        contact_name: str = "",
        contact_phone: str = "",
        telegram_username: str = "",
        telegram_messages: Optional[List[str]] = None,
    ) -> None:
        self.lead_id = lead_id
        self.lead_name = lead_name or f"Lid #{lead_id}"
        self.price = price
        self.status_name = status_name
        self.pipeline_name = pipeline_name
        self.responsible_user = responsible_user
        self.tags = tags or []
        self.custom_fields = custom_fields or {}
        self.contact_name = contact_name
        self.contact_phone = contact_phone
        self.telegram_username = telegram_username
        self.telegram_messages = telegram_messages or []

    def format_crm_prompt_block(self) -> str:
        """Build text block describing CRM lead fields for AI prompt."""
        lines = [
            f"- Lid ID va nomi: #{self.lead_id} — {self.lead_name}",
            f"- Byudjet / Qiymat: {self.price:,} so'm / $" if self.price else "- Byudjet: Ko'rsatilmagan",
        ]
        if self.pipeline_name or self.status_name:
            lines.append(f"- Voronka va Bosqich: {self.pipeline_name} -> {self.status_name}")
        if self.responsible_user:
            lines.append(f"- Mas'ul menejer: {self.responsible_user}")
        if self.tags:
            lines.append(f"- Teglar: {', '.join(self.tags)}")
        if self.contact_name:
            lines.append(f"- Mijoz ismi: {self.contact_name}")
        if self.contact_phone:
            lines.append(f"- Telefon: {self.contact_phone}")
        if self.telegram_username:
            lines.append(f"- Telegram: @{self.telegram_username}")

        for k, v in self.custom_fields.items():
            if v:
                lines.append(f"- {k}: {v}")

        return "\n".join(lines)

    def format_telegram_prompt_block(self) -> str:
        """Build text block describing Telegram chat history for AI prompt."""
        if not self.telegram_messages:
            return "Ushbu mijoz bilan avvalgi Telegram yozishmalari topilmadi."
        return "\n".join(self.telegram_messages[-20:])

    def format_crm_note_block(self) -> str:
        """Build formatted markdown block for AmoCRM note."""
        items: List[str] = []
        if self.price:
            items.append(f"💰 Byudjet: {self.price:,}")
        if self.status_name:
            items.append(f"📌 Bosqich: {self.status_name}")
        for k, v in list(self.custom_fields.items())[:3]:
            items.append(f"🔹 {k}: {v}")
        
        crm_part = " | ".join(items) if items else "Ma'lumotlar to'liq kiritilmagan"
        tg_part = (
            f"@{self.telegram_username} ({len(self.telegram_messages)} ta xabar tarixi)"
            if self.telegram_username or self.telegram_messages
            else "Mavjud emas"
        )
        return f"📋 **CRM Ma'lumotlari:** {crm_part}\n💬 **Telegram:** {tg_part}"


class OmnichannelContextFetcher:
    """Helper to fetch CRM lead custom fields and Telegram history asynchronously."""

    def __init__(self, amocrm: Any, tg_client: Optional[Any] = None, db: Optional[Any] = None) -> None:
        self.amocrm = amocrm
        self.tg_client = tg_client
        self.db = db

    async def fetch_lead_omnichannel_context(
        self,
        lead_id: int,
        caller_phone: str = "",
    ) -> OmnichannelContext:
        """Fetch CRM lead, custom fields, contact, and Telegram chat history."""
        lead_name = ""
        price = 0
        status_name = ""
        pipeline_name = ""
        responsible_user = ""
        tags: List[str] = []
        custom_fields: Dict[str, str] = {}
        contact_name = ""
        contact_phone = caller_phone
        telegram_username = ""
        telegram_messages: List[str] = []

        try:
            lead_data = await self._fetch_lead_data(lead_id)
            if lead_data:
                lead_name = str(lead_data.get("name") or "")
                price = int(lead_data.get("price") or 0)
                status_name = str(lead_data.get("status_name") or lead_data.get("status_id") or "")
                pipeline_name = str(lead_data.get("pipeline_name") or lead_data.get("pipeline_id") or "")
                
                # Tags
                tags_raw = lead_data.get("tags") or lead_data.get("_embedded", {}).get("tags", [])
                if isinstance(tags_raw, list):
                    for t in tags_raw:
                        if isinstance(t, dict) and t.get("name"):
                            tags.append(str(t["name"]))
                        elif isinstance(t, str):
                            tags.append(t)

                # Custom fields
                for cf in lead_data.get("custom_fields_values") or []:
                    fn = cf.get("field_name") or cf.get("field_code")
                    vals = [str(v.get("value", "")) for v in cf.get("values", []) if v.get("value")]
                    if fn and vals:
                        custom_fields[str(fn)] = ", ".join(vals)

                # Contact lookup
                c_phone, c_user, c_name = await self._fetch_contact_info(lead_data)
                if c_phone and not contact_phone:
                    contact_phone = c_phone
                if c_user:
                    telegram_username = c_user
                if c_name:
                    contact_name = c_name

        except Exception as exc:
            logger.warning("[OMNICHANNEL] Error fetching lead data for #%s: %s", lead_id, exc)

        # Telegram History
        try:
            telegram_messages = await self._fetch_telegram_history(
                phone=contact_phone,
                username=telegram_username,
            )
        except Exception as exc:
            logger.debug("[OMNICHANNEL] Telegram history lookup error: %s", exc)

        return OmnichannelContext(
            lead_id=lead_id,
            lead_name=lead_name,
            price=price,
            status_name=status_name,
            pipeline_name=pipeline_name,
            responsible_user=responsible_user,
            tags=tags,
            custom_fields=custom_fields,
            contact_name=contact_name,
            contact_phone=contact_phone,
            telegram_username=telegram_username,
            telegram_messages=telegram_messages,
        )

    async def _fetch_lead_data(self, lead_id: int) -> Optional[Dict[str, Any]]:
        """Safely fetch lead details from AmoCRM."""
        if not self.amocrm:
            return None
        getter = getattr(self.amocrm, "get_lead_details", None) or getattr(self.amocrm, "get_lead", None)
        if callable(getter):
            res = getter(lead_id)
            return await res if asyncio.iscoroutine(res) else res
        return None

    async def _fetch_contact_info(self, lead_data: Dict[str, Any]) -> Tuple[str, str, str]:
        """Extract phone, telegram username, and contact name from lead's contact."""
        phone, username, name = "", "", ""
        contacts = lead_data.get("_embedded", {}).get("contacts", [])
        if not contacts or not self.amocrm:
            return phone, username, name

        first_cid = contacts[0].get("id")
        if not first_cid:
            return phone, username, name

        try:
            getter = getattr(self.amocrm, "get_contact_details", None) or getattr(self.amocrm, "get_contact", None)
            if callable(getter):
                res = getter(int(first_cid))
                c_details = await res if asyncio.iscoroutine(res) else res
                if c_details:
                    name = str(c_details.get("name") or "")
                    for cf in c_details.get("custom_fields_values") or []:
                        code = str(cf.get("field_code") or "").upper()
                        fn = str(cf.get("field_name") or "").upper()
                        for val in cf.get("values") or []:
                            v = str(val.get("value") or "")
                            if not v:
                                continue
                            if code == "PHONE" and not phone:
                                phone = v
                            elif any(k in fn or k in code for k in ["TELEGRAM", "TG", "USERNAME"]) and not username:
                                username = v.replace("@", "").strip()
        except Exception as exc:
            logger.debug("[OMNICHANNEL] Error fetching contact details: %s", exc)

        return phone, username, name

    async def _fetch_telegram_history(self, phone: str, username: str) -> List[str]:
        """Fetch recent telegram messages from tg_client if available."""
        if not self.tg_client or (not phone and not username):
            return []

        messages: List[str] = []
        try:
            entity = username or phone
            async for msg in self.tg_client.iter_messages(entity, limit=20):
                txt = str(getattr(msg, "text", "") or "").strip()
                if not txt:
                    continue
                sender = "Menejer/Biz" if getattr(msg, "out", False) else "Mijoz"
                dt = msg.date.strftime("%Y-%m-%d %H:%M") if getattr(msg, "date", None) else ""
                messages.append(f"[{dt}] {sender}: {txt}")
        except Exception as exc:
            logger.debug("[OMNICHANNEL] iter_messages failed for %s: %s", username or phone, exc)

        return list(reversed(messages))
