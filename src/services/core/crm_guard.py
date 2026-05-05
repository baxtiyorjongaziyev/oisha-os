"""
CRM Guard — AmoCRM intizomini nazorat qiluvchi agent.
Vazifasi: Zadachasi yo'q lidlarni topish va jazolash/ogohlantirish.
"""

import logging
from typing import List, Dict
from src.services.core.amocrm_sync import AmoCRMSync

logger = logging.getLogger("CRMGuard")


class CRMGuard:
    def __init__(self, amo: AmoCRMSync, db, bot=None, nagger=None):
        self.amo = amo
        self.db = db
        self.bot = bot
        self.nagger = nagger
        self.HUNTER_PIPELINE = 10117998
        self.CLOSER_PIPELINE = 10123314

    async def check_discipline(self, pipeline_id: int):
        """
        Pipeline'dagi barcha lidlarni tekshiradi.
        Zadachasi yo'qlarni aniqlaydi.
        """
        logger.info(f"[GUARD] {pipeline_id} pipeline tekshirilyapti...")
        leads = await self._get_active_leads(pipeline_id)
        if not leads:
            logger.info(
                f"[GUARD] {pipeline_id} pipeline uchun tekshiriladigan aktiv lead topilmadi."
            )
            return

        # Fetch all active tasks to avoid N+1 problem
        tasks = await self._get_all_active_tasks()
        leads_with_tasks = {
            t.get("entity_id") for t in tasks if t.get("entity_type") == "leads"
        }

        # Group leads by manager
        manager_map = {}
        for lead in leads:
            if lead["id"] not in leads_with_tasks:
                m_id = lead.get("responsible_user_id")
                if m_id not in manager_map:
                    manager_map[m_id] = []
                manager_map[m_id].append(lead)

        # Notify managers who have leads without tasks or stagnant leads
        if self.nagger:
            for m_id, problem_leads in manager_map.items():
                if problem_leads:
                    # Get manager info (simplified for demo)
                    m_name = f"Menejer_{m_id}"
                    await self.nagger.nag_about_stagnation(m_id, m_name, problem_leads)

    async def _get_active_leads(self, pipeline_id: int) -> List[Dict]:
        """AmoCRM'dan aktiv lidlarni olish."""
        import requests

        url = f"{self.amo.base_url}/api/v4/leads"
        params = {"filter[pipeline_id]": pipeline_id, "limit": 50}
        try:
            resp = requests.get(url, headers=self.amo._get_headers(), params=params)
            if resp.status_code == 200:
                return resp.json().get("_embedded", {}).get("leads", [])
            return []
        except Exception as e:
            logger.error(f"[GUARD] Lead fetch failed: {e}")
            return []

    async def _get_all_active_tasks(self) -> List[Dict]:
        """Barcha aktiv vazifalarni bir marta olish."""
        import requests

        url = f"{self.amo.base_url}/api/v4/tasks"
        params = {"filter[is_completed]": 0, "limit": 250}
        try:
            resp = requests.get(url, headers=self.amo._get_headers(), params=params)
            if resp.status_code == 200:
                return resp.json().get("_embedded", {}).get("tasks", [])
            return []
        except Exception as e:
            logger.error(f"[GUARD] Bulk task fetch failed: {e}")
            return []
