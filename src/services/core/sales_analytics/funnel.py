"""
Pipeline Funnel calculation for sales analytics.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta

import structlog

logger = structlog.get_logger()


class PipelineFunnelMixin:
    """Mixin for calculating pipeline funnels."""

    def generate_pipeline_funnel(self, days: int = 7) -> str:
        now = time.time()
        period_start = int((datetime.now() - timedelta(days=days)).timestamp())
        sales_leads = self._get_all_leads(self.SALES_PIPELINE)

        total = len(sales_leads)
        active = lost = won = won_week = stagnated = 0
        revenue = revenue_week = 0

        for lead in sales_leads:
            status = lead.get("status_id", 0)
            updated = lead.get("updated_at", 0)
            closed_at = lead.get("closed_at", 0)
            price = lead.get("price", 0) or 0
            if status == self.STATUS_WON:
                won += 1
                revenue += price
                if closed_at and closed_at >= period_start:
                    won_week += 1
                    revenue_week += price
            elif status == self.STATUS_LOST:
                lost += 1
            else:
                active += 1
                if (now - updated) > 86400 * 3:
                    stagnated += 1

        win_rate = (won / total * 100) if total else 0
        avg_deal = (revenue / won) if won else 0

        report = "SALES PIPELINE FUNNEL\n"
        report += f"Oxirgi {days} kun ({datetime.now().strftime('%d.%m.%Y')})\n"
        report += "-" * 30 + "\n"
        report += "\nSALES Pipeline\n"
        report += f"   Jami: {total} ta lid\n"
        report += f"   Aktiv: {active}\n"
        report += f"   Won: {won} ({revenue:,.0f} so'm)\n".replace(",", " ")
        report += f"   Lost: {lost}\n"
        if stagnated > 0:
            report += f"   Stagnatsiya (3+ kun): {stagnated}\n"
        report += f"\n   Win Rate (SALES): {win_rate:.0f}%\n"
        report += "\n" + "-" * 30
        report += f"\nHAFTALIK NATIJALAR ({days} kun):\n"
        report += f"   Yopilgan: {won_week} ta bitim\n"
        report += f"   Tushum: {revenue_week:,.0f} so'm\n".replace(",", " ")
        report += f"   O'rtacha bitim: {avg_deal:,.0f} so'm\n".replace(",", " ")
        report += f"\nUMUMIY CONVERSIYA: {win_rate:.1f}%"
        report += f"\n   ({total} lid -> {won} won)"
        report += "\n\nTAVSIYALAR:\n"
        if stagnated > 0:
            report += f"   SALES'da {stagnated} ta lid 3+ kun harakatsiz - qayta ishlang\n"
        if win_rate < 30:
            report += f"   Win Rate past ({win_rate:.0f}%) - Sales bosqichlarini tekshiring\n"
        if lost > active:
            report += "   SALES'da ko'p lid yo'qolmoqda - kvalifikatsiya sifatini oshiring\n"
        if won_week == 0:
            report += "   Bu hafta 0 ta bitim yopilgan - urgent harakatlar kerak!\n"
        if win_rate >= 50:
            report += f"   Win Rate yuqori ({win_rate:.0f}%) - ajoyib natija!\n"
        return report
