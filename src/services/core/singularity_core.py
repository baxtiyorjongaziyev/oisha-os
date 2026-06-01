import logging
import datetime
import os
import asyncio
from src import config

logger = logging.getLogger(__name__)

from src.database import Database  # type: ignore
from src.services.core.airtable_sync import AirtableSync
from src.services.core.gcontacts import GoogleContactsSync
from src.services.debug.global_super_hub import GiantResourceHub, GlobalSuperAI  # type: ignore
from src.services.core.escalation_agent import EscalationAgent
from src.services.core.wow_service_engine import WowServiceEngine
from src.services.core.gdrive import GoogleDriveSync
from src.services.core.crm_file_offloader import CRMFileOffloader
from src.services.core.amocrm_sync import AmoCRMSync
from src.settings import settings

db = Database()
airtable = AirtableSync()
gcontacts = GoogleContactsSync()


class ProactiveWorker:
    """Oishaning avtonom, proactive faoliyati uchun mas'ul ishchi."""

    def __init__(self, context=None, db_instance=None):
        self.context = context
        self.db = db_instance or db
        self.is_running = False

        # Offloader initialize
        amo = AmoCRMSync(
            subdomain=config.AMOCRM_SUBDOMAIN,
            client_id=config.AMOCRM_CLIENT_ID,
            client_secret=config.AMOCRM_CLIENT_SECRET,
            redirect_url=config.AMOCRM_REDIRECT_URL,
        )
        gdrive = GoogleDriveSync(settings.GSHEET_CREDS_FILE)
        self.crm_offloader = CRMFileOffloader(amo, gdrive)

    async def _should_run_job(self, job_name: str, hour: int, minute: int = 0) -> bool:
        """Berilgan vaqtdan o'tgan bo'lsa va bugun hali bajarilmagan bo'lsa True qaytaradi."""
        now = datetime.datetime.now()
        today = now.strftime("%Y-%m-%d")

        # Check if time has passed
        if now.hour < hour or (now.hour == hour and now.minute < minute):
            return False

        # Check if already run today
        if await self.db.is_job_run(job_name, today):
            return False

        return True

    async def start_loop(self):
        """Avtonom siklni ishga tushirish."""
        if self.is_running:
            return
        self.is_running = True
        logger.info("[SINGULARITY] Proactive Worker started.")

        while self.is_running:
            try:
                now = datetime.datetime.now()

                # 1. Tungi zaxiralash (03:00+)
                if await self._should_run_job("daily_backup", 3):
                    await self.perform_daily_backup()
                    await db.mark_job_run("daily_backup", now.strftime("%Y-%m-%d"))

                # AmoCRM File Offload (Cleanup) - 03:15+
                if await self._should_run_job("crm_file_offload", 3, 15):
                    logger.info("[SINGULARITY] Starting AmoCRM File Offload cleanup...")
                    await self.crm_offloader.run(dry_run=False)
                    await db.mark_job_run("crm_file_offload", now.strftime("%Y-%m-%d"))

                # 2. Ertalabki bozor tahlili (08:00+)
                if await self._should_run_job("morning_brief", 8):
                    await self.generate_morning_brief()
                    await db.mark_job_run("morning_brief", now.strftime("%Y-%m-%d"))

                # 4. Avtonom topshiriqlar tahlili (Har 2 soatda)
                if now.hour % 2 == 0 and now.minute == 0:
                    await self.analyze_and_extract_tasks()

                # 5. Strategik rivojlanish va Recruiter (Har 6 soatda)
                if now.hour % 6 == 0 and now.minute == 15:
                    await self.analyze_and_generate_strategy()

                # 6. Kunlik hisobot va Ertangi reja (21:00+)
                if await self._should_run_job("daily_report", 21):
                    await self.generate_daily_report_and_planning()
                    await db.mark_job_run("daily_report", now.strftime("%Y-%m-%d"))

                # 7. Airtable Pipeline Control (10:00+)
                if await self._should_run_job("airtable_control", 10):
                    await self.airtable_pipeline_control()
                    await db.mark_job_run("airtable_control", now.strftime("%Y-%m-%d"))

                # 8. Role-Based Orchestration (Har 4 soatda)
                if now.hour % 4 == 0 and now.minute == 30:
                    await self.run_role_based_orchestration()

                # 9. TEAM DISCIPLINE & ACCOUNTABILITY (Enforcer Mode)
                # Morning Plans (09:30+)
                if await self._should_run_job("enforcer_morning", 9, 30):
                    await self.enforce_team_accountability("morning")
                    await self.db.mark_job_run(
                        "enforcer_morning", now.strftime("%Y-%m-%d")
                    )

                # Mid-day Report (13:30+)
                if await self._should_run_job("enforcer_lunch", 13, 30):
                    await self.enforce_team_accountability("lunch")
                    await self.db.mark_job_run(
                        "enforcer_lunch", now.strftime("%Y-%m-%d")
                    )

                # Evening Result (18:30+)
                if await self._should_run_job("enforcer_evening", 18, 30):
                    await self.enforce_team_accountability("evening")
                    await self.db.mark_job_run(
                        "enforcer_evening", now.strftime("%Y-%m-%d")
                    )

                # 10. ESCALATION & FEEDBACK LOOP (Every 30 minutes)
                if now.minute % 30 == 0:
                    escalator = EscalationAgent(
                        self.db, self.context.bot if self.context else None
                    )
                    await escalator.check_pending_feedbacks()

                # 11. WOW-SERVICE AUDIT (Every 60 minutes)
                if now.minute == 15:  # Run at HH:15
                    wow_engine = WowServiceEngine(
                        self.db, self.context.bot if self.context else None
                    )
                    await wow_engine.process_active_journeys()

                await asyncio.sleep(60)  # Har minutda tekshirish
            except Exception as e:
                logger.error(f"[WORKER ERROR] {e}")
                await asyncio.sleep(60)

    async def perform_daily_backup(self):
        """Avtonom zaxiralash (Local + Cloud Simulation)."""
        logger.info("[PROACTIVE] Starting daily backup of bot_memory.db...")
        try:
            import shutil
            import os

            backup_dir = "backups"
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"{backup_dir}/bot_memory_backup_{timestamp}.db"

            # Local backup
            shutil.copy2("bot_memory.db", backup_file)
            logger.info(f"✅ Local backup created: {backup_file}")

            # Cloud backup Simulation (as defined in GiantResourceHub)
            GiantResourceHub.google_drive_backup(backup_file)

            # Clean old backups (keep last 7 days)
            # (Optional improvement logic here)
        except Exception as e:
            logger.error(f"[BACKUP ERROR] {e}")

    async def generate_morning_brief(self):
        """Ertalabki hisobotni tayyorlash."""
        logger.info("[PROACTIVE] Generating morning brief...")
        # Perplexity orqali yangiliklar
        news = GlobalSuperAI.perplexity_search(
            "O'zbekiston va dunyodagi eng muhim biznes yangiliklar 2026",
            getattr(config, "PERPLEXITY_KEY", None),
        )
        # Faktlarni saqlash
        await db.add_learned_fact(
            0, f"MORNING_BRIEF_{datetime.date.today()}: {news[:500]}"
        )
        # Bu yerda foydalanuvchiga xabar yuborish logikasi (agar chat bo'lsa)

    async def monitor_cloud_resources(self):
        """VPS va Cloud resurslarni monitor qilish."""
        logger.info("[PROACTIVE] Monitoring system resources...")
        try:
            from src.services.core.monitor_resources import (
                ResourceMonitor,
                check_resources_now,
            )

            # Fallback to global db if self.db not set
            mon_db = getattr(self, "db", db)
            monitor = ResourceMonitor(mon_db)
            stats = await monitor.get_stats()

            if stats["ram_percent"] > monitor.threshold_ram:
                logger.warning(
                    f"⚠️ [PROACTIVE ALERT] Critical RAM usage: {stats['ram_percent']}%"
                )

                # Notification logic: Always try to notify Owner
                owner_id = int(config.OWNER_ID or 0)
                if owner_id:
                    msg = await check_resources_now()
                    alert_text = f"🆘 <b>SYSTEM CRITICAL ALERT</b>\n\n{msg}"

                    # Try using context if available (python-telegram-bot)
                    if self.context and hasattr(self.context, "bot"):
                        await self.context.bot.send_message(
                            chat_id=owner_id, text=alert_text, parse_mode="HTML"
                        )
                    else:
                        # Fallback to Telethon if available in global src.main
                        try:
                            from src.main import client as telethon_client

                            if telethon_client:
                                await telethon_client.send_message(
                                    "me", alert_text, parse_mode="html"
                                )
                        except:
                            logger.error(
                                "[PROACTIVE] Failed to send alert via Telethon fallback."
                            )
        except Exception as e:
            logger.error(f"[PROACTIVE] Monitoring error: {e}")

    async def analyze_and_extract_tasks(self):
        """Oxirgi suhbatlardan topshiriqlarni (tasks) ajratib olish."""
        logger.info("[PROACTIVE] Analyzing conversations for autonomous tasks...")

        if not self.context:
            logger.warning(
                "[PROACTIVE] No context available for task extraction notification."
            )
            return

        try:
            # 1. Oxirgi 50 ta xabarni olish
            messages = await db.get_recent_all_messages(limit=50)  # Barcha chatlardan
            if not messages:
                return

            log_text = "\n".join([f"User {m[0]}: {m[1]}" for m in messages])

            # 2. Gemini orqali tahlil qilish
            query = (
                "Quyidagi suhbatlarni tahlil qil va undagi konkret topshiriqlarni (vazifalarni) ajratib ol. "
                "Faqat yangi, hali bajarilmagan va aniq xodimga yoki jamoaga tegishli topshiriqlarni top. "
                "Javobni FAQAT quyidagi JSON formatida ber: "
                '{"tasks": [{"title": "...", "assigned_to": "@username or role", "deadline": "YYYY-MM-DD"}]}\n\n'
                f"Suhbatlar:\n{log_text}"
            )

            # DeepSeek yoki Gemini ishlatish (Configga qarab)
            api_key = getattr(config, "GEMINI_API_KEY", None)
            if not api_key:
                return

            # promptni yuboramiz (ASYNCHRONOUS & SAFE)
            from google import genai
            from src.main import safe_ai_call

            client = genai.Client(api_key=api_key)

            response = await safe_ai_call(
                client=client,
                prompt=query,
                model=settings.GEMINI_CALL_MODEL,
                mime_type="application/json",
            )

            if not response:
                return

            import json

            data = json.loads(response.text)
            tasks = data.get("tasks", [])

            for task in tasks:
                title = task.get("title")
                who = task.get("assigned_to", "Jamoa")

                # Egasi (Owner) ga tasdiqlash uchun yuborish
                if config.OWNER_ID and self.context:
                    from telegram import InlineKeyboardMarkup, InlineKeyboardButton

                    text = (
                        f"🎯 <b>AVTONOM TOPSHIRIQ ANIQLANDI</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"📝 <b>Vazifa:</b> {title}\n"
                        f"👤 <b>Mas'ul:</b> {who}\n\n"
                        f"Buni jamoa vazifalariga qo'shaymi?"
                    )
                    # Callback data: task_conf:title|who
                    # Limit length for callback data
                    safe_title = title[:30].replace("|", " ")
                    callback_data = f"task_conf:{safe_title}|{who}"

                    keyboard = [
                        [
                            InlineKeyboardButton("✅ Ha", callback_data=callback_data),
                            InlineKeyboardButton(
                                "❌ Yo'q", callback_data="task_ignore"
                            ),
                        ]
                    ]

                    try:
                        await self.context.bot.send_message(
                            chat_id=int(config.OWNER_ID),
                            text=text,
                            parse_mode="HTML",
                            reply_markup=InlineKeyboardMarkup(keyboard),
                        )
                        logger.info(
                            f"[PROACTIVE] Potential task detected and sent for approval: {title}"
                        )
                    except Exception as e:
                        logger.error(
                            f"[PROACTIVE] Failed to send message to owner: {e}"
                        )

        except Exception as e:
            logger.error(f"[TASK EXTRACTION ERROR] {e}")

    async def analyze_and_generate_strategy(self):
        """Agentlikni N1 qilish uchun strategik gipotezalar va xodim qidiruvi."""
        logger.info("[PROACTIVE] Generating strategic hypotheses...")

        if not self.context:
            return

        try:
            # 1. Jamoa tarkibini olish
            team = await self.db.get_team_roles()
            team_str = "\n".join(
                [f"- {t['name']} (@{t['username']}): {t['role']}" for t in team]
            )

            # 2. Mavjud vazifalarni tahlil qilish
            recent_tasks = await self.db.get_pending_tasks()
            tasks_str = "\n".join(
                [
                    f"- {t['description']} (Assigned to: {t['assigned_to']})"
                    for t in recent_tasks
                ]
            )

            # 3. Strategik prompt
            query = (
                "Sen 'Jon Branding' agentligining CEO-sisan. Maqsading: Agentlikni O'zbekistonda va dunyoda №1 qilish. "
                f"Hozirgi jamoa:\n{team_str}\n\n"
                f"Mavjud vazifalar:\n{tasks_str}\n\n"
                "Quyidagilarni ishlab chiq:\n"
                "1. Agentlikni rivojlantirish uchun 2 ta yangi STRATEGIK gipoteza (vazifa).\n"
                "2. Ulardan birini jamoaga topshir (agar mos odam bo'lsa) YOKI hammasi uchun umumiy 'Checklist' (Poll) yaratishni taklif qil.\n"
                "3. Agar kerakli mutaxassis (masalan, Motion Designer, Marketing Head) jamoada yo'q bo'lsa, "
                "u uchun professional 'Job Description' tayyorla yoki yangi AI Agent yaratishni taklif qil.\n\n"
                "Javobni FAQAT JSON formatida ber: "
                '{"strategies": [{"id": 1, "title": "...", "action": "assign|assign_checklist|recruit|ai_agent", "target": "@username or job_title", "description": "...", "checklist_items": ["item1", "item2"]}]}'
            )

            api_key = getattr(config, "GEMINI_API_KEY", None)
            if not api_key:
                return

            from google import genai
            from src.main import safe_ai_call

            client = genai.Client(api_key=api_key)

            response = await safe_ai_call(
                client=client,
                prompt=query,
                model=settings.GEMINI_CALL_MODEL,
                mime_type="application/json",
            )

            if not response:
                return

            import json

            data = json.loads(response.text)
            strategies = data.get("strategies", [])

            for strategy in strategies:
                title = strategy.get("title")
                action = strategy.get("action")
                target = strategy.get("target")
                desc = strategy.get("description")

                text = (
                    f"🏆 <b>STRATEGIK REJA: N1 SARI</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 <b>Yo'nalish:</b> {title}\n"
                    f"🛠 <b>Amal:</b> {action.upper()}\n"
                    f"🎯 <b>Nishon:</b> {target}\n\n"
                    f"📝 <b>Tafsilot:</b> {desc}\n\n"
                    f"Buni tasdiqlaysizmi?"
                )

                # Callback: strat_conf:action|target|index (limit data)
                # checklist_items ni vaqtinchalik xotirada saqlash uchun id kerak bo'lishi mumkin,
                # lekin hozircha sodda qilamiz: agar checklist bo'lsa title-ni ishlatamiz.
                safe_title = title[:20].replace(":", "").replace("|", "")
                callback_data = f"strat_conf:{action}|{safe_title}"

                # Agar checklist bo'lsa, elementlarni desc ichiga qo'shamiz (user ko'rishi uchun)
                items = strategy.get("checklist_items", [])
                if items:
                    desc += "\n\n📋 <b>Checklist:</b>\n" + "\n".join(
                        [f"- {i}" for i in items]
                    )
                    # Checklist elementlarini callback orqali uzatib bo'lmaydi (limit),
                    # shuning uchun ularni description-dan qayta ajratib olamiz yoki title orqali query qilamiz.
                    # Hozircha description-ga yashirin qilib qo'shib qo'yamiz yoki title-dan foydalanamiz.

                from telegram import InlineKeyboardMarkup, InlineKeyboardButton

                keyboard = [
                    [
                        InlineKeyboardButton(
                            "✅ Tasdiqlash", callback_data=callback_data
                        ),
                        InlineKeyboardButton(
                            "❌ Rad etish", callback_data="strat_ignore"
                        ),
                    ]
                ]

                if config.OWNER_ID:
                    await self.context.bot.send_message(
                        chat_id=int(config.OWNER_ID),
                        text=text,
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                    )

            logger.info("[PROACTIVE] Strategic advice sent for portal review.")

        except Exception as e:
            logger.error(f"[STRATEGY ERROR] {e}")

    async def generate_daily_report_and_planning(self):
        """Kunlik hisobot va ertangi kun uchun topshiriqlar."""
        logger.info("[PROACTIVE] Generating daily report and tomorrow's plan...")

        try:
            # 1. Statistika
            stats = await self.db.get_task_completion_stats(days=1)
            stats_str = "\n".join(
                [
                    f"- {s['username']}: {s['completed']}/{s['total']} vazifa bajarildi"
                    for s in stats
                ]
            )

            # 2. Ertangi plan uchun Gemini-dan so'rash
            query = (
                "Sen 'Jon Branding' CEO-sisan. Bugungi natijalar:\n"
                f"{stats_str}\n\n"
                "Jamoa uchun ertangi kunlik topshiriqlar (3-5 ta) va motivatsion xulosa ber. "
                "Javobni chiroyli HTML formatida ber."
            )

            from google import genai
            from src.main import safe_ai_call

            client = genai.Client(api_key=config.GEMINI_API_KEY)

            response = await safe_ai_call(
                client=client, prompt=query, model=settings.GEMINI_CALL_MODEL
            )

            if not response:
                return

            if config.OWNER_ID:
                await self.context.bot.send_message(
                    chat_id=int(config.OWNER_ID),
                    text=f"📊 <b>KUNLIK HISOBOT VA REJA</b>\n\n{response.text}",
                    parse_mode="HTML",
                )
        except Exception as e:
            logger.error(f"[DAILY REPORT ERROR] {e}")

    async def airtable_pipeline_control(self):
        """Airtable loyihalarini nazorat qilish."""
        logger.info("[PROACTIVE] Checking Airtable projects...")
        try:
            projects = airtable.get_projects()
            for p in projects:
                fields = p.get("fields", {})
                name = fields.get("Project Name", "Unknown")
                stage = fields.get("Stage", "Draft")

                # Agar kechikayotgan bo'lsa yoki etap o'tishi kerak bo'lsa eslatma
                msg = f"📅 <b>Airtable Alert:</b> '{name}' loyihasi hozir '{stage}' bosqichida. Uni keyingi etapga o'tkazishni unutmang!"
                if config.OWNER_ID:
                    await self.context.bot.send_message(
                        chat_id=int(config.OWNER_ID), text=msg, parse_mode="HTML"
                    )
        except Exception as e:
            logger.error(f"[AIRTABLE CONTROL ERROR] {e}")

    async def run_role_based_orchestration(self):
        """AmoCRM va Airtable-dan vazifalarni olib rollarga bo'lib berish."""
        logger.info("[PROACTIVE] Running role-based orchestration...")
        try:
            # 1. Jamoani olish
            team = await self.db.get_team_roles()
            [u for u in team if u["role"] == "Hunter"]
            [u for u in team if u["role"] == "Closer"]
            namers = [u for u in team if u["role"] == "Namer"]
            pms = [u for u in team if u["role"] == "PM"]

            # 2. AmoCRM -> Hunter & Closer
            from src.services.core.crm_integration import CRMIntegration

            CRMIntegration()
            # Eslatma: Haqiqiy tokenni ishlatish kerak, hozircha mavjud API orqali
            # Bu qismda Amo-dan yangi lead/vazifalarni olish mantiqi bo'ladi

            # 3. Airtable -> Namer & PM
            projects = airtable.get_projects()
            for p in projects:
                fields = p.get("fields", {})
                stage = fields.get("Stage", "").lower()
                name = fields.get("Project Name", "Nomsiz")

                target_user = None
                if "naming" in stage and namers:
                    target_user = namers[0]["username"]
                elif pms:
                    target_user = pms[0]["username"]

                if target_user:
                    msg = f"🔔 <b>LOYIHA TOPSHIRIG'I (Airtable)</b>\nLoyiha: {name}\nMas'ul: @{target_user}\nHolat: {stage}"
                    if config.OWNER_ID:
                        await self.context.bot.send_message(
                            chat_id=int(config.OWNER_ID), text=msg, parse_mode="HTML"
                        )

        except Exception as e:
            logger.error(f"[ORCHESTRATION ERROR] {e}")

    async def detect_introductions_and_outreach(self):
        """Chatlardagi tanishuv xabarlarini aniqlash va networking taklif qilish."""
        logger.info("[PROACTIVE] Scanning for new introductions...")
        try:
            messages = await self.db.get_recent_all_messages(
                limit=50
            )  # Oxirgi 50 xabar

            introductions = []
            for msg in messages:
                text = msg.get("text", "")
                if any(
                    word in text.lower()
                    for word in [
                        "ismim",
                        "tanishtir",
                        "biznesim",
                        "shug'ullanaman",
                        "xizmatlar",
                    ]
                ):
                    introductions.append(f"User: {msg.get('username')}, Text: {text}")

            if introductions:
                query = (
                    "Quyidagi xabarlardan o'zini tanishtirgan biznesmenlar yoki potentsial hamkorlarni ajrat:\n"
                    f"{introductions}\n\n"
                    "Ularga qisqa 'Networking' taklifi yoz va natijani JSON formatida qaytar:\n"
                    '{"leads": [{"username": "...", "name": "...", "note": "...", "pitch": "..."}]}'
                )
                from google import genai

                client = genai.Client(api_key=config.GEMINI_API_KEY)
                response = await client.aio.models.generate_content(
                    model=settings.GEMINI_CALL_MODEL,
                    contents=query,
                    config={"response_mime_type": "application/json"},
                )

                import json

                data = json.loads(response.text)
                for lead in data.get("leads", []):
                    username = lead.get("username")
                    name = lead.get("name")
                    note = lead.get("note")

                    # Google Contacts-ga saqlash taklifi
                    text = (
                        f"🤝 <b>YANGI LEAD (NETWORKING)</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"👤 <b>Ism:</b> {name} (@{username})\n"
                        f"📝 <b>Eslatma:</b> {note}\n\n"
                        f"Ushbu kontaktni Google Contacts-ga saqlaymi?"
                    )

                    callback_data = f"lead_save:{username}|{name[:15]}"
                    from telegram import InlineKeyboardMarkup, InlineKeyboardButton

                    keyboard = [
                        [
                            InlineKeyboardButton(
                                "✅ Saqlash", callback_data=callback_data
                            ),
                            InlineKeyboardButton(
                                "❌ Kerak emas", callback_data="lead_ignore"
                            ),
                        ]
                    ]

                    if config.OWNER_ID:
                        await self.context.bot.send_message(
                            chat_id=int(config.OWNER_ID),
                            text=text,
                            parse_mode="HTML",
                            reply_markup=InlineKeyboardMarkup(keyboard),
                        )
        except Exception as e:
            logger.error(f"[NETWORKING ERROR] {e}")

    async def analyze_and_fix_self(self):
        """Loglarni tahlil qilish va muammolarni bartaraf etish (Self-Evolution)."""
        logger.info("[EVOLUTION] Starting Autonomous Self-Analysis...")

        try:
            # 1. Eng oxirgi loglarni o'qish
            log_content = ""
            if os.path.exists("bot.log"):
                with open("bot.log", "r", encoding="utf-8") as f:
                    # Oxirgi 100 qatorni olish
                    lines = f.readlines()
                    log_content = "".join(lines[-100:])

            error_json = ""
            if os.path.exists("ai_errors.json"):
                with open("ai_errors.json", "r", encoding="utf-8") as f:
                    error_json = f.read()[-2000:]

            if not log_content and not error_json:
                return "Tahlil qilish uchun ma'lumot yetarli emas."

            # 2. DeepSeek orqali tahlil qilish
            query = f"Quyidagi xatolarni tahlil qil va tuzatish uchun qisqa maslahat ber. Loglar: {log_content}\nJSON: {error_json}"
            api_key = getattr(config, "DEEPSEEK_KEY", None)

            analysis = GlobalSuperAI.deepseek_reasoning(query, api_key)

            # 3. Bilim sifatida saqlash (Use instance db)
            await self.db.add_learned_fact(
                0, f"SELF_EVOLUTION_REPORT_{datetime.date.today()}: {analysis[:1000]}"
            )

            logger.info(f"[EVOLUTION] Analysis complete: {analysis[:100]}")
            return analysis
        except Exception as e:
            logger.error(f"[EVOLUTION ERROR] {e}")
            return None

    @staticmethod
    def auto_optimize_prompts():
        """System instruction'larni tahlil qilib optimallashtirish (Future)."""
        pass

    async def enforce_team_accountability(self, shift_type: str):
        """Jamoani tag qilgan holda hisobotlarni talab qilish (Morning, Lunch, Evening)."""
        logger.info(f"[ENFORCER] Running {shift_type} accountability check...")

        team = await self.db.get_active_team_members()
        if not team:
            logger.warning("[ENFORCER] No active team members found in DB to tag.")
            return

        # Taglarni shakllantirish
        tags = []
        for member in team:
            username = member.get("username")
            name = member.get("first_name") or "Xodim"
            user_id = member.get("user_id")

            if username:
                if not username.startswith("@"):
                    username = f"@{username}"
                tags.append(
                    f"{username} ({member.get('role') or member.get('detailed_role') or 'Staff'})"
                )
            else:
                tags.append(
                    f"<a href='tg://user?id={user_id}'>{name}</a> ({member.get('role') or member.get('detailed_role') or 'Staff'})"
                )

        tags_str = "\n".join([f"• {t}" for t in tags])

        # Xabar matnini tanlash
        if shift_type == "morning":
            title = "☀️ **MORNING STANDUP: REJALARNI ANIQLaSHTIRISh**"
            msg = (
                f"Assalomu alaykum jamoa! Kunlik ish tartibini jiddiy boshlaymiz.\n\n"
                f"{tags_str}\n\n"
                f"Sizlardan bugungi konkret **YUKLAMA** (topshiriqlariz) nimalardan iboratligini so'rayman. "
                f"Har biringiz o'z yo'nalishingiz bo'yicha 3 ta asosiy vazifani yozib qoldiring! 📝"
            )
        elif shift_type == "lunch":
            title = "🥗 **MID-DAY CHECK: ORALIQ HISOBOT**"
            msg = (
                f"Diqqat jamoa! Kun yarmi o'tdi.\n\n"
                f"{tags_str}\n\n"
                f"Tushlikka chiqishdan oldin ertalabki rejalarning necha foizi bajarilganini hisobot qiling! "
                f"Blokerlar bormi? Nima yordam kerak? Talab qilaman! 🏁"
            )
        else:  # evening
            title = "🏁 **EVENING RESULT: PLAN-FAKT TAHLILI**"
            msg = (
                f"Ish kuni yakunlandi. Endi natija vaqti!\n\n"
                f"{tags_str}\n\n"
                f"Bugungi barcha vazifalar bo'yicha yakuniy hisobotni tushiring. "
                f"Natijasiz ish — bu ish emas. Har biringiz o'z 'Plan-Fact'ingizni yozing! 🔥"
            )

        full_message = f"👸 **OISHA: ENFORCER MODE** 👸\n\n{title}\n\n{msg}"

        # Xabarni yuborish (PROJECTS_GROUP_ID)
        target_chat = getattr(config, "PROJECTS_GROUP_ID", None) or getattr(
            config, "CRM_GROUP_ID", None
        )
        if not target_chat:
            logger.error(
                "[ENFORCER] Neither PROJECTS_GROUP_ID nor CRM_GROUP_ID found in config."
            )
            return

        try:
            # Main Telethon client or PtB bot can be used.
            # Given current architecture, we'll try to use the shared client from main.py if possible,
            # or use context if PtB is active.

            # Using Telethon as primary enforcer (shows as 'Oisha Userbot')
            from src.main import client as telethon_client

            if telethon_client:
                await telethon_client.send_message(
                    target_chat, full_message, parse_mode="html"
                )
                logger.info(
                    f"✅ [ENFORCER] {shift_type} notification sent to {target_chat}"
                )
            else:
                logger.error(
                    "[ENFORCER] Telethon client not available for team tagging."
                )
        except Exception as e:
            logger.error(f"❌ [ENFORCER ERROR] Failed to send notification: {e}")
