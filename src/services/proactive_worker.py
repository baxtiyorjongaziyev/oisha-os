import sqlite3
import datetime
import os
import sys
import logging
from telegram.ext import Application
import asyncio

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import bot modules from src
from src import config
from src.database import Database
from src.agents.researcher_agent import ResearcherAgent

async def generate_ai_message(user_id: int, prompt: str):
    """AI orqali dinamik va samimiy xabar yaratish."""
    # API keylarni yuklash
    api_keys = {
        "gemini": os.environ.get("GEMINI_API_KEY") or getattr(config, "GEMINI_API_KEY", ""),
        "groq": os.environ.get("GROQ_API_KEY", "")
    }
    
    agent = ResearcherAgent("proactive_bot", config.SYSTEM_INSTRUCTION, api_keys)
    # ResearcherAgent ning process_task metodidan foydalanamiz (u fallback ga ega)
    response = await agent.process_task(user_id, prompt)
    
    # Telegram HTML uchun sanitizatsiya
    response = response.replace("<p>", "").replace("</p>", "\n")
    response = response.replace("<br>", "\n").replace("<br/>", "\n")
    return response

class ProactiveWorker:
    def __init__(self, bot, crm):
        self.bot = bot
        self.crm = crm

    async def _check_amocrm_stagnation(self):
        """AmoCRM stagnatsiya siyosatini tekshirish."""
        logger.info("[PROACTIVE] Checking AmoCRM stagnation...")
        stagnated_leads = self.crm.amocrm.check_stagnated_leads(hours=24)
        
        if stagnated_leads:
            msg = "💡 **FOLLOW-UP DRAFT IDEAS (Stagnation) 💡**\n\nBu mijozlar 24 soatdan beri jim. Mana ba'zi xabar g'oyalari:\n"
            for lead in stagnated_leads[:5]: # Maksimum 5 ta
                msg += f"- **{lead.get('name')}** uchun draft:\n   `Assalomu alaykum, {lead.get('name')}. Loyihangiz bo'yicha qandaydir savollar bormi?`\n"
            
            msg += "\n@Oydin_JonBranding va @Inomjon_JonBranding, ushbu xabarlarni ko'rib chiqing va mijozga yuboring."
            await self.bot.send_message(config.CRM_GROUP_ID, msg, parse_mode="Markdown")

    async def _send_daily_sales_report(self):
        """Kunlik sotuv hisobotini yuborish."""
        # Faqat belgilangan vaqtda yuborish (masalan 09:00 yoki 18:00)
        from datetime import datetime
        now = datetime.now()
        if now.hour == 18 and now.minute < 30: # Har kuni 18:00 larda
            logger.info("[PROACTIVE] Sending daily sales report...")
            report = self.crm.amocrm.get_sales_report()
            msg = (
                f"📈 **OYLIK SOTUV HISOBOTI (PLAN-FAKT)**\n\n"
                f"🎯 Reja: 80,000,000 so'm\n"
                f"✅ Fakt: {report['fact']:,} so'm\n"
                f"📊 Progress: {report['percent']:.1f}%\n"
                f"📦 Yopilgan bitimlar: {report['count']} ta"
            )
            await self.bot.send_message(config.CRM_GROUP_ID, msg, parse_mode="Markdown")

