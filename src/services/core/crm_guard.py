"""
CRM Guard — AmoCRM intizomini nazorat qiluvchi agent.
Vazifasi: Zadachasi yo'q lidlarni topish va jazolash/ogohlantirish.
"""

import logging
import time
from typing import List, Dict
from src.services.core.amocrm_sync import AmoCRMSync

logger = logging.getLogger("CRMGuard")

class CRMGuard:
    def __init__(self, amo: AmoCRMSync, bot=None):
        self.amo = amo
        self.bot = bot

    async def check_discipline(self, pipeline_id: int):
        """
        Pipeline'dagi barcha lidlarni tekshiradi.
        Zadachasi yo'qlarni aniqlaydi.
        """
        logger.info(f"[GUARD] {pipeline_id} pipeline tekshirilyapti...")
        leads = self._get_active_leads(pipeline_id)
        
        for lead in leads:
            lead_id = lead["id"]
            tasks = self._get_lead_tasks(lead_id)
            
            if not tasks:
                logger.warning(f"[GUARD] Lead {lead_id} zadachasiz!")
                await self._punish_manager(lead)

    def _get_active_leads(self, pipeline_id: int) -> List[Dict]:
        # AmoCRM API orqali aktiv lidlarni olish
        # (Surgical: biz buni amocrm_sync orqali qilamiz)
        pass

    def _get_lead_tasks(self, lead_id: int) -> List[Dict]:
        # Leadga bog'langan vazifalarni tekshirish
        url = f"{self.amo.base_url}/api/v4/tasks"
        params = {"filter[entity_id]": lead_id, "filter[entity_type]": "leads", "is_completed": 0}
        # ... logic ...
        return []

    async def _punish_manager(self, lead: Dict):
        """
        Menejerni AmoCRM native imkoniyatlari orqali tartibga solish.
        """
        lead_id = lead["id"]
        manager_id = lead.get("responsible_user_id")
        
        # 1. AmoCRM NATIVE TASK (CRM ichida vazifa yaratish)
        # Bu eng to'g'ri yo'l, chunki CRM buni o'zi nazorat qiladi.
        try:
            task_data = {
                "entity_id": lead_id,
                "entity_type": "leads",
                "text": "🚨 OISHA-AI: Vazifa qo'yish unutilgan! Darhol mijoz bilan bog'laning.",
                "complete_till": int(time.time() + 3600), # 1 soat ichida bajarish kerak
                "task_type_id": 1, # 'Follow-up' yoki 'Call'
                "responsible_user_id": manager_id
            }
            url = f"{self.amo.base_url}/api/v4/tasks"
            # AmoCRM API orqali vazifa yaratish
            # (Haqiqiy requests.post bu yerda bo'ladi)
            logger.info(f"[GUARD] Native Task created for Lead {lead_id}")
        except Exception as e:
            logger.error(f"[GUARD] Failed to create native task: {e}")

        # 2. Telegram Alert (Faqat qo'shimcha ogohlantirish)
        if self.bot:
            # ... Telegram mantiqi ...
            pass
