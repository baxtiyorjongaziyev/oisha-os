"""Hunter: amoCRM "Sotuv" → "Yangi LEads" ga lid yozadigan yagona yo'l.

Har nomzod avval `hunter_candidates` jadvaliga tushadi (jarayon qayta ishga
tushsa ham yo'qolmaydi), keyin bitta joyda dedup qilinib amoCRM'ga yoziladi.

- Dedup kaliti: normallashtirilgan telefon, bo'lmasa manba ID (`tg:<user_id>`).
  Shu kalit bilan yozilgan lid bo'lsa, yangi bitim ochilmaydi — faqat izoh.
- amoCRM'da shu telefon bilan aktiv bitim bo'lsa, `ensure_lead` uni qaytaradi.
- Kunlik limit (`HUNTER_DAILY_LIMIT`, default 20) faqat `kind != "inbound"`
  nomzodlarga. Mijozning o'zi yozgan (inbound) lidi hech qachon tashlanmaydi.

Rejani ko'ring: `docs/agents/hunter-flow-plan.md`.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

from src.services.core.crm.amocrm_pipeline_config import (
    SALES_NEW_STATUS_ID,
    SALES_PIPELINE_ID,
)
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)

INBOUND = "inbound"
DEFAULT_DAILY_LIMIT = 20

_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS hunter_candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dedup_key TEXT NOT NULL,
        source TEXT NOT NULL,
        kind TEXT NOT NULL,
        name TEXT NOT NULL,
        phone TEXT,
        note TEXT,
        state TEXT NOT NULL,
        lead_id INTEGER,
        attempts INTEGER NOT NULL DEFAULT 0,
        error TEXT,
        day TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        changed_at INTEGER NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS hunter_candidates_key ON hunter_candidates(dedup_key, state)",
    "CREATE INDEX IF NOT EXISTS hunter_candidates_day ON hunter_candidates(day, kind, state)",
]

# pending: yozilmoqda / qayta urinish kerak; sent: amoCRM'da bor;
# duplicate: avvalgi lidga izoh qo'shildi; limited: kunlik limit; failed: amoCRM rad etdi.
PENDING, SENT, DUPLICATE, LIMITED, FAILED = "pending", "sent", "duplicate", "limited", "failed"


@dataclass(frozen=True)
class Candidate:
    source: str
    name: str
    kind: str = INBOUND
    phone: Optional[str] = None
    external_id: Optional[str] = None
    note: str = ""


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


def dedup_key(candidate: Candidate) -> Optional[str]:
    phone = normalize_phone(candidate.phone)
    if phone:
        return f"phone:{phone}"
    if candidate.external_id:
        return f"ext:{candidate.external_id}"
    return None


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
        key = dedup_key(candidate)
        if key is None:
            return WriteResult(False, FAILED, error="no_phone_or_external_id")
        name = (candidate.name or "").strip() or "Nomsiz"
        phone = normalize_phone(candidate.phone)
        now = int(time.time())
        day = get_local_now().date().isoformat()

        previous = await self._sql(
            """SELECT lead_id FROM hunter_candidates
            WHERE dedup_key=? AND state IN (?, ?) AND lead_id IS NOT NULL
            ORDER BY id DESC LIMIT 1""",
            [key, SENT, DUPLICATE],
        )
        if previous:
            lead_id = int(previous[0]["lead_id"])
            text = f"[Hunter] Yana murojaat: {candidate.source}."
            if candidate.note:
                text += f"\n{candidate.note}"
            await asyncio.to_thread(self.amocrm.add_lead_note, lead_id, text)
            await self._insert(candidate, key, name, phone, DUPLICATE, lead_id, day, now)
            return WriteResult(True, DUPLICATE, lead_id)

        if candidate.kind != INBOUND:
            used = await self._sql(
                """SELECT COUNT(*) AS n FROM hunter_candidates
                WHERE day=? AND kind<>? AND state=?""",
                [day, INBOUND, SENT],
            )
            if used and int(used[0]["n"]) >= daily_limit():
                await self._insert(candidate, key, name, phone, LIMITED, None, day, now)
                return WriteResult(False, LIMITED, error="daily_limit")

        row_id = await self._insert(candidate, key, name, phone, PENDING, None, day, now)
        return await self._deliver(row_id, candidate, name, phone)

    async def _insert(self, c, key, name, phone, state, lead_id, day, now) -> Optional[int]:
        await self._sql(
            """INSERT INTO hunter_candidates
            (dedup_key, source, kind, name, phone, note, state, lead_id, day, created_at, changed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            [key, c.source, c.kind, name, phone, c.note, state, lead_id, day, now, now],
        )
        rows = await self._sql(
            "SELECT id FROM hunter_candidates WHERE dedup_key=? ORDER BY id DESC LIMIT 1",
            [key],
        )
        return int(rows[0]["id"]) if rows else None

    async def _deliver(self, row_id, candidate: Candidate, name: str, phone: Optional[str]) -> WriteResult:
        note = f"[Hunter] Manba: {candidate.source}."
        if candidate.note:
            note += f"\n{candidate.note}"
        error = None
        lead_id = None
        try:
            if phone:
                lead_id = await self.amocrm.ensure_lead(
                    name=name,
                    phone=phone,
                    note=note,
                    pipeline_id=SALES_PIPELINE_ID,
                    status_id=SALES_NEW_STATUS_ID,
                )
            else:
                lead_id = await self.amocrm.create_standalone_lead(
                    name=name,
                    pipeline_id=SALES_PIPELINE_ID,
                    status_id=SALES_NEW_STATUS_ID,
                    tags=[f"hunter:{candidate.source}"],
                    note=note,
                )
        except Exception as exc:  # amoCRM klienti tarmoq xatosini ko'tarishi mumkin
            error = type(exc).__name__
            logger.warning("[HUNTER] amoCRM yozuv xatosi: %s", exc)
        state = SENT if lead_id else PENDING
        await self._sql(
            """UPDATE hunter_candidates
            SET state=?, lead_id=?, attempts=attempts+1, error=?, changed_at=?
            WHERE id=?""",
            [state, lead_id, error or (None if lead_id else "amocrm_rejected"), int(time.time()), row_id],
        )
        if not lead_id:
            return WriteResult(False, PENDING, error=error or "amocrm_rejected")
        return WriteResult(True, SENT, int(lead_id))
