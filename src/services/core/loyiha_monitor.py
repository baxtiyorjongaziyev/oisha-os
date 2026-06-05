"""
Loyiha Ritmi Monitor — Blok 9, 14
Airtable loyihalar bo'yicha sariq/qizil xavf signallari.

Sariq  = deadline 3 kun yoki kamroq qolgan
Qizil  = deadline bugun yoki o'tib ketgan
"""
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

YELLOW_DAYS = 3


class LoyihaMonitor:
    """
    Kunlik loyiha risk skaneri. Airtable'dan faol loyihalar olinib,
    deadline yaqinlashganlarga sariq, o'tib ketganlarga qizil signal chiqariladi.
    """

    def __init__(self, airtable, db, settings):
        self.airtable = airtable
        self.db = db
        self.settings = settings

    async def run(self) -> str:
        """Full risk scan. Returns Telegram-formatted alert, or '' if all clear."""
        try:
            projects = await asyncio.to_thread(self.airtable.get_projects, True)
        except Exception as e:
            logger.error("LoyihaMonitor: Airtable error: %s", e)
            return ""

        today = date.today()
        red, yellow, no_deadline = [], [], []

        for p in projects:
            stage = p.get("stage", "")
            if stage in self.airtable.DONE_STAGES:
                continue

            name = p.get("project_name") or p.get("name") or "Nomsiz"
            deadline_str = p.get("deadline") or ""
            manager = p.get("manager") or "—"
            record_id = p.get("id") or ""
            url = self.airtable.get_record_url(record_id) if record_id else None

            if not deadline_str:
                no_deadline.append({"name": name, "manager": manager, "stage": stage})
                continue

            try:
                dl = datetime.fromisoformat(deadline_str[:10]).date()
            except (ValueError, TypeError):
                continue

            days_left = (dl - today).days
            entry = {
                "name": name,
                "manager": manager,
                "stage": stage,
                "deadline": dl.strftime("%d.%m.%Y"),
                "days_left": days_left,
                "url": url,
            }
            if days_left <= 0:
                red.append(entry)
            elif days_left <= YELLOW_DAYS:
                yellow.append(entry)

        return self._format_alert(red, yellow, no_deadline)

    async def get_risk_summary(self) -> dict:
        """Returns counts dict for dashboard use."""
        try:
            projects = await asyncio.to_thread(self.airtable.get_projects)
        except Exception:
            return {"red": 0, "yellow": 0, "no_deadline": 0, "total_active": 0}

        today = date.today()
        red = yellow = no_deadline = total_active = 0

        for p in projects:
            if p.get("stage") in self.airtable.DONE_STAGES:
                continue
            total_active += 1
            dl_str = p.get("deadline") or ""
            if not dl_str:
                no_deadline += 1
                continue
            try:
                dl = datetime.fromisoformat(dl_str[:10]).date()
                days_left = (dl - today).days
                if days_left <= 0:
                    red += 1
                elif days_left <= YELLOW_DAYS:
                    yellow += 1
            except (ValueError, TypeError):
                pass

        return {"red": red, "yellow": yellow, "no_deadline": no_deadline, "total_active": total_active}

    def _format_alert(self, red: list, yellow: list, no_deadline: list) -> str:
        if not red and not yellow and not no_deadline:
            return ""

        lines = ["🗂 *LOYIHA RITMI — XAVF SKANERI*\n"]

        if red:
            lines.append(f"🔴 *QIZIL XAVF — {len(red)} ta (deadline o'tdi/bugun):*")
            for p in red:
                link = f"[{p['name']}]({p['url']})" if p.get("url") else p["name"]
                note = f"{abs(p['days_left'])} kun kechikkan" if p["days_left"] < 0 else "BUGUN"
                lines.append(f"  • {link} | {p['stage']} | PM: {p['manager']} | {note}")
            lines.append("")

        if yellow:
            lines.append(f"🟡 *SARIQ XAVF — {len(yellow)} ta ({YELLOW_DAYS} kun va kam qolgan):*")
            for p in yellow:
                link = f"[{p['name']}]({p['url']})" if p.get("url") else p["name"]
                lines.append(f"  • {link} | {p['stage']} | PM: {p['manager']} | {p['days_left']} kun")
            lines.append("")

        if no_deadline:
            lines.append(f"⚫ *DEADLINE YO'Q — {len(no_deadline)} ta:*")
            for p in no_deadline[:5]:
                lines.append(f"  • {p['name']} | {p['stage']} | PM: {p['manager']}")
            if len(no_deadline) > 5:
                lines.append(f"  ... va yana {len(no_deadline) - 5} ta")
            lines.append("")

        lines.append(f"_Skan: {datetime.now().strftime('%d.%m.%Y %H:%M')}_")
        return "\n".join(lines)
