import logging
from src.database import Database
from src.time_utils import get_local_now
from src.services.core.gdrive import GoogleDriveSync
from src.services.core.crm.crm_file_offloader import CRMFileOffloader
from src.settings import settings
from src import config

logger = logging.getLogger(__name__)


class ProactiveWorker:
    """Proaktiv fon vazifalarini boshqaruvchi markaziy ishchi."""

    def __init__(self, bot, crm):
        self.bot = bot
        self.crm = crm
        self.db = Database()
        gdrive = GoogleDriveSync(settings.GSHEET_CREDS_FILE)
        self.crm_offloader = CRMFileOffloader(crm.amocrm, gdrive)

    async def _check_amocrm_stagnation(self):
        """AmoCRM stagnatsiya siyosatini tekshirish."""
        logger.info("[PROACTIVE] Checking AmoCRM stagnation...")
        stagnated_leads = self.crm.amocrm.check_stagnated_leads(hours=24)

        if stagnated_leads:
            msg = "💡 **FOLLOW-UP DRAFT IDEAS (Stagnation) 💡**\n\nBu mijozlar 24 soatdan beri jim. Mana ba'zi xabar g'oyalari:\n"
            for lead in stagnated_leads[:5]:
                msg += f"- **{lead.get('name')}** uchun draft:\n   `Assalomu alaykum, {lead.get('name')}. Loyihangiz bo'yicha qandaydir savollar bormi?`\n"

            msg += "\n@Oydin_JonBranding, @Inomjon_JonBranding va @jonbranding_pm, ushbu xabarlarni ko'rib chiqing va mijozga yuboring."
            await self.bot.send_message(config.CRM_GROUP_ID, msg, parse_mode="Markdown")

    async def _send_daily_sales_report(self):
        """Kunlik sotuv hisobotini yuborish."""
        now = get_local_now()
        if now.hour == 18 and now.minute == 0:
            today = now.strftime("%Y-%m-%d")
            if await self.db.is_job_run("daily_sales_report", today):
                return

            try:
                report = self.crm.amocrm.get_sales_report()
                msg = (
                    f"📈 **OYLIK SOTUV HISOBOTI (PLAN-FAKT)**\n\n"
                    f"🎯 Reja: 80,000,000 so'm\n"
                    f"✅ Fakt: {report['fact']:,} so'm\n"
                    f"📊 Progress: {report['percent']:.1f}%\n"
                    f"📦 Yopilgan bitimlar: {report['count']} ta"
                )
                await self.bot.send_message(
                    config.CRM_GROUP_ID, msg, parse_mode="Markdown"
                )
                await self.db.mark_job_run("daily_sales_report", today)
            except Exception as e:
                logger.error(f"[PROACTIVE] Error sending daily sales report: {e}")

    async def _run_crm_offload(self):
        """AmoCRM diskini tozalash (offload) jarayonini boshqarish."""
        now = get_local_now()
        if now.hour == 3 and now.minute == 0:
            today = now.strftime("%Y-%m-%d")
            if await self.db.is_job_run("crm_file_offload", today):
                return

            try:
                stats = await self.crm_offloader.run(dry_run=False)
                if stats and stats.get("offloaded", 0) > 0:
                    msg = (
                        f"🧹 **AMO_CRM STORAGE CLEANUP**\n\n"
                        f"✅ Ko'chirilgan fayllar: {stats['offloaded']} ta\n"
                        f"📂 Barcha fayllar Google Drive-ga xavfsiz o'tkazildi.\n"
                        f"📊 Xatolar: {stats['errors']}"
                    )
                    await self.bot.send_message(
                        config.CRM_GROUP_ID, msg, parse_mode="Markdown"
                    )

                await self.db.mark_job_run("crm_file_offload", today)
            except Exception as e:
                logger.error(f"[PROACTIVE] CRM Offload error: {e}")
