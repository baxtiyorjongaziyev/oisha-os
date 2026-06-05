"""
Order Lifecycle — Blok 51, 52
Buyurtma hayot sikli: CRM (yopildi) → Airtable (loyiha) → final → follow-up.

Gap detection: yopilgan deal lekin Airtable'da loyiha yo'q → qizil signal.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

WON_STATUS_ID = 142   # AmoCRM "Muvaffaqiyatli yopildi" statusi
LOOKUP_DAYS = 45       # Faqat so'nggi N kungi won deallarni tekshir


class OrderLifecycle:
    """
    CRM'dagi yopilgan deallar Airtable'da loyiha sifatida mavjudligini tekshiradi.
    Uzilgan zanjir aniqlansa — qizil signal chiqaradi.
    """

    def __init__(self, crm, airtable, db, settings):
        self.crm = crm
        self.airtable = airtable
        self.db = db
        self.settings = settings

    async def detect_gaps(self) -> str:
        """
        Won deals without matching Airtable project.
        Returns Telegram alert string, or '' if no gaps.
        """
        try:
            crm_leads = await self.crm.get_leads(status_id=WON_STATUS_ID)
        except Exception as exc:
            logger.error("OrderLifecycle CRM: %s", exc)
            return ""

        try:
            projects = await asyncio.to_thread(self.airtable.get_projects)
        except Exception as exc:
            logger.error("OrderLifecycle Airtable: %s", exc)
            return ""

        # Build normalized name set from Airtable
        airtable_names: set = set()
        for p in projects:
            raw = p.get("project_name") or p.get("name") or ""
            airtable_names.add(raw.lower().strip())

        cutoff = datetime.now() - timedelta(days=LOOKUP_DAYS)
        missing = []

        for lead in crm_leads[:60]:
            created_ts = lead.get("created_at") or 0
            if created_ts and datetime.fromtimestamp(created_ts) < cutoff:
                continue

            lead_name = (lead.get("name") or "").strip()
            if not lead_name:
                continue

            norm = lead_name.lower()
            # Exact or partial match
            found = norm in airtable_names or any(
                norm in an or an in norm
                for an in airtable_names
                if len(an) > 4
            )
            if not found:
                missing.append({
                    "name": lead_name,
                    "id": lead.get("id"),
                    "price": lead.get("price") or 0,
                    "date": datetime.fromtimestamp(created_ts).strftime("%d.%m.%Y")
                    if created_ts
                    else "?",
                })

        if not missing:
            return ""

        lines = [
            "🚨 *BUYURTMA ZANJIRI UZILGAN*\n",
            f"CRM'da yopilgan, Airtable'da loyiha *yo'q* — {len(missing)} ta:\n",
        ]
        for m in missing[:10]:
            lines.append(
                f"• *{m['name']}* | {m['price']:,} UZS | CRM: {m['date']}"
            )
        if len(missing) > 10:
            lines.append(f"... va yana {len(missing) - 10} ta")

        lines.append(
            "\n_To'lov olindi — Shturman Airtable kartasini ochishi shart edi!_"
        )
        return "\n".join(lines)

    async def get_summary(self) -> str:
        """Full lifecycle health check: gap detection + payment-less in-progress."""
        parts = []

        gap_alert = await self.detect_gaps()
        if gap_alert:
            parts.append(gap_alert)

        # Projects in execution without payment status
        try:
            projects = await asyncio.to_thread(self.airtable.get_projects)
            in_progress_stages = {"Ijroda", "In Progress", "Bajarilmoqda", "Loyiha ustida ishlanmoqda"}
            no_pay = [
                p for p in projects
                if p.get("stage") in in_progress_stages
                and not (p.get("payment_status") or "").strip()
            ]
            if no_pay:
                names = "\n".join(
                    f"  • {p.get('project_name') or p.get('name') or '?'}"
                    for p in no_pay[:6]
                )
                parts.append(
                    f"⚠️ *To'lov statusi yo'q loyihalar (ijroda):* {len(no_pay)} ta\n{names}"
                )
        except Exception:
            pass

        if not parts:
            return "✅ *Buyurtma zanjiri:* Barcha jarayonlar tartibda."

        return "\n\n".join(parts)

    async def get_won_without_project(self, days: int = LOOKUP_DAYS) -> list:
        """
        Returns list of won deals missing from Airtable.
        Used for programmatic access.
        """
        try:
            crm_leads = await self.crm.get_leads(status_id=WON_STATUS_ID)
            projects = await asyncio.to_thread(self.airtable.get_projects)
        except Exception:
            return []

        airtable_names: set = set()
        for p in projects:
            raw = p.get("project_name") or p.get("name") or ""
            airtable_names.add(raw.lower().strip())

        cutoff = datetime.now() - timedelta(days=days)
        result = []

        for lead in crm_leads[:60]:
            ts = lead.get("created_at") or 0
            if ts and datetime.fromtimestamp(ts) < cutoff:
                continue
            name = (lead.get("name") or "").strip()
            if not name:
                continue
            norm = name.lower()
            if norm not in airtable_names and not any(
                norm in an or an in norm for an in airtable_names if len(an) > 4
            ):
                result.append(lead)

        return result