async def send_proactive_followups():
    """Bazadagi idle foydalanuvchilarni topadi va AI tomonidan yaratilgan follow-up yuboradi."""
    logger.info("Proactive follow-up job started...")
    
    bot_token = os.environ.get("BOT_TOKEN") or config.BOT_TOKEN
    if not bot_token: return
        
    app = Application.builder().token(bot_token).build()
    db = Database()
    now = datetime.datetime.now()
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, first_name, service_type, last_seen, meeting_time, meeting_status FROM users WHERE is_lead_forwarded != 2")
            rows = cursor.fetchall()
            
            for row in rows:
                user_id, first_name, service_type, last_seen_str, meeting_time, meeting_status = row
                if not last_seen_str: continue

                last_seen = datetime.datetime.fromisoformat(last_seen_str)
                hours_diff = (now - last_seen).total_seconds() / 3600
                
                message = None
                if meeting_status == 'scheduled' and hours_diff > 2:
                    prompt = f"Mijoz {first_name} bilan uchrashuv belgilangan edi. U hozir jim. Unga samimiy, Oisha uslubida eslatma yozing. 'Eslab qoldingizmi' kabi shablonlardan qoching. Insoniy va iliq bo'lsin."
                    message = await generate_ai_message(user_id, prompt)
                    cursor.execute("UPDATE users SET meeting_status = 'completed', last_seen = ? WHERE user_id = ?", (now.isoformat(), user_id))
                    
                elif not meeting_time and 24 <= hours_diff <= 48:
                    prompt = f"Mijoz {first_name} bilan {service_type or 'loyiha'} haqida gaplashgan edik. 1 kundan beri yozmadi. Unga juda samimiy, xuddi Baxtiyorjon akaning yordamchisi kabi, unga qiziqish bildirib xabar yozing. Botligingiz bilinmasin."
                    message = await generate_ai_message(user_id, prompt)
                    cursor.execute("UPDATE users SET last_seen = ? WHERE user_id = ?", (now.isoformat(), user_id))
                    
                if message:
                    try:
                        draft_msg = (
                            f"💡 **FOLLOW-UP DRAFT IDEA**\n\n"
                            f"**Kimga**: {first_name} (ID: {user_id})\n"
                            f"**Xizmat**: {service_type or 'Noma`lum'}\n\n"
                            f"```\n{message}\n```\n"
                            f"👆 Ushbu xabarni ko'chirib, mijozga yuborishingiz mumkin."
                        )
                        await app.bot.send_message(chat_id=config.CRM_GROUP_ID, text=draft_msg, parse_mode="Markdown")
                        conn.commit()
                        await asyncio.sleep(2)
                    except Exception as e:
                        logger.error(f"[SEND ERROR] {user_id}: {e}")
    except Exception as e:
        logger.error(f"[DB ERROR in Proactive] {e}")

async def distribute_team_tasks(force: bool = False):
    """10:00 va 14:00 da Hunter/Closer lidlarni menejerlar o'rtasida taqsimlash."""
    from src.database import Database
    import src.config as config
    from src.services.amocrm_sync import AmoCRMSync
    from telegram import Bot
    
    db = Database()
    now = datetime.datetime.now()
    today = now.strftime('%Y-%m-%d')
    target_hours = [10, 14]
    
    if not force and now.hour not in target_hours:
        logger.debug(f"[DISTRIBUTION] Skipping: Hour {now.hour} is not in {target_hours}")
        return

    hour_to_mark = now.hour if not force else (14 if now.hour >= 14 else 10)
    job_key = f"team_distribution_{hour_to_mark}"
    
    if not force and db.is_job_run(job_key, today):
        logger.debug(f"[DISTRIBUTION] Skipping: Job {job_key} already run today.")
        return

    logger.info(f"[DISTRIBUTION] Starting {hour_to_mark}:00 lead assignment cycle (Force={force})...")
    
    from src.services.mission_control import MissionControl
    from src.services.enterprise_reporter import EnterpriseReporter
    from src.services.crm_service import CRMService
    
    mc = MissionControl(db)
    crm_service = CRMService()
    reporter = EnterpriseReporter(db, crm_service)
    
    # 1. Get managers
    managers = await mc.get_manager_list()
    if not managers:
        logger.warning("[DISTRIBUTION] No managers found in settings or DB.")
        return

    # 2. Distribute and save to DB
    distribution = await mc.distribute_missions(managers)
    if not distribution:
        logger.info("[DISTRIBUTION] No active missions to distribute.")
        return

    # 3. Generate Morning Plan message
    msg = await reporter.generate_morning_plan(distribution)

    if bot_token and group_id:
        from telegram import Bot
        bot = Bot(token=bot_token)
        try:
            await bot.send_message(chat_id=group_id, text=msg, parse_mode="HTML", disable_web_page_preview=True, message_thread_id=thread_id)
            db.mark_job_run(job_key, today)
            logger.info(f"[DISTRIBUTION] Cycle {now.hour}:00 completed.")
        except Exception as e:
            logger.error(f"[XATO] Team Distribution: {e}")

