"""Har bir qo'ng'iroq hodisasi — javob berilganmi yoki yo'qmi.

KO'R NUQTA (2026-08-10 gacha):
    `call_analyzer` faqat YOZUVI BOR qo'ng'iroqlarni ko'rardi:

        if not audio_url:
            continue

    Javobsiz qo'ng'iroqda yozuv bo'lmaydi — demak u bazaga umuman
    tushmasdi. Natijada teskari rag'bat paydo bo'lgan edi:

        Sotuvchi qancha ko'p qo'ng'iroqni ko'tarmasa, uning o'rtacha bali
        SHUNCHA YAXSHI ko'rinadi — chunki faqat javob berganlari baholanadi.

    Ya'ni "qaysi sotuvchi pul yo'qotyapti?" degan savolga eng to'g'ri javob
    ba'zan umuman telefon ko'tarmaydigan odam bo'lishi mumkin, va u eski
    tizimda eng yaxshi ko'rinardi.

NEGA ALOHIDA JADVAL:
    Bu qatorlarni `call_analyses` ga qo'shish xavfli edi — u yerdan
    o'qiydigan bir nechta joy ball bo'yicha FILTRLAMAYDI
    (`sales_quality._fetch_call_analysis_rows` "SELECT *" qiladi,
    `intelligence.get_latest_call_analysis` esa oxirgi qatorni oladi).
    Baholanmagan qo'ng'iroq u yerda "0 ball" bo'lib ko'rinardi va
    sotuvchini asossiz jazolardi. Shuning uchun sifat tahlili
    `call_analyses` da, qo'ng'iroq HAJMI shu yerda turadi.

JAVOB BERILGANINI ANIQLASH:
    `duration > 0` — gaplashilgan vaqt bo'lsa, qo'ng'iroq javob berilgan.
    Bu provayderdan qat'i nazar ishonchli signal. AmoCRM `call_status`
    kodlari provayderga qarab farq qiladi, shuning uchun ular xom holda
    saqlanadi, lekin mantiq ularga TAYANMAYDI.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set

from src.services.utils.db_rows import fetch_rows
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)

TABLE = "call_events"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS call_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id TEXT UNIQUE,
    lead_id INTEGER,
    manager_id INTEGER,
    manager_name TEXT,
    direction TEXT,
    phone TEXT,
    duration_seconds INTEGER DEFAULT 0,
    answered INTEGER DEFAULT 0,
    has_recording INTEGER DEFAULT 0,
    analyzed INTEGER DEFAULT 0,
    call_status TEXT,
    occurred_at TEXT,
    created_at TEXT
)
"""

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_call_events_created ON call_events(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_call_events_manager ON call_events(manager_name)",
    "CREATE INDEX IF NOT EXISTS idx_call_events_lead ON call_events(lead_id)",
)

_ensured: Set[int] = set()

_SELECT_RECENT_SQL = (
    "SELECT manager_name, duration_seconds, answered, has_recording, "
    "analyzed, direction, lead_id, call_id, created_at "
    "FROM call_events WHERE created_at >= datetime('now', ?) "
    "ORDER BY created_at DESC"
)


