"""
Real numbers CRM pipeline audit and junk/stagnant lead identification mixin.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import requests

from src.time_utils import get_local_now

logger = logging.getLogger(__name__)


def _calculate_audit_metrics(
    all_leads: List[Dict[str, Any]], all_tasks: List[Dict[str, Any]], now_ts: float,
    won_status: Any, lost_status: Any
) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {
        "total_leads": len(all_leads), "active_leads": 0, "stagnant_24h": [],
        "stagnant_48h": [], "stagnant_7d": [], "no_tasks": [], "overdue_tasks": [],
        "revenue_at_risk": 0,
    }
    for lead in all_leads:
        if lead.get("status_id") in [won_status, lost_status]:
            continue
        metrics["active_leads"] += 1
        lead_id = lead.get("id")
        hours_stagnant = (now_ts - lead.get("updated_at", 0)) / 3600
        price = lead.get("price", 0) or 0

        if hours_stagnant > 24:
            metrics["stagnant_24h"].append(lead)
            metrics["revenue_at_risk"] += price
        if hours_stagnant > 48:
            metrics["stagnant_48h"].append(lead)
        if hours_stagnant > 7 * 24:
            metrics["stagnant_7d"].append(lead)

        lead_tasks = [t for t in all_tasks if t.get("entity_id") == lead_id]
        if not lead_tasks:
            metrics["no_tasks"].append(lead)
        elif any(t.get("complete_till", 0) < now_ts for t in lead_tasks):
            metrics["overdue_tasks"].append(lead)
    return metrics


def _calculate_health_score(metrics: Dict[str, Any], unsorted_count: int) -> int:
    penalties = (
        len(metrics["no_tasks"]) * 10
        + len(metrics["overdue_tasks"]) * 5
        + len(metrics["stagnant_24h"]) * 3
        + len(metrics["stagnant_48h"]) * 5
        + len(metrics["stagnant_7d"]) * 10
        + unsorted_count * 2
    )
    return max(0, 100 - min(penalties, 100))


class AuditMixin:
    """Handles deep CRM audit, junk lead detection, and stagnation alerts."""

    async def _fetch_leads_and_tasks(self) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
        all_leads: List[Dict[str, Any]] = []
        for page in [1, 2]:
            url = f"{self.crm.amocrm.base_url}/api/v4/leads?limit=100&page={page}"
            resp = requests.get(url, headers=self.crm.amocrm._get_headers(), timeout=30)
            if resp.status_code == 200:
                all_leads.extend(resp.json().get("_embedded", {}).get("leads", []))
            else:
                break
        all_tasks = await self.crm.amocrm.get_tasks() if all_leads else []
        unsorted_count = 0
        try:
            un_resp = requests.get(f"{self.crm.amocrm.base_url}/api/v4/leads/unsorted", headers=self.crm.amocrm._get_headers(), timeout=30)
            if un_resp.status_code == 200:
                unsorted_count = len(un_resp.json().get("_embedded", {}).get("unsorted", []))
        except Exception:
            pass
        return all_leads, all_tasks, unsorted_count

    async def get_real_numbers_audit(self) -> str:
        """Real raqamlarda jamoa auditi."""
        now = get_local_now()
        all_leads, all_tasks, unsorted = await self._fetch_leads_and_tasks()
        if not all_leads:
            return "❌ **XATO:** AmoCRM'dan lidlar olinmadi. Token tekshiring."

        metrics = _calculate_audit_metrics(all_leads, all_tasks, time.time(), self.WON_STATUS, self.LOST_STATUS)
        health_score = _calculate_health_score(metrics, unsorted)

        report = [
            f"📊 *OISHA-OS: CRM HYGIENE & PERFORMANCE AUDIT*\n📅 _{now.strftime('%d.%m.%Y | %H:%M')}_\n",
            f"📈 **CRM SALOMATLIGI: {health_score}%**",
            f"• Jami aktiv lidlar: **{metrics['active_leads']} ta**",
            f"• ❌ Vazifasiz lidlar: **{len(metrics['no_tasks'])} ta**",
            f"• ⏰ Muddati o'tgan vazifalar: **{len(metrics['overdue_tasks'])} ta**",
            f"• 🐌 24h Stagnatsiya: **{len(metrics['stagnant_24h'])} ta**",
            f"• 💰 Xavf ostidagi summa: **{metrics['revenue_at_risk']:,.0f} so'm**",
        ]
        return "\n".join(report)

    async def identify_junk_leads(self, limit: int = 250) -> List[Dict[str, Any]]:
        """Identify 'junk' leads in amoCRM based on inactivity, lack of data, or stagnation."""
        all_leads = await self.crm.amocrm.get_leads_detailed(limit=limit)
        if not all_leads:
            return []
        junk = []
        now_ts = time.time()
        for lead in all_leads:
            if lead.get("status_id") in [self.WON_STATUS, self.LOST_STATUS]:
                continue
            updated_at = lead.get("updated_at", 0)
            if (now_ts - updated_at) > (14 * 86400):  # 14 days inactive
                junk.append(lead)
        return junk

    async def get_junk_leads_report(self) -> str:
        """Format junk leads into readable report."""
        junk = await self.identify_junk_leads(limit=100)
        if not junk:
            return "✅ **CRM TOZA:** Hech qanday bekorchi (junk) sdelkalar topilmadi."
        lines = [f"🧹 **CRM TOZALIK AUDITI:** Jami {len(junk)} ta shubhali sdelka aniqlandi:"]
        for lead in junk[:10]:
            lines.append(f"• ID: `{lead.get('id')}` | {lead.get('name', 'Nomsiz')} | ${lead.get('price', 0)}")
        return "\n".join(lines)