async def check_amocrm_stagnation():
    """AmoCRM stagnatsiya siyosatini tekshirish va AI bilan maslahat berish."""
    from src.database import Database
    import src.config as config
    from src.settings import settings
    
    # [GOD MODE] Cooldown & Schedule Check (Optimization)
    db = Database()
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    now = datetime.datetime.now()
    
    # 1. Check if already sent today
    if db.is_job_run("stagnation_alert", today):
        return

    # 2. Schedule Check (Fire at 10:00 AM UZT)
    if now.hour != 10:
        return

    logger.info("[STAGNATION] Time to audit! Checking AmoCRM...")
    from src.services.amocrm_sync import AmoCRMSync
    amo = AmoCRMSync(config.AMOCRM_SUBDOMAIN, config.AMOCRM_CLIENT_ID, config.AMOCRM_CLIENT_SECRET, config.AMOCRM_REDIRECT_URL)
    stagnated = amo.check_stagnated_leads(hours=24)
    
    if stagnated:
        bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
        group_id = getattr(config, "CRM_GROUP_ID", None)
        owner_id = getattr(config, "OWNER_ID", None)
        if not (bot_token and (group_id or owner_id)): 
            return
        
        from telegram import Bot
        bot = Bot(token=bot_token)
        
        # [ENTERPRISE] Daily Memory: Ensure it fires 3 times per day (10:00, 14:00, 18:00)
        db = Database()
        now = datetime.datetime.now()
        today = now.strftime('%Y-%m-%d')
        target_hours = [10, 14, 18] # 3 times a day
        
        # 1. Schedule Check
        if now.hour not in target_hours:
            return

        # 2. Check if this specific hour was already sent today
        job_key = f"stagnation_alert_{now.hour}"
        if db.is_job_run(job_key, today):
            return

        # 1. Guruh uchun umumiy ogohlantirish
        msg = "🚨 <b>STAGNATION ALERT (24h+)</b>\n\nQuyidagi bitimlar harakatsiz qolmoqda:\n"
        for lead in stagnated[:5]:
            msg += f"• <a href='https://{config.AMOCRM_SUBDOMAIN}.amocrm.ru/leads/detail/{lead.get('id')}'>{lead.get('name')}</a>\n"
        
        msg += "\n@Oydin_JonBranding va @tezmenejer, iltimos statusni tekshiring."
        
        # Target topic for CRM alerts
        thread_id = getattr(config, "TOPIC_CRM_ID", None)
        
        try:
            await bot.send_message(chat_id=group_id, text=msg, parse_mode="HTML", disable_web_page_preview=True, message_thread_id=thread_id)
            db.mark_job_run(job_key, today) # Mark this specific hour as done
            logger.info(f"[STAGNATION] Alert for {now.hour}:00 sent successfully!")
        except Exception as e:
            logger.error(f"[XATO] Stagnation Group Alert: {e}")

        # 2. Owner uchun AI tavsiyasi (Eng qimmat bitim uchun)
        if owner_id:
            try:
                top_lead = max(stagnated, key=lambda x: x.get('price', 0))
                prompt = f"Ushbu bitim '{top_lead.get('name')}' 24 soatdan beri '{top_lead.get('status_name')}' statusida turibdi. Narxi: {top_lead.get('price')} so'm. Uni yopish yoki harakatlantirish uchun Baxtiyorjon akaga 2-3 ta qisqa taktik maslahat bering."
                advice = await generate_ai_message(owner_id, prompt)
                await bot.send_message(chat_id=owner_id, text=f"💡 <b>Taktik Maslahat:</b>\n{advice}", parse_mode="HTML")
            except Exception as e:
                logger.warning(f"[STAGNATION ADVICE ERROR] {e}")

async def check_airtable_deadlines():
    """Airtable 72 soatlik deadline monitoringi."""
    logger.info("Project deadline check started...")
    from src.services.airtable_sync import AirtableSync
    import src.config as config
    
    sync = AirtableSync()
    upcoming = sync.get_upcoming_deadlines(hours=24)
    
    if upcoming:
        bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
        group_id = getattr(config, "PROJECTS_GROUP_ID", None)
        if not (bot_token and group_id): return
        
        from telegram import Bot
        bot = Bot(token=bot_token)
        
        msg = "⏳ **URGENT PROJECT DEADLINE (24h)**\n\nQuyidagi topshiriqlar muddati tugashiga 1 kun qoldi:\n"
        for p in upcoming[:5]:
            fields = p.get("fields", {})
            msg += f"- {fields.get('Name')} (Stage: {fields.get('Stage')}, Deadline: {fields.get('Deadline')})\n"
            
        try:
            await bot.send_message(chat_id=group_id, text=msg, parse_mode="Markdown")
            logger.info(f"[PROACTIVE] {len(upcoming)} ta loyiha deadline'i yaqin.")
        except Exception as e:
            logger.error(f"[XATO] Airtable deadline alert: {e}")
            
