"""Yangi lidni hozir ishda turgan sotuvchiga berish va sotuvgacha kuzatish.

Owner qoidasi (2026-10-26):
- Yangi lidlar (reklama, DM, qo'ng'iroq) → Mumtozmaxal, Rayxona.
- Networking (biznes trening, tanishuv) lidlar → avval Shahnoza, keyin Mumtozmaxal/Rayxona.
  Shahnoza yangi lid olmaydi: o'qishda bo'lishi mumkin, networking bilan munosabat quradi.

"Hozir ishda" = davomat tizimida bugun oxirgi belgisi `check_in` (ketmagan).
Bir guruh ichida bugun eng kam lid olgan sotuvchiga beriladi.
Hech kim ishda bo'lmasa lid `unassigned` qoladi va kuzatuv sikli birinchi kelgan
sotuvchiga beradi. Lid 30 daqiqa "Yangi"da tursa eslatma, 60 daqiqada boshqa
ishdagi sotuvchiga o'tkaziladi (bir marta). Quiet-hours'da (23–07) xabar yo'q.
"""
from __future__ import annotations

import asyncio
import html
import logging
import time
from typing import Any, Dict, List, Optional

from src.services.core.crm.amocrm_pipeline_config import SALES_NEW_STATUS_ID
from src.time_utils import get_local_now, is_quiet_hours

logger = logging.getLogger(__name__)

NEW, NETWORKING = "new", "networking"
# kind -> (asosiy guruh, zaxira guruh). Ismlar davomatdagi `employees.name` boshlanishi.
ROUTES = {
    NEW: (["mumtoz", "rayxon", "rayhon"], []),
    NETWORKING: (["shahnoz"], ["mumtoz", "rayxon", "rayhon"]),
}
NETWORKING_SOURCES = {"telegram_group_tn5", "networking", "tez_natija"}
REMIND_AFTER_SECONDS = 30 * 60
REASSIGN_AFTER_SECONDS = 60 * 60
AMO_LEAD_URL = "https://jonbranding.amocrm.ru/leads/detail/{}"

FIRST_STEP = {
    NEW: "5 daqiqa ichida qo'ng'iroq qiling. Ehtiyojni so'rang: qaysi xizmat, muddat, byudjet.",
    NETWORKING: "Avval tanishuvni eslating (qaysi trening), sotuvdan oldin munosabat quring.",
}

_SCHEMA = """CREATE TABLE IF NOT EXISTS lead_assignments (
    lead_id INTEGER PRIMARY KEY,
    lead_name TEXT NOT NULL,
    source TEXT NOT NULL,
    kind TEXT NOT NULL,
    employee_id INTEGER,
    employee_name TEXT,
    state TEXT NOT NULL,
    assigned_at INTEGER,
    reminded INTEGER NOT NULL DEFAULT 0,
    reassigned INTEGER NOT NULL DEFAULT 0,
    claimed_at INTEGER,
    checked_at INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL)"""
_CLAIM_TTL_SECONDS = 600


def lead_kind(source: str) -> str:
    return NETWORKING if source in NETWORKING_SOURCES else NEW


def _matches(name: str, prefixes: List[str]) -> bool:
    low = (name or "").strip().lower()
    return any(low.startswith(p) for p in prefixes)


def _notify_group(text: str, lead_id: int) -> bool:
    from src.services.core.instagram.leadgen_router import _notify_telegram

    markup = {"inline_keyboard": [[{"text": "🧾 amoCRM", "url": AMO_LEAD_URL.format(lead_id)}]]}
    return _notify_telegram(text, markup)


