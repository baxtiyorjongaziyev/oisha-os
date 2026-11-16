"""Kunlik "pul keltiradigan eng muhim ish" kun tartibi (Toshkent vaqti, Du–Shan).

09:30 — har bir aʼzoga aniq ish taklifi (amoCRM maʼlumotidan)
11:30 — javob bermaganlarga bir marta muloyim eslatma
15:00 — kelishilgan ish boʻyicha bir marta "qanday ketyapti?"
18:30 — egasiga kunlik xulosa

Yakshanba va ish vaqtidan tashqarida hech narsa yuborilmaydi.
`DAILY_PRIORITY_ENABLED=0` bilan butunlay oʻchiriladi.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

from src.time_utils import get_local_now

logger = logging.getLogger("DailyPriority")

SLOTS: Dict[Tuple[int, int], str] = {
    (9, 30): "morning",
    (11, 30): "nudge",
    (15, 0): "followup",
    (18, 30): "summary",
}


def is_enabled() -> bool:
    from src.services.core.daily_priority.engine import is_enabled as _enabled

    return _enabled()


def slot_for(now) -> Optional[str]:
    if now.weekday() >= 6:  # yakshanba
        return None
    return SLOTS.get((now.hour, now.minute))


def _owner_id() -> Optional[int]:
    try:
        from src.settings import settings

        value = getattr(settings, "OWNER_ID", None)
        return int(value) if value else None
    except Exception:
        return None


async def run_slot(slot: str, bot: Any, now) -> Any:
    from src.services.core.daily_priority import engine

    runners: Dict[str, Callable[[], Awaitable[Any]]] = {
        "morning": lambda: engine.run_morning(bot, now),
        "nudge": lambda: engine.run_nudge(bot, now),
        "followup": lambda: engine.run_followup(bot, now),
        "summary": lambda: engine.run_owner_summary(bot, now, _owner_id()),
    }
    return await runners[slot]()


async def daily_priority_checkin_loop(bot_runtime: Any) -> None:
    await asyncio.sleep(5)
    logger.info("[DAILY] Kun tartibi ishga tushdi: 09:30 / 11:30 / 15:00 / 18:30 (Du–Shan).")
    last_fired = ""
    while True:
        try:
            now = get_local_now()
            slot = slot_for(now) if is_enabled() else None
            fire_key = f"{now:%Y-%m-%d-%H-%M}"
            if slot and fire_key != last_fired:
                last_fired = fire_key
                result = await run_slot(slot, bot_runtime, now)
                logger.info("[DAILY] %s bajarildi: %s", slot, result)
        except Exception:
            logger.error("[DAILY] Kun tartibida xato.", exc_info=True)
        await asyncio.sleep(20)