async def check_airtable_stagnation():
    """Airtable loyihalar stagnatsiyasini tekshirish va Inomjonga eslatma yuborish."""
    logger.info("Airtable stagnation check started...")
    from src.services.airtable_sync import AirtableSync
    import src.config as config
    from src.database import Database
    
    # [ENTERPRISE] Daily Memory: Ensure it fires 3 times per day (10:00, 14:00, 18:00)
    db = Database()
    now = datetime.datetime.now()
    today = now.strftime('%Y-%m-%d')
    target_hours = [10, 14, 18] # 3 times a day
    
    # 1. Schedule Check
    if now.hour not in target_hours:
        return

    # 2. Check if this specific hour was already sent today
    job_key = f"airtable_stagnation_{now.hour}"
    if db.is_job_run(job_key, today):
        return

    sync = AirtableSync()
    overdue = sync.get_overdue_projects()
    
    if overdue:
        bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
        group_id = getattr(config, "PROJECTS_GROUP_ID", None)
        # Target topic for tasks/projects
        thread_id = getattr(config, "TOPIC_TASKS_ID", None)
        
        if not (bot_token and group_id): return
        
        from telegram import Bot
        bot = Bot(token=bot_token)
        
        msg = "🏗 **AIRTABLE STAGNATION ALERT** 🏗\n\n"
        msg += "📢 @Inomjon_JonBranding, quyidagi loyihalar to'xtab qolgan yoki muddati o'tgan:\n\n"
        
        for p in overdue[:5]:
            fields = p.get("fields", {})
            # Localized field mapping:
            p_name = fields.get('Loyiha nomi') or fields.get('Project Name') or fields.get('Name') or "Nomsiz"
            stage = fields.get('Status') or fields.get('Stage') or fields.get('Holati') or "Noma'lum"
            deadline = fields.get('Deadline') or fields.get('Muddati') or "Belgilanmagan"
            
            msg += f"• <b>{p_name}</b> (Bosqich: {stage}, Muddat: {deadline})\n"
            
        msg += "\nIltimos, ushbu loyihalarni harakatga keltiring yoki statusni yangilang!"
        
        try:
            # First attempt: Send to specified thread
            await bot.send_message(chat_id=group_id, text=msg, parse_mode="HTML", message_thread_id=thread_id)
            logger.info(f"[AIRTABLE STAGNATION] Alert for {now.hour}:00 sent successfully to thread {thread_id}.")
        except Exception as e:
            logger.warning(f"[XATO] Thread failed, falling back to direct group: {e}")
            try:
                # Fallback: Send to direct group
                await bot.send_message(chat_id=group_id, text=msg, parse_mode="HTML")
                logger.info(f"[AIRTABLE STAGNATION] Alert for {now.hour}:00 sent via fallback.")
            except Exception as e2:
                logger.error(f"[CRITICAL XATO] Airtable stagnation alert failed completely: {e2}")
                return

        db.mark_job_run(job_key, today)

