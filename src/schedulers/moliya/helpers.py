"""Moliya hisobotlari uchun umumiy yordamchi funksiyalar."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Qancha qator ko'rsatiladi — xabar 4096 belgidan oshmasligi uchun
MAX_ROWS = 20

UZBEK_MONTHS = {
    "01": "Yanvar", "02": "Fevral", "03": "Mart", "04": "Aprel",
    "05": "May", "06": "Iyun", "07": "Iyul", "08": "Avgust",
    "09": "Sentabr", "10": "Oktabr", "11": "Noyabr", "12": "Dekabr",
}


def fmt(n: Any) -> str:
    """1234567.8 -> '1 234 568'"""
    try:
        return f"{round(float(n or 0)):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


def esc(s: Any) -> str:
    """Telegram HTML uchun xavfsiz matn."""
    if s is None:
        return "—"
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def select_name(value: Any) -> str:
    """singleSelect maydoni obyekt yoki matn bo'lishi mumkin."""
    if isinstance(value, dict):
        return (value.get("name") or "").strip()
    return (value or "").strip() if isinstance(value, str) else ""


def link_names(value: Any) -> str:
    """Linked-record maydonidan nomlarni chiqarish."""
    if not value:
        return ""
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, dict):
                out.append(item.get("name") or item.get("id") or "")
            else:
                out.append(str(item))
        return ", ".join(x for x in out if x)
    return str(value)


async def read_table(table_name: str) -> list[dict]:
    """AirtableSync sinxron — thread'da chaqiramiz, event loop bloklanmasin."""
    from src.services.core.airtable_sync import AirtableSync

    def _work() -> list[dict]:
        client = AirtableSync(table_name=table_name)
        return client.get_projects()

    try:
        return await asyncio.to_thread(_work)
    except Exception:
        logger.error("[MOLIYA] '%s' jadvalini o'qishda xato", table_name, exc_info=True)
        return []


_TITLE_FIELDS = ("Nomi", "Nom", "Name", "Kategoriya", "Kategoriya nomi")


def record_title(fields: dict) -> str:
    """Yozuvning ko'rinadigan nomi — ma'lum nom maydonlari, bo'lmasa birinchi matn."""
    for key in _TITLE_FIELDS:
        val = fields.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    for val in fields.values():
        if isinstance(val, str) and val.strip() and not val.startswith("rec"):
            return val.strip()
    return ""


async def read_name_map(*table_names: str) -> dict[str, str]:
    """Linked-record ID -> nom lug'ati. Birinchi mavjud jadval ishlatiladi."""
    for name in table_names:
        records = await read_table(name)
        if not records:
            continue
        out = {}
        for r in records:
            title = record_title(r.get("fields", {}) or {})
            if r.get("id") and title:
                out[r["id"]] = title
        if out:
            return out
    logger.warning("[MOLIYA] Nom lug'ati topilmadi: %s", ", ".join(table_names))
    return {}


async def send(text: str, topic_attr: str) -> bool:
    """Moliya guruhining kerakli topikiga yuborish.

    ``topic_attr`` — ``settings`` dagi topic o'zgaruvchisi nomi.
    Topic topilmasa guruhning umumiy oqimiga tushadi.
    """
    from src.settings import settings
    from src.services.core.tool_adapters import send_group_message_with_fallback

    group_id = getattr(settings, "HISOBCHI_FINANCE_GROUP_ID", None)
    if not group_id:
        logger.warning("[MOLIYA] HISOBCHI_FINANCE_GROUP_ID sozlanmagan — yuborilmadi")
        return False

    thread_id = getattr(settings, topic_attr, None)

    bot_token = os.environ.get("BOT_TOKEN") or getattr(settings, "BOT_TOKEN", None)
    if hasattr(bot_token, "get_secret_value"):
        bot_token = bot_token.get_secret_value()
    if not bot_token:
        logger.warning("[MOLIYA] BOT_TOKEN topilmadi — yuborilmadi")
        return False

    try:
        from telegram import Bot

        bot = Bot(token=bot_token)
        await send_group_message_with_fallback(
            bot,
            chat_id=group_id,
            text=text[:4000],
            parse_mode="HTML",
            thread_id=thread_id,
            allow_userbot_fallback=False,
        )
        return True
    except Exception:
        logger.error("[MOLIYA] Telegramga yuborishda xato", exc_info=True)
        return False


_ran_in_memory: set[tuple[str, str]] = set()


async def once_per_day(job_key: str, day: str) -> bool:
    """Kuniga bir marta ishlashini kafolatlash (restart'dan keyin ham).

    DB ishlamasa xotiradagi to'plam fallback bo'ladi — shu jarayon ichida
    takror yuborilmaydi.
    """
    key = (job_key, day)
    if key in _ran_in_memory:
        return False
    _ran_in_memory.add(key)
    try:
        from src.db import get_db

        return await get_db().claim_job_run(job_key, day)
    except Exception:
        logger.warning("[MOLIYA] job dedup DB ishlamadi (%s)", job_key, exc_info=True)
        return True


async def release_day(job_key: str, day: str) -> None:
    """Yuborish muvaffaqiyatsiz bo'lsa claim'ni bo'shatish — keyingi sikl qayta urinadi."""
    _ran_in_memory.discard((job_key, day))
    try:
        from src.db import get_db

        await get_db().release_job_run(job_key, day)
    except Exception:
        logger.warning("[MOLIYA] job claim bo'shatilmadi (%s)", job_key, exc_info=True)


async def run_once_per_day(job_key: str, day: str, runner) -> None:
    """Claim -> runner; runner False qaytarsa yoki yiqilsa claim bo'shatiladi."""
    if not await once_per_day(job_key, day):
        return
    ok = False
    try:
        ok = bool(await runner())
    finally:
        if not ok:
            logger.warning("[MOLIYA] %s yuborilmadi — qayta urinish uchun bo'shatildi", job_key)
            await release_day(job_key, day)
