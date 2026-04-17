
import asyncio
import logging
import datetime
from src.services.core.crm_service import CRMService
from src.database import Database
import src.config as config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CRMHygieneBot:
    """
    AmoCRM-da tartibni saqlash: vazifasi yo'q bitimlarni topish va ogohlantirish.
    """
    def __init__(self):
        self.crm = CRMService()
        self.db = Database()
        self.WON_STATUS = 142
        self.LOST_STATUS = 143

    async def run_audit(self):
        """Auditni ishga tushirish: Stagnatsiya va vazifasiz lidlar."""
        logger.info("[HYGIENE] CRM Audit boshlanmoqda...")
        
        # 1. Barcha lidlarni olish
        leads = await self.crm.amocrm.get_leads_detailed(limit=100)
        if not leads:
            logger.warning("[HYGIENE] Lillar topilmadi.")
            return

        dirty_leads = []
        for l in leads:
            if l.get('status_id') in [self.WON_STATUS, self.LOST_STATUS]:
                continue

            lead_id = l.get('id')
            
            # 2. Vazifalar bor-yo'qligini tekshirish (AmoCRM API orqali)
            # Eslatma: Bu yerda har bir lid uchun API chaqiruvi bo'lishi mumkin, 
            # batch olish optimalroq lekin hozircha soddalashtiramiz.
            tasks = await self.crm.amocrm.get_tasks() # Biz barcha ochiq vazifalarni olamiz
            lead_tasks = [t for t in tasks if t.get('entity_id') == lead_id]

            if not lead_tasks:
                dirty_leads.append(l)

        if not dirty_leads:
            logger.info("[HYGIENE] Hamma narsa joyida. 'Kir' lidlar topilmadi.")
            return

        logger.info(f"[HYGIENE] {len(dirty_leads)} ta 'kir' lid topildi. Choralar ko'rilmoqda...")

        # 3. Choralar ko'rish
        for l in dirty_leads:
            l_id = l.get('id')
            responsible_id = l.get('responsible_user_id')
            manager_name = self.crm.amocrm.get_user_name(responsible_id)
            
            # Tag qo'shish
            await self.crm.amocrm.add_lead_tag(l_id, "Vazifa Yo'q!")
            
            # Izoh qo'shish
            note_text = f"🚨 OISHA AUDIT: Bu bitimda vazifa belgilanmagan! @{manager_name}, iltimos vazifa qo'shing."
            self.crm.amocrm.add_lead_note(l_id, note_text)
            
            logger.info(f"[HYGIENE] Lead {l_id} tagged and noted.")
            await asyncio.sleep(1) # API limitlariga rioya qilish

        # 4. Hisobatni guruhga yuborish (ixtiyoriy)
        await self.send_hygiene_report(dirty_leads)

    async def send_hygiene_report(self, dirty_leads):
        """Guruhga 'Dirty Leads' hisobotini yuborish."""
        if not dirty_leads: return
        
        bot_token = config.BOT_TOKEN
        group_id = config.CRM_GROUP_ID
        
        report = [f"🧹 <b>OISHA HYGIENE REPORT</b>"]
        report.append(f"CRM-da <b>{len(dirty_leads)} ta</b> bitimda vazifa belgilanmagan! Bu sotuv yo'qolishiga olib keladi.\n")
        
        for l in dirty_leads[:10]: # Max 10 ta
            name = l.get('name', 'Nomsiz')
            report.append(f"• {name} (ID: {l.get('id')})")
            
        report.append("\n⚠️ <i>Barcha menejerlarga ogohlantirish yuborildi.</i>")
        
        from telegram import Bot
        bot = Bot(token=bot_token)
        try:
            await bot.send_message(chat_id=group_id, text="\n".join(report), parse_mode="HTML")
        except Exception as e:
            logger.error(f"[HYGIENE REPORT ERROR] {e}")

if __name__ == "__main__":
    bot = CRMHygieneBot()
    asyncio.run(bot.run_audit())
