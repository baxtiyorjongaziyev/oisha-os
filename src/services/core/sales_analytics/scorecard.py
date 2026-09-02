"""
Manager Scorecard calculation and formatting for sales analytics.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, List

import requests
import structlog

logger = structlog.get_logger()


class ManagerScorecardMixin:
    """Mixin for calculating and formatting manager scorecards."""

    def _get_all_leads(self, pipeline_id: int = None) -> List[Dict]:
        url = f"{self.amo.base_url}/api/v4/leads"
        params = {"limit": 250, "with": "contacts"}
        if pipeline_id:
            params["filter[pipeline_id]"] = pipeline_id

        all_leads = []
        try:
            resp = requests.get(url, headers=self.amo._get_headers(), params=params, timeout=30)
            if resp.status_code == 200:
                leads = resp.json().get("_embedded", {}).get("leads", [])
                all_leads.extend(leads)
        except Exception as e:
            logger.error(f"[ANALYTICS] Error fetching leads: {e}")
        return all_leads

    def _get_user_name(self, user_id: int) -> str:
        try:
            url = f"{self.amo.base_url}/api/v4/users/{user_id}"
            resp = requests.get(url, headers=self.amo._get_headers(), timeout=30)
            if resp.status_code == 200:
                name = resp.json().get("name", f"User_{user_id}")
                if "Baxtiyorjon Gaziyev" in name:
                    return "Oydin (Sales Manager)"
                return name
        except Exception:
            logger.debug("[SALES_ANALYTICS] Failed to fetch user name for user_id=%s", user_id, exc_info=True)
        return f"User_{user_id}"

    def generate_manager_scorecard(self) -> str:
        now = time.time()
        today_start = int(
            datetime.now().replace(hour=0, minute=0, second=0).timestamp()
        )
        month_start = int(
            datetime.now().replace(day=1, hour=0, minute=0, second=0).timestamp()
        )

        all_leads = self._get_all_leads(self.SALES_PIPELINE)
        manager_stats: Dict[int, Dict] = {}

        for lead in all_leads:
            responsible = lead.get("responsible_user_id")
            if not responsible:
                continue

            if responsible not in manager_stats:
                manager_stats[responsible] = {
                    "name": None,
                    "sales_active": 0,
                    "today_touched": 0,
                    "today_won": 0,
                    "month_won": 0,
                    "month_revenue": 0,
                    "stagnated": 0,
                    "total_active": 0,
                }

            stats = manager_stats[responsible]
            status_id = lead.get("status_id", 0)
            pipeline_id = lead.get("pipeline_id", 0)
            updated_at = lead.get("updated_at", 0)
            closed_at = lead.get("closed_at", 0)
            price = lead.get("price", 0) or 0

            if status_id not in [self.STATUS_WON, self.STATUS_LOST]:
                stats["total_active"] += 1
                if pipeline_id == self.SALES_PIPELINE:
                    stats["sales_active"] += 1

                if (now - updated_at) > 86400:
                    stats["stagnated"] += 1

                if updated_at >= today_start:
                    stats["today_touched"] += 1

            if status_id == self.STATUS_WON:
                if closed_at and closed_at >= today_start:
                    stats["today_won"] += 1
                if closed_at and closed_at >= month_start:
                    stats["month_won"] += 1
                    stats["month_revenue"] += price

        for uid in manager_stats:
            manager_stats[uid]["name"] = self._get_user_name(uid)

        report = "📊 <b>BUGUNGI SOTUV HISOBOTI</b>\n"
        report += f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        report += "━" * 30 + "\n"

        if not manager_stats:
            report += "\n⚠️ Hozircha hech qanday ma'lumot yo'q."
            return report

        sorted_managers = sorted(
            manager_stats.items(), key=lambda x: x[1]["month_revenue"], reverse=True
        )

        total_revenue = 0
        total_won = 0

        for i, (uid, s) in enumerate(sorted_managers, 1):
            name = s["name"] or f"Menejer_{uid}"
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."

            report += f"\n{medal} <b>{name}</b>\n"
            report += f"   👥 Ish jarayonidagi mijozlar: {s['total_active']} ta\n"
            report += f"   ✅ Bugun muloqot qilgan: {s['today_touched']} | Sotuv: {s['today_won']}\n"

            if s["month_won"] > 0:
                report += f"   💰 Oylik natija: {s['month_won']} ta sotuv = {s['month_revenue']:,.0f} so'm\n".replace(
                    ",", " "
                )
            else:
                report += "   💰 Oylik natija: 0 ta sotuv\n"

            if s["stagnated"] > 0:
                report += f"   🚨 <b>DIQQAT: {s['stagnated']} ta mijoz 24 soatdan beri qarovsiz!</b>\n"

            report += (
                "   📝 CRM Intizomi: Har bir mijozda vazifa (zadacha) bo'lishi shart!\n"
            )

            total_revenue += s["month_revenue"]
            total_won += s["month_won"]

        target = 80_000_000
        pct = (total_revenue / target * 100) if target > 0 else 0
        bar_fill = int(pct / 10)
        bar = "█" * min(bar_fill, 10) + "░" * (10 - int(pct / 10))

        report += "\n" + "━" * 30
        report += "\n📈 <b>JAMOA NATIJASI:</b>"
        report += (
            f"\n   Jami sotuv: {total_won} ta | {total_revenue:,.0f} so'm".replace(
                ",", " "
            )
        )
        report += f"\n   🎯 Oylik maqsad: {target:,.0f} so'm ({pct:.0f}%)".replace(
            ",", " "
        )
        report += f"\n   [{bar}]"

        report += "\n\n💡 <b>OISHA-AI MASLAHATLARI:</b>\n"
        report += "1. <b>Vazifasiz (zadacha) mijoz — yo'qolgan mijoz!</b> Agar hozir zadacha qo'ymasangiz, u esdan chiqadi.\n"
        report += "2. <b>Izohlar (primechaniya) sifatli bo'lsin:</b> Mijoz nima dedi? Nega sotib olmadi? Shularni yozmasangiz, xatolarni tuzata olmaysiz.\n"
        report += "3. <b>CRM — bu sizning yordamchingiz,</b> dushmaningiz emas. To'g'ri ishlatsangiz, sotuvingiz 2 barobar oshadi! 🚀"

        return report