async def send_daily_report():
    """Kunlik umumiy statistika va jamoa samaradorligi hisoboti."""
    logger.info("Daily report job started...")
    from src.services.amocrm_sync import AmoCRMSync
    from src.services.airtable_sync import AirtableSync
    from src.services.enterprise_reporter import EnterpriseReporter
    from src.services.crm_service import CRMService
    import src.config as config
    
    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    group_id = getattr(config, "CRM_GROUP_ID", None)
    # Target topic for reports
    thread_id = getattr(config, "TOPIC_REPORTS_ID", None)
    
    if not (bot_token and group_id): 
        logger.warning("[DAILY REPORT] Bot token yoki Group ID topilmadi.")
        return

    db = Database()
    
    # Bugun hisobot yuborilganmi? (Duplicate run oldini olish)
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    if db.is_job_run("daily_report", today):
        logger.info("[DAILY REPORT] Allaqachon bugun yuborilgan. Skip.")
        return

    try:
        crm_service = CRMService()
        airtable = AirtableSync()
        reporter = EnterpriseReporter(db, crm_service, airtable)
        
        report_msg = await reporter.get_team_efficiency_report()
        
        from telegram import Bot
        bot = Bot(token=bot_token)
        
        # 1. Jamoa guruhiga yuborish
        try:
            await bot.send_message(chat_id=group_id, text=report_msg, parse_mode="HTML", message_thread_id=thread_id)
            logger.info(f"[DAILY REPORT] Jamoa guruhiga ({group_id}) yuborildi.")
        except Exception as html_err:
            logger.warning(f"[DAILY REPORT] HTML yuborishda xato, Plain Text-da qayta urinish: {html_err}")
            await bot.send_message(chat_id=group_id, text=report_msg, parse_mode=None, message_thread_id=thread_id)
        
        # 2. Owner-ga (Baxtiyor aka) yuborish
        owner_id = getattr(config, "OWNER_ID", None)
        if owner_id and str(owner_id) != str(group_id):
            try:
                await bot.send_message(chat_id=owner_id, text=report_msg, parse_mode="HTML")
                logger.info(f"[DAILY REPORT] Owner-ga ({owner_id}) yuborildi.")
            except Exception as e:
                logger.warning(f"[DAILY REPORT] Owner-ga HTML yuborishda xato, Plain-ga o'tildi: {e}")
                await bot.send_message(chat_id=owner_id, text=report_msg, parse_mode=None)
            
        # Vazifani bajarilgan deb belgilash
        db.mark_job_run("daily_report", today)
        
    except Exception as e:
        logger.error(f"[XATO] Daily Report tayyorlash yoki yuborishda: {e}", exc_info=True)

async def send_morning_briefing():
    """Ertalabki reja, ruhlantiruvchi gaplar va ustuvor vazifalar."""
    logger.info("Morning briefing job started...")
    import src.config as config
    
    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    group_id = getattr(config, "CRM_GROUP_ID", None)
    # Target topic for morning briefing
    thread_id = getattr(config, "TOPIC_GENERAL_ID", None)
    if not (bot_token and group_id): return

    db = Database()
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    if db.is_job_run("morning_briefing", today):
        logger.info("[MORNING BRIEFING] Allaqachon bugun yuborilgan. Skip.")
        return

    priorities = db.get_priority_tasks(limit=3)
    
    priority_text = ""
    if priorities:
        priority_text = "\n\n📌 <b>Bugungi ustuvor vazifalar:</b>\n"
        for p in priorities:
            name = p.get('name') or p.get('username') or "Unknown"
            priority_text += f"• {p['title']} — <i>{name}</i>\n"

    # AI xabarini shakllantirish
    # [GOD MODE] Special Billing Reminder for April 3rd
    billing_reminder = ""
    if today == "2026-04-03":
        billing_reminder = (
            "\n\n⚠️ **ESLATMA:** Bugun Google Cloud Billing (to'lov) masalasini hal qilishimiz kerak edi. "
            "To'lov amalga oshirilishi bilan botni 24/7 rejimga o'tkazaman va barcha yangilanishlar zudlik bilan ishga tushadi."
        )

    prompt = (
        "Bugundagi ish kunida jamoani ruhlantiring. "
        f"Baxtiyorjon aka bilan bugun katta marralarni zabt etishlarida ko'maklashishga tayyor ekanligingizni bildiring. {priority_text if priorities else ''} "
        f"{billing_reminder}"
        "Xabar samimiy, insoniy va HTML formatda bo'lsin."
    )
    
    from src.services.proactive_worker import generate_ai_message
    briefing = await generate_ai_message(999, prompt) # 999 - tizim/guruh ID sifatida
    if priorities:
        briefing += priority_text
        
    try:
        from telegram import Bot
        bot = Bot(token=bot_token)
        
        # HTML Sanitizatsiya (Oisha v9 Stable)
        clean_briefing = briefing.replace("<p>", "").replace("</p>", "\n")
        clean_briefing = clean_briefing.replace("<ul>", "").replace("</ul>", "")
        clean_briefing = clean_briefing.replace("<li>", "• ").replace("</li>", "\n")
        
        try:
            await bot.send_message(chat_id=group_id, text=clean_briefing, parse_mode="HTML", message_thread_id=thread_id)
            logger.info(f"[MORNING BRIEFING] Jamoa guruhiga ({group_id}) yuborildi.")
        except Exception as html_err:
            logger.warning(f"[MORNING BRIEFING] HTML xato, Plain-ga o'tilmoqda: {html_err}")
            await bot.send_message(chat_id=group_id, text=briefing, parse_mode=None, message_thread_id=thread_id)

    except Exception as e:
        logger.error(f"[XATO] Morning Briefing yuborishda: {e}", exc_info=True)

