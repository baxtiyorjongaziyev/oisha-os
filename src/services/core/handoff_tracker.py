"""
Handoff Tracker — Blok 15
Bo'limlar orasida vazifa/mijoz uzatishni kuzatadi.

Qoida: "Qabul qildim" tasdiqi bo'lmasa, javobgarlik eski mas'ulda qoladi.
2 soat ichida tasdiq kelmasa — qizil signal.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

CONFIRM_HOURS = 2
TABLE = "handoffs"


class HandoffStatus:
    PENDING = "pending"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"


class HandoffTracker:
    """
    Lead yoki loyiha bo'limdan-bo'limga o'tishida yozma tasdiq talab qiladi.
    DB table: handoffs
    """

    def __init__(self, db, settings):
        self.db = db
        self.settings = settings

    async def init_table(self) -> None:
        """Create handoffs table if not exists."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {TABLE} (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_role  TEXT    NOT NULL,
                    to_role    TEXT    NOT NULL,
                    to_user_id INTEGER,
                    subject    TEXT    NOT NULL,
                    lead_id    INTEGER,
                    details    TEXT    DEFAULT '',
                    status     TEXT    DEFAULT 'pending',
                    created_at TEXT    NOT NULL,
                    confirmed_at TEXT,
                    deadline   TEXT    NOT NULL,
                    chat_id    INTEGER
                )
            """)
            await conn.commit()
        finally:
            await conn.close()

    async def create(
        self,
        from_role: str,
        to_role: str,
        subject: str,
        details: str = "",
        lead_id: Optional[int] = None,
        to_user_id: Optional[int] = None,
        chat_id: Optional[int] = None,
    ) -> int:
        """Create handoff record. Returns handoff ID."""
        now = datetime.now()
        deadline = (now + timedelta(hours=CONFIRM_HOURS)).isoformat()
        conn = await self.db.get_connection()
        try:
            cur = await conn.execute(
                f"""INSERT INTO {TABLE}
                    (from_role, to_role, to_user_id, subject, lead_id, details,
                     status, created_at, deadline, chat_id)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (from_role, to_role, to_user_id, subject, lead_id, details,
                 HandoffStatus.PENDING, now.isoformat(), deadline, chat_id),
            )
            await conn.commit()
            return cur.lastrowid or 0
        finally:
            await conn.close()

    async def confirm(self, handoff_id: int) -> bool:
        """Mark handoff confirmed. Returns True if record was pending."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                f"UPDATE {TABLE} SET status=?, confirmed_at=? WHERE id=? AND status=?",
                (HandoffStatus.CONFIRMED, datetime.now().isoformat(),
                 handoff_id, HandoffStatus.PENDING),
            )
            await conn.commit()
            return True
        except Exception as exc:
            logger.error("HandoffTracker.confirm: %s", exc)
            return False
        finally:
            await conn.close()

    async def check_expired(self) -> str:
        """
        Expire pending handoffs past deadline.
        Returns Telegram alert string listing expired ones.
        """
        now_iso = datetime.now().isoformat()
        conn = await self.db.get_connection()
        try:
            cur = await conn.execute(
                f"SELECT id, from_role, to_role, subject, created_at "
                f"FROM {TABLE} WHERE status=? AND deadline < ?",
                (HandoffStatus.PENDING, now_iso),
            )
            rows = await cur.fetchall()

            if rows:
                ids = ",".join(str(r[0]) for r in rows)
                await conn.execute(
                    f"UPDATE {TABLE} SET status=? WHERE id IN ({ids})",
                    (HandoffStatus.EXPIRED,),
                )
                await conn.commit()
        finally:
            await conn.close()

        if not rows:
            return ""

        lines = [f"⚠️ *HANDOFF TASDIQLANMADI — {len(rows)} ta*\n"]
        for r in rows:
            hid, from_role, to_role, subject, created_at = r
            created_fmt = created_at[:16].replace("T", " ") if created_at else "?"
            lines.append(f"• #{hid} *{subject}* | {from_role} → {to_role} | {created_fmt}")
        lines.append(
            "\n_Tasdiq bo'lmasa, javobgarlik *eski mas'ulda* qoladi._"
        )
        return "\n".join(lines)

    async def get_pending(self) -> list:
        """Return list of all pending handoffs."""
        conn = await self.db.get_connection()
        try:
            cur = await conn.execute(
                f"SELECT id, from_role, to_role, subject, deadline "
                f"FROM {TABLE} WHERE status=? ORDER BY created_at DESC",
                (HandoffStatus.PENDING,),
            )
            return await cur.fetchall()
        finally:
            await conn.close()

    def format_message(
        self, handoff_id: int, from_role: str, to_role: str, subject: str, details: str
    ) -> str:
        """Format the handoff notification to send to recipient."""
        return (
            f"📨 *HANDOFF #{handoff_id}*\n\n"
            f"Kimdan: {from_role}\n"
            f"Kimga: {to_role}\n"
            f"Mavzu: *{subject}*\n\n"
            f"{details}\n\n"
            f"✅ Qabul qilish: `/confirm_handoff {handoff_id}`\n"
            f"⏰ Muddat: {CONFIRM_HOURS} soat"
        )
