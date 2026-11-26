"""Ish kunlari 10:00 (Toshkent) da Airtable boʻshliqlarini loyihalar guruhiga yuboradi.

PMʼlar ismi bilan belgilanadi. ``AIRTABLE_GAPS_ENABLED=0`` bilan oʼchiriladi.
Kuniga bir marta: restartdan keyin 10:00–10:29 oynasidan tashqarida yuborilmaydi.
"""
from __future__ import annotations

import asyncio
import logging
import os

from src.time_utils import get_local_now

logger = logging.getLogger(__name__)

SEND_HOUR = 10
WINDOW_MINUTES = 30
WORKDAYS = frozenset({0, 1, 2, 3, 4})


def _to_int(raw) -> int | None:
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


def resolve_group_id(fallback=None) -> int | None:
    """AIRTABLE_GAPS_GROUP_ID > settings.PROJECTS_GROUP_ID (loyihalar guruhi) > fallback."""
    override = _to_int(os.getenv("AIRTABLE_GAPS_GROUP_ID", ""))
    if override:
        return override
    try:
        from src.settings import settings

        projects = _to_int(getattr(settings, "PROJECTS_GROUP_ID", None))
    except Exception:
        projects = None
    return projects or fallback


def resolve_topic_id() -> int | None:
    """Topic faqat guruh AIRTABLE_GAPS_GROUP_ID bilan aniq berilganda qoʻllanadi.

    Aks holda eski guruh topigi yangi guruhga tushib xabarni buzmasligi uchun
    General (thread yoʻq) ishlatiladi.
    """
    if not _to_int(os.getenv("AIRTABLE_GAPS_GROUP_ID", "")):
        return None
    topic = _to_int(os.getenv("AIRTABLE_GAPS_TOPIC_ID", ""))
    return topic if topic and topic > 1 else None


def should_send(now, sent_on) -> bool:
    return (
        now.weekday() in WORKDAYS
        and now.hour == SEND_HOUR
        and now.minute < WINDOW_MINUTES
        and sent_on != now.date()
    )


async def send_missing_fields_report(bot_client, team_group_id, today) -> bool:
    from src.services.core.airtable.missing_fields import build_report_message

    text = await asyncio.to_thread(build_report_message, today)
    if not text:
        logger.info("[AT-GAPS] Boʻshliq yoʻq yoki maʼlumot olinmadi — yuborilmadi")
        return False
    kwargs = {"parse_mode": "html", "disable_web_page_preview": True}
    topic = resolve_topic_id()
    if topic:
        kwargs["message_thread_id"] = topic
    await bot_client.send_message(team_group_id, text, **kwargs)
    logger.info("[AT-GAPS] Hisobot yuborildi")
    return True


async def airtable_missing_fields_loop(bot_client, team_group_id) -> None:
    team_group_id = resolve_group_id(team_group_id)
    if os.getenv("AIRTABLE_GAPS_ENABLED", "1") != "1" or not bot_client or not team_group_id:
        logger.info("[AT-GAPS] Oʻchirilgan yoki guruh sozlanmagan")
        return
    await asyncio.sleep(120)
    sent_on = None
    while True:
        try:
            now = get_local_now()
            if should_send(now, sent_on):
                sent_on = now.date()
                await send_missing_fields_report(bot_client, team_group_id, now.date())
        except Exception as exc:
            logger.error("[AT-GAPS] Loop error: %s", exc)
        await asyncio.sleep(60)