async def send_overdue_nudges():
    """Vazifasi kechikayotgan xodimlarni guruhda (tagging) ogohlantirish."""
    db = Database()
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    if db.is_job_run("overdue_nudges", today):
        logger.info("[NUDGES] Allaqachon bugun yuborilgan. Skip.")
        return

    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    # Using specific Group ID for projects/tasks
    group_id = getattr(config, "PROJECTS_GROUP_ID", None)
    # Target topic for tasks/nudges
    thread_id = getattr(config, "TOPIC_TASKS_ID", None)
    if not (bot_token and group_id): return

    overdue = db.get_overdue_tasks()
    if not overdue: return
    
    # ... (kod davomi)
    
    try:
        from telegram import Bot
        bot = Bot(token=bot_token)
        
        # Foydalanuvchilar bo'yicha guruhlash
        by_user = {}
        for t in overdue:
            uid = t['assigned_to']
            if uid not in by_user: by_user[uid] = {"name": t.get('name') or t.get('username') or "Xodim", "tasks": []}
            by_user[uid]["tasks"].append(t.get('title') or t.get('description') or "Vazifa")

        msg = "📢 <b>DIQQAT: Kechikayotgan vazifalar bo'yicha eslatma!</b>\n\n"
        for uid, data in by_user.items():
            tag = f"<a href='tg://user?id={uid}'>{data['name']}</a>"
            msg += f"👤 {tag}:\n"
            for task_title in data['tasks']:
                msg += f"  • {task_title}\n"
            msg += "\n"
        
        msg += "<i>Iltimos, ish kunini yakunlashdan oldin ushbu vazifalarni bajaring!</i>"
        
        await bot.send_message(chat_id=group_id, text=msg, parse_mode="HTML", message_thread_id=thread_id)
        db.mark_job_run("overdue_nudges", today)
        logger.info(f"[PROACTIVE] Public nudges sent for {len(by_user)} users.")
    except Exception as e:
        logger.error(f"[XATO] Public Nudge yuborishda: {e}")

async def send_evening_fact_report():
    """Kechki Plan-Fakt natijalarini audit qilish va guruhga yuborish."""
    logger.info("Evening Fact report job started...")
    from src.services.enterprise_reporter import EnterpriseReporter
    from src.services.crm_service import CRMService
    import src.config as config
    
    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    group_id = getattr(config, "TEAM_GROUP_ID", config.CRM_GROUP_ID)
    thread_id = getattr(config, "TOPIC_REPORTS_ID", None)
    
    if not (bot_token and group_id): return
    
    db = Database()
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    if db.is_job_run("evening_fact", today):
        logger.info("[EVENING FACT] Allaqachon bugun yuborilgan. Skip.")
        return

    try:
        crm_service = CRMService()
        reporter = EnterpriseReporter(db, crm_service)
        report_msg = await reporter.generate_plan_fact_report()
        
        from telegram import Bot
        bot = Bot(token=bot_token)
        await bot.send_message(chat_id=group_id, text=report_msg, parse_mode="HTML", message_thread_id=thread_id)
        db.mark_job_run("evening_fact", today)
        logger.info("[EVENING FACT] Sent successfully.")
    except Exception as e:
        logger.error(f"[XATO] Evening Fact: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Proactive AI Worker")
    parser.add_argument("--job", choices=["followup", "report", "briefing", "stagnation", "deadlines", "distribute", "fact"], default="followup", help="Kaysi vazifani bajarish kerak?")
    args = parser.parse_args()
    
    if args.job == "followup":
        asyncio.run(send_proactive_followups())
    elif args.job == "report":
        asyncio.run(send_daily_report())
    elif args.job == "briefing":
        asyncio.run(send_morning_briefing())
    elif args.job == "stagnation":
        asyncio.run(check_amocrm_stagnation())
    elif args.job == "deadlines":
        asyncio.run(check_airtable_deadlines())
    elif args.job == "distribute":
        asyncio.run(distribute_team_tasks(force=True))
    elif args.job == "fact":
        asyncio.run(send_evening_fact_report())
