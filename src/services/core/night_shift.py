import asyncio
import datetime
import logging
import os
import time
from src import config
from src.database import Database
from src.services.core.amocrm_sync import AmoCRMSync
from src.services.core.crm_service import CRMService
from src.agents.researcher_agent import ResearcherAgent
from src.services.debug.google_service import GoogleService
from src.services.core.airtable_sync import AirtableSync
from src.services.core.historical_sync import HistoricalSyncService

logger = logging.getLogger("NightShift")

class NightShiftService:
    """Oisha Kecha Rejimi - Jamoa uxlayotgan paytda foydali ishlar bilan shug'ullanadi."""
    
    def __init__(self, bot_client=None):
        self.bot = bot_client
        self.db = Database()
        self.crm = AmoCRMSync(
            config.AMOCRM_SUBDOMAIN, 
            config.AMOCRM_CLIENT_ID, 
            config.AMOCRM_CLIENT_SECRET, 
            config.AMOCRM_REDIRECT_URL
        )
        self.google = GoogleService()
        self.airtable = AirtableSync()
        self.api_keys = {
            "gemini": os.environ.get("GEMINI_API_KEY") or getattr(config, "GEMINI_API_KEY", ""),
            "groq": os.environ.get("GROQ_API_KEY", "")
        }
        self.researcher = ResearcherAgent("night_researcher", config.SYSTEM_INSTRUCTION, self.api_keys)
        # Bir kunlik vazifani ikki marta ishga tushmasligi uchun
        self._fired_dates: dict[str, datetime.date] = {}

    def _should_run_once_today(self, job_key: str, now: datetime.datetime) -> bool:
        last = self._fired_dates.get(job_key)
        if last == now.date():
            return False
        self._fired_dates[job_key] = now.date()
        return True

    async def run_overnight_cycle(self):
        """Asosiy sikl - Ma'lum vaqtlarda vazifalarni bajaradi."""
        logger.info("🌙 Night Shift Service is active and monitoring time...")
        while True:
            try:
                now = datetime.datetime.now()
                # 2 daqiqalik oyna: soat 01:00:00–01:01:59 oralig'ida bir marta ishlaydi (o'tkazib yubormaslik)
                slot_ok = lambda h, m: now.hour == h and m <= now.minute < m + 2

                # 00:00 - Historical Backlog Sync (1 Year History)
                if slot_ok(0, 0) and self._should_run_once_today("history_sync", now):
                    from src.api_server import add_activity
                    add_activity("🚀 Historical Sync boshlandi", "1 yillik yozishmalar tahlil qilinmoqda...", "info")
                    if self.bot:
                        sync_service = HistoricalSyncService(self.db, self.bot)
                        asyncio.create_task(sync_service.start_backlog_sync(days=365))
                    await asyncio.sleep(70)

                # 01:00 - CRM Hygiene (Deduplication & Sync)
                if slot_ok(1, 0) and self._should_run_once_today("hygiene", now):
                    from src.api_server import add_activity
                    add_activity("🌙 CRM Hygiene boshlandi", "Airtable va AmoCRM ma'lumotlari bir xillashtirilmoqda...", "info")
                    await self.sync_and_cleanup()
                    await asyncio.sleep(70)

                # 02:00 - Lead Intelligence (OSINT)
                if slot_ok(2, 0) and self._should_run_once_today("lead_intel", now):
                    from src.api_server import add_activity
                    add_activity("🔍 Lead Intelligence boshlandi", "Yangi lidlar bo'yicha OSINT tadqiqot o'tkazilmoqda...", "info")
                    await self.perform_lead_research()
                    await asyncio.sleep(70)

                # 04:00 - Strategic Battlecards (Calendar Briefing)
                if slot_ok(4, 0) and self._should_run_once_today("battlecards", now):
                    from src.api_server import add_activity
                    add_activity("🚀 Battlecards tayyorlanmoqda", "Bugungi uchrashuvlar tahlili boshlandi...", "info")
                    await self.generate_daily_reflection()
                    await asyncio.sleep(70)

            except Exception as e:
                logger.error(f"🌙 [NIGHT_SHIFT_ERROR] Cycle execution failed: {e}")

            await asyncio.sleep(60)

    async def perform_lead_research(self):
        """Yangi lidlar bo'yicha OSINT va tahlil o'tkazish (Soat 02:00)."""
        logger.info("🌙 [LEAD_INTEL] Starting deep research on new leads...")
        try:
            # 'Initial Contact' statusidagi lidlarni olish
            leads = await self.crm.get_leads(status_id=config.AMOCRM_INITIAL_STATUS_ID if hasattr(config, 'AMOCRM_INITIAL_STATUS_ID') else None)
            
            for lead in leads[:10]: # Limit for stability
                lead_id = lead.get('id')
                lead_name = lead.get('name', 'Noma\'lum')
                
                # AI Research prompt
                prompt = (
                    f"Mijoz: {lead_name}. Ushbu lid bo'yicha OSINT tadqiqot o'tkazing. "
                    f"Ularning ijtimoiy tarmoqlarini, kompaniyasini va branding ehtiyojlarini tahlil qiling. "
                    f"Natijani 3 gapda, AmoCRM uchun 'Oisha Tahlili' sifatida yozing."
                )
                analysis = await self.researcher.process_task(0, prompt)
                
                # Write back to CRM
                await self.crm.add_lead_note(lead_id, f"🔍 OISHA LEAD INTELLIGENCE:\n\n{analysis}")
                from src.api_server import add_activity
                add_activity("Lid boyitildi", f"{lead_name} bo'yicha OSINT ma'lumotlar AmoCRM'ga yozildi.", "success")
                logger.info(f"✅ Researched lead: {lead_name}")
                
        except Exception as e:
            logger.error(f"🌙 [LEAD_INTEL_ERROR] {e}")

    async def generate_daily_reflection(self):
        """Bugungi uchrashuvlar uchun Battlecards tayyorlash (Soat 04:00)."""
        logger.info("🌙 [BATTLECARDS] Preparing strategic briefing...")
        try:
            if not self.google.calendar: return
            
            events = self.google.calendar.get_upcoming_events()
            if not events: return
            
            report = "🚀 **BUGUNGI STRATEGIK BRIFING (Battlecards)** 🚀\n\n"
            for event in events:
                summary = event.get('summary', 'Uchrashuv')
                start = event.get('start', {}).get('dateTime', 'No vaqt')
                description = event.get('description', '')
                
                # AI Analysis of the meeting context
                brief = await self.researcher.process_task(0, f"Uchrashuv: {summary}. Tavsif: {description}. Ushbu uchrashuvda qanday strategik yondashuv kerakligini 1 gapda ayting.")
                report += f"⏰ **{start[11:16]}** — {summary}\n💡 *Maslahat:* {brief}\n\n"
            
            # Send to OWNER via Telegram (AdminBot or direct via client)
            # Assuming AdminBot instance is accessible or use config/settings
            if self.bot:
                from src.settings import settings
                await self.bot.send_message(settings.OWNER_ID, report, parse_mode='markdown')
                
        except Exception as e:
            logger.error(f"🌙 [BATTLECARDS_ERROR] {e}")

    async def sync_and_cleanup(self):
        """Airtable va AmoCRM sinxronizatsiyasi, dublikatlarni tozalash (Soat 01:00)."""
        logger.info("🌙 [HYGIENE] Starting CRM cleanup...")
        try:
            # 1. Stagnated leads tagging
            stagnated = self.crm.check_stagnated_leads(hours=48)
            for lead in stagnated:
                await self.crm.add_lead_tag(lead['id'], "STAGNATED")
            
            # 2. Overdue project alerts from Airtable (faqat log, xabar 09:00 dan keyin yuboriladi)
            overdue = self.airtable.get_overdue_projects()
            if overdue:
                from src.services.core.airtable_sync import AirtableSync as _AT
                logger.info(f"🌙 [HYGIENE] Found {len(overdue)} overdue projects")
                _now = datetime.datetime.now()
                if self.bot and _now.hour >= 9:
                    from src.settings import settings
                    msg = "⚠️ **MUDDATI O'TGAN LOYIHALAR (Airtable):**\n\n"
                    for p in overdue[:5]:
                        f = p.get('fields', {})
                        name = _AT._get_field(f, "project_name") or "Nomsiz"
                        deadline = _AT._get_field(f, "deadline") or "N/A"
                        msg += f"• {name} ({deadline})\n"
                    await self.bot.send_message(settings.OWNER_ID, msg)
                
            logger.info("✅ CRM Hygiene cycle completed.")
        except Exception as e:
            logger.error(f"🌙 [HYGIENE_ERROR] {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Night Shift logic ready.")
