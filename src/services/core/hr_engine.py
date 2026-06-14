from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from src.database_pool import DatabasePool, db_pool

logger = logging.getLogger(__name__)

ROLE_ICONS: dict[str, str] = {
    "hunter": "🎯",
    "setter": "📞",
    "expert": "🧠",
    "closer": "🤝",
    "designer": "🎨",
    "manager": "👔",
    "ceo": "👑",
}

VALID_ROLES = set(ROLE_ICONS.keys())


def _role_icon(role: str) -> str:
    return ROLE_ICONS.get(role.lower(), "👤")


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class HREngine:
    """Manages employees, KPI records, payroll and team reporting."""

    def __init__(self, db: Optional[DatabasePool] = None) -> None:
        self._db = db or db_pool

    # ------------------------------------------------------------------
    # Employee CRUD
    # ------------------------------------------------------------------

    async def get_all_employees(self) -> list[dict]:
        """Return all active employees as plain dicts."""
        rows = await self._db.execute(
            "SELECT * FROM employees WHERE is_active = 1 ORDER BY name"
        )
        return [dict(r) for r in rows]

    async def get_employee_by_telegram(self, telegram_id: int) -> dict | None:
        rows = await self._db.execute(
            "SELECT * FROM employees WHERE telegram_id = ? LIMIT 1",
            [telegram_id],
        )
        return dict(rows[0]) if rows else None

    async def add_employee(
        self,
        telegram_id: Optional[int],
        name: str,
        role: str,
        base_salary: int,
        amo_id: Optional[int] = None,
        hire_date: Optional[str] = None,
    ) -> int:
        """Insert a new employee and return the new row id."""
        rows = await self._db.execute(
            """
            INSERT INTO employees (telegram_id, name, role, base_salary, amo_id, hire_date, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            [telegram_id, name, role.lower(), base_salary, amo_id, hire_date],
        )
        await self._db.commit()
        # Fetch the last inserted id
        id_rows = await self._db.execute("SELECT last_insert_rowid() AS id")
        return int(id_rows[0]["id"]) if id_rows else 0

    async def update_salary(self, employee_id: int, new_salary: int) -> None:
        await self._db.execute(
            "UPDATE employees SET base_salary = ? WHERE id = ?",
            [new_salary, employee_id],
        )
        await self._db.commit()

    async def deactivate_employee(self, employee_id: int) -> None:
        await self._db.execute(
            "UPDATE employees SET is_active = 0 WHERE id = ?",
            [employee_id],
        )
        await self._db.commit()

    # ------------------------------------------------------------------
    # KPI
    # ------------------------------------------------------------------

    def _calculate_kpi_score(
        self,
        leads_handled: int,
        deals_closed: int,
        revenue_generated: int,
    ) -> float:
        raw = (
            deals_closed * 40
            + leads_handled * 10
            + min(revenue_generated // 100_000, 50)
        ) / 100.0
        return round(_clamp(raw, 0.0, 10.0), 2)

    async def record_kpi(
        self,
        employee_id: int,
        period: str,
        leads_handled: int,
        deals_closed: int,
        revenue_generated: int,
    ) -> int:
        """Upsert KPI for an employee/period pair. Returns the row id."""
        score = self._calculate_kpi_score(leads_handled, deals_closed, revenue_generated)

        # Check for existing record
        existing = await self._db.execute(
            "SELECT id FROM kpi_scores WHERE employee_id = ? AND period = ? LIMIT 1",
            [employee_id, period],
        )
        if existing:
            row_id = int(existing[0]["id"])
            await self._db.execute(
                """
                UPDATE kpi_scores
                SET leads_handled = ?, deals_closed = ?, revenue_generated = ?, score = ?
                WHERE id = ?
                """,
                [leads_handled, deals_closed, revenue_generated, score, row_id],
            )
            await self._db.commit()
            return row_id

        await self._db.execute(
            """
            INSERT INTO kpi_scores (employee_id, period, leads_handled, deals_closed, revenue_generated, score)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [employee_id, period, leads_handled, deals_closed, revenue_generated, score],
        )
        await self._db.commit()
        id_rows = await self._db.execute("SELECT last_insert_rowid() AS id")
        return int(id_rows[0]["id"]) if id_rows else 0

    async def get_kpi_report(self, period: str) -> list[dict]:
        """All employees' KPI for a given period, sorted by score DESC."""
        rows = await self._db.execute(
            """
            SELECT k.*, e.name, e.role
            FROM kpi_scores k
            JOIN employees e ON e.id = k.employee_id
            WHERE k.period = ?
            ORDER BY k.score DESC
            """,
            [period],
        )
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Payroll & summary
    # ------------------------------------------------------------------

    async def get_team_summary(self) -> dict:
        all_rows = await self._db.execute("SELECT role, base_salary, is_active FROM employees")
        total = len(all_rows)
        active_rows = [r for r in all_rows if r["is_active"]]
        active = len(active_rows)
        by_role: dict[str, int] = {}
        total_payroll = 0
        for r in active_rows:
            role = r["role"]
            by_role[role] = by_role.get(role, 0) + 1
            total_payroll += (r["base_salary"] or 0)
        return {
            "total_employees": total,
            "active": active,
            "by_role": by_role,
            "total_payroll": total_payroll,
        }

    async def get_monthly_payroll(self, period: str) -> int:  # noqa: ARG002 — period reserved for future use
        """Sum of base_salary for all currently active employees."""
        rows = await self._db.execute(
            "SELECT SUM(base_salary) AS total FROM employees WHERE is_active = 1"
        )
        if rows and rows[0]["total"] is not None:
            return int(rows[0]["total"])
        return 0

    # ------------------------------------------------------------------
    # Formatted reports (Uzbek Telegram text)
    # ------------------------------------------------------------------

    async def format_team_report(self, period: str) -> str:
        summary = await self.get_team_summary()
        kpi_list = await self.get_kpi_report(period)
        payroll = await self.get_monthly_payroll(period)

        kpi_by_emp: dict[int, dict] = {k["employee_id"]: k for k in kpi_list}
        employees = await self.get_all_employees()

        lines: list[str] = [
            f"👥 *Jamoa hisoboti — {period}*",
            f"Faol xodimlar: {summary['active']} / {summary['total_employees']}",
            f"Oylik ish haqi fondi: *{payroll:,} so'm*",
            "",
            "📊 *Rollar bo'yicha:*",
        ]
        for role, count in sorted(summary["by_role"].items()):
            icon = _role_icon(role)
            lines.append(f"  {icon} {role.capitalize()}: {count} kishi")

        if kpi_list:
            lines.append("")
            lines.append(f"🏆 *KPI reytingi ({period}):*")
            for i, kpi in enumerate(kpi_list, 1):
                score = kpi.get("score", 0.0)
                icon = _role_icon(kpi.get("role", ""))
                medal = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else f"{i}."))
                lines.append(
                    f"  {medal} {icon} {kpi['name']} — {score:.1f}/10 "
                    f"(bitimlar: {kpi['deals_closed']}, lidlar: {kpi['leads_handled']})"
                )
        else:
            lines.append("")
            lines.append(f"ℹ️ {period} uchun KPI ma'lumotlari yo'q.")

        if employees:
            lines.append("")
            lines.append("👤 *Xodimlar ro'yxati:*")
            for emp in employees:
                icon = _role_icon(emp.get("role", ""))
                kpi = kpi_by_emp.get(emp["id"])
                kpi_str = f" | KPI: {kpi['score']:.1f}" if kpi else ""
                lines.append(
                    f"  {icon} {emp['name']} ({emp['role']}) — {emp['base_salary']:,} so'm{kpi_str}"
                )

        return "\n".join(lines)

    async def format_advance_requests(self) -> str:
        rows = await self._db.execute(
            """
            SELECT a.id, a.amount, a.reason, a.requested_at,
                   e.name AS employee_name, e.role
            FROM advances a
            JOIN employees e ON e.id = a.employee_id
            WHERE a.status = 'pending'
            ORDER BY a.requested_at ASC
            """
        )
        if not rows:
            return "✅ Kutilayotgan avans so'rovlari yo'q."

        lines: list[str] = [f"💵 *Avans so'rovlari ({len(rows)} ta):*", ""]
        for row in rows:
            icon = _role_icon(row.get("role", ""))
            reason = row["reason"] or "sabab ko'rsatilmagan"
            date_str = (row["requested_at"] or "")[:10]
            lines.append(
                f"  {icon} *{row['employee_name']}* — {row['amount']:,} so'm\n"
                f"     📝 {reason}\n"
                f"     📅 {date_str}"
            )
        return "\n".join(lines)
