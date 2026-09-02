"""
Stagnation alert and monitoring for sales analytics.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, List

import structlog

logger = structlog.get_logger()


class StagnationAlertMixin:
    """Mixin for identifying and alerting on stagnated leads."""

    def get_stagnated_leads_by_manager(self, hours: int = 24) -> Dict[int, List[Dict]]:
        now = time.time()
        limit = hours * 3600
        result: Dict[int, List[Dict]] = {}

        for pipeline_name, pipeline_id in [
            ("SALES", self.SALES_PIPELINE),
        ]:
            leads = self._get_all_leads(pipeline_id)
            for lead in leads:
                status_id = lead.get("status_id", 0)
                if status_id in [self.STATUS_WON, self.STATUS_LOST]:
                    continue

                updated_at = lead.get("updated_at", 0)
                if (now - updated_at) > limit:
                    responsible = lead.get("responsible_user_id", 0)
                    if responsible not in result:
                        result[responsible] = []

                    idle_hours = int((now - updated_at) / 3600)
                    idle_days = idle_hours // 24

                    result[responsible].append(
                        {
                            "id": lead["id"],
                            "name": lead.get("name", "Nomsiz"),
                            "pipeline": pipeline_name,
                            "idle_hours": idle_hours,
                            "idle_text": (
                                f"{idle_days} kun"
                                if idle_days >= 1
                                else f"{idle_hours} soat"
                            ),
                            "link": f"https://{self.amo.subdomain}.amocrm.ru/leads/detail/{lead['id']}",
                            "price": lead.get("price", 0) or 0,
                        }
                    )

        return result

    def generate_stagnation_alert(self, hours: int = 24) -> str:
        stagnated = self.get_stagnated_leads_by_manager(hours)

        if not stagnated:
            return ""

        total_count = sum(len(leads) for leads in stagnated.values())
        total_value = sum(l["price"] for leads in stagnated.values() for l in leads)

        report = "🚨 <b>STAGNATSIYA ALERT</b>\n"
        report += f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        report += f"⚠️ {total_count} ta lid {hours}+ soat harakatsiz"
        if total_value > 0:
            report += f" (umumiy: {total_value:,.0f} so'm)".replace(",", " ")
        report += "\n" + "━" * 30 + "\n"

        for uid, leads in stagnated.items():
            name = self._get_user_name(uid)
            report += f"\n👤 <b>{name}</b> — {len(leads)} ta lid:\n"

            for lead in sorted(leads, key=lambda x: x["idle_hours"], reverse=True)[:5]:
                emoji = (
                    "🔴"
                    if lead["idle_hours"] >= 72
                    else "🟡" if lead["idle_hours"] >= 48 else "⚠️"
                )
                report += f"   {emoji} {lead['name']} ({lead['pipeline']}) — <b>{lead['idle_text']}</b>"
                if lead["price"] > 0:
                    report += f" 💰{lead['price']:,.0f}".replace(",", " ")
                report += "\n"

            if len(leads) > 5:
                report += f"   ... va yana {len(leads) - 5} ta\n"

        report += "\n💡 <i>Harakatsiz lidlar — yo'qotilgan foyda! Bugun bog'laning yoki sababini belgilang.</i>"
        return report