class LeadAssigner:
    def __init__(self, amocrm: Any, pool: Any, notify=_notify_group):
        self.amocrm = amocrm
        self.pool = pool
        self.notify = notify
        self._ready = False

    async def _sql(self, query: str, params: Optional[list] = None):
        rows = await self.pool.execute(query, params or [])
        await self.pool.commit()
        return rows or []

    async def init(self) -> None:
        if not self._ready:
            await self._sql(_SCHEMA)
            self._ready = True

    async def on_duty(self) -> List[Dict[str, Any]]:
        """Bugun kelgan va hali ketmagan, amoCRM ID'si bor xodimlar."""
        today = get_local_now().date().isoformat()
        try:
            rows = await self._sql(
                """SELECT e.employee_id, e.kind, emp.name, emp.amo_id, emp.telegram_id
                FROM attendance_events e JOIN employees emp ON emp.id = e.employee_id
                WHERE e.work_date = ? AND emp.is_active = 1
                ORDER BY e.server_ts, e.id""",
                [today],
            )
        except Exception as exc:  # davomat jadvallari hali yo'q bo'lishi mumkin
            logger.warning("[ASSIGN] davomat o'qilmadi: %s", type(exc).__name__)
            return []
        last: Dict[int, Dict[str, Any]] = {}
        for r in rows:
            last[int(r["employee_id"])] = dict(r)
        return [r for r in last.values() if r["kind"] == "check_in" and r.get("amo_id")]

    async def _load_today(self, employee_id: int) -> int:
        start = int(time.time()) - 86400
        rows = await self._sql(
            "SELECT COUNT(*) AS n FROM lead_assignments WHERE employee_id=? AND assigned_at>=?",
            [employee_id, start],
        )
        return int(rows[0]["n"]) if rows else 0

    async def pick(self, kind: str, exclude: Optional[int] = None) -> Optional[Dict[str, Any]]:
        duty = [p for p in await self.on_duty() if int(p["employee_id"]) != exclude]
        for group in ROUTES[kind]:
            pool = [p for p in duty if _matches(p["name"], group)]
            if pool:
                loads = [(await self._load_today(int(p["employee_id"])), p["name"], p) for p in pool]
                return min(loads, key=lambda t: (t[0], t[1]))[2]
        return None

    async def assign_new(self, lead_id: int, lead_name: str, source: str) -> Optional[str]:
        """Yangi bitimni ishdagi sotuvchiga beradi. Sotuvchi ismi yoki None."""
        await self.init()
        kind = lead_kind(source)
        await self._sql(
            """INSERT INTO lead_assignments (lead_id, lead_name, source, kind, state, created_at)
            VALUES (?,?,?,?, 'unassigned', ?) ON CONFLICT(lead_id) DO NOTHING""",
            [lead_id, lead_name, source, kind, int(time.time())],
        )
        if not await self._claim(lead_id, "unassigned"):
            return None  # boshqa jarayon allaqachon beryapti
        person = await self.pick(kind)
        if person is None:
            await self._unclaim(lead_id, "unassigned")
            if not is_quiet_hours():
                await self._send(
                    f"🆕 <b>Yangi lid</b>: {html.escape(lead_name)} ({html.escape(source)})\n"
                    "⚠️ Hozir ishda sotuvchi yo'q — birinchi kelganga beriladi.",
                    lead_id,
                )
            return None
        return await self._give(lead_id, lead_name, source, kind, person, "🆕 <b>Yangi lid</b>", "unassigned")

    async def _send(self, text: str, lead_id: int) -> bool:
        # Telegram so'rovi bloklovchi — event loop'ni to'xtatmasin.
        return bool(await asyncio.to_thread(self.notify, text, lead_id))

    async def _claim(self, lead_id: int, from_state: str) -> bool:
        now = int(time.time())
        rows = await self._sql(
            """UPDATE lead_assignments SET state='claiming', claimed_at=?
            WHERE lead_id=? AND (state=? OR (state='claiming' AND claimed_at < ?))
            RETURNING lead_id""",
            [now, lead_id, from_state, now - _CLAIM_TTL_SECONDS],
        )
        return bool(rows)

    async def _unclaim(self, lead_id: int, state: str) -> None:
        await self._sql(
            "UPDATE lead_assignments SET state=?, claimed_at=NULL WHERE lead_id=? AND state='claiming'",
            [state, lead_id],
        )

    async def _give(self, lead_id, lead_name, source, kind, person, title, from_state,
                    reassign: bool = False) -> Optional[str]:
        """Da'vo qilingan (claiming) lidni beradi; muvaffaqiyatsiz bo'lsa holat qaytariladi."""
        ok = await asyncio.to_thread(
            self.amocrm.update_lead_responsible, int(lead_id), int(person["amo_id"])
        )
        if not ok:
            logger.warning("[ASSIGN] amoCRM mas'ul o'zgarmadi: lead=%s", lead_id)
            await self._unclaim(lead_id, from_state)
            return None
        await self._sql(
            """UPDATE lead_assignments SET employee_id=?, employee_name=?, state='assigned',
            assigned_at=?, reminded=0, claimed_at=NULL, reassigned=MAX(reassigned, ?)
            WHERE lead_id=?""",
            [int(person["employee_id"]), person["name"], int(time.time()), int(reassign), lead_id],
        )
        if not is_quiet_hours():
            await self._send(
                f"{title}: {html.escape(lead_name)} ({html.escape(source)})\n"
                f"👤 Mas'ul: <b>{html.escape(person['name'])}</b>\n"
                f"👉 {FIRST_STEP[kind]}",
                lead_id,
            )
        return person["name"]

    async def _still_new(self, lead_id: int) -> Optional[bool]:
        """True: hali "Yangi"da; False: ilgarilagan/yopilgan; None: o'qib bo'lmadi."""
        lead = await self.amocrm.get_lead(int(lead_id))
        if not lead:
            return None
        return lead.get("status_id") == SALES_NEW_STATUS_ID

    async def follow_up_once(self) -> Dict[str, int]:
        """Biriktirilmaganlarni beradi, "Yangi"da qolganlarni eslatadi/o'tkazadi."""
        await self.init()
        stats = {"assigned": 0, "reminded": 0, "reassigned": 0}
        if is_quiet_hours():
            return stats
        now = int(time.time())
        for row in await self._sql(
            """SELECT * FROM lead_assignments WHERE state='unassigned'
            OR (state='claiming' AND claimed_at < ?) ORDER BY created_at LIMIT 20""",
            [now - _CLAIM_TTL_SECONDS],
        ):
            lead_id = int(row["lead_id"])
            fresh = await self._still_new(lead_id)
            if fresh is None:
                continue
            if not fresh:  # amoCRM'da qo'lda ishlangan yoki yopilgan
                await self._sql("UPDATE lead_assignments SET state='working' WHERE lead_id=?", [lead_id])
                continue
            person = await self.pick(row["kind"])
            if person and await self._claim(lead_id, "unassigned") and await self._give(
                lead_id, row["lead_name"], row["source"], row["kind"], person, "🆕 <b>Lid berildi</b>",
                "unassigned",
            ):
                stats["assigned"] += 1
        # Eng uzoq tekshirilmaganlardan boshlab — limit hech bir lidni och qoldirmaydi.
        for row in await self._sql(
            """SELECT * FROM lead_assignments WHERE state='assigned' AND assigned_at < ?
            ORDER BY checked_at, lead_id LIMIT 50""",
            [now - REMIND_AFTER_SECONDS],
        ):
            lead_id = int(row["lead_id"])
            await self._sql("UPDATE lead_assignments SET checked_at=? WHERE lead_id=?", [now, lead_id])
            fresh = await self._still_new(lead_id)
            if fresh is None:
                continue
            if not fresh:
                await self._sql("UPDATE lead_assignments SET state='working' WHERE lead_id=?", [lead_id])
                continue
            age = now - int(row["assigned_at"])
            if age >= REASSIGN_AFTER_SECONDS and not row["reassigned"]:
                person = await self.pick(row["kind"], exclude=int(row["employee_id"]))
                if person and await self._claim(lead_id, "assigned"):
                    if await self._give(
                        lead_id, row["lead_name"], row["source"], row["kind"], person,
                        f"🔁 <b>1 soat javobsiz, o'tkazildi</b> (oldin: {html.escape(row['employee_name'] or '')})",
                        "assigned", reassign=True,
                    ):
                        stats["reassigned"] += 1
                    continue
            if not row["reminded"] and await self._send(
                f"⏰ <b>{html.escape(row['employee_name'] or '')}</b>, lid 30 daqiqadan beri \"Yangi\"da: "
                f"{html.escape(row['lead_name'])}\n👉 {FIRST_STEP[row['kind']]}",
                lead_id,
            ):
                await self._sql("UPDATE lead_assignments SET reminded=1 WHERE lead_id=?", [lead_id])
                stats["reminded"] += 1
        return stats
