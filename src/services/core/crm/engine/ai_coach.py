"""Oisha CRM — AI Sotuv Murabbiyi va Surgical Missions Dvigateli.

Ushbu modul har bir bitim uchun BANT va SPIN metodologiyasi
boʻyicha tezkor tahlil qilib, sotuvchi uchun 3 ta aniq
operatsion qadamni (Surgical Mission) belgilab beradi.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.services.core.crm.engine.schema import DealModel, TimelineEventCreate
from src.services.core.crm.engine.store import OishaCrmStore

logger = logging.getLogger(__name__)


class CrmAiCoach:
    """Sotuvchilar uchun AI murabbiy va missiyalar generatori."""

    def __init__(self, store: OishaCrmStore) -> None:
        self.store = store

    def generate_surgical_mission(self, deal_id: int) -> Dict[str, Any]:
        """Bitim boʻyicha 3 qadamli operatsion taktikani generatsiya qilish."""
        deal = self.store.get_deal(deal_id)
        if not deal:
            return {"error": "Bitim topilmadi"}

        cf = deal.custom_fields
        pain = cf.get("initial_comment") or cf.get("pain_point") or "Umumiy xizmatlar boʻyicha qiziqish"
        budget = deal.price if deal.price > 0 else "Belgilanmagan"

        # 3 ta aniq operatsion qadam
        step_1 = f"1. Qualify: Mijozning asosiy ogʻrigʻini aniqlash (\"{pain}\" boʻyicha 2 ta ochiq savol berish)."
        step_2 = "2. Value: Jon Branding portfolio keyslaridan 1 ta mos namuna koʻrsatish va qiymatni asoslash."
        step_3 = "3. Close: Aniq sanaga 15 daqiqalik strategik Zoom yoki ofis uchrashuvini belgilash."

        mission_text = (
            f"🎯 <b>Oisha AI Surgical Mission (Bitim #{deal.id}):</b>\n\n"
            f"{step_1}\n"
            f"{step_2}\n"
            f"{step_3}\n\n"
            f"💡 <i>Tavsiya etilgan byudjet yoʻnalishi: {budget}</i>"
        )

        # Kartochka tarixiga yozish
        self.store.add_timeline_event(
            TimelineEventCreate(
                deal_id=deal.id,
                event_type="ai_mission",
                author="Oisha AI",
                text=mission_text,
                metadata={
                    "step_1": step_1,
                    "step_2": step_2,
                    "step_3": step_3,
                },
            )
        )

        return {
            "success": True,
            "deal_id": deal.id,
            "mission": {
                "step_1": step_1,
                "step_2": step_2,
                "step_3": step_3,
            },
            "formatted_text": mission_text,
        }
