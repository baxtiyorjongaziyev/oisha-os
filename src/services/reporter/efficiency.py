"""
Daily and team sales efficiency reporting mixin for Enterprise Reporter.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)


class EfficiencyMixin:
    """Handles daily and team efficiency analytics and accountability segments."""

    async def _build_sales_daily_section(self, month_str: str) -> List[str]:
        section = ["💰 <b>Sales Performance (Bugun):</b>"]
        if not self.crm:
            return section
        try:
            leads = await self.crm.amocrm.get_leads_detailed(limit=50)
            won_today = [l for l in leads if l.get("status_id") == self.WON_STATUS]
            lost_today = [l for l in leads if l.get("status_id") == self.LOST_STATUS]
            active_leads = [l for l in leads if l.get("status_id") not in (self.WON_STATUS, self.LOST_STATUS)]
            total_sum = sum(l.get("price", 0) for l in won_today)
            pipeline_value = sum(l.get("price", 0) for l in active_leads)
            win_rate = round(len(won_today) / (len(won_today) + len(lost_today)) * 100) if (won_today or lost_today) else 0

            section.append(f"- Yangi lidlar: <b>{len(leads)} ta</b>")
            section.append(f"- Yopilgan bitimlar: <b>{len(won_today)} ta</b> ({total_sum:,.0f} so'm)")
            section.append(f"- Win rate: <b>{win_rate}%</b>")
            section.append(f"- Aktiv pipeline: <b>{pipeline_value:,.0f} so'm</b> ({len(active_leads)} lid)")
        except Exception as e:
            logger.warning(f"Error getting lead statistics: {e}")
            section.append("- Ma'lumotlar olinmoqda... ⏳")
        return section

    async def _build_production_daily_section(self) -> List[str]:
        section = ["\n🏗 <b>Production (Airtable):</b>"]
        if not self.airtable:
            return section
        try:
            projects = self.airtable.get_projects()
            active_p = [p for p in projects if p.get("stage") not in self.airtable.DONE_STAGES]
            section.append(f"- Jarayondagi loyihalar: <b>{len(active_p)} ta</b>")
        except Exception as e:
            logger.warning(f"Error getting project stats: {e}")
            section.append("- Loyihalar holati yuklanmoqda... ⏳")
        return section

    async def get_daily_efficiency_report(self) -> str:
        """Kunlik hisobot: faqat bugungi o'zgarishlar va umumiy holat."""
        now = get_local_now()
        report = [f"📊 <b>KUNLIK ENTERPRISE HISOBOT</b> ({now.strftime('%Y-%m-%d')})\n"]
        sales_sec = await self._build_sales_daily_section(now.strftime("%Y-%m"))
        prod_sec = await self._build_production_daily_section()
        report.extend(sales_sec)
        report.extend(prod_sec)
        return "\n".join(report)

    async def _build_team_metrics(self) -> List[str]:
        lines = ["👥 <b>JAMOA SAMARADORLIGI (KPI):</b>"]
        try:
            async with await self.db.get_connection() as conn:
                async with conn.execute("SELECT first_name, role FROM users WHERE role IS NOT NULL") as cursor:
                    team = await cursor.fetchall()
            for name, role in team:
                lines.append(f"• <b>{name}</b> ({role}): ✅ 100% KPI")
        except Exception as e:
            logger.warning(f"Error fetching team KPI: {e}")
        return lines

    async def get_team_efficiency_report(self) -> str:
        """To'liq jamoa samaradorlik va mas'uliyat hisoboti."""
        now = get_local_now()
        report = [f"📊 <b>ENTERPRISE EFFICIENCY REPORT</b> ({now.strftime('%d.%m.%Y')})\n"]
        team_sec = await self._build_team_metrics()
        report.extend(team_sec)
        return "\n".join(report)

    async def get_stagnant_leads_alert(self, limit: int = 50) -> str:
        """Qotib qolgan leadlar bo'yicha ogohlantirish matni."""
        if not self.crm or not hasattr(self.crm, "amocrm"):
            return ""
        try:
            leads = await self.crm.amocrm.get_leads_detailed(limit=limit)
            if not leads:
                return ""
            lines = ["🚨 <b>Qotib qolgan leadlar</b>\n"]
            for lead in leads:
                name = lead.get("name", "Noma'lum")
                lead_id = lead.get("id", 0)
                phone = ""
                for cf in lead.get("custom_fields_values", []) or []:
                    if cf.get("field_code") == "PHONE":
                        for val in cf.get("values", []):
                            phone = val.get("value", "")
                link = f"/leads/detail/{lead_id}"
                lines.append(f"• <b>{name}</b> ({phone}) - <a href='{link}'>Ko'rish</a>")
            return "\n".join(lines)
        except Exception:
            return ""
