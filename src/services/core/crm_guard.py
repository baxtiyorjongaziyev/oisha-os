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
        Menejerni 'chiroyli' majburlash.
        1. AmoCRM'da avtomatik zadacha ochish.
        2. Telegram'da shaxsiy 'hay-hay' xabari yuborish.
        """
        manager_id = lead.get("responsible_user_id")
        lead_name = lead.get("name", "Nomsiz lid")
        
        # 1. Avto-Zadacha
        task_text = f"🚨 TIZIM OGOHLANTIRISHI: Ushbu mijozda zadacha yo'q edi. Oisha-AI avtomatik yaratdi. Tezda bog'laning!"
        # self.amo.create_task(...) 
        
        # 2. Telegram Alert
        if self.bot:
            msg = (
                f"🚨 <b>INTIZOM OGOHLANTIRISHI!</b>\n\n"
                f"Oydin, siz <b>'{lead_name}'</b> mijoziga vazifa qo'yishni unutdingiz.\n"
                f"CRM'da zadacha bo'lmasligi — mijozni yo'qotish bilan teng.\n\n"
                f"👉 Men siz uchun avtomatik zadacha ochdim. Iltimos, darhol bajaring!"
            )
            # await self.bot.send_message(manager_telegram_id, msg)
            pass
