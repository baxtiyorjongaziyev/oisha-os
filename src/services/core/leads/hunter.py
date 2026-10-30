"""Hunter: amoCRM "Sotuv" → "Yangi LEads" ga lid yozadigan yagona yo'l.

Har nomzod `hunter_candidates` jurnaliga yoziladi (jarayon qayta ishga tushsa
ham yo'qolmaydi). Shaxs `hunter_keys` orqali aniqlanadi: telefon va manba ID
(`tg:<user_id>`) — ikkalasi ham bir xil lidga bog'lanadi.

- Kalit atomik band qilinadi (`INSERT ... ON CONFLICT DO NOTHING RETURNING`):
  bir vaqtda kelgan ikki nomzoddan faqat bittasi amoCRM'ga yozadi.
- Mavjud lid bo'lsa, u amoCRM'da qayta tekshiriladi: aktiv bo'lsa — izoh,
  yopilgan (142/143) bo'lsa — yangi bitim ochiladi.
- Kunlik limit (`HUNTER_DAILY_LIMIT`, default 20) faqat `kind != "inbound"`
  nomzodlarga. Mijozning o'zi yozgan (inbound) lidi hech qachon tashlanmaydi.

Rejani ko'ring: `docs/agents/hunter-flow-plan.md`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.services.core.crm.amocrm_pipeline_config import (
    SALES_NEW_STATUS_ID,
    SALES_PIPELINE_ID,
    STATUS_WON,
)
from src.time_utils import get_local_now, is_quiet_hours

logger = logging.getLogger(__name__)

INBOUND = "inbound"
SIGNAL = "signal"
DEFAULT_DAILY_LIMIT = 20
STATUS_LOST = 143
_CLOSED_STATUSES = {STATUS_WON, STATUS_LOST}
# Band qilingan, lekin tugallanmagan kalit shu vaqtdan keyin qayta olinishi mumkin.
_RESERVATION_TTL_SECONDS = 300
MAX_ATTEMPTS = 5
_RETRY_AFTER_SECONDS = 600

_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS hunter_candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dedup_key TEXT NOT NULL,
        source TEXT NOT NULL,
        kind TEXT NOT NULL,
        name TEXT NOT NULL,
        phone TEXT,
        external_id TEXT,
        custom_fields TEXT,
        note TEXT,
        state TEXT NOT NULL,
        lead_id INTEGER,
        attempts INTEGER NOT NULL DEFAULT 0,
        error TEXT,
        notified INTEGER NOT NULL DEFAULT 0,
        day TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        changed_at INTEGER NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS hunter_candidates_day ON hunter_candidates(day, kind, state)",
    """CREATE TABLE IF NOT EXISTS hunter_keys (
        key TEXT PRIMARY KEY,
        lead_id INTEGER,
        reserved_at INTEGER,
        updated_at INTEGER NOT NULL)""",
]

# pending: yozilmadi, qayta urinish kerak; sent: yangi bitim; duplicate: aktiv
# bitimga izoh qo'shildi; limited: kunlik limit; busy: shu shaxs hozir yozilmoqda.
PENDING, SENT, DUPLICATE, LIMITED, FAILED, BUSY = (
    "pending", "sent", "duplicate", "limited", "failed", "busy",
)


@dataclass(frozen=True)
class Candidate:
    source: str
    name: str
    kind: str = INBOUND
    phone: Optional[str] = None
    external_id: Optional[str] = None
    note: str = ""
    custom_fields: Optional[List[Dict[str, Any]]] = None


@dataclass(frozen=True)
class WriteResult:
    ok: bool
    state: str
    lead_id: Optional[int] = None
    error: Optional[str] = None


def normalize_phone(raw: Optional[str]) -> Optional[str]:
    """`+998XXXXXXXXX` yoki None. 9 raqamli mahalliy raqamga 998 qo'shiladi."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) == 12 and digits.startswith("998"):
        return "+" + digits
    if 10 <= len(digits) <= 15 and not digits.startswith("998"):
        return "+" + digits
    return None


def identity_keys(candidate: Candidate) -> List[str]:
    keys = []
    phone = normalize_phone(candidate.phone)
    if phone:
        keys.append(f"phone:{phone}")
    if candidate.external_id:
        keys.append(f"ext:{candidate.external_id}")
    return keys


def daily_limit() -> int:
    try:
        return max(0, int(os.getenv("HUNTER_DAILY_LIMIT", DEFAULT_DAILY_LIMIT)))
    except ValueError:
        return DEFAULT_DAILY_LIMIT


