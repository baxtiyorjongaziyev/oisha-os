"""
Customer 360 Collector.

Aggregates client data across AmoCRM, Airtable, Telegram,
Instagram, and Voice Calls into a unified Customer360Profile.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from src.services.customer_360.models import CallInteraction, Customer360Profile

logger = logging.getLogger(__name__)


class Customer360Collector:
    """Collects and merges client context from all active channels."""

    def __init__(
        self,
        amocrm: Any = None,
        airtable: Any = None,
        telegram_client: Any = None,
        db: Any = None,
    ) -> None:
        self.amocrm = amocrm
        self.airtable = airtable
        self.telegram_client = telegram_client
        self.db = db

    async def collect_profile(
        self,
        identifier: str,
        lead_id: Optional[int] = None,
        phone: Optional[str] = None,
        name: Optional[str] = None,
        call_event: Optional[Dict[str, Any]] = None,
    ) -> Customer360Profile:
        """
        Build a Customer360Profile by looking up across all data sources.
        identifier can be a phone number, client name, or lead ID.
        """
        resolved_name = name or identifier
        resolved_phone = phone or ""
        resolved_lead_id = lead_id

        # Normalize phone if identifier looks like a phone number
        cleaned_id = "".join(c for c in identifier if c.isdigit() or c == "+")
        if len(cleaned_id) >= 9 and not resolved_phone:
            resolved_phone = cleaned_id

        profile = Customer360Profile(
            name=resolved_name,
            phone=resolved_phone,
            amocrm_lead_id=resolved_lead_id,
        )

        # 1. AmoCRM ma'lumotlarini yig'ish
        await self._enrich_from_amocrm(profile)

        # 2. Airtable ma'lumotlarini yig'ish
        await self._enrich_from_airtable(profile)

        # 3. Telegram yozishmalarini yig'ish
        await self._enrich_from_telegram(profile)

        # 4. Agar qo'ng'iroq tahlili berilgan bo'lsa, uni qo'shish
        if call_event:
            self._add_call_event(profile, call_event)

        # 5. Ma'lumotlar bazasidagi avvalgi qo'ng'iroqlarni yuklash
        await self._load_historical_calls(profile)

        return profile

    async def _enrich_from_amocrm(self, profile: Customer360Profile) -> None:
        """AmoCRM dan bitim, kontakt va statuslarni olish."""
        if not self.amocrm:
            try:
                from src.services.core.crm.amocrm_sync import AmoCRMSync
                self.amocrm = AmoCRMSync()
            except Exception as e:
                logger.debug(f"[C360] AmoCRMSync init fallback: {e}")
                return

        lead_data: Optional[Dict[str, Any]] = None
        try:
            if profile.amocrm_lead_id:
                lead_data = await asyncio.to_thread(
                    self.amocrm.get_lead, profile.amocrm_lead_id
                )
            elif profile.phone:
                lead_data = await asyncio.to_thread(
                    self.amocrm.find_active_lead_by_phone, profile.phone
                )
        except Exception as ex:
            logger.warning(f"[C360] AmoCRM fetch error: {ex}")

        if lead_data:
            profile.amocrm_lead_id = lead_data.get("id", profile.amocrm_lead_id)
            lead_name = lead_data.get("name")
            if lead_name and (profile.name == profile.phone or not profile.name):
                profile.name = lead_name
            profile.amocrm_lead_name = lead_name or ""
            profile.amocrm_budget = int(lead_data.get("price") or 0)
            
            # Teglar
            tags = lead_data.get("tags") or []
            if isinstance(tags, list):
                profile.tags = [t.get("name", str(t)) if isinstance(t, dict) else str(t) for t in tags]

            # Mas'ul menejer
            resp_id = lead_data.get("responsible_user_id")
            if resp_id:
                profile.responsible_manager = f"Menejer #{resp_id}"

            # Kontaktlar
            contacts = lead_data.get("contacts") or []
            if contacts and isinstance(contacts, list):
                c0 = contacts[0]
                if isinstance(c0, dict):
                    c_name = c0.get("name")
                    if c_name and profile.name == str(profile.amocrm_lead_id):
                        profile.name = c_name

    async def _enrich_from_airtable(self, profile: Customer360Profile) -> None:
        """Airtable dan loyiha ijrosi va moliyaviy balansni olish."""
        if not self.airtable:
            try:
                from src.services.core.airtable_sync import AirtableSync
                self.airtable = AirtableSync()
            except Exception as e:
                logger.debug(f"[C360] AirtableSync init fallback: {e}")
                return

        try:
            projects = await asyncio.to_thread(self.airtable.get_projects)
            if not projects:
                return

            query_lower = profile.name.lower()
            for rec in projects:
                fields = rec.get("fields", {})
                p_name = fields.get("Project Name") or fields.get("Name") or ""
                if query_lower in p_name.lower() or (p_name.lower() in query_lower and len(p_name) > 3):
                    profile.airtable_project_name = p_name
                    profile.airtable_phase = fields.get("Status") or fields.get("Phase") or "Jarayonda"
                    profile.airtable_paid = float(fields.get("Paid") or fields.get("To'langan") or 0.0)
                    profile.airtable_debt = float(fields.get("Debt") or fields.get("Qarz") or 0.0)
                    profile.airtable_deadline = fields.get("Deadline") or fields.get("Tugash sanasi") or ""
                    break
        except Exception as ex:
            logger.debug(f"[C360] Airtable enrich error: {ex}")

    async def _enrich_from_telegram(self, profile: Customer360Profile) -> None:
        """Telegram yozishmalarini olish."""
        if not profile.phone and not profile.telegram_username:
            return

        try:
            from src.services.call_analytics.omnichannel_context import OmnichannelContextFetcher
            fetcher = OmnichannelContextFetcher(self.amocrm, self.telegram_client)
            if profile.amocrm_lead_id:
                omni = await fetcher.fetch_lead_omnichannel_context(profile.amocrm_lead_id)
                if omni:
                    if omni.telegram_username:
                        profile.telegram_username = omni.telegram_username
                    if omni.telegram_messages:
                        profile.telegram_messages = omni.telegram_messages
        except Exception as ex:
            logger.debug(f"[C360] Telegram enrich error: {ex}")

    def _add_call_event(self, profile: Customer360Profile, call_event: Dict[str, Any]) -> None:
        """Yangi qo'ng'iroq voqeasini profilga qo'shish."""
        interaction = CallInteraction(
            call_id=str(call_event.get("call_id") or ""),
            timestamp=call_event.get("timestamp") or profile.updated_at,
            duration_seconds=int(call_event.get("duration_seconds") or 0),
            caller_phone=str(call_event.get("caller_phone") or profile.phone),
            manager_name=str(call_event.get("manager_name") or profile.responsible_manager or "Sotuvchi"),
            category=str(call_event.get("category") or "Mijoz"),
            summary=str(call_event.get("summary") or ""),
            client_mood=str(call_event.get("client_mood") or "Neytral"),
            client_talk_pct=int(call_event.get("client_talk_pct") or 50),
            manager_talk_pct=int(call_event.get("manager_talk_pct") or 50),
            seller_score=call_event.get("seller_score"),
            client_score=call_event.get("client_score"),
            agreed_datetime=call_event.get("agreed_datetime"),
            conversion_advice=call_event.get("conversion_advice"),
            transcript=str(call_event.get("transcript") or ""),
        )
        profile.calls.insert(0, interaction)

    async def _load_historical_calls(self, profile: Customer360Profile) -> None:
        """Bazadan avvalgi qo'ng'iroq yozuvlarini o'qish."""
        if not profile.phone and not profile.amocrm_lead_id:
            return
        try:
            from src.database import get_db
            db = get_db()
            conn = await db.get_connection()
            query = "SELECT call_id, duration_seconds, summary, client_mood, created_at, category FROM call_analyses WHERE caller_phone = ? OR lead_id = ? ORDER BY created_at DESC LIMIT 5"
            cursor = await conn.execute(query, (profile.phone, profile.amocrm_lead_id or 0))
            rows = await cursor.fetchall()
            existing_ids = {c.call_id for c in profile.calls}
            for r in rows:
                cid = str(r[0])
                if cid not in existing_ids:
                    profile.calls.append(
                        CallInteraction(
                            call_id=cid,
                            duration_seconds=int(r[1] or 0),
                            summary=str(r[2] or ""),
                            client_mood=str(r[3] or "Neytral"),
                            timestamp=str(r[4] or ""),
                            category=str(r[5] or "Mijoz"),
                            caller_phone=profile.phone,
                            manager_name=profile.responsible_manager or "Sotuvchi",
                        )
                    )
        except Exception as ex:
            logger.debug(f"[C360] Historical calls error: {ex}")
