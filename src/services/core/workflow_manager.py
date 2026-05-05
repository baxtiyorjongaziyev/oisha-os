import asyncio
import datetime
import logging
from src.database import Database
from src.services.core.amocrm_sync import AmoCRMSync
from src.settings import settings
from src.services.core.enterprise_reporter import EnterpriseReporter

logger = logging.getLogger(__name__)


class WorkflowManager:
    def __init__(self, db: Database, crm: AmoCRMSync, client=None):
        self.db = db
        self.crm = crm
        self.client = client
        self.reporter = EnterpriseReporter(
            db, crm
        )  # Lazy init or passing actual CRMService is better

        # Pipeline to Role Mapping
        self.PIPELINE_ROLE_MAP = {
            10117998: "hunter",  # Hunter bosqichlari
            10123314: "closer",  # Closer bosqichlari
            10123318: "pm",  # Farmer bosqichlari (Inomjon PM)
            10427390: "qa",  # Sifat Nazorati (Butun jamoa)
        }

    async def sync_workflow_assignments(self):
        """
        AmoCRM dagi lidlarni tekshirib, ularni tegishli xodimlarga avtomatik biriktirish.
        """
        logger.info("[WORKFLOW] Checking for lead re-assignments...")

        leads = self.crm.get_leads_detailed()
        if not leads:
            return

        for lead in leads:
            lead_id = lead.get("id")
            pipeline_id = lead.get("pipeline_id")
            current_responsible = lead.get("responsible_user_id")

            target_role = self.PIPELINE_ROLE_MAP.get(pipeline_id)
            if not target_role:
                continue

            # Agar Sifat Nazorati bo'lsa, butun jamoaga xabar beramiz
            if target_role == "qa":
                # Maxsus mantiq: Faqat bir marta xabar berish (DB orqali tekshirish mumkin)
                continue

            # Role dagi xodimni topish
            team_member = await self.db.get_user_by_role(target_role)
            if not team_member:
                logger.warning(
                    f"[WORKFLOW] No team member found for role: {target_role}"
                )
                continue

            # Agar hozirgi mas'ul shaxs AmoCRM da botning admini bo'lsa (yoki noto'g'ri bo'lsa)
            # va bizda bu role uchun xodim bo'lsa, yangilaymiz.
            # Eslatma: AmoCRM User ID va Telegram User ID farq qiladi.
            # Hozircha Telegram orqali xabar berishni ustuvor qilamiz.

            await self.notify_assignment(team_member["user_id"], lead)

    async def notify_assignment(self, tg_user_id: int, lead: dict):
        """
        Xodimga Telegram orqali yangi lid haqida xabar berish.
        """
        if not self.client:
            return

        lead_id = lead.get("id")
        lead_name = lead.get("name", "Nomsiz Lid")
        price = lead.get("price", 0)

        # AmoCRM linkini yaratish
        amocrm_link = (
            f"https://{settings.AMOCRM_SUBDOMAIN}.amocrm.ru/leads/detail/{lead_id}"
        )

        message = (
            f"👸 **Oisha-OS: Yangi Topshiriq!** 👸\n\n"
            f"🔹 **Lid:** {lead_name}\n"
            f"🔹 **Byudjet:** {price} $\n"
            f"🔹 **Holat:** {lead.get('status_id')}\n\n"
            f"🔗 [AmoCRM-da ko'rish]({amocrm_link})\n\n"
            f"✅ Iltimos, mijoz bilan bog'laning va jarayonni davom ettiring!"
        )

        try:
            # Avval bu lid uchun xabar yuborilganini tekshirish (Double notification oldini olish)
            # Hozircha oddiy yuboramiz.
            await self.client.send_message(tg_user_id, message)
            logger.info(
                f"[WORKFLOW] Notification sent to {tg_user_id} for lead {lead_id}"
            )
        except Exception as e:
            logger.error(f"[WORKFLOW NOTIFY ERROR] {e}")

    async def check_airtable_reminders(self):
        """Airtable-dagi loyihalarni monitoring qilish va PMga eslatma yuborish."""
        logger.info("[WORKFLOW] Airtable monitoringi boshlandi... 👸🛡️")

        from src.services.core.airtable_sync import AirtableSync

        at_sync = AirtableSync(table_name="Projects")
        records = at_sync.get_projects()

        if not records:
            return

        for record in records:
            fields = record.get("fields", {})
            record_id = record.get("id")
            project_name = (
                fields.get("Project Name") or fields.get("Loyiha nomi") or "Unknown"
            )
            stage = fields.get("Stage") or fields.get("Status") or "Unknown"
            responsible = fields.get("Mas'ul") or fields.get("Responsible") or "Unknown"

            # Agar loyiha hali yakunlanmagan bo'lsa (masalan 'Done' emas)
            if stage.lower() not in ["done", "yakunlandi", "arxiv"]:
                # 1. PM (Inomjon) ga eslatma yuzborish
                # Mas'ul kishini DB-dan qidirish
                pm_user = await self.db.get_user_by_role("pm")
                pm_mention = (
                    f"@{pm_user['username']}"
                    if pm_user and pm_user.get("username")
                    else "@baxtiyorjon"
                )
                pm_id = pm_user["user_id"] if pm_user else settings.OWNER_ID

                message = (
                    f"❗ **LOYIHA ESLATMASI**\n\n"
                    f"📁 **Loyiha:** {project_name}\n"
                    f"🔄 **Bosqich:** {stage}\n"
                    f"👤 **Mas'ul:** {responsible}\n\n"
                    f"📢 {pm_mention} ushbu loyihani yakunlash bo'yicha harakatlar rejasi tayyormi? 👸🛡️"
                )

                # 1. Ichki guruhga yuborish (CRM_GROUP_ID)
                try:
                    await self.client.send_message(settings.CRM_GROUP_ID, message)
                    logger.info(f"[WORKFLOW] Group reminder sent for: {project_name}")
                except Exception as e:
                    logger.error(f"[WORKFLOW] Group send error: {e}")

                # 2. PM ga to'g'ridan-to'g'ri (DM) yuborish
                try:
                    dm_message = f"👸 **Oisha-OS Eslatmasi:**\n\nSizga biriktirilgan '{project_name}' loyihasi hozirda **{stage}** bosqichida. Uni yakunlashni unutmang! 🚀"
                    await self.client.send_message(pm_id, dm_message)
                    logger.info(
                        f"[WORKFLOW] Direct PM reminder sent for: {project_name}"
                    )
                except Exception as e:
                    logger.error(f"[WORKFLOW] DM send error: {e}")

                # Bir oz kutib keyingisiga o'tish (rate limit)
                await asyncio.sleep(3)

    async def check_periodic_schedules(self):
        """Har kuni 09:00 (Reja) va 18:00 (Natija) da xabar yuborish va intizomni tekshirish."""
        now = datetime.datetime.now()

        # Shanba/Yakshanba - dam olish (lekin Boss xohlasa yoqish mumkin)
        if now.weekday() >= 5:
            return

        today_date = now.strftime("%Y-%m-%d")
        hour = now.hour
        minute = now.minute

        from src.services.utils.team_hub import TeamHub

        # 1. MORNING PLAN REQUEST (09:00 - 09:15)
        if hour == 9 and 0 <= minute <= 15:
            job_name = "morning_plan_request"
            if not await self.db.is_job_run(job_name, today_date):
                logger.info(f"[WORKFLOW] Requesting morning plans for {today_date}")
                members = await self.db.get_team_roles()  # Barcha jamoa a'zolari

                msg = "☀️ **Xayrli tong, Princess Safety jamoasi!** 👸🛡️\n\n"
                msg += f"Bugun: **{today_date}**\n\n"
                msg += "Tizim bo'yicha barcha pozitsiya egalaridan **Kunlik Reja** kutilyapti:\n"

                for m in members:
                    mention = f"@{m['username']}" if m.get("username") else m["name"]
                    msg += f"🔹 {mention} ({m['role']})\n"

                msg += "\n⚠️ *Iltimos, rejalaringizni shu guruhga yozing!*"

                if settings.CRM_GROUP_ID:
                    await self.client.send_message(settings.CRM_GROUP_ID, msg)
                    await self.db.mark_job_run(job_name, today_date)

        # 2. EVENING RESULT CHECK (18:00 - 18:30)
        if hour == 18 and 0 <= minute <= 30:
            job_name = "evening_result_request"
            if not await self.db.is_job_run(job_name, today_date):
                logger.info(f"[WORKFLOW] Checking evening results for {today_date}")

                msg = "🌙 **Kechki Hisobot Vaqti Keldi!** 👸🛡️\n\n"
                msg += "Bugun nima ishlar qilindi? Barcha pozitsiya egalari natijalarni yozishi shart:\n"

                # Kimlar reja yozganini tekshirish (Accountability)
                discipline = TeamHub.get_daily_discipline_summary()

                msg += f"✅ Reja yozganlar: {', '.join(discipline['plans']) or 'Hali hech kim'}\n"
                msg += "\n🚀 *Natijalarni kutyapman!*"

                if settings.CRM_GROUP_ID:
                    await self.client.send_message(settings.CRM_GROUP_ID, msg)
                    await self.db.mark_job_run(job_name, today_date)

    async def workflow_monitor_loop(self):
        """Barcha monitoring vazifalarini ishga tushirish."""
        logger.info("[WORKFLOW] Monitoring loop ishga tushdi... 👸🛡️")
        while True:
            try:
                # 1. AmoCRM re-assignments (Existing logic)
                await self.sync_workflow_assignments()

                # 2. Airtable reminders (Existing logic)
                await self.check_airtable_reminders()

                # 3. Scheduled reports (09:00 / 20:00)
                await self.check_periodic_schedules()

                # 4. New Enterprise Proactive Audit
                # Check for stagnant leads
                stagnant_alert = await self.reporter.get_stagnant_leads_alert()
                if stagnant_alert:
                    group_id = settings.CRM_GROUP_ID
                    if group_id:
                        await self.client.send_message(group_id, stagnant_alert)
                        logger.info("[WORKFLOW] Stagnation alert sent to group.")

            except Exception as e:
                logger.error(f"[WORKFLOW LOOP ERROR] {e}")

            # Workflow interval (typically 1 hour for these audits)
            interval = getattr(settings, "WORKFLOW_INTERVAL", 600)
            await asyncio.sleep(interval)
