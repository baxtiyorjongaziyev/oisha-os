"""
Follow-up Scheduler — Blok 16
Loyiha topshirilgandan 12 kun keyin avtomatik mijoz follow-up.

Maqsad: fikr-mulohaza, referral va qayta sotuv imkoniyatini qo'ldan boy bermaslik.
"""
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

FOLLOWUP_DAYS = 12
TABLE = "followup_schedule"


class FollowupScheduler:
    """
    Loyiha 'Yakunlangan' bosqichiga o'tganda FOLLOWUP_DAYS kunlik
    follow-up rejalashtiriladi va muddati kelganda alert yuboriladi.
    """

    DONE_STAGES = {"Yakunlangan", "Done", "Completed", "Topshirildi"}

    def __init__(self, airtable, db, settings):
        self.airtable = airtable
        self.db = db
        self.settings = settings

    async def init_table(self) -> None:
        conn = await self.db.get_connection()
        try:
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {TABLE} (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name      TEXT NOT NULL,
                    client_phone      TEXT DEFAULT '',
                    client_name       TEXT DEFAULT '',
                    manager_id        INTEGER,
                    followup_date     TEXT NOT NULL,
                    done_at           TEXT NOT NULL,
                    status            TEXT DEFAULT 'scheduled',
                    airtable_record_id TEXT DEFAULT ''
                )
            """)
            await conn.commit()
        finally:
            await conn.close()

    async def sync_completed_projects(self) -> int:
        """
        Scan Airtable for newly completed projects, schedule follow-ups.
        Returns count of newly scheduled items.
        """
        try:
            projects = await asyncio.to_thread(self.airtable.get_projects)
        except Exception as exc:
            logger.error("FollowupScheduler.sync: %s", exc)
            return 0

        scheduled = 0
        for p in projects:
            if p.get("stage") not in self.DONE_STAGES:
                continue
            record_id = p.get("id") or ""
            if not record_id or await self._already_scheduled(record_id):
                continue

            name = p.get("project_name") or p.get("name") or "Loyiha"
            now = datetime.now()
            followup_date = (now + timedelta(days=FOLLOWUP_DAYS)).date()

            await self._insert(
                project_name=name,
                followup_date=followup_date,
                done_at=now,
                airtable_record_id=record_id,
            )
            scheduled += 1

        return scheduled

    async def run_due(self) -> str:
        """
        Find and return follow-ups due today.
        Marks them as 'sent' so they don't repeat.
        """
        today = date.today().isoformat()
        conn = await self.db.get_connection()
        try:
            cur = await conn.execute(
                f"SELECT id, project_name, client_phone, client_name, done_at "
                f"FROM {TABLE} WHERE status='scheduled' AND followup_date <= ?",
                (today,),
            )
            due = await cur.fetchall()

            if due:
                ids = ",".join(str(r[0]) for r in due)
                await conn.execute(
                    f"UPDATE {TABLE} SET status='sent' WHERE id IN ({ids})"
                )
                await conn.commit()
        finally:
            await conn.close()

        if not due:
            return ""

        lines = [f"📅 *{FOLLOWUP_DAYS}-KUNLIK FOLLOW-UP — {len(due)} ta*\n"]
        lines.append("Quyidagi mijozlarga bugun murojaat qiling:\n")

        for row in due:
            _, name, phone, client_name, done_at = row
            done_fmt = done_at[:10] if done_at else "?"
            lines.append(f"*{name}*")
            if client_name:
                lines.append(f"  👤 {client_name}")
            if phone:
                lines.append(f"  📞 {phone}")
            lines.append(f"  Topshirildi: {done_fmt}")
            lines.append("  So'rang: taassurot, referral, keyingi ehtiyoj")
            lines.append("")

        lines.append("_Fikr-mulohaza → Case → Referral_")
        return "\n".join(lines)

    async def get_upcoming(self, days_ahead: int = 3) -> str:
        """Show follow-ups due within next N days."""
        from_d = date.today().isoformat()
        to_d = (date.today() + timedelta(days=days_ahead)).isoformat()

        conn = await self.db.get_connection()
        try:
            cur = await conn.execute(
                f"SELECT project_name, followup_date FROM {TABLE} "
                f"WHERE status='scheduled' AND followup_date BETWEEN ? AND ? "
                f"ORDER BY followup_date",
                (from_d, to_d),
            )
            rows = await cur.fetchall()
        finally:
            await conn.close()

        if not rows:
            return ""

        lines = [f"📋 *{days_ahead} kun ichida follow-up kerak:*"]
        for name, fl_date in rows:
            lines.append(f"  • {name} — {fl_date}")
        return "\n".join(lines)

    # ---- internals ----

    async def _insert(
        self,
        project_name: str,
        followup_date: date,
        done_at: datetime,
        airtable_record_id: str = "",
        client_phone: str = "",
        client_name: str = "",
    ) -> None:
        conn = await self.db.get_connection()
        try:
            await conn.execute(
                f"""INSERT INTO {TABLE}
                    (project_name, client_phone, client_name,
                     followup_date, done_at, airtable_record_id)
                    VALUES (?,?,?,?,?,?)""",
                (project_name, client_phone, client_name,
                 followup_date.isoformat(), done_at.isoformat(), airtable_record_id),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def _already_scheduled(self, airtable_record_id: str) -> bool:
        conn = await self.db.get_connection()
        try:
            cur = await conn.execute(
                f"SELECT id FROM {TABLE} WHERE airtable_record_id=? LIMIT 1",
                (airtable_record_id,),
            )
            return (await cur.fetchone()) is not None
        finally:
            await conn.close()
