"""Egasiz inhouse lead eslatmasi.

Meta Lead Ads orqali inhouse'ga (Sotuv voronkasi, "taqsimot:inhouse" tegi) tushgan lead
30 daqiqadan beri hali bot nomida turgan bo'lsa, Target Leads guruhiga bir marta eslatma
yuboriladi. UTC lead'lariga tegilmaydi. Quiet-hours (23:00–07:00) vaqtida jim turadi.
"""
from __future__ import annotations

import asyncio
import html
import logging
import time
from typing import Any, Dict, List, Set

from src.services.core.crm.amocrm_pipeline_config import SALES_PIPELINE_ID
from src.time_utils import is_quiet_hours

logger = logging.getLogger("UnownedLeadAlert")

BOT_RESPONSIBLE_USER_ID = 13021974  # @jonbranding_assistant
INHOUSE_TAG = "taqsimot:inhouse"
UNOWNED_AFTER_SECONDS = 30 * 60
MAX_LEAD_AGE_SECONDS = 24 * 3600  # eski backlog uchun spam qilmaslik
CHECK_INTERVAL_SECONDS = 5 * 60

_alerted: Set[int] = set()


def find_unowned_inhouse_leads(leads: List[Dict[str, Any]], now: float) -> List[Dict[str, Any]]:
    """Egasi hali bot bo'lgan, 30 daqiqadan oshgan, ochiq inhouse lead'lar."""
    result = []
    for lead in leads:
        if lead.get("status_id") in (142, 143):
            continue
        if lead.get("responsible_user_id") != BOT_RESPONSIBLE_USER_ID:
            continue
        tags = {t.get("name") for t in (lead.get("_embedded") or {}).get("tags") or []}
        if INHOUSE_TAG not in tags:
            continue
        age = now - int(lead.get("created_at") or now)
        if UNOWNED_AFTER_SECONDS <= age <= MAX_LEAD_AGE_SECONDS and lead["id"] not in _alerted:
            result.append(lead)
    return result


def build_alert_text(lead: Dict[str, Any], now: float) -> str:
    minutes = int((now - int(lead.get("created_at") or now)) // 60)
    name = html.escape(str(lead.get("name") or "Nomsiz lead"))
    return (
        "⚠️ <b>Lead egasiz turibdi</b>\n\n"
        f"📌 {name}\n"
        f"⏱ {minutes} daqiqadan beri hech kim olmadi\n\n"
        "Lead'ni olgan menejer AmoCRM'da <b>Mas'ul</b>ga o'z ismini qo'ysin."
    )


async def check_unowned_leads_once(amocrm: Any) -> int:
    if is_quiet_hours():
        return 0
    leads = await amocrm.get_leads(limit=250, **{"filter[pipeline_id][]": SALES_PIPELINE_ID, "order[created_at]": "desc"})
    now = time.time()
    from src.services.core.instagram.leadgen_router import _notify_telegram

    sent = 0
    for lead in find_unowned_inhouse_leads(leads, now):
        lead_id = int(lead["id"])
        markup = {"inline_keyboard": [[{"text": "🧾 AmoCRM bitimi", "url": f"https://jonbranding.amocrm.ru/leads/detail/{lead_id}"}]]}
        if await asyncio.to_thread(_notify_telegram, build_alert_text(lead, now), markup):
            _alerted.add(lead_id)
            sent += 1
    return sent


async def unowned_lead_alert_loop() -> None:
    logger.info("[UNOWNED LEAD] inhouse egasiz lead nazorati ishga tushdi")
    await asyncio.sleep(30)
    from src.services.core.instagram.leadgen_router import _amocrm_instance

    while True:
        try:
            sent = await check_unowned_leads_once(_amocrm_instance())
            if sent:
                logger.info("[UNOWNED LEAD] %d ta eslatma yuborildi", sent)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("[UNOWNED LEAD] loop error: %s", exc, exc_info=True)
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
