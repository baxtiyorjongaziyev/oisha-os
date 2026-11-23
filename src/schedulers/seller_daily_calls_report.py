"""Har bir sotuvchiga kunlik qoʻngʻiroqlar hisoboti — oʻz leads topicʻiga.

MoiZvonki "Общая статистика" koʻrinishi (Jami / Kiruvchi / Chiquvchi × Jami, Javob berildi,
Javobsiz, Davomiylik) Bot API Rich/Widget jadvali sifatida yuboriladi
(``send_oisha_kpi_report``: guruhda Rich Table, xatoda oddiy matn).
Sotuvchilar roʻyxati va topiclar ``remote_staff_checkin_scheduler.get_reps()`` dan olinadi.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional

logger = logging.getLogger("SellerDailyCalls")

DIRECTION_IN = 0  # MoiZvonki: 0 = kiruvchi, 1 = chiquvchi


@dataclass
class _Bucket:
    total: int = 0
    answered: int = 0
    talk_sec: int = 0

    @property
    def missed(self) -> int:
        return self.total - self.answered


@dataclass
class SellerCallStats:
    all: _Bucket
    incoming: _Bucket
    outgoing: _Bucket


def is_enabled() -> bool:
    val = os.getenv("SELLER_DAILY_CALLS_REPORT_ENABLED", "1").strip().lower()
    return val in {"1", "true", "yes", "on"}


def fmt_hms(seconds: int) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def aggregate(calls: Iterable[dict], emails: Iterable[str]) -> SellerCallStats:
    wanted = {e.strip().lower() for e in emails if e and e.strip()}
    stats = SellerCallStats(_Bucket(), _Bucket(), _Bucket())
    for c in calls:
        if (c.get("user_account") or "").strip().lower() not in wanted:
            continue
        side = stats.incoming if c.get("direction") == DIRECTION_IN else stats.outgoing
        answered = bool(int(c.get("answered") or 0))
        dur = int(c.get("duration") or 0) if answered else 0
        for b in (stats.all, side):
            b.total += 1
            if answered:
                b.answered += 1
                b.talk_sec += dur
    return stats


def table_rows(s: SellerCallStats) -> List[List[Any]]:
    cols = (s.all, s.incoming, s.outgoing)
    return [
        ["Jami", *[b.total for b in cols]],
        ["Javob berildi", *[b.answered for b in cols]],
        ["Javobsiz", *[b.missed for b in cols]],
        ["Davomiylik", *[fmt_hms(b.talk_sec) for b in cols]],
    ]


def _day_bounds(day: datetime) -> tuple[int, int]:
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(start.timestamp()), int((start + timedelta(days=1)).timestamp()) - 1


def _fetch_day_calls(start_ts: int, end_ts: int) -> Optional[List[dict]]:
    email = os.environ.get("MOIZVONKI_EMAIL", "")
    api_key = os.environ.get("MOIZVONKI_API_KEY", "")
    if not email or not api_key:
        logger.warning("[SELLER_CALLS] MOIZVONKI_EMAIL/API_KEY yoʻq — hisobot oʻtkazib yuborildi.")
        return None
    from scripts.daily_sales_calls_report import fetch_calls

    return fetch_calls(email, api_key, start_ts, end_ts, os.environ.get("MOIZVONKI_DOMAIN", ""))


def _default_client() -> Any:
    from src import config
    from src.services.core.telegram.ai_features.bot_api_client import TelegramBotAPI10Client

    token = config.BOT_TOKEN
    token = token.get_secret_value() if hasattr(token, "get_secret_value") else str(token or "")
    return TelegramBotAPI10Client(token) if token else None


async def send_seller_daily_call_reports(
    now: datetime,
    *,
    client: Any = None,
    fetch_calls: Callable[[int, int], Optional[List[dict]]] = _fetch_day_calls,
    reps: Optional[List[Dict[str, Any]]] = None,
) -> int:
    """Bugungi qoʻngʻiroqlar statistikasini har bir sotuvchining topicʻiga yuboradi.

    Qaytaradi: muvaffaqiyatli yuborilgan hisobotlar soni.
    """
    from src.schedulers.remote_staff_checkin_scheduler import (
        DEFAULT_REP_EMAILS,
        get_reps,
        get_target_destination,
    )
    from src.services.core.telegram.ai_features.kpi_reports import send_oisha_kpi_report

    client = client or _default_client()
    if client is None:
        logger.warning("[SELLER_CALLS] BOT_TOKEN yoʻq.")
        return 0

    start_ts, end_ts = _day_bounds(now)
    calls = await asyncio.to_thread(fetch_calls, start_ts, end_ts)
    if calls is None:
        return 0

    chat_id, rayxon_topic = get_target_destination()
    day = now.strftime("%d.%m.%Y")
    sent = 0
    for rep in reps if reps is not None else get_reps():
        key = str(rep.get("key") or "")
        name = str(rep.get("name") or key)
        topic = rayxon_topic if key == "rayxon" else rep.get("topic")
        stats = aggregate(calls, rep.get("emails") or (DEFAULT_REP_EMAILS if key == "rayxon" else []))
        a = stats.all
        rate = round(100 * a.answered / a.total) if a.total else 0
        try:
            await send_oisha_kpi_report(
                client,
                chat_id,
                title=f"{name} — kunlik qoʻngʻiroqlar",
                subtitle=f"{day} • MoiZvonki",
                kpis=[("Jami", a.total), ("Javob", f"{a.answered} ({rate}%)"),
                      ("Suhbat", fmt_hms(a.talk_sec))],
                table_headers=["Koʻrsatkich", "Jami", "Kiruvchi", "Chiquvchi"],
                table_rows=table_rows(stats),
                numeric_cols=(1, 2, 3),
                is_private_chat=False,
                message_thread_id=int(topic) if topic else None,
            )
            sent += 1
            logger.info("[SELLER_CALLS] %s hisobot yuborildi (topic=%s)", name, topic)
        except Exception:
            logger.exception("[SELLER_CALLS] %s hisobot yuborilmadi", name)
    return sent
