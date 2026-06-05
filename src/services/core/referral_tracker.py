"""
Referral Tracker — Blok 26
Kim tavsiya berdi, natija qanday — to'liq kuzatuv tizimi.

Tizim: referral qayd etiladi → lead yaratiladi → konvertatsiya bo'lsa belgilanadi.
"""
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

TABLE = "referrals"


class ReferralTracker:
    """
    Referral manba va konvertatsiya natijalarini kuzatadi.
    DB table: referrals
    """

    def __init__(self, db, crm, settings):
        self.db = db
        self.crm = crm
        self.settings = settings

    async def init_table(self) -> None:
        conn = await self.db.get_connection()
        try:
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {TABLE} (
                    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_name        TEXT NOT NULL,
                    referrer_phone       TEXT DEFAULT '',
                    referrer_telegram_id INTEGER,
                    referred_name        TEXT NOT NULL,
                    referred_phone       TEXT DEFAULT '',
                    lead_id              INTEGER,
                    status               TEXT DEFAULT 'new',
                    notes                TEXT DEFAULT '',
                    created_at           TEXT NOT NULL,
                    converted_at         TEXT,
                    deal_amount          REAL DEFAULT 0
                )
            """)
            await conn.commit()
        finally:
            await conn.close()

    async def register(
        self,
        referrer_name: str,
        referred_name: str,
        referrer_phone: str = "",
        referred_phone: str = "",
        referrer_telegram_id: Optional[int] = None,
        lead_id: Optional[int] = None,
        notes: str = "",
    ) -> int:
        """
        Register a new referral.
        Returns the referral ID.
        """
        conn = await self.db.get_connection()
        try:
            cur = await conn.execute(
                f"""INSERT INTO {TABLE}
                    (referrer_name, referrer_phone, referrer_telegram_id,
                     referred_name, referred_phone, lead_id, notes, created_at)
                    VALUES (?,?,?,?,?,?,?,?)""",
                (referrer_name, referrer_phone, referrer_telegram_id,
                 referred_name, referred_phone, lead_id, notes,
                 datetime.now().isoformat()),
            )
            await conn.commit()
            return cur.lastrowid or 0
        finally:
            await conn.close()

    async def mark_converted(self, referral_id: int, deal_amount: float = 0.0) -> bool:
        """Mark referral as converted (client paid)."""
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                f"UPDATE {TABLE} SET status='converted', converted_at=?, deal_amount=? WHERE id=?",
                (datetime.now().isoformat(), deal_amount, referral_id),
            )
            await conn.commit()
            return True
        except Exception as exc:
            logger.error("ReferralTracker.mark_converted: %s", exc)
            return False
        finally:
            await conn.close()

    async def get_weekly_report(self) -> str:
        """Weekly referral performance report."""
        conn = await self.db.get_connection()
        try:
            cur = await conn.execute(
                f"SELECT referrer_name, referred_name, status, deal_amount, created_at "
                f"FROM {TABLE} ORDER BY created_at DESC LIMIT 100"
            )
            rows = await cur.fetchall()
        finally:
            await conn.close()

        if not rows:
            return "📣 *Referral tizimi:* Hali referral qayd etilmagan.\n\nSkaut yoki Kapitan referral qo'shishi uchun: `/referral_add`"

        total = len(rows)
        converted = [r for r in rows if r[2] == "converted"]
        revenue = sum(r[3] or 0.0 for r in converted)
        conv_pct = len(converted) / total * 100 if total else 0.0

        lines = [
            "📣 *REFERRAL HISOBOTI*\n",
            f"Jami: *{total} ta*",
            f"Konvertatsiya: *{len(converted)} ta* ({conv_pct:.0f}%)",
            f"Daromad: *{revenue:,.0f} UZS*\n",
        ]

        # Top referrers
        from collections import Counter
        counts: Counter = Counter(r[0] for r in rows)
        lines.append("🏆 *Ko'p tavsiya berganlar:*")
        for name, cnt in counts.most_common(5):
            lines.append(f"  • {name}: {cnt} ta")

        # Pending
        pending = [r for r in rows if r[2] == "new"]
        if pending:
            lines.append(f"\n⏳ *Natija kutilayotgan:* {len(pending)} ta")
            for r in pending[:3]:
                lines.append(f"  • {r[1]} ← {r[0]} tavsiyasi")

        lines.append(f"\n_Hisobot: {datetime.now().strftime('%d.%m.%Y')}_")
        return "\n".join(lines)

    async def get_pending(self) -> str:
        """List of referrals without conversion result."""
        conn = await self.db.get_connection()
        try:
            cur = await conn.execute(
                f"SELECT id, referrer_name, referred_name, referred_phone, created_at "
                f"FROM {TABLE} WHERE status='new' ORDER BY created_at DESC LIMIT 20"
            )
            rows = await cur.fetchall()
        finally:
            await conn.close()

        if not rows:
            return ""

        lines = [f"📋 *Natija kutilayotgan referrallar ({len(rows)} ta):*\n"]
        for rid, referrer, referred, phone, created in rows:
            date_str = created[:10] if created else "?"
            phone_str = f" | {phone}" if phone else ""
            lines.append(f"#{rid} {referred}{phone_str} ← {referrer} | {date_str}")

        return "\n".join(lines)
