"""Oisha CRM — Raqamli Voronka (Digital Pipeline) va Avtomatlashtirish Dvigateli.

Ushbu modul amoCRMʼning Digital Voronka imkoniyatlarini mahalliy
darajada bajaradi: bosqich oʻzgarganda avtomatik vazifalar yuklash,
Telegram bildirishnomalari va AI Surgical Mission taktikalarini ishga tushirish.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List, Optional

from src.services.core.crm.engine.schema import (
    DealModel,
    TaskCreate,
    TimelineEventCreate,
)
from src.services.core.crm.engine.store import OishaCrmStore

logger = logging.getLogger(__name__)

# Bosqichlar boʻyicha avtomatik vazifalar qoidalari (Default Triggers)
STAGE_AUTO_TASKS: Dict[str, Dict[str, Any]] = {
    "inbox": {
        "title": "Yangi lid bilan 15 daqiqada bogʻlanish",
        "task_type": "Qoʻngʻiroq qilish",
        "offset_minutes": 15,
    },
    "initial_contact": {
        "title": "Mijoz bilan birlamchi suhbat oʻtkazish va ehtiyojni bilish",
        "task_type": "Qoʻngʻiroq qilish",
        "offset_minutes": 60,
    },
    "spin_discovery": {
        "title": "SPIN savollar asosida muammo va yechimni chuqur tahlil qilish",
        "task_type": "Qoʻngʻiroq qilish",
        "offset_hours": 4,
    },
    "proposal_sent": {
        "title": "Tijoriy taklif koʻrib chiqilganini tekshirish",
        "task_type": "Qoʻngʻiroq qilish",
        "offset_hours": 24,
    },
    "meeting_scheduled": {
        "title": "Strategik uchrashuv oʻtkazish va taqdimot qilish",
        "task_type": "Uchrashuv",
        "offset_hours": 24,
    },
    "contract_signing": {
        "title": "Shartnoma va toʻlov hisobini nazorat qilish",
        "task_type": "Toʻlov nazorati",
        "offset_hours": 12,
    },
}


class CrmAutomationEngine:
    """Raqamli voronka avtomatizatsiyasi."""

    def __init__(self, store: OishaCrmStore) -> None:
        self.store = store

    def handle_stage_changed(self, deal: DealModel, stage_slug: str) -> Optional[int]:
        """Bitim yangi bosqichga oʻtganda avto-vazifa va harakatlarni bajarish."""
        rule = STAGE_AUTO_TASKS.get(stage_slug)
        if not rule:
            return None

        now = datetime.now()
        if "offset_minutes" in rule:
            due_dt = now + timedelta(minutes=rule["offset_minutes"])
        else:
            due_dt = now + timedelta(hours=rule.get("offset_hours", 2))

        due_str = due_dt.strftime("%Y-%m-%d %H:%M")
        task = self.store.create_task(
            TaskCreate(
                deal_id=deal.id,
                title=rule["title"],
                task_type=rule["task_type"],
                responsible_name=deal.responsible_name or "Shahnoza Abdijabborova",
                due_at=due_str,
            )
        )
        logger.info("Avto-vazifa yaratildi: deal #%d -> task #%d (%s)", deal.id, task.id, rule["title"])
        return task.id

    def build_telegram_alert(self, deal: DealModel, event_name: str) -> str:
        """Sotuvchilar yoki rahbarlar guruhi uchun chiroyli Telegram bildirishnomasi."""
        price_fmt = f"{deal.price:,.0f} soʻm".replace(",", " ") if deal.price else "Kiritilmagan"
        return (
            f"🔔 <b>Oisha CRM: {event_name}</b>\n\n"
            f"📌 <b>Bitim:</b> {deal.name} (#{deal.id})\n"
            f"👤 <b>Mijoz:</b> {deal.contact_name or 'Nomaʼlum'}\n"
            f"📞 <b>Telefon:</b> {deal.phone or 'Yoʻq'}\n"
            f"💰 <b>Byudjet:</b> {price_fmt}\n"
            f"📍 <b>Manba:</b> {deal.source or 'Toʻgʻridan-toʻgʻri'}\n"
            f"👨‍💼 <b>Masʼul:</b> {deal.responsible_name or 'Tayinlanmagan'}\n"
        )
