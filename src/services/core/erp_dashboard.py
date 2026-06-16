"""
erp_dashboard.py — Aggregated ERP dashboard for Oisha-OS.

Combines FinanceEngine, HREngine, and ProjectEngine into a single
reporting surface.  All public methods are async.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from src.services.core.erp_schema import ERPSnapshot
from src.services.core.finance_engine import FinanceEngine
from src.services.core.hr_engine import HREngine
from src.services.core.project_engine import ProjectEngine

logger = logging.getLogger(__name__)


def _current_period() -> str:
    """Return current month as YYYY-MM."""
    return date.today().strftime("%Y-%m")


def _fmt_money(amount: int) -> str:
    """Format integer amount as space-separated thousands (Uzbek style)."""
    return f"{amount:,}".replace(",", " ")


def _compact(amount: int) -> str:
    """Compact millions/thousands notation (e.g. 45M, 450K)."""
    if abs(amount) >= 1_000_000:
        return f"{amount // 1_000_000}M"
    if abs(amount) >= 1_000:
        return f"{amount // 1_000}K"
    return str(amount)


class ERPDashboard:
    """Aggregated view over all three ERP engines."""

    def __init__(self, db) -> None:
        self.finance = FinanceEngine(db)
        self.hr = HREngine(db)
        self.projects = ProjectEngine(db)
        self.db = db

    # ------------------------------------------------------------------
    # Core snapshot
    # ------------------------------------------------------------------

    async def get_snapshot(self, period: Optional[str] = None) -> ERPSnapshot:
        """
        Build an ERPSnapshot for *period* (YYYY-MM).  Uses the current
        calendar month when *period* is None.

        Extra dashboard-specific metrics are stored as dynamic attributes
        on the returned object:
          .payroll_cost      — total monthly payroll
          .overdue_projects  — number of projects past their deadline
          .pipeline_value    — sum of active project budgets
          .cash_flow_status  — 'healthy' | 'warning' | 'critical'
        """
        period = period or _current_period()

        # --- Finance ---
        cf = await self.finance.get_cash_flow_summary(period)
        monthly_revenue: int = cf["revenue"]
        monthly_expenses: int = cf["expenses"]
        net_profit: int = cf["net"]

        outstanding_invoices = await self.finance.get_outstanding_invoices()
        outstanding_amount: int = sum(
            inv["amount"] - inv["paid_amount"] for inv in outstanding_invoices
        )
        outstanding_count: int = len(outstanding_invoices)

        adv_summary = await self.finance.get_advance_summary()
        pending_advances: int = adv_summary["pending_count"]
        pending_advance_total: int = adv_summary["pending_total"]

        # --- Payroll ---
        payroll_cost: int = await self.hr.get_monthly_payroll(period)

        # --- HR ---
        team_summary = await self.hr.get_team_summary()
        total_employees: int = team_summary["active"]

        # --- Projects ---
        proj_stats = await self.projects.get_project_stats()
        active_projects: int = proj_stats["total_active"]
        overdue_projects: int = proj_stats["overdue_count"]
        pipeline_value: int = proj_stats["total_value"]

        # --- Expense breakdown for top_expenses ---
        breakdown = await self.finance.get_expense_breakdown(period)
        top_expenses: list[dict] = [
            {"category": cat, "total": total}
            for cat, total in list(breakdown.items())[:5]
        ]

        # --- Cash-flow health status ---
        # Ratio: net_profit / payroll_cost
        # >= 1.0  → healthy   (covering payroll with profit to spare)
        # >= 0.0  → warning   (profitable but margin < full payroll)
        # <  0.0  → critical  (loss-making)
        if payroll_cost > 0:
            ratio = net_profit / payroll_cost
        else:
            ratio = 1.0 if net_profit >= 0 else -1.0

        if ratio >= 1.0:
            cash_flow_status = "healthy"
        elif ratio >= 0.0:
            cash_flow_status = "warning"
        else:
            cash_flow_status = "critical"

        snapshot = ERPSnapshot(
            period=period,
            total_revenue=monthly_revenue,
            total_expenses=monthly_expenses,
            net_profit=net_profit,
            outstanding_invoices=outstanding_count,
            outstanding_amount=outstanding_amount,
            pending_advances=pending_advances,
            pending_advance_total=pending_advance_total,
            active_projects=active_projects,
            active_employees=total_employees,
            top_expenses=top_expenses,
        )

        # Extra attributes consumed by other dashboard methods
        snapshot.overdue_projects = overdue_projects          # type: ignore[attr-defined]
        snapshot.pipeline_value = pipeline_value              # type: ignore[attr-defined]
        snapshot.payroll_cost = payroll_cost                  # type: ignore[attr-defined]
        snapshot.cash_flow_status = cash_flow_status          # type: ignore[attr-defined]

        return snapshot

    # ------------------------------------------------------------------
    # Full Uzbek ERP report
    # ------------------------------------------------------------------

    async def format_full_report(self, period: Optional[str] = None) -> str:
        """
        Complete Uzbek ERP status report combining Finance, HR, and Projects
        sections, styled for Telegram MarkdownV1.
        """
        period = period or _current_period()
        snap = await self.get_snapshot(period)

        # Emoji helpers
        status_emoji_map = {"healthy": "✅", "warning": "⚠️", "critical": "🚨"}
        status_emoji = status_emoji_map.get(
            snap.cash_flow_status, "❓"  # type: ignore[attr-defined]
        )
        net_emoji = "📈" if snap.net_profit >= 0 else "📉"
        overdue_proj_emoji = "✅" if snap.overdue_projects == 0 else "⚠️"  # type: ignore[attr-defined]

        # ── Finance section ──────────────────────────────────────────
        finance_lines: list[str] = [
            f"━━━ 💰 MOLIYA ({period}) ━━━",
            f"💵 Daromad:              {_fmt_money(snap.total_revenue)} UZS",
            f"💸 Xarajatlar:           {_fmt_money(snap.total_expenses)} UZS",
            f"👥 Ish haqi fondi:       {_fmt_money(snap.payroll_cost)} UZS",  # type: ignore[attr-defined]
            f"{net_emoji} Sof foyda:          {_fmt_money(snap.net_profit)} UZS",
            f"{status_emoji} Naqd pul holati:   {snap.cash_flow_status.upper()}",  # type: ignore[attr-defined]
            f"🧾 Kutilayotgan to'lovlar: {snap.outstanding_invoices} ta "
            f"({_fmt_money(snap.outstanding_amount)} UZS)",
            f"💼 Kutilayotgan avanslar: {snap.pending_advances} ta "
            f"({_fmt_money(snap.pending_advance_total)} UZS)",
        ]
        if snap.top_expenses:
            finance_lines.append("📊 Top xarajatlar:")
            for item in snap.top_expenses:
                finance_lines.append(
                    f"   • {item['category'].capitalize()}: "
                    f"{_fmt_money(item['total'])} UZS"
                )

        # ── HR section ───────────────────────────────────────────────
        kpi_list = await self.hr.get_kpi_report(period)
        avg_kpi: float = (
            sum(k["score"] for k in kpi_list) / len(kpi_list) if kpi_list else 0.0
        )
        kpi_emoji = "✅" if avg_kpi >= 7 else ("⚠️" if avg_kpi >= 4 else "🚨")

        hr_lines: list[str] = [
            f"━━━ 👥 JAMOA ({period}) ━━━",
            f"👤 Faol xodimlar:    {snap.active_employees} kishi",
            f"💰 Oylik ish haqi:   {_fmt_money(snap.payroll_cost)} UZS",  # type: ignore[attr-defined]
            f"{kpi_emoji} O'rtacha KPI:    {avg_kpi:.1f} / 10",
        ]
        if kpi_list:
            hr_lines.append("🏆 KPI reytingi:")
            for i, kpi in enumerate(kpi_list[:5], 1):
                medal = (
                    "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                )
                hr_lines.append(
                    f"   {medal} {kpi['name']} — {kpi['score']:.1f} "
                    f"(bitimlar: {kpi['deals_closed']})"
                )
        else:
            hr_lines.append(f"ℹ️ {period} uchun KPI ma'lumotlari yo'q.")

        # ── Projects section ─────────────────────────────────────────
        proj_lines: list[str] = [
            "━━━ 📁 LOYIHALAR ━━━",
            f"📂 Faol loyihalar:   {snap.active_projects} ta",
            f"💰 Pipeline qiymati: {_fmt_money(snap.pipeline_value)} UZS",  # type: ignore[attr-defined]
            f"{overdue_proj_emoji} Muddati o'tgan:   {snap.overdue_projects} ta",  # type: ignore[attr-defined]
        ]
        overdue_list = await self.projects.get_overdue_projects()
        if overdue_list:
            proj_lines.append("⚠️ Kechikkan loyihalar:")
            for p in overdue_list[:5]:
                days = abs(p.get("days_until_deadline") or 0)
                proj_lines.append(
                    f"   • {p['title']} ({p['client_name']}) — {days} kun kechikdi"
                )

        # ── Assemble full report ─────────────────────────────────────
        sections: list[str] = (
            [f"🏢 *OISHA ERP HISOBOT — {period}*", ""]
            + finance_lines
            + [""]
            + hr_lines
            + [""]
            + proj_lines
            + ["", "━━━━━━━━━━━━━━━━", f"📅 Sanasi: {date.today().isoformat()}"]
        )
        return "\n".join(sections)

    # ------------------------------------------------------------------
    # Health score
    # ------------------------------------------------------------------

    async def get_health_score(self, period: Optional[str] = None) -> dict:
        """
        Return a dict with keys:
            score           — int 0–100
            status          — str label (Uzbek)
            issues          — list[str] of identified problems
            recommendations — list[str] of suggested actions

        Scoring:
            +30  net_profit > 0
            +20  no overdue projects
            +20  no overdue invoices
            +20  team KPI average > 7
            +10  pending advance requests < 3
        """
        period = period or _current_period()
        snap = await self.get_snapshot(period)
        kpi_list = await self.hr.get_kpi_report(period)

        score = 0
        issues: list[str] = []
        recommendations: list[str] = []

        # +30 — net profit positive
        if snap.net_profit > 0:
            score += 30
        else:
            issues.append("Sof foyda manfiy yoki nolga teng")
            recommendations.append("Xarajatlarni kamaytiring yoki daromadni oshiring")

        # +20 — no overdue projects
        overdue_proj: int = snap.overdue_projects  # type: ignore[attr-defined]
        if overdue_proj == 0:
            score += 20
        else:
            issues.append(f"{overdue_proj} ta loyiha muddati o'tgan")
            recommendations.append("Kechikkan loyihalar uchun tezkor reja tuzing")

        # +20 — no overdue invoices
        outstanding = await self.finance.get_outstanding_invoices()
        overdue_inv = sum(1 for inv in outstanding if inv["days_overdue"] > 0)
        if overdue_inv == 0:
            score += 20
        else:
            issues.append(f"{overdue_inv} ta invoice muddati o'tgan")
            recommendations.append("Mijozlarga to'lov eslatmasi yuboring")

        # +20 — team KPI average > 7
        avg_kpi: float = (
            sum(k["score"] for k in kpi_list) / len(kpi_list) if kpi_list else 0.0
        )
        if avg_kpi > 7:
            score += 20
        else:
            if kpi_list:
                issues.append(f"O'rtacha KPI past: {avg_kpi:.1f}/10")
                recommendations.append(
                    "Jamoaga motivatsion ko'mak bering va treninglar o'tkazing"
                )
            else:
                issues.append(f"{period} uchun KPI ma'lumotlari kiritilmagan")
                recommendations.append("Xodimlar KPI ballarini kiriting")

        # +10 — pending advance requests < 3
        if snap.pending_advances < 3:
            score += 10
        else:
            issues.append(
                f"{snap.pending_advances} ta avans so'rovi ko'rib chiqilmagan"
            )
            recommendations.append("Avans so'rovlarini tezroq ko'rib chiqing")

        # Determine Uzbek status label
        if score >= 85:
            status = "A'lo — Biznes sog'lom ✅"
        elif score >= 65:
            status = "Yaxshi — Kichik muammolar bor ⚠️"
        elif score >= 40:
            status = "O'rtacha — E'tibor talab etadi ⚠️"
        else:
            status = "Xavfli — Zudlik bilan chora ko'ring 🚨"

        return {
            "score": score,
            "status": status,
            "issues": issues,
            "recommendations": recommendations,
        }

    # ------------------------------------------------------------------
    # Quick one-liner status
    # ------------------------------------------------------------------

    async def format_quick_status(self, period: Optional[str] = None) -> str:
        """
        Single-line Uzbek status string, e.g.:
        "✅ Biznes sog'lom | Daromad: 45M | Loyihalar: 8 | Jamoa: 12"
        """
        period = period or _current_period()
        snap = await self.get_snapshot(period)

        status_map = {
            "healthy":  "✅ Biznes sog'lom",
            "warning":  "⚠️ Diqqat talab",
            "critical": "🚨 Kritik holat",
        }
        status_label = status_map.get(
            snap.cash_flow_status, "❓ Noma'lum"  # type: ignore[attr-defined]
        )

        parts: list[str] = [
            status_label,
            f"Daromad: {_compact(snap.total_revenue)}",
            f"Loyihalar: {snap.active_projects}",
            f"Jamoa: {snap.active_employees}",
        ]
        # Surface warning details inline if problems exist
        overdue_p: int = snap.overdue_projects  # type: ignore[attr-defined]
        if overdue_p:
            parts.append(f"⚠️ Kechikkan: {overdue_p}")
        if snap.outstanding_invoices:
            parts.append(f"🧾 Invoice: {snap.outstanding_invoices}")

        return " | ".join(parts)
