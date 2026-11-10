"""
Farmer Transition Engine.
Sotuv boʻlimida yopilgan (Won / 142) bitimlarni avtomatik
Farmer (Loyiha & Brief / 80215334) voronkasiga oʻtkazish xizmati.
"""

from __future__ import annotations

import asyncio
import html
import logging
import time
from typing import Any, Dict, List, Optional

from src.services.core.crm.amocrm_pipeline_config import (
    FARMER_PIPELINE_ID,
    SALES_PIPELINE_ID,
    STATUS_WON,
)
from src.services.core.crm.amocrm_sync import AmoCRMSync
from src.settings import settings

logger = logging.getLogger("FarmerTransition")

DEFAULT_FARMER_START_STATUS_ID = 80215334  # Loyiha va Brief
DEFAULT_TASK_HOURS = 24


class FarmerTransitionService:
    """Sotuv bitimlarini Farmer (yetkazib berish) voronkasiga uzatuvchi servis."""

    def __init__(
        self,
        amocrm: Optional[AmoCRMSync] = None,
        bot_runtime: Any = None,
        db: Any = None,
    ) -> None:
        self.amocrm = amocrm or AmoCRMSync()
        self.bot_runtime = bot_runtime
        self.db = db

    async def hand_off_to_farmer(
        self,
        sales_lead_id: int,
        lead_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Sotuv bitimini Farmer voronkasiga xavfsiz va dublikatsiz oʻtkazish."""
        if not sales_lead_id:
            return {"success": False, "reason": "empty_sales_lead_id"}

        already_done = await self._is_already_transitioned(sales_lead_id)
        if already_done:
            logger.info("[FARMER] Lead %s allaqachon Farmerʼga oʻtkazilgan.", sales_lead_id)
            return {"success": False, "reason": "already_transitioned"}

        lead = lead_data or await self.amocrm.get_lead(sales_lead_id)
        if not lead:
            logger.warning("[FARMER] Lead %s maʼlumotlari olinmadi.", sales_lead_id)
            return {"success": False, "reason": "lead_not_found"}

        status_id = int(lead.get("status_id") or 0)
        pipeline_id = int(lead.get("pipeline_id") or 0)
        if status_id != STATUS_WON or (pipeline_id and pipeline_id != SALES_PIPELINE_ID):
            logger.info(
                "[FARMER] Lead %s mos kelmadi (status=%s, pipeline=%s).",
                sales_lead_id,
                status_id,
                pipeline_id,
            )
            return {"success": False, "reason": "lead_not_eligible_for_farmer"}

        farmer_lead_id = await self._create_farmer_deal(sales_lead_id, lead)
        if not farmer_lead_id:
            return {"success": False, "reason": "farmer_deal_creation_failed"}

        await self._create_onboarding_task(farmer_lead_id, lead)
        await self._record_transition_note(sales_lead_id, farmer_lead_id)
        await self._mark_transitioned(sales_lead_id, farmer_lead_id)
        await self._notify_team(sales_lead_id, farmer_lead_id, lead)

        return {
            "success": True,
            "sales_lead_id": sales_lead_id,
            "farmer_lead_id": farmer_lead_id,
        }

    async def _is_already_transitioned(self, sales_lead_id: int) -> bool:
        """Oldin oʻtkazilganligini tekshirish (idempotentlik)."""
        if not self.db:
            return False
        key = f"farmer_transition:{sales_lead_id}"
        try:
            conn = await self.db.get_connection()
            res = conn.execute("SELECT value FROM kv_store WHERE key = ?", (key,))
            if hasattr(res, "__await__"):
                res = await res
            row = res.fetchone() if hasattr(res, "fetchone") else None
            return bool(row)
        except Exception as exc:
            logger.debug("[FARMER] KV check error: %s", exc)
            return False

    async def _mark_transitioned(self, sales_lead_id: int, farmer_lead_id: int) -> None:
        """Oʻtkazilganlik holatini bazada saqlash."""
        if not self.db:
            return
        key = f"farmer_transition:{sales_lead_id}"
        now_ts = int(time.time())
        val = f"{farmer_lead_id}:{now_ts}"
        try:
            conn = await self.db.get_connection()
            res = conn.execute(
                "INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
                (key, val),
            )
            if hasattr(res, "__await__"):
                await res
        except Exception as exc:
            logger.warning("[FARMER] KV save error: %s", exc)

    async def _create_farmer_deal(
        self,
        sales_lead_id: int,
        lead: Dict[str, Any],
    ) -> Optional[int]:
        """Farmer voronkasida yangi bitim yaratish."""
        raw_name = str(lead.get("name") or f"Lid #{sales_lead_id}")
        brand_name = self._extract_field_value(lead, 1551701)
        farmer_name = f"[Farmer] {brand_name or raw_name}"
        price = int(lead.get("price") or 0)

        custom_fields = self._filter_forwardable_custom_fields(lead)
        contacts = lead.get("_embedded", {}).get("contacts", []) or []

        url = f"{self.amocrm.base_url}/api/v4/leads"
        payload_lead: Dict[str, Any] = {
            "name": farmer_name,
            "pipeline_id": FARMER_PIPELINE_ID,
            "status_id": DEFAULT_FARMER_START_STATUS_ID,
            "price": price,
        }
        if custom_fields:
            payload_lead["custom_fields_values"] = custom_fields
        if contacts:
            payload_lead["_embedded"] = {
                "contacts": [{"id": int(c.get("id"))} for c in contacts if c.get("id")]
            }

        headers = self.amocrm._get_headers()
        import requests

        try:
            resp = await asyncio.to_thread(
                requests.post,
                url,
                headers=headers,
                json=[payload_lead],
                timeout=25,
            )
            if resp.status_code in (200, 201):
                leads_data = resp.json().get("_embedded", {}).get("leads", []) or []
                if leads_data and leads_data[0].get("id"):
                    new_id = int(leads_data[0]["id"])
                    logger.info("[FARMER] Yangi Farmer biti yaratildi: #%s", new_id)
                    return new_id
            logger.error("[FARMER] Farmer bitimi yaratishda xato: HTTP %s %s", resp.status_code, resp.text[:200])
        except Exception as exc:
            logger.error("[FARMER] Farmer bitimi yaratishda istisno: %s", exc)
        return None

    def _extract_field_value(self, lead: Dict[str, Any], field_id: int) -> Optional[str]:
        """Lid custom fields orasidan qiymatni ajratib olish."""
        fields = lead.get("custom_fields_values") or []
        for f in fields:
            if f.get("field_id") == field_id:
                values = f.get("values") or []
                if values and values[0].get("value"):
                    return str(values[0]["value"]).strip()
        return None

    def _filter_forwardable_custom_fields(self, lead: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Loyiha uchun kerakli maydonlarni koʻchirib oʻtkazish."""
        allowed_ids = {
            1034663,  # Lead manbasi
            1034673,  # Faoliyat sohasi
            1037937,  # Telegram @username
            1427493,  # Mijozning ehtiyoji (AI)
            1427563,  # Google Drive folder
            1545967,  # Qoldiq toʻlov sanasi
            1545969,  # Avans summasi
            1551701,  # Brend / Biznes nomi
            1552241,  # Xizmat
        }
        res: List[Dict[str, Any]] = []
        for f in lead.get("custom_fields_values") or []:
            if f.get("field_id") in allowed_ids:
                res.append(
                    {
                        "field_id": f["field_id"],
                        "values": f.get("values", []),
                    }
                )
        return res

    async def _create_onboarding_task(self, farmer_lead_id: int, lead: Dict[str, Any]) -> bool:
        """Farmer loyihasi uchun dastlabki onboarding vazifasini ochish."""
        deadline = int(time.time()) + (DEFAULT_TASK_HOURS * 3600)
        task_text = (
            "🎯 Oisha-OS: Yangi loyiha onboardingi boshlash, mijoz briefini "
            "toʻldirish va loyiha ish rejasini tasdiqlash."
        )
        try:
            res = await self.amocrm.create_task(
                element_id=farmer_lead_id,
                text=task_text,
                complete_till=deadline,
                responsible_user_id=lead.get("responsible_user_id"),
            )
            return bool(res)
        except Exception as exc:
            logger.warning("[FARMER] Onboarding vazifasi ochishda xato: %s", exc)
            return False

    async def _record_transition_note(self, sales_lead_id: int, farmer_lead_id: int) -> None:
        """Sotuv kartasiga Farmer loyihasi havolasini qayd etish."""
        note_text = (
            f"🚀 Bitim muvaffaqiyatli yopildi va Farmer voronkasiga uzatildi.\n"
            f"Farmer Lead ID: #{farmer_lead_id}\n"
            f"Bosqich: Loyiha va Brief\n"
            f"Havola: https://jonbranding.amocrm.ru/leads/detail/{farmer_lead_id}"
        )
        try:
            await self.amocrm.add_lead_note(sales_lead_id, note_text)
        except Exception as exc:
            logger.debug("[FARMER] Eslatma yozishda xato: %s", exc)

    async def _notify_team(
        self,
        sales_lead_id: int,
        farmer_lead_id: int,
        lead: Dict[str, Any],
    ) -> None:
        """Telegram guruhiga bayramona xabar yuborish."""
        if not self.bot_runtime:
            return
        group_id = (
            getattr(settings, "CRM_GROUP_ID", None)
            or getattr(settings, "TEAM_GROUP_ID", None)
        )
        if not group_id:
            return

        name = html.escape(str(lead.get("name") or f"Lid #{sales_lead_id}"))
        price = int(lead.get("price") or 0)
        price_str = f"{price:,}".replace(",", " ")

        msg = (
            f"🎉 <b>Yangi Loyiha — Farmer Voronkasiga Oʻtdi!</b>\n\n"
            f"📌 <b>Loyiha:</b> {name}\n"
            f"💰 <b>Summa:</b> {price_str} soʻm\n"
            f"📂 <b>Voronka:</b> Farmer bosqichlari ➔ Loyiha va Brief\n"
            f"🔗 <a href='https://jonbranding.amocrm.ru/leads/detail/{farmer_lead_id}'>amoCRM Farmer Kartasi</a>\n\n"
            f"🎯 <i>Vazifa: 24 soat ichida mijoz briefi olinishi va onboarding boshlanishi shart!</i>"
        )
        try:
            await self.bot_runtime.send_message(
                chat_id=group_id,
                text=msg,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception as exc:
            logger.warning("[FARMER] Telegram xabarnoma xatosi: %s", exc)
