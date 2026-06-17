"""Sotuvchi uchun kunlik digest va stagnatsiya aniqlash."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from src.settings import settings
from src.services.core.amocrm_sync import AmoCRMSync
from src.services.core.amocrm_pipeline_config import (
    ACTIVE_PIPELINE_IDS,
    REACTIVATION_DAILY_LIMIT,
    REACTIVATION_PIPELINE_ID,
    SALES_PIPELINE_ID,
)

logger = logging.getLogger(__name__)

STAGNATION_HOURS = {
    "Yangi so'rov": 24,
    "Birinchi kontakt qilindi": 48,
    "Bog'lanib bo'lmadi": 48,
    "Muloqot boshlandi": 72,
    "Sifatli lead": 72,
    "Uchrashuv belgilandi": 48,
    "Konsultatsiya o'tdi": 72,
    "Brief / Ehtiyoj aniqlandi": 96,
    "Prezentatsiya & KP": 96,
    "Follow-up / Qaror kutilyapti": 48,
    "Muzokara / Shartnoma": 72,
}
DEFAULT_STAGNATION_HOURS = 72


class SalesRepService:
    def __init__(self):
        self.amo = AmoCRMSync(
            subdomain=settings.AMOCRM_SUBDOMAIN,
            client_id=settings.AMOCRM_CLIENT_ID,
            client_secret=(
                settings.AMOCRM_CLIENT_SECRET.get_secret_value()
                if settings.AMOCRM_CLIENT_SECRET
                else ""
            ),
            redirect_url=settings.AMOCRM_REDIRECT_URL,
        )
        self.amo._load_token()

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.amo.base_url}{path}"
        r = requests.get(url, headers=self.amo._get_headers(), params=params or {}, timeout=30)
        if r.status_code == 401 and self.amo.refresh_token():
            r = requests.get(url, headers=self.amo._get_headers(), params=params or {}, timeout=30)
        if r.status_code in (204, 404):
            return {}
        r.raise_for_status()
        return r.json()

    def get_manager_leads(self, manager_amo_id: int, pipeline_ids: list[int] | None = None) -> list[dict]:
        """Menejerning barcha ochiq lidlarini olish."""
        if pipeline_ids is None:
            pipeline_ids = ACTIVE_PIPELINE_IDS
        all_leads = []
        for pid in pipeline_ids:
            data = self._get("/api/v4/leads", {
                "filter[responsible_user_id]": manager_amo_id,
                "filter[pipeline_id]": pid,
                "limit": 250,
                "with": "contacts,pipeline,status",
            })
            leads = data.get("_embedded", {}).get("leads", [])
            all_leads.extend(l for l in leads if l.get("status_id") not in (142, 143))
        return all_leads

    def get_stagnated_leads(self, leads: list[dict]) -> list[dict]:
        """Stagnatsiyaga uchragan lidlarni aniqlash."""
        now = datetime.now(timezone.utc)
        stagnated = []
        for lead in leads:
            status_name = (lead.get("_embedded", {}).get("status", {}) or {}).get("name", "")
            threshold_hours = STAGNATION_HOURS.get(status_name, DEFAULT_STAGNATION_HOURS)
            updated_at = lead.get("updated_at", 0) or 0
            if updated_at:
                updated = datetime.fromtimestamp(updated_at, tz=timezone.utc)
                if (now - updated).total_seconds() / 3600 > threshold_hours:
                    lead["_stagnation_hours"] = int((now - updated).total_seconds() / 3600)
                    stagnated.append(lead)
        return stagnated

    def get_todays_top5(self, leads: list[dict]) -> list[dict]:
        """Eng muhim 5 ta lid — stagnatsiyalilar birinchi, keyin updated_at bo'yicha eski."""
        stagnated = self.get_stagnated_leads(leads)
        stagnated_ids = {l["id"] for l in stagnated}

        priority = sorted(stagnated, key=lambda l: l.get("_stagnation_hours", 0), reverse=True)
        rest = sorted(
            [l for l in leads if l["id"] not in stagnated_ids],
            key=lambda l: l.get("updated_at", 0),
        )
        combined = priority + rest
        return combined[:5]

    def format_lead_line(self, lead: dict, idx: int) -> str:
        """Lid uchun qisqa matn qatori."""
        name = lead.get("name", "—")
        status = (lead.get("_embedded", {}).get("status", {}) or {}).get("name", "")
        lead_id = lead["id"]
        stag = lead.get("_stagnation_hours")
        url = f"https://{settings.AMOCRM_SUBDOMAIN}.amocrm.ru/leads/detail/{lead_id}"
        stag_str = f" ⚠️ {stag}s" if stag else ""
        return f"{idx}. [{name}]({url})\n   📍 {status}{stag_str}"

    async def send_daily_digest(self, bot, manager_tg_id: int, manager_amo_id: int) -> None:
        """Menejergа kunlik shaxsiy digest yuborish."""
        try:
            leads = self.get_manager_leads(manager_amo_id)
            top5 = self.get_todays_top5(leads)

            if not top5:
                await bot.send_message(manager_tg_id, "✅ Bugun sizda faol lid yo'q.")
                return

            lines = [self.format_lead_line(l, i + 1) for i, l in enumerate(top5)]
            text = (
                f"🎯 *Bugungi TOP-5 lidingiz*\n\n"
                + "\n\n".join(lines)
                + f"\n\n📊 Jami ochiq: {len(leads)} ta lid"
            )
            await bot.send_message(manager_tg_id, text, parse_mode="markdown", disable_web_page_preview=True)
        except Exception as e:
            logger.error("[SalesRepService] digest error for %s: %s", manager_tg_id, e)
