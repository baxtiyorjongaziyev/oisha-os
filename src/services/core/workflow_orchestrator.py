import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from src.services.amocrm_sync import AmoCRMSync
from src.services.airtable_sync import AirtableSync

logger = logging.getLogger(__name__)

class WorkflowOrchestrator:
    """
    AmoCRM -> Airtable -> Portfolio zanjirini boshqaradigan markaziy 'Miya'.
    """
    def __init__(self, amocrm: AmoCRMSync, airtable: AirtableSync, notify_callback=None, team_group_id=None, advisor_agent=None):
        self.amocrm = amocrm
        self.airtable = airtable
        self.notify_callback = notify_callback
        self.team_group_id = team_group_id
        self.advisor_agent = advisor_agent
        
        # [CONFIG] Statuslar
        self.AMO_TRIGGER_STATUS = 142 
        self.AIRTABLE_DONE_STAGE = "Done"
        
        # [TEAM] Managerlar ro'yxati (2.3)
        self.TEAM = ["Ali", "Vali", "G'ani"] 
        self._last_assigned_index = 0

    def _get_next_manager(self):
        """Managerlarni navbatma-navbat tayinlash (Round-Robin)."""
        manager = self.TEAM[self._last_assigned_index]
        self._last_assigned_index = (self._last_assigned_index + 1) % len(self.TEAM)
        return manager

    async def _notify(self, text: str, send_to_team=True):
        """Xabarni ham sizga, ham jamoa guruhiga yuborish."""
        # 1. Owner/AdminBot callback
        if self.notify_callback:
            await self.notify_callback(text)
        
        # 2. Team Group Notification (4.4)
        if send_to_team and self.team_group_id:
            try:
                # Oisha (Userbot) orqali guruhga yuboramiz
                # Eslatma: 'self.amocrm' yoki 'self.airtable' orqali clientga ruxsat yo'q, 
                # lekin bizga bot_client yoki user_client kerak. 
                # Biz notify_callback ni 'admin_bot.notify_lead' ga bog'laganmiz. 
                # AdminBot-ni yangilab, unga guruhga yuborishni o'rgatamiz.
                pass 
            except Exception as e:
                logger.error(f"[TEAM NOTIFY ERROR] {e}")

    async def run_systematizer_sync(self, client=None):
        """
        Markaziy sinxronizatsiya vazifasi.
        1. AmoCRM'dagi yangi 'Yutilgan' bitimlarni tekshiradi.
        2. Airtable'da loyiha yaratadi (agar avval yaratilmagan bo'lsa).
        3. Airtable'dagi 'Done' loyihalarni aniqlab, portfolioga tayyorlaydi.
        """
        logger.info("👸 Oisha-OS: 'Order-to-Portfolio' tizimlashtirish tekshiruvi boshlandi... 🛡️")
        
        # 1. AmoCRM'dan bitimlarni olish
        leads = await self.amocrm.get_leads(status_id=self.AMO_TRIGGER_STATUS)
        
        for lead in leads:
            lead_id = lead.get("id")
            lead_name = lead.get("name")
            
            # Tekshirish: Bu loyiha Airtable'da bormi? (AmoCRM ID orqali)
            # Eslatma: Airtable'da 'AmoCRM_ID' degan maydon bo'lishi kerak.
            existing_projects = self.airtable.get_projects()
            found = False
            for p in existing_projects:
                if str(p.get("fields", {}).get("AmoCRM_ID")) == str(lead_id):
                    found = True
                    break
            
            if not found:
                logger.info(f"🚀 Yangi bitim aniqlandi! Airtable-da loyiha yaratilmoqda: {lead_name}")
                
                # Airtable'da yangi loyiha yaratish
                manager = self._get_next_manager()
                new_project_fields = {
                    "Project Name": lead_name,
                    "AmoCRM_ID": str(lead_id),
                    "Stage": "To Do",
                    "Manager": manager,
                    "Budget": lead.get("price", 0),
                    "Created At": datetime.now().strftime("%Y-%m-%d"),
                    "Last_Sync_Stage": "To Do"
                }
                
                self.airtable.create_record(new_project_fields)
                
                # AmoCRM-ga izoh qoldirish
                self.amocrm.add_lead_note(lead_id, f"Oisha: Airtable-da loyiha ochildi. Mas'ul: {manager} ✅")

                # [SALES CELEBRATION DISABLED: Shifting to Telegram Kirim Topic Trigger per user request]
                # responsible_id = lead.get("responsible_user_id")
                # manager_name = self.amocrm.get_user_name(responsible_id)
                # ... celebration_text logic removed from here ...
                pass
            else:
                # [NEW] Feedback Loop: Airtable statusi o'zgargan bo'lsa AmoCRM-ga yozamiz
                for p in existing_projects:
                    if str(p.get("fields", {}).get("AmoCRM_ID")) == str(lead_id):
                        current_stage = p.get("fields", {}).get("Stage")
                        last_sync = p.get("fields", {}).get("Last_Sync_Stage")
                        
                        if current_stage != last_sync:
                            logger.info(f"🔄 Status Sync: {lead_name} -> {current_stage}")
                            self.amocrm.add_lead_note(lead_id, f"Oisha Update: Loyiha bosqichi '{current_stage}' ga o'zgardi. 👸🛡️")
                            self.airtable.update_project_fields(p.get("id"), {"Last_Sync_Stage": current_stage})
                            
                            # Celebration Logic (4.4)
                            if current_stage == self.AIRTABLE_DONE_STAGE:
                                await self._notify(f"🥳 **Muvaffaqiyat!**\n\n'{lead_name}' loyihasi yakunlandi! ✅\nManager: {p.get('fields', {}).get('Manager')}\n\nJamoani tabriklayman! 👸👑")
                        break

        # [NEW] Deadline Alerts (3.3)
        upcoming = self.airtable.get_upcoming_deadlines(hours=24)
        for p in upcoming:
            fields = p.get("fields", {})
            if not fields.get("Deadline_Alert_Sent"):
                logger.warning(f"⏰ [ALERT] Loyiha muddati yaqin: {fields.get('Project Name')}")
                await self._notify(f"⚠️ **DIQQAT!**\n\n'{fields.get('Project Name')}' loyihasi muddati tugashiga 24 soatdan kam vaqt qoldi! ⏳\nMas'ul: {fields.get('Manager')}\n\nIltimos, harakatni tezlashtiring! 👸🛡️")
                # Flag qo'yamiz
                self.airtable.update_project_fields(p.get("id"), {"Deadline_Alert_Sent": True})

        # 2. Airtable'dan 'Done' loyihalarni tahlil qilish
        done_projects = self.airtable.get_projects_by_stage(self.AIRTABLE_DONE_STAGE)
        for p in done_projects:
            fields = p.get("fields", {})
            if not fields.get("Portfolio_Requested"):
                logger.info(f"✨ Loyiha '{fields.get('Project Name')}' yakunlandi! Portfolio so'rovi yuborilmoqda...")
                
                # Bu yerda Owner-ga xabar yuborish mantiqi bo'ladi (Telethon orqali)
                # Task: Telethon orqali Baxtiyor aka-ga xabar yuborish
                
                # Flag qo'yamizki, qayta-qayta so'ramasin
                self.airtable.update_project_fields(p.get("id"), {"Portfolio_Requested": True})

        logger.info("👸 Oisha-OS: Tizimlashtirish tekshiruvi yakunlandi. 👸🛡️")

    async def background_loop(self, interval_minutes=15):
        """Uzluksiz tekshiruv sikli."""
        while True:
            try:
                await self.run_systematizer_sync()
            except Exception as e:
                logger.error(f"❌ WorkflowOrchestrator-da xato: {e}")
            await asyncio.sleep(interval_minutes * 60)
