from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Optional

from src.database_pool import DatabasePool, db_pool

logger = logging.getLogger(__name__)

VALID_STAGES = ("brief", "design", "revision", "delivery", "payment", "done")

STAGE_ICONS: dict[str, str] = {
    "brief": "📋",
    "design": "🎨",
    "revision": "🔄",
    "delivery": "📦",
    "payment": "💳",
    "done": "✅",
}

STAGE_LABELS: dict[str, str] = {
    "brief": "Brifing",
    "design": "Dizayn",
    "revision": "Tahrirlash",
    "delivery": "Topshirish",
    "payment": "To'lov",
    "done": "Tugallangan",
}


def _stage_icon(stage: str) -> str:
    return STAGE_ICONS.get(stage, "❓")


def _today_iso() -> str:
    return date.today().isoformat()


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _days_until(deadline: Optional[str]) -> Optional[int]:
    if not deadline:
        return None
    try:
        dl = date.fromisoformat(deadline[:10])
        return (dl - date.today()).days
    except (ValueError, TypeError):
        return None


class ProjectEngine:
    """Manages project lifecycle, payments and reporting."""

    def __init__(self, db: Optional[DatabasePool] = None) -> None:
        self._db = db or db_pool

    # ------------------------------------------------------------------
    # Project CRUD
    # ------------------------------------------------------------------

    async def create_project(
        self,
        title: str,
        client_name: str,
        amo_lead_id: Optional[int],
        budget: int,
        deadline: Optional[str],
        assigned_to: Optional[int] = None,
    ) -> int:
        """Create a new project and return its id."""
        await self._db.execute(
            """
            INSERT INTO projects
                (title, client_name, amo_lead_id, budget, deadline, assigned_to, stage, started_at)
            VALUES (?, ?, ?, ?, ?, ?, 'brief', ?)
            """,
            [title, client_name, amo_lead_id, budget, deadline, assigned_to, _now_iso()],
        )
        await self._db.commit()
        id_rows = await self._db.execute("SELECT last_insert_rowid() AS id")
        return int(id_rows[0]["id"]) if id_rows else 0

    async def update_stage(self, project_id: int, stage: str) -> None:
        if stage not in VALID_STAGES:
            raise ValueError(f"Invalid stage '{stage}'. Must be one of: {VALID_STAGES}")
        await self._db.execute(
            "UPDATE projects SET stage = ? WHERE id = ?",
            [stage, project_id],
        )
        await self._db.commit()

    async def record_payment(self, project_id: int, amount: int) -> None:
        """Add amount to project paid_amount, and update linked invoice if one exists."""
        await self._db.execute(
            "UPDATE projects SET paid_amount = paid_amount + ? WHERE id = ?",
            [amount, project_id],
        )
        # Update the first pending/partial invoice linked to this project
        invoice_rows = await self._db.execute(
            """
            SELECT id, amount, paid_amount FROM invoices
            WHERE project_id = ? AND status != 'paid'
            ORDER BY created_at ASC
            LIMIT 1
            """,
            [project_id],
        )
        if invoice_rows:
            inv = invoice_rows[0]
            inv_id = inv["id"]
            new_paid = int(inv["paid_amount"] or 0) + amount
            inv_total = int(inv["amount"] or 0)
            new_status = "paid" if new_paid >= inv_total else "partial"
            await self._db.execute(
                "UPDATE invoices SET paid_amount = ?, status = ? WHERE id = ?",
                [new_paid, new_status, inv_id],
            )
        await self._db.commit()

    async def assign_to_employee(self, project_id: int, employee_id: int) -> None:
        await self._db.execute(
            "UPDATE projects SET assigned_to = ? WHERE id = ?",
            [employee_id, project_id],
        )
        await self._db.commit()

    async def complete_project(self, project_id: int) -> None:
        await self._db.execute(
            "UPDATE projects SET stage = 'done', completed_at = ? WHERE id = ?",
            [_now_iso(), project_id],
        )
        await self._db.commit()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_active_projects(self) -> list[dict]:
        """All non-done projects with days_until_deadline injected."""
        rows = await self._db.execute(
            "SELECT * FROM projects WHERE stage != 'done' ORDER BY deadline ASC NULLS LAST"
        )
        result = []
        for r in rows:
            d = dict(r)
            d["days_until_deadline"] = _days_until(d.get("deadline"))
            result.append(d)
        return result

    async def get_overdue_projects(self) -> list[dict]:
        """Active projects whose deadline has already passed."""
        today = _today_iso()
        rows = await self._db.execute(
            """
            SELECT * FROM projects
            WHERE stage != 'done'
              AND deadline IS NOT NULL
              AND deadline < ?
            ORDER BY deadline ASC
            """,
            [today],
        )
        result = []
        for r in rows:
            d = dict(r)
            d["days_until_deadline"] = _days_until(d.get("deadline"))
            result.append(d)
        return result

    async def get_project_stats(self) -> dict:
        """Aggregate stats across active projects."""
        rows = await self._db.execute(
            "SELECT budget, paid_amount, deadline FROM projects WHERE stage != 'done'"
        )
        total_active = len(rows)
        total_value = sum(int(r["budget"] or 0) for r in rows)
        collected = sum(int(r["paid_amount"] or 0) for r in rows)
        outstanding = total_value - collected
        today = _today_iso()
        overdue_count = sum(
            1 for r in rows
            if r.get("deadline") and str(r["deadline"]) < today
        )
        return {
            "total_active": total_active,
            "total_value": total_value,
            "collected": collected,
            "outstanding": outstanding,
            "overdue_count": overdue_count,
        }

    # ------------------------------------------------------------------
    # Formatted report (Uzbek Telegram text)
    # ------------------------------------------------------------------

    async def format_projects_report(self) -> str:
        projects = await self.get_active_projects()
        stats = await self.get_project_stats()

        lines: list[str] = [
            "📁 *Faol loyihalar hisoboti*",
            "",
            f"Jami faol: *{stats['total_active']}* ta",
            f"Umumiy qiymat: *{stats['total_value']:,} so'm*",
            f"Yig'ilgan: *{stats['collected']:,} so'm*",
            f"Qoldiq: *{stats['outstanding']:,} so'm*",
        ]
        if stats["overdue_count"]:
            lines.append(f"⚠️ Muddati o'tgan: *{stats['overdue_count']}* ta")

        if not projects:
            lines.append("")
            lines.append("✅ Hozirda faol loyihalar yo'q.")
            return "\n".join(lines)

        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━")

        for proj in projects:
            stage = proj.get("stage", "brief")
            icon = _stage_icon(stage)
            stage_label = STAGE_LABELS.get(stage, stage.capitalize())
            title = proj.get("title", "Nomsiz")
            client = proj.get("client_name", "—")
            budget = int(proj.get("budget") or 0)
            paid = int(proj.get("paid_amount") or 0)
            days = proj.get("days_until_deadline")
            deadline_raw = proj.get("deadline")

            # Build deadline string
            if deadline_raw:
                dl_str = str(deadline_raw)[:10]
                if days is None:
                    deadline_display = dl_str
                elif days < 0:
                    deadline_display = f"⚠️ {dl_str} ({abs(days)} kun kechikdi)"
                elif days == 0:
                    deadline_display = f"🔴 Bugun ({dl_str})"
                elif days <= 3:
                    deadline_display = f"🟡 {dl_str} ({days} kun qoldi)"
                else:
                    deadline_display = f"🟢 {dl_str} ({days} kun qoldi)"
            else:
                deadline_display = "belgilanmagan"

            progress_pct = round(paid / budget * 100) if budget else 0

            block = [
                f"{icon} *{title}*",
                f"   👤 Mijoz: {client}",
                f"   📌 Bosqich: {stage_label}",
                f"   💰 Byudjet: {budget:,} so'm | To'landi: {paid:,} so'm ({progress_pct}%)",
                f"   📅 Muddat: {deadline_display}",
            ]
            lines.extend(block)
            lines.append("")

        # Trim trailing blank line
        if lines and lines[-1] == "":
            lines.pop()

        return "\n".join(lines)