async def _maybe_await(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        value = row.get(key, default)
    else:
        value = getattr(row, key, default)
    return default if value is None else value


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


async def ensure_call_events_schema(db: Any, *, force: bool = False) -> bool:
    """Jadval borligiga kafolat. Fail-soft — chaqiruvchi oqim to'xtamaydi."""
    if db is None:
        return False
    if not force and id(db) in _ensured:
        return True
    try:
        conn = await _maybe_await(db.get_connection())
        if conn is None:
            return False
        await _maybe_await(conn.execute(_CREATE_TABLE))
        for statement in _INDEXES:
            try:
                await _maybe_await(conn.execute(statement))
            except Exception as exc:
                logger.warning("[CALL EVENTS] Indeks yaratilmadi: %s", exc)
        await _maybe_await(conn.commit())
    except Exception as exc:
        logger.warning("[CALL EVENTS] Migratsiya yiqildi: %s", exc)
        return False
    _ensured.add(id(db))
    return True


def reset_schema_cache() -> None:
    """Testlar uchun."""
    _ensured.clear()


def is_answered(duration_seconds: Any) -> bool:
    """Qo'ng'iroqqa javob berilganmi?

    Gaplashilgan vaqt bo'lsa — javob berilgan. Yozuv borligi mezon EMAS:
    yozuv sozlamalari o'chirilgan bo'lishi mumkin, lekin suhbat bo'lgan.
    """
    return _to_int(duration_seconds) > 0


def format_duration(seconds: float) -> str:
    """Soniyani `mm:ss` ko'rinishida."""
    total = max(0, int(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


@dataclass
class CallVolume:
    """Qo'ng'iroq hajmi ko'rsatkichlari (reklamadagi panel)."""

    manager_name: str = ""
    total: int = 0
    answered: int = 0
    missed: int = 0
    analyzed: int = 0
    total_talk_seconds: int = 0

    @property
    def answer_rate(self) -> float:
        return (self.answered / self.total * 100) if self.total else 0.0

    @property
    def avg_duration_seconds(self) -> float:
        """O'rtacha suhbat — FAQAT javob berilganlar bo'yicha.

        Javobsizlarni ham qo'shsak (0 soniya), o'rtacha sun'iy pasayadi va
        ko'rsatkich ikkita boshqa muammoni bitta raqamga aralashtiradi.
        """
        return (self.total_talk_seconds / self.answered) if self.answered else 0.0

    @property
    def avg_duration_label(self) -> str:
        return format_duration(self.avg_duration_seconds)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manager_name": self.manager_name,
            "total": self.total,
            "answered": self.answered,
            "missed": self.missed,
            "analyzed": self.analyzed,
            "answer_rate": round(self.answer_rate, 1),
            "avg_duration_seconds": round(self.avg_duration_seconds),
            "avg_duration": self.avg_duration_label,
        }


def aggregate_volume(rows: Sequence[Any]) -> Dict[str, CallVolume]:
    """Sotuvchi kesimida qo'ng'iroq hajmi."""
    by_manager: Dict[str, CallVolume] = {}
    for row in rows:
        name = str(_row_get(row, "manager_name", "") or "").strip()
        if not name:
            continue
        volume = by_manager.setdefault(name, CallVolume(manager_name=name))
        volume.total += 1
        if _to_int(_row_get(row, "answered", 0)):
            volume.answered += 1
            volume.total_talk_seconds += _to_int(_row_get(row, "duration_seconds", 0))
        else:
            volume.missed += 1
        if _to_int(_row_get(row, "analyzed", 0)):
            volume.analyzed += 1
    return by_manager


def team_volume(rows: Sequence[Any]) -> CallVolume:
    """Jamoa bo'yicha yig'indi (menejeri noma'lum qo'ng'iroqlar ham kiradi)."""
    total = CallVolume(manager_name="")
    for row in rows:
        total.total += 1
        if _to_int(_row_get(row, "answered", 0)):
            total.answered += 1
            total.total_talk_seconds += _to_int(_row_get(row, "duration_seconds", 0))
        else:
            total.missed += 1
        if _to_int(_row_get(row, "analyzed", 0)):
            total.analyzed += 1
    return total


class CallEventLog:
    """Qo'ng'iroq hodisalarini yozadi va o'qiydi."""

    def __init__(self, db: Any):
        self.db = db

    async def record(
        self,
        *,
        call_id: str,
        lead_id: int,
        duration_seconds: int,
        has_recording: bool,
        manager_id: Optional[int] = None,
        manager_name: str = "",
        direction: str = "",
        phone: str = "",
        call_status: Any = None,
        occurred_at: str = "",
    ) -> bool:
        """Bitta qo'ng'iroqni qayd etadi. Idempotent (call_id yagona)."""
        if self.db is None or not call_id:
            return False
        await ensure_call_events_schema(self.db)
        now = get_local_now().isoformat()
        try:
            conn = await _maybe_await(self.db.get_connection())
            await _maybe_await(
                conn.execute(
                    "INSERT OR IGNORE INTO call_events "
                    "(call_id, lead_id, manager_id, manager_name, direction, "
                    " phone, duration_seconds, answered, has_recording, "
                    " analyzed, call_status, occurred_at, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(call_id),
                        int(lead_id or 0),
                        int(manager_id) if manager_id else None,
                        manager_name,
                        direction or "",
                        phone or "",
                        max(_to_int(duration_seconds), 0),
                        1 if is_answered(duration_seconds) else 0,
                        1 if has_recording else 0,
                        0,
                        str(call_status) if call_status is not None else None,
                        occurred_at or now,
                        now,
                    ),
                )
            )
            await _maybe_await(conn.commit())
            return True
        except Exception as exc:
            logger.warning("[CALL EVENTS] %s yozilmadi: %s", call_id, exc)
            return False

    async def mark_analyzed(self, call_id: str) -> bool:
        """Tahlil muvaffaqiyatli tugaganini belgilaydi."""
        if self.db is None or not call_id:
            return False
        try:
            conn = await _maybe_await(self.db.get_connection())
            await _maybe_await(
                conn.execute(
                    "UPDATE call_events SET analyzed = 1 WHERE call_id = ?",
                    (str(call_id),),
                )
            )
            await _maybe_await(conn.commit())
            return True
        except Exception as exc:
            logger.warning("[CALL EVENTS] %s analyzed belgilanmadi: %s", call_id, exc)
            return False

    async def fetch_recent(self, days: int = 30) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        try:
            return await fetch_rows(self.db, _SELECT_RECENT_SQL, [f"-{int(days)} days"])
        except Exception as exc:
            logger.error("[CALL EVENTS] O'qib bo'lmadi: %s", exc)
            return []

    async def volume_summary(self, days: int = 30) -> Dict[str, Any]:
        """Reklamadagi panel: jami / samarali / o'tkazib yuborilgan / o'rtacha."""
        rows = await self.fetch_recent(days)
        team = team_volume(rows)
        return {
            "days": days,
            "total": team.total,
            "answered": team.answered,
            "missed": team.missed,
            "analyzed": team.analyzed,
            "answer_rate": round(team.answer_rate, 1),
            "avg_duration": team.avg_duration_label,
            "avg_duration_seconds": round(team.avg_duration_seconds),
            "managers": [v.to_dict() for v in sorted(
                aggregate_volume(rows).values(),
                key=lambda v: v.answer_rate,
                reverse=True,
            )],
            "has_data": team.total > 0,
        }