class HunterWriter:
    def __init__(self, amocrm: Any, pool: Any):
        self.amocrm = amocrm
        self.pool = pool
        self._ready = False

    async def _sql(self, query: str, params: Optional[list] = None):
        rows = await self.pool.execute(query, params or [])
        await self.pool.commit()
        return rows or []

    async def init(self) -> None:
        if not self._ready:
            for statement in _SCHEMA:
                await self._sql(statement)
            self._ready = True

    async def submit(self, candidate: Candidate) -> WriteResult:
        await self.init()
        keys = identity_keys(candidate)
        if not keys:
            return WriteResult(False, FAILED, error="no_phone_or_external_id")
        name = (candidate.name or "").strip() or "Nomsiz"
        phone = normalize_phone(candidate.phone)
        day = get_local_now().date().isoformat()
        log = lambda state, lead_id=None, error=None: self._log(  # noqa: E731
            candidate, keys[0], name, phone, state, lead_id, error, day
        )

        known = await self._known_lead(keys)
        if known is not None:
            lead = await self.amocrm.get_lead(known)
            if lead is None:
                await log(PENDING, known, "lead_check_failed")
                return WriteResult(False, PENDING, known, "lead_check_failed")
            if lead.get("status_id") not in _CLOSED_STATUSES:
                return await self._append(candidate, keys, known, log)
            # Yopilgan bitim: yangi murojaat yangi bitim bo'ladi.
        elif phone and hasattr(self.amocrm, "find_active_lead_by_phone"):
            # Hunter'dan oldin ochilgan aktiv bitim (masalan Muzokarada) — "Yangi"ga qaytarilmaydi.
            active = await asyncio.to_thread(self.amocrm.find_active_lead_by_phone, phone)
            if active and active.get("id"):
                return await self._append(candidate, keys, int(active["id"]), log)

        if candidate.kind != INBOUND and await self._used_today(day) >= daily_limit():
            await log(LIMITED, error="daily_limit")
            return WriteResult(False, LIMITED, error="daily_limit")

        if not await self._reserve(keys):
            await log(BUSY, error="in_flight")
            return WriteResult(False, BUSY, error="in_flight")
        try:
            lead_id, error = await self._create(candidate, name, phone)
        finally:
            await self._release(keys, None)
        if not lead_id:
            await log(PENDING, error=error)
            return WriteResult(False, PENDING, error=error)
        await self._bind(keys, lead_id)
        await log(SENT, lead_id)
        await self._assign(lead_id, name, candidate.source)
        return WriteResult(True, SENT, lead_id)

    async def _assign(self, lead_id: int, name: str, source: str) -> None:
        """Yangi bitimni ishdagi sotuvchiga beradi. Xato yozuvni buzmaydi."""
        try:
            from src.services.core.leads.assignment import LeadAssigner, assignment_enabled

            if not await assignment_enabled(self.pool):
                return
            await LeadAssigner(self.amocrm, self.pool).assign_new(lead_id, name, source)
        except Exception as exc:
            logger.warning("[HUNTER] lid biriktirilmadi: %s", type(exc).__name__)

    async def _known_lead(self, keys: List[str]) -> Optional[int]:
        best = None
        for key in keys:
            rows = await self._sql(
                "SELECT lead_id, updated_at FROM hunter_keys WHERE key=? AND lead_id IS NOT NULL",
                [key],
            )
            if rows and (best is None or rows[0]["updated_at"] > best["updated_at"]):
                best = rows[0]
        return int(best["lead_id"]) if best else None

    async def _used_today(self, day: str) -> int:
        rows = await self._sql(
            "SELECT COUNT(*) AS n FROM hunter_candidates WHERE day=? AND kind<>? AND state=?",
            [day, INBOUND, SENT],
        )
        return int(rows[0]["n"]) if rows else 0

    async def _reserve(self, keys: List[str]) -> bool:
        now = int(time.time())
        taken: List[str] = []
        for key in keys:
            rows = await self._sql(
                """INSERT INTO hunter_keys(key, lead_id, reserved_at, updated_at)
                VALUES (?, NULL, ?, ?)
                ON CONFLICT(key) DO UPDATE SET reserved_at=excluded.reserved_at
                WHERE hunter_keys.reserved_at IS NULL
                   OR hunter_keys.reserved_at < ?
                RETURNING key""",
                [key, now, now, now - _RESERVATION_TTL_SECONDS],
            )
            if not rows:
                await self._release(taken, None)
                return False
            taken.append(key)
        return True

    async def _release(self, keys: List[str], lead_id: Optional[int]) -> None:
        for key in keys:
            await self._sql("UPDATE hunter_keys SET reserved_at=NULL WHERE key=?", [key])

    async def _bind(self, keys: List[str], lead_id: int) -> None:
        now = int(time.time())
        for key in keys:
            await self._sql(
                """INSERT INTO hunter_keys(key, lead_id, reserved_at, updated_at)
                VALUES (?, ?, NULL, ?)
                ON CONFLICT(key) DO UPDATE SET lead_id=excluded.lead_id,
                    updated_at=excluded.updated_at""",
                [key, lead_id, now],
            )

    async def _append(self, candidate: Candidate, keys, lead_id: int, log) -> WriteResult:
        text = f"[Hunter] Yana murojaat: {candidate.source}."
        if candidate.note:
            text += f"\n{candidate.note}"
        if not await asyncio.to_thread(self.amocrm.add_lead_note, lead_id, text):
            await log(PENDING, lead_id, "note_failed")
            return WriteResult(False, PENDING, lead_id, "note_failed")
        await self._bind(keys, lead_id)  # yangi aniqlangan telefonni ham bog'laydi
        await log(DUPLICATE, lead_id)
        return WriteResult(True, DUPLICATE, lead_id)

    async def _create(self, candidate: Candidate, name: str, phone: Optional[str]):
        tag = f"hunter:{candidate.source}"
        note = f"[Hunter] Manba: {candidate.source}."
        if candidate.note:
            note += f"\n{candidate.note}"
        try:
            if phone:
                lead_id = await self.amocrm.ensure_lead(
                    name=name,
                    phone=phone,
                    note=note,
                    pipeline_id=SALES_PIPELINE_ID,
                    status_id=SALES_NEW_STATUS_ID,
                    custom_fields=candidate.custom_fields,
                )
                if lead_id and not await self.amocrm.add_lead_tag(int(lead_id), tag):
                    logger.warning("[HUNTER] teg qo'yilmadi: lead=%s", lead_id)
            else:
                lead_id = await self.amocrm.create_standalone_lead(
                    name=name,
                    pipeline_id=SALES_PIPELINE_ID,
                    status_id=SALES_NEW_STATUS_ID,
                    tags=[tag],
                    note=note,
                    custom_fields=candidate.custom_fields,
                )
        except Exception as exc:  # amoCRM klienti tarmoq xatosini ko'tarishi mumkin
            logger.warning("[HUNTER] amoCRM yozuv xatosi: %s", exc)
            return None, type(exc).__name__
        return (int(lead_id), None) if lead_id else (None, "amocrm_rejected")

    async def _log(self, c, key, name, phone, state, lead_id, error, day) -> None:
        now = int(time.time())
        await self._sql(
            """INSERT INTO hunter_candidates
            (dedup_key, source, kind, name, phone, external_id, custom_fields, note,
             state, lead_id, attempts, error, day, created_at, changed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,1,?,?,?,?)""",
            [key, c.source, c.kind, name, phone, c.external_id,
             json.dumps(c.custom_fields, ensure_ascii=False) if c.custom_fields else None,
             c.note, state, lead_id, error, day, now, now],
        )

    async def retry_pending(self, limit: int = 20) -> Dict[str, int]:
        """`pending` nomzodlarni qayta yuboradi. Quiet-hours'da hech narsa qilmaydi."""
        await self.init()
        stats = {"retried": 0, "sent": 0, "failed": 0}
        if is_quiet_hours():
            return stats
        rows = await self._sql(
            """SELECT * FROM hunter_candidates WHERE state=? AND changed_at < ?
            ORDER BY id LIMIT ?""",
            [PENDING, int(time.time()) - _RETRY_AFTER_SECONDS, limit],
        )
        for row in rows:
            attempts = int(row["attempts"])
            if attempts >= MAX_ATTEMPTS:
                await self._set_state(row["id"], FAILED)
                stats["failed"] += 1
                continue
            await self._set_state(row["id"], "retried")
            result = await self.submit(Candidate(
                source=row["source"], kind=row["kind"], name=row["name"],
                phone=row["phone"], external_id=row["external_id"], note=row["note"] or "",
                custom_fields=json.loads(row["custom_fields"]) if row["custom_fields"] else None,
            ))
            stats["retried"] += 1
            if result.ok:
                stats["sent"] += 1
            else:
                await self._sql(
                    """UPDATE hunter_candidates SET attempts=?
                    WHERE id=(SELECT MAX(id) FROM hunter_candidates WHERE dedup_key=?)""",
                    [attempts + 1, row["dedup_key"]],
                )
        return stats

    async def unnotified_failures(self, limit: int = 20) -> List[Dict[str, Any]]:
        await self.init()
        return await self._sql(
            """SELECT id, source, name, phone, error, attempts FROM hunter_candidates
            WHERE state=? AND notified=0 ORDER BY id LIMIT ?""",
            [FAILED, limit],
        )

    async def mark_notified(self, row_ids: List[int]) -> None:
        for row_id in row_ids:
            await self._sql("UPDATE hunter_candidates SET notified=1 WHERE id=?", [row_id])

    async def _set_state(self, row_id: int, state: str) -> None:
        await self._sql(
            "UPDATE hunter_candidates SET state=?, changed_at=? WHERE id=?",
            [state, int(time.time()), row_id],
        )
