from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


class FinanceEngine:
    def __init__(self, db) -> None:
        self._db = db

    async def get_monthly_revenue(self, period: str) -> int:
        rows = await self._db.execute(
            "SELECT COALESCE(SUM(paid_amount), 0) AS total FROM invoices WHERE created_at LIKE ?",
            [f"{period}%"],
        )
        return int(rows[0]["total"]) if rows else 0

    async def get_outstanding_invoices(self) -> list[dict]:
        rows = await self._db.execute(
            """
            SELECT id, client_name, amount, paid_amount, due_date, status
            FROM invoices
            WHERE status IN ('pending', 'partial', 'overdue')
            ORDER BY due_date ASC
            """,
        )
        today = date.today().isoformat()
        result = []
        for row in rows:
            due = row["due_date"] or ""
            days_overdue = 0
            if due and due < today:
                try:
                    delta = date.today() - date.fromisoformat(due)
                    days_overdue = delta.days
                except ValueError:
                    pass
            result.append(
                {
                    "id": row["id"],
                    "client_name": row["client_name"],
                    "amount": row["amount"],
                    "paid_amount": row["paid_amount"],
                    "due_date": due,
                    "days_overdue": days_overdue,
                }
            )
        return result

    async def get_cash_flow_summary(self, period: str) -> dict:
        revenue = await self.get_monthly_revenue(period)

        expense_rows = await self._db.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE expense_date LIKE ?",
            [f"{period}%"],
        )
        expenses = int(expense_rows[0]["total"]) if expense_rows else 0

        advance_rows = await self._db.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM advances WHERE status = 'paid' AND processed_at LIKE ?",
            [f"{period}%"],
        )
        advances_paid = int(advance_rows[0]["total"]) if advance_rows else 0

        return {
            "revenue": revenue,
            "expenses": expenses,
            "net": revenue - expenses,
            "advances_paid": advances_paid,
        }

    async def get_expense_breakdown(self, period: str) -> dict:
        rows = await self._db.execute(
            """
            SELECT category, COALESCE(SUM(amount), 0) AS total
            FROM expenses
            WHERE expense_date LIKE ?
            GROUP BY category
            ORDER BY total DESC
            """,
            [f"{period}%"],
        )
        return {row["category"]: int(row["total"]) for row in rows}

    async def add_expense(
        self,
        category: str,
        description: Optional[str],
        amount: int,
        expense_date: Optional[str],
        recorded_by: Optional[int],
    ) -> int:
        eff_date = expense_date or date.today().isoformat()
        rows = await self._db.execute(
            """
            INSERT INTO expenses (category, description, amount, expense_date, recorded_by)
            VALUES (?, ?, ?, ?, ?)
            RETURNING id
            """,
            [category, description, amount, eff_date, recorded_by],
        )
        await self._db.commit()
        if rows:
            return int(rows[0]["id"])
        rows2 = await self._db.execute("SELECT last_insert_rowid() AS id")
        return int(rows2[0]["id"])

    async def add_invoice(
        self,
        client_name: str,
        project_id: Optional[int],
        amount: int,
        due_date: Optional[str],
        notes: Optional[str],
    ) -> int:
        rows = await self._db.execute(
            """
            INSERT INTO invoices (client_name, project_id, amount, due_date, notes)
            VALUES (?, ?, ?, ?, ?)
            RETURNING id
            """,
            [client_name, project_id, amount, due_date, notes],
        )
        await self._db.commit()
        if rows:
            return int(rows[0]["id"])
        rows2 = await self._db.execute("SELECT last_insert_rowid() AS id")
        return int(rows2[0]["id"])

    async def mark_invoice_paid(self, invoice_id: int, paid_amount: int) -> None:
        inv_rows = await self._db.execute(
            "SELECT amount FROM invoices WHERE id = ?",
            [invoice_id],
        )
        if not inv_rows:
            raise ValueError(f"Invoice {invoice_id} not found")
        total = int(inv_rows[0]["amount"])
        status = "paid" if paid_amount >= total else "partial"
        await self._db.execute(
            "UPDATE invoices SET paid_amount = ?, status = ? WHERE id = ?",
            [paid_amount, status, invoice_id],
        )
        await self._db.commit()

    async def request_advance(
        self,
        employee_id: int,
        amount: int,
        reason: Optional[str],
    ) -> int:
        rows = await self._db.execute(
            """
            INSERT INTO advances (employee_id, amount, reason)
            VALUES (?, ?, ?)
            RETURNING id
            """,
            [employee_id, amount, reason],
        )
        await self._db.commit()
        if rows:
            return int(rows[0]["id"])
        rows2 = await self._db.execute("SELECT last_insert_rowid() AS id")
        return int(rows2[0]["id"])

    async def approve_advance(self, advance_id: int, approved_by: int) -> None:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        await self._db.execute(
            "UPDATE advances SET status = 'approved', approved_by = ?, processed_at = ? WHERE id = ?",
            [approved_by, now, advance_id],
        )
        await self._db.commit()

    async def get_advance_summary(self) -> dict:
        rows = await self._db.execute(
            """
            SELECT
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending_count,
                SUM(CASE WHEN status = 'pending' THEN amount ELSE 0 END) AS pending_total,
                SUM(CASE WHEN status = 'approved' THEN amount ELSE 0 END) AS approved_total,
                SUM(CASE WHEN status = 'paid' THEN amount ELSE 0 END) AS paid_total
            FROM advances
            """,
        )
        row = rows[0] if rows else {}
        return {
            "pending_count": int(row.get("pending_count") or 0),
            "pending_total": int(row.get("pending_total") or 0),
            "approved_total": int(row.get("approved_total") or 0),
            "paid_total": int(row.get("paid_total") or 0),
        }

    def _fmt_money(self, amount: int) -> str:
        return f"{amount:,}".replace(",", " ")

    async def format_cash_flow_report(self, period: str) -> str:
        cf = await self.get_cash_flow_summary(period)
        breakdown = await self.get_expense_breakdown(period)
        outstanding = await self.get_outstanding_invoices()
        adv = await self.get_advance_summary()

        revenue = cf["revenue"]
        expenses = cf["expenses"]
        net = cf["net"]
        advances_paid = cf["advances_paid"]

        net_emoji = "📈" if net >= 0 else "📉"

        category_icons = {
            "salary": "👥",
            "tools": "🛠",
            "marketing": "📣",
            "office": "🏢",
            "rent": "🏠",
            "other": "📦",
        }

        breakdown_lines = "\n".join(
            f"  {category_icons.get(cat, '•')} {cat.capitalize()}: {self._fmt_money(total)} UZS"
            for cat, total in breakdown.items()
        )
        if not breakdown_lines:
            breakdown_lines = "  Xarajatlar yo'q"

        outstanding_total = sum(
            r["amount"] - r["paid_amount"] for r in outstanding
        )
        overdue_count = sum(1 for r in outstanding if r["days_overdue"] > 0)

        lines = [
            f"💼 *MOLIYAVIY HISOBOT — {period}*",
            "",
            f"💰 Daromad:      {self._fmt_money(revenue)} UZS",
            f"💸 Xarajatlar:   {self._fmt_money(expenses)} UZS",
            f"🔄 Avanslar (to'langan): {self._fmt_money(advances_paid)} UZS",
            f"{net_emoji} Sof foyda:   {self._fmt_money(net)} UZS",
            "",
            "📊 *Xarajatlar bo'yicha:*",
            breakdown_lines,
            "",
            "🧾 *Kutilayotgan to'lovlar:*",
            f"  Jami: {len(outstanding)} ta invoice — {self._fmt_money(outstanding_total)} UZS",
            f"  Muddati o'tgan: {overdue_count} ta",
            "",
            "💼 *Avanslar:*",
            f"  ⏳ Kutilayotgan: {adv['pending_count']} ta — {self._fmt_money(adv['pending_total'])} UZS",
            f"  ✅ Tasdiqlangan: {self._fmt_money(adv['approved_total'])} UZS",
            f"  💳 To'langan:   {self._fmt_money(adv['paid_total'])} UZS",
        ]

        return "\n".join(lines)
