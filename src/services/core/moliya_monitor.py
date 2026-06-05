"""
Moliya Monitor — Blok 25, 28
P&L, cashflow, to'lov kechikishi va marja nazorati.

Qizil signal: marja < 30%, final fayl to'lovsiz berilgan, kechikkan to'lov.
"""
import asyncio
import logging
from datetime import date, datetime
from typing import Optional

logger = logging.getLogger(__name__)

MIN_MARGIN_PCT = 30.0


class MoliyaMonitor:
    """
    Airtable moliya yozuvlari (Kirim/Chiqim jadval) asosida
    haftalik P&L, cashflow va qizil signal alertlari.
    """

    def __init__(self, airtable, db, settings):
        self.airtable = airtable
        self.db = db
        self.settings = settings

    async def get_cashflow_report(self) -> str:
        """Haftalik cashflow + sariq/qizil signal."""
        try:
            records = await asyncio.to_thread(self.airtable.get_finance_records)
        except Exception as e:
            logger.error("MoliyaMonitor: %s", e)
            return "❌ Moliya ma'lumotlari yuklanmadi."

        income_recs = [r for r in records if r.get("table") == "Kirim"]
        expense_recs = [r for r in records if r.get("table") == "Chiqim"]

        total_income = sum(self._amount(r) for r in income_recs)
        total_expense = sum(self._amount(r) for r in expense_recs)
        net = total_income - total_expense
        margin_pct = (net / total_income * 100) if total_income > 0 else 0.0

        overdue = self._find_overdue(income_recs)

        margin_icon = "🔴" if margin_pct < MIN_MARGIN_PCT else "🟢"
        lines = [
            "💰 *MOLIYA NAZORATI*\n",
            f"📥 Tushum:    *{total_income:>12,.0f} UZS*",
            f"📤 Xarajat:   *{total_expense:>12,.0f} UZS*",
            f"📊 Sof foyda: *{net:>12,.0f} UZS*",
            f"{margin_icon} Marja:     *{margin_pct:>8.1f}%*  (min: {MIN_MARGIN_PCT:.0f}%)",
        ]

        if overdue:
            lines.append(f"\n⚠️ *Kechikkan to'lovlar ({len(overdue)} ta):*")
            for o in overdue[:6]:
                lines.append(f"  • {o['name']} — {o['amount']:,.0f} UZS | {o['due_date']}")

        if margin_pct < MIN_MARGIN_PCT:
            lines.append(
                f"\n🚨 *QIZIL SIGNAL:* Marja {margin_pct:.1f}% — {MIN_MARGIN_PCT:.0f}% dan past!\n"
                "F.G. moliya holatini ko'rib chiqsin."
            )

        lines.append(f"\n_Hisobot: {datetime.now().strftime('%d.%m.%Y %H:%M')}_")
        return "\n".join(lines)

    async def check_unpaid_finals(self) -> str:
        """
        Yakunlangan (Done) bosqichdagi loyihalardan to'lov tasdiqlanmagan holatlarni aniqlash.
        Qizil signal: final fayl to'lovsiz berilgan.
        """
        try:
            projects = await asyncio.to_thread(self.airtable.get_projects)
        except Exception as e:
            return f"❌ Loyihalar yuklanmadi: {e}"

        done_stages = {"Yakunlangan", "Done", "Completed", "Topshirildi"}
        issues = []

        for p in projects:
            if p.get("stage") not in done_stages:
                continue
            pay_status = (p.get("payment_status") or "").lower()
            if "to'liq" in pay_status or "paid" in pay_status or "100%" in pay_status:
                continue
            issues.append({
                "name": p.get("project_name") or p.get("name") or "Nomsiz",
                "stage": p.get("stage", "?"),
                "payment_status": p.get("payment_status") or "Belgilanmagan",
                "budget": self._budget(p),
            })

        if not issues:
            return ""

        lines = [
            "🚨 *FINAL FAYL XAVFI*\n",
            "Yakunlangan loyihalarda to'lov tasdiqlanmagan:\n",
        ]
        for i in issues[:10]:
            lines.append(
                f"• *{i['name']}* | {i['stage']} | "
                f"To'lov: {i['payment_status']} | {i['budget']:,.0f} UZS"
            )
        if len(issues) > 10:
            lines.append(f"... va yana {len(issues) - 10} ta")

        return "\n".join(lines)

    async def get_margin_breakdown(self) -> str:
        """Per-project margin check: which projects are below 30%."""
        try:
            projects = await asyncio.to_thread(self.airtable.get_projects)
            records = await asyncio.to_thread(self.airtable.get_finance_records)
        except Exception as e:
            return f"❌ Ma'lumot yuklanmadi: {e}"

        expense_by_project: dict = {}
        for r in records:
            if r.get("table") != "Chiqim":
                continue
            proj = (r.get("loyiha") or r.get("project") or "").strip()
            if proj:
                expense_by_project[proj] = expense_by_project.get(proj, 0.0) + self._amount(r)

        low_margin = []
        for p in projects:
            if p.get("stage") in self.airtable.DONE_STAGES:
                continue
            name = p.get("project_name") or p.get("name") or ""
            budget = self._budget(p)
            if budget <= 0:
                continue
            expense = expense_by_project.get(name, 0.0)
            if expense > 0:
                margin = (budget - expense) / budget * 100
                if margin < MIN_MARGIN_PCT:
                    low_margin.append({"name": name, "budget": budget, "expense": expense, "margin": margin})

        if not low_margin:
            return f"✅ Barcha loyihalarda marja {MIN_MARGIN_PCT:.0f}% dan yuqori."

        lines = [f"⚠️ *Marja {MIN_MARGIN_PCT:.0f}% dan past loyihalar:*\n"]
        for lm in sorted(low_margin, key=lambda x: x["margin"]):
            lines.append(
                f"• *{lm['name']}* | "
                f"Narx: {lm['budget']:,.0f} | "
                f"Xarajat: {lm['expense']:,.0f} | "
                f"Marja: {lm['margin']:.1f}%"
            )
        return "\n".join(lines)

    # ---- internal helpers ----

    def _amount(self, record: dict) -> float:
        for key in ("amount", "summa", "narx", "price", "value"):
            val = record.get(key)
            if val is not None:
                return self._to_float(val)
        return 0.0

    def _budget(self, project: dict) -> float:
        for key in ("budget", "Kelishgan narx", "Jami loyiha narxi (UZS)"):
            val = project.get(key)
            if val is not None:
                return self._to_float(val)
        return 0.0

    def _to_float(self, val) -> float:
        if isinstance(val, (int, float)):
            return float(val)
        try:
            return float(str(val).replace(",", "").replace(" ", "").replace("UZS", "").strip())
        except (ValueError, TypeError):
            return 0.0

    def _find_overdue(self, income_records: list) -> list:
        today = date.today()
        overdue = []
        for r in income_records:
            status = (r.get("status") or r.get("payment_status") or "").lower()
            if "kutil" not in status and "pending" not in status:
                continue
            due_raw = r.get("due_date") or r.get("sana") or r.get("date")
            if not due_raw:
                continue
            try:
                due_date = datetime.fromisoformat(str(due_raw)[:10]).date()
            except (ValueError, TypeError):
                continue
            if due_date >= today:
                continue
            overdue.append({
                "name": r.get("name") or r.get("loyiha") or "Noma'lum",
                "amount": self._amount(r),
                "due_date": due_date.strftime("%d.%m.%Y"),
            })
        return overdue
