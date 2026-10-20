"""Hunter: amoCRM'ga yozilmay qolgan (`pending`) nomzodlarni qayta yuborish.

5 urinishdan keyin ham yozilmagan (`failed`) nomzodlar haqida owner'ga Telegram
xabari yuboriladi. Xabar ketgani `notified=1` bilan belgilanadi; yuborilmasa
keyingi aylanishda qayta urinadi. Quiet-hours'da (23:00–07:00) hech narsa qilmaydi.
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
from typing import Any, Dict, List

import requests

from src.time_utils import is_quiet_hours

logger = logging.getLogger("HunterRetryScheduler")

_INTERVAL_SECONDS = 900


def _amocrm():
    from src.api.routes.state import api_state

    if api_state.amocrm_instance:
        return api_state.amocrm_instance
    from src.services.core.crm.amocrm.sync import AmoCRMSync

    return AmoCRMSync()


def build_failure_text(rows: List[Dict[str, Any]]) -> str:
    lines = [f"⚠️ <b>Hunter: {len(rows)} ta lid amoCRM'ga yozilmadi</b>", ""]
    for row in rows:
        who = html.escape(str(row.get("name") or "Nomsiz"))
        phone = html.escape(str(row.get("phone") or "raqamsiz"))
        source = html.escape(str(row.get("source") or ""))
        error = html.escape(str(row.get("error") or "noma'lum"))
        lines.append(f"• {who} ({phone}) — {source}, {row.get('attempts')} urinish, xato: {error}")
    lines += ["", "Qo'lda kiritish kerak: /api/simple-crm/"]
    return "\n".join(lines)


def _send_owner(text: str) -> bool:
    from src.settings import settings

    token = settings.BOT_TOKEN.get_secret_value()
    owner = settings.OWNER_ID
    if not token or not owner:
        logger.warning("[HUNTER-RETRY] BOT_TOKEN yoki OWNER_ID yo'q, xabar yuborilmadi")
        return False
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": owner, "text": text, "parse_mode": "HTML"},
            timeout=20,
        )
        return response.status_code == 200
    except requests.RequestException as e:
        logger.warning("[HUNTER-RETRY] owner xabari xatosi: %s", type(e).__name__)
        return False


async def notify_failures_once(writer) -> int:
    if is_quiet_hours():
        return 0
    rows = await writer.unnotified_failures()
    if not rows:
        return 0
    if not await asyncio.to_thread(_send_owner, build_failure_text(rows)):
        return 0
    await writer.mark_notified([int(r["id"]) for r in rows])
    return len(rows)


async def hunter_retry_loop() -> None:
    """Har 15 daqiqada `pending` nomzodlarni qayta yuboradi, `failed` haqida xabar beradi."""
    from src.database_pool import db_pool
    from src.services.core.leads.hunter import HunterWriter

    if os.getenv("HUNTER_RETRY_ENABLED", "1") != "1":
        logger.info("[HUNTER-RETRY] Disabled by HUNTER_RETRY_ENABLED")
        return
    await asyncio.sleep(180)
    while True:
        try:
            writer = HunterWriter(_amocrm(), db_pool)
            stats = await writer.retry_pending()
            if stats["retried"] or stats["failed"]:
                logger.info("[HUNTER-RETRY] %s", stats)
            notified = await notify_failures_once(writer)
            if notified:
                logger.info("[HUNTER-RETRY] owner'ga %d ta failed lid haqida xabar", notified)
        except Exception as e:
            logger.error("[HUNTER-RETRY] Error: %s", e)
        await asyncio.sleep(_INTERVAL_SECONDS)
