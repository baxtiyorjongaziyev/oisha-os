"""Oisha CRM — Kiruvchi Lidlar Oqimi (Lead Intake Hub).

Saytlar, Telegram botlar, Meta Lead Ads va tashqi formalardan
tushadigan barcha yangi murojaatlarni qabul qilib, dublikatlarni
tekshiradi va «Saralanmaganlar» voronkasiga joylashtiradi.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

from src.services.core.crm.engine.automation import CrmAutomationEngine
from src.services.core.crm.engine.schema import (
    DealCreate,
    DealModel,
    IntakeLeadPayload,
    TimelineEventCreate,
)
from src.services.core.crm.engine.store import OishaCrmStore

logger = logging.getLogger(__name__)


def normalize_phone_number(phone: str) -> str:
    """Telefon raqamni toza +998 formatiga keltirish."""
    cleaned = re.sub(r"[^\d+]", "", phone.strip())
    if cleaned.startswith("8") and len(cleaned) == 11:
        cleaned = "+7" + cleaned[1:]
    elif cleaned.startswith("998") and not cleaned.startswith("+"):
        cleaned = "+" + cleaned
    elif len(cleaned) == 9 and not cleaned.startswith("+"):
        cleaned = "+998" + cleaned
    return cleaned


class LeadIntakeService:
    """Yangi lidlarni qabul qilish va saralash xizmati."""

    def __init__(self, store: OishaCrmStore, automation: Optional[CrmAutomationEngine] = None) -> None:
        self.store = store
        self.automation = automation or CrmAutomationEngine(store)

    def process_incoming_lead(self, payload: IntakeLeadPayload) -> Dict[str, Any]:
        """Yangi murojaatni qabul qilish."""
        clean_phone = normalize_phone_number(payload.phone)

        # 1. Mavjud faol bitimni tekshirish (Dublikatlarni himoyalash)
        with self.store._get_conn() as conn:
            existing = conn.execute(
                "SELECT id, name FROM crm_deals WHERE phone = ? AND is_active = 1 ORDER BY id DESC LIMIT 1",
                (clean_phone,),
            ).fetchone()

        if existing:
            deal_id = existing["id"]
            note_text = f"🔄 Qayta murojaat tushdi: \"{payload.name}\". Izoh: {payload.comment or 'Yoʻq'}"
            self.store.add_timeline_event(
                TimelineEventCreate(
                    deal_id=deal_id,
                    event_type="note",
                    author=payload.source,
                    text=note_text,
                )
            )
            logger.info("Mavjud bitimga qayta murojaat biriktirildi: deal #%d", deal_id)
            return {
                "status": "duplicate_merged",
                "deal_id": deal_id,
                "message": "Mijoz allaqachon mavjud, yangi xabar tarixga qoʻshildi",
            }

        # 2. Yangi bitim ochish (Default: Pipeline 1, Stage 1 — Saralanmaganlar)
        deal_create = DealCreate(
            name=payload.name or f"Murojaat {clean_phone}",
            pipeline_id=1,
            stage_id=1,
            phone=clean_phone,
            email=payload.email,
            company_name=payload.company_name,
            source=payload.source or "Veb-sayt",
            tags=payload.tags,
            custom_fields={
                **payload.custom_fields,
                "initial_comment": payload.comment or "",
            },
        )
        deal = self.store.create_deal(deal_create)

        # 3. Avto-vazifa yaratish ("15 daqiqada bogʻlanish")
        task_id = self.automation.handle_stage_changed(deal, "inbox")

        # 4. Telegram alert matnini shakllantirish
        alert_text = self.automation.build_telegram_alert(deal, "Yangi Kiruvchi Lid!")

        return {
            "status": "created",
            "deal_id": deal.id,
            "task_id": task_id,
            "telegram_alert": alert_text,
        }
