import sqlite3
import datetime
import os
import sys
import logging
from html import escape
from typing import Any, Dict, List, Optional
from telegram.ext import Application
import asyncio
from src.time_utils import get_local_now
from src.services.core.agent_loop import AgentTask, AgentTaskResult, MinimalAgentLoop
from src.services.core.agent_policy import AgentPolicyEngine
from src.services.core.agent_verifier import NotificationOutcomeVerifier
from src.services.core.client_journey_playbook import (
    assess_project_portfolio,
    assess_sales_pipeline,
    build_department_direct_messages,
    render_excellence_report,
)
from src.services.core.tool_adapters import build_default_tool_registry
from src.services.core.escalation_agent import EscalationAgent
from src.services.core.persona_hub import get_persona
from src.services.core.gdrive import GoogleDriveSync
from src.services.core.crm_file_offloader import CRMFileOffloader
from src.settings import settings
from telegram import Bot

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DAILY_PLAN_PHASES: Dict[str, Dict[str, str]] = {
    "initial": {
        "job": "daily_plan_initial",
        "title": "📝 <b>Kunlik plan (Internal PM Audit)</b>",
        "deadline": "11:30",
        "tone": "Loyiha bo'yicha bugungi aniq delivery-planingizni topshiring. Hech bir loyiha stagnatsiyada qolmasligi shart.",
    },
    "reminder": {
        "job": "daily_plan_reminder",
        "title": "⏰ <b>PM Audit: Plan hanuz yo'q</b>",
        "deadline": "14:00",
        "tone": "Loyiha bosqichlari bo'yicha kechikish xavfi bor. Plan topshirish intizomini ta'minlang.",
    },
    "escalation": {
        "job": "daily_plan_escalation",
        "title": "🚨 <b>Operatsion eskalatsiya (Strict COO)</b>",
        "deadline": "Darhol",
        "tone": "Audit natijasida intizom buzilishi aniqlandi. Loyihalar xavf ostida. PM darhol hisobot bersin.",
    },
}

PM_STAGE_HINTS = [
    (("brief", "brif"), ("Konsept / yo'nalish", "Brifni yopib, kreativ yo'nalishni tasdiqlang.")),
    (("strategy", "strategiya", "research", "tahlil"), ("Naming / copy", "Research deliverable'ni yakunlab, ijodiy blokka uzating.")),
    (("naming", "copy", "nom"), ("Design", "Tanlangan variantni dizayn ishiga topshiring.")),
    (("design", "dizayn", "draft", "maket"), ("Client review", "Mijoz feedbackini bugun oling va deadline ni qayta mahkamlang.")),
    (("review", "feedback", "approval", "tasdiq"), ("Revision / production", "Feedbackni yopib, keyingi etapni kalendarga kiriting.")),
    (("production", "dev", "fayl", "topshirish"), ("Delivery", "Topshirish paketini tayyorlab, final sanani yoping.")),
]

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
    
    # Determine persona based on user_id (context)
    # If user_id is a manager/team member, use Internal (but check if task is client-facing)
    system_instruction = get_persona(is_team_member=True) 
    
    agent = ResearcherAgent("proactive_bot", system_instruction, api_keys)
    # ResearcherAgent ning process_task metodidan foydalanamiz (u fallback ga ega)
    response = await agent.process_task(user_id, prompt)
    
    # Telegram HTML uchun sanitizatsiya
    response = response.replace("<p>", "").replace("</p>", "\n")
    response = response.replace("<br>", "\n").replace("<br/>", "\n")
    return response


def _safe_text(value: Any, fallback: str = "Noma'lum") -> str:
    text = str(value).strip() if value is not None else ""
    return text or fallback


def _mention(member: Dict[str, Any]) -> str:
    username = (member.get("username") or "").strip()
    name = escape(_safe_text(member.get("name"), f"User_{member.get('user_id', '0')}"))
    if username:
        return f"@{escape(username)}"

    user_id = member.get("user_id")
    if user_id:
        return f"<a href='tg://user?id={user_id}'>{name}</a>"
    return name


def _lead_idle_hours(lead: Dict[str, Any], now_ts: Optional[int] = None) -> int:
    now_epoch = now_ts or int(get_local_now().timestamp())
    updated_at = int(lead.get("updated_at") or 0)
    if updated_at <= 0:
        return 0
    return max(0, int((now_epoch - updated_at) / 3600))


def _format_idle_text(hours: int) -> str:
    if hours >= 48:
        return f"{hours // 24} kun"
    return f"{hours} soat"


def _sales_action_for_lead(lead: Dict[str, Any]) -> str:
    idle_hours = _lead_idle_hours(lead)
    pipeline_id = int(lead.get("pipeline_id") or 0)
    price = int(lead.get("price") or 0)

    if idle_hours >= 72:
        return "bugun qo'ng'iroq qiling, e'tirozni yozing va keyingi qaror sanasini CRMga kiriting"
    if pipeline_id == 10123314:
        if price >= 10_000_000:
            return "qaror beruvchi va narx e'tirozini yopadigan taklif yuboring"
        return "yakunlovchi follow-up yuborib, meeting yoki to'lov sanasini aniq mahkamlang"
    return "briefni aniqlashtirib, keyingi meeting yoki КП sanasini belgilang"


def _sales_manager_playbook(leads: List[Dict[str, Any]]) -> str:
    high_value = any(int(lead.get("price") or 0) >= 10_000_000 for lead in leads)
    older_than_3d = any(_lead_idle_hours(lead) >= 72 for lead in leads)
    if older_than_3d:
        return "1) bugun qo'ng'iroq, 2) yo'qotish sababini yozish, 3) keyingi sanani CRMga kiritish"
    if high_value:
        return "1) qaror beruvchini topish, 2) qiymatni qayta asoslash, 3) taklifga deadline qo'yish"
    return "1) follow-up yuborish, 2) next stepni yozish, 3) lidni bosqichsiz qoldirmaslik"


def _project_stage_recommendation(stage_name: str) -> tuple[str, str]:
    normalized = (stage_name or "").lower()
    for keywords, recommendation in PM_STAGE_HINTS:
        if any(keyword in normalized for keyword in keywords):
            return recommendation
    return ("Keyingi stage aniqlansin", "Statusni yangilang yoki blokerni yozib, keyingi mas'ulni belgilang.")


def _project_age_days(project: Dict[str, Any]) -> int:
    from src.services.core.airtable_sync import AirtableSync as _AT # type: ignore

    fields = project.get("fields", {})
    start_raw = _AT._get_field(fields, "start_date")
    if not start_raw:
        return 0

    try:
        created_dt = datetime.datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
    except ValueError:
        return 0

    now = get_local_now()
    if created_dt.tzinfo is not None:
        now_cmp = now.astimezone(datetime.timezone.utc)
    else:
        now_cmp = now.replace(tzinfo=None)
    return max(0, (now_cmp - created_dt).days)


async def _run_notification_agent(
    db: Database,
    task: AgentTask,
    executor,
):
    loop = MinimalAgentLoop(db)
    policy_engine = AgentPolicyEngine(db)
    verifier = NotificationOutcomeVerifier()

    decision = await policy_engine.evaluate_action(task)
    await loop.log_stage(task, "agent_policy", decision.to_payload(), success=decision.allowed)
    if not decision.allowed:
        plan = loop.plan_task(task)
        execution = {
            "task_id": task.task_id,
            "success": False,
            "reason": decision.reason,
            "policy": decision.to_payload(),
            "blocked_at": get_local_now().isoformat(),
        }
        verification = {
            "task_id": task.task_id,
            "success": False,
            "reason": decision.reason,
            "verification_mode": "policy_gate",
            "verified_at": get_local_now().isoformat(),
        }
        await loop.log_stage(task, "agent_execute", execution, success=False)
        await loop.log_stage(task, "agent_verify", verification, success=False)
        return AgentTaskResult(
            task_id=task.task_id,
            success=False,
            plan=plan,
            execution=execution,
            verification=verification,
            finished_at=get_local_now().isoformat(),
        )

    return await loop.run(task, executor, verifier.verify)


async def demand_daily_plans(phase: str = "initial") -> bool:
    """Kunlik planni jamoa a'zolaridan qat'iy talab qiladi."""
    import src.config as config

    phase_config = DAILY_PLAN_PHASES.get(phase)
    if not phase_config:
        logger.warning(f"[DAILY PLAN] Unknown phase requested: {phase}")
        return False

    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    group_id = getattr(config, "TEAM_GROUP_ID", getattr(config, "CRM_GROUP_ID", None))
    thread_id = getattr(config, "TOPIC_GENERAL_ID", None)
    if not (bot_token and group_id):
        return False

    db = Database()
    today = get_local_now().strftime("%Y-%m-%d")
    job_key = phase_config["job"]
    if await db.is_job_run(job_key, today):
        return False

    missing = await db.get_missing_reports(report_type="morning_plan", date_str=today)
    
    # Agar hech kim plan topshirmagan bo'lsa - jamoadan vazifalarni bo'lib taqsimlashni talab qilish
    if not missing:
        # Barcha jamoa a'zolarini olish
        all_members = await db.get_team_members()
        if all_members and phase == "initial":
            logger.info(f"[DAILY PLAN] No plans submitted by anyone, demanding task distribution for phase={phase}.")
            
            # Vazifalarni bo'lib taqsimlashni talab qilish xabari
            group_message = (
                f"{phase_config['title']}\n\n"
                "📢 <b>DIQQAT!</b> Hali hech kim kunlik reja topshirmagan.\n\n"
                "🎯 <b>JAMOADAN TALAB:</b>\n"
                "• Har bir menejer bugungi vazifalarini aniqlang\n"
                "• AmoCRM'dagi aktiv lidlarni tekshiring\n"
                "• Bir-biringizga yordam bering\n\n"
                "✍️ <b>REJA TOPSHIRISH FORMATI:</b>\n"
                "<code>PLAN: 1) Asosiy natija 2) Bugun yopiladigan ish 3) Kerakli yordam</code>\n\n"
                f"⏰ <b>Deadline: {phase_config['deadline']}</b>"
            )
            
            missing_lines = [f"• {_mention(m)}" for m in all_members]
            group_message += f"\n\n<b>Reja topshirish talab etiladi:</b>\n{chr(10).join(missing_lines)}"
            
            missing = all_members  # Barcha a'zolarga DM yuborish uchun
        else:
            logger.info(f"[DAILY PLAN] Everyone already submitted for phase={phase}.")
            return False
    else:
        missing_lines = []
        for member in missing:
            role_label = member.get("position") or member.get("detailed_role") or member.get("role") or "Team"
            missing_lines.append(f"• {_mention(member)} — {escape(_safe_text(role_label, 'Team'))}")

        footer = (
            "Javob formati: <code>PLAN: 1) asosiy natija 2) bugun yopiladigan ish 3) blocker</code>\n"
            f"Deadline: <b>{phase_config['deadline']}</b>."
        )
        group_message = (
            f"{phase_config['title']}\n\n"
            f"{phase_config['tone']}\n\n"
            "<b>Plan topshirmaganlar:</b>\n"
            f"{chr(10).join(missing_lines)}\n\n"
            f"{footer}"
        )

    if phase == "escalation" and getattr(config, "OWNER_ID", None):
        owner_mention = f"<a href='tg://user?id={config.OWNER_ID}'>Owner</a>"
        group_message += f"\n\nEskalat qabul qiluvchi: {owner_mention}"

    missing_user_ids = [int(member["user_id"]) for member in missing if member.get("user_id")]
    task = AgentTask(
        task_id=f"{job_key}:{today}",
        kind="daily_plan_demand",
        goal=f"Daily plan discipline: {phase}",
        payload={
            "phase": phase,
            "group_id": group_id,
            "thread_id": thread_id,
            "missing_user_ids": missing_user_ids,
            "missing_count": len(missing),
        },
        planner_notes=[
            "Plan topshirmaganlar aniqlanadi",
            "Guruhga intizom xabari yuboriladi",
            "Har bir a'zoga shaxsiy eslatma yuboriladi",
        ],
        requested_by="scheduler",
    )
    registry = build_default_tool_registry(bot_token=bot_token)

    async def executor(agent_task: AgentTask) -> Dict[str, Any]:
        telegram_tool = registry.get("telegram")
        group_result = await telegram_tool.send_group_message(
            group_id,
            group_message,
            thread_id=thread_id,
        )

        direct_messages = []
        for member in missing:
            user_id = member.get("user_id")
            if not user_id:
                continue
            direct_messages.append(
                {
                    "user_id": user_id,
                    "text": (
                        f"{phase_config['title']}\n\n"
                        f"{phase_config['tone']}\n"
                        f"Format: <code>PLAN: ...</code>\n"
                        f"Deadline: <b>{phase_config['deadline']}</b>."
                    ),
                    "parse_mode": "HTML",
                }
            )
        dm_result = await telegram_tool.send_direct_messages(direct_messages)

        return {
            "success": group_result.success,
            "group_sent": group_result.success,
            "group_result": group_result.to_payload(),
            "dm_result": dm_result.to_payload(),
            "sent_count": group_result.sent_count + dm_result.sent_count,
            "dm_sent": dm_result.sent_count,
            "dm_attempted": dm_result.metadata.get("attempted", 0),
            "dm_failed": dm_result.failed_targets,
            "phase": agent_task.payload.get("phase"),
            "missing_count": agent_task.payload.get("missing_count"),
            "tools_used": registry.list_names(),
        }

    result = await _run_notification_agent(db, task, executor)
    if not result.success:
        logger.error(f"[DAILY PLAN] {phase} delivery failed: {result.verification}")
        return False

    await db.mark_job_run(job_key, today)
    logger.info(
        f"[DAILY PLAN] {phase} request sent for {len(missing)} members. "
        f"DM sent={result.execution.get('dm_sent', 0)} failed={len(result.execution.get('dm_failed', []))}"
    )
    return True

class ProactiveWorker:
    def __init__(self, bot, crm):
        self.bot = bot
        self.crm = crm
        self.db = Database()
        # Initialize offloader
        gdrive = GoogleDriveSync(settings.GSHEET_CREDS_FILE)
        self.crm_offloader = CRMFileOffloader(crm.amocrm, gdrive)

    async def _check_amocrm_stagnation(self):
        """AmoCRM stagnatsiya siyosatini tekshirish."""
        logger.info("[PROACTIVE] Checking AmoCRM stagnation...")
        stagnated_leads = self.crm.amocrm.check_stagnated_leads(hours=24)
        
        if stagnated_leads:
            msg = "💡 **FOLLOW-UP DRAFT IDEAS (Stagnation) 💡**\n\nBu mijozlar 24 soatdan beri jim. Mana ba'zi xabar g'oyalari:\n"
            for lead in stagnated_leads[:5]: # Maksimum 5 ta
                msg += f"- **{lead.get('name')}** uchun draft:\n   `Assalomu alaykum, {lead.get('name')}. Loyihangiz bo'yicha qandaydir savollar bormi?`\n"
            
            msg += "\n@Oydin_JonBranding, @Inomjon_JonBranding va @jonbranding_pm, ushbu xabarlarni ko'rib chiqing va mijozga yuboring."
            await self.bot.send_message(config.CRM_GROUP_ID, msg, parse_mode="Markdown")

    async def _send_daily_sales_report(self):
        """Kunlik sotuv hisobotini yuborish."""
        # Faqat belgilangan vaqtda yuborish (faqat 18:00 da, bir marta)
        now = get_local_now()
        if now.hour == 18 and now.minute == 0: # Faqat 18:00 da
            # Bir marta yuborishni tekshirish
            today = now.strftime('%Y-%m-%d')
            if await self.db.is_job_run("daily_sales_report", today):
                logger.info("[PROACTIVE] Daily sales report already sent today. Skipping.")
                return

            logger.info("[PROACTIVE] Sending daily sales report...")
            try:
                report = self.crm.amocrm.get_sales_report()
                msg = (
                    f"📈 **OYLIK SOTUV HISOBOTI (PLAN-FAKT)**\n\n"
                    f"🎯 Reja: 80,000,000 so'm\n"
                    f"✅ Fakt: {report['fact']:,} so'm\n"
                    f"📊 Progress: {report['percent']:.1f}%\n"
                    f"📦 Yopilgan bitimlar: {report['count']} ta"
                )
                await self.bot.send_message(config.CRM_GROUP_ID, msg, parse_mode="Markdown")
                await self.db.mark_job_run("daily_sales_report", today)
                logger.info("[PROACTIVE] Daily sales report sent successfully.")
            except Exception as e:
                logger.error(f"[PROACTIVE] Error sending daily sales report: {e}")

    async def _run_crm_offload(self):
        """AmoCRM diskini tozalash (offload) jarayonini boshqarish."""
        now = get_local_now()
        # Har kuni soat 03:00 da ishga tushirish
        if now.hour == 3 and now.minute == 0:
            today = now.strftime('%Y-%m-%d')
            if await self.db.is_job_run("crm_file_offload", today):
                return

            logger.info("[PROACTIVE] Start AmoCRM File Offload process...")
            try:
                # Haqiqiy o'chirish bilan ishga tushirish
                stats = await self.crm_offloader.run(dry_run=False)
                
                if stats and stats.get("offloaded", 0) > 0:
                    msg = (
                        f"🧹 **AMO_CRM STORAGE CLEANUP**\n\n"
                        f"✅ Ko'chirilgan fayllar: {stats['offloaded']} ta\n"
                        f"📂 Barcha fayllar Google Drive-ga xavfsiz o'tkazildi.\n"
                        f"📊 Xatolar: {stats['errors']}"
                    )
                    await self.bot.send_message(config.CRM_GROUP_ID, msg, parse_mode="Markdown")
                
                await self.db.mark_job_run("crm_file_offload", today)
            except Exception as e:
                logger.error(f"[PROACTIVE] CRM Offload error: {e}")

async def send_proactive_followups():
    """Bazadagi idle foydalanuvchilarni topadi va AI tomonidan yaratilgan follow-up yuboradi."""
    logger.info("Proactive follow-up job started...")
    # Bir martalik ishda guruhga yuboriladigan draftlar soni (spam oldini olish)
    MAX_DRAFTS_PER_RUN = 5
    MAX_ROWS_SCAN = 200
    drafts_sent = 0

    bot_token = os.environ.get("BOT_TOKEN") or config.BOT_TOKEN
    if not bot_token: return
        
    app = Application.builder().token(bot_token).build()
    db = Database()
    now = get_local_now()
    
    try:
        async with await db.get_connection() as conn:
            async with conn.execute("SELECT user_id, first_name, service_type, last_seen, meeting_time, meeting_status FROM users WHERE is_lead_forwarded != 2") as cursor:
                rows = await cursor.fetchall()
                rows = rows[:MAX_ROWS_SCAN]

                for row in rows:
                    if drafts_sent >= MAX_DRAFTS_PER_RUN:
                        logger.info("[PROACTIVE] Follow-up draft limitiga yetildi, jarayon to'xtatildi.")
                        break
                    user_id, first_name, service_type, last_seen_str, meeting_time, meeting_status = row
                    if not last_seen_str: continue

                    last_seen = datetime.datetime.fromisoformat(last_seen_str)
                    hours_diff = (now - last_seen).total_seconds() / 3600
                    
                    message = None
                    if meeting_status == 'scheduled' and hours_diff > 2:
                        prompt = f"Mijoz {first_name} bilan uchrashuv belgilangan edi. U hozir jim. Unga samimiy, Oisha uslubida eslatma yozing. 'Eslab qoldingizmi' kabi shablonlardan qoching. Insoniy va iliq bo'lsin."
                        message = await generate_ai_message(user_id, prompt)
                        await conn.execute("UPDATE users SET meeting_status = 'completed', last_seen = ? WHERE user_id = ?", (now.isoformat(), user_id))
                        
                    elif not meeting_time and 24 <= hours_diff <= 48:
                        prompt = f"Mijoz {first_name} bilan {service_type or 'loyiha'} haqida gaplashgan edik. 1 kundan beri yozmadi. Unga juda samimiy, xuddi Baxtiyorjon akaning yordamchisi kabi, unga qiziqish bildirib xabar yozing. Botligingiz bilinmasin."
                        message = await generate_ai_message(user_id, prompt)
                        await conn.execute("UPDATE users SET last_seen = ? WHERE user_id = ?", (now.isoformat(), user_id))
                        
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
                            drafts_sent += 1
                            await conn.commit()
                            await asyncio.sleep(2)
                        except Exception as e:
                            logger.error(f"[SEND ERROR] {user_id}: {e}")
    except Exception as e:
        logger.error(f"[DB ERROR in Proactive] {e}")

async def distribute_team_tasks(force: bool = False):
    """10:00 va 14:00 da Hunter/Closer lidlarni menejerlar o'rtasida taqsimlash."""
    from src.database import Database
    import src.config as config
    from src.services.core.amocrm_sync import AmoCRMSync
    
    db = Database()
    now = get_local_now()
    today = now.strftime('%Y-%m-%d')
    target_hours = [10, 14]
    
    if not force and now.hour not in target_hours:
        logger.debug(f"[DISTRIBUTION] Skipping: Hour {now.hour} is not in {target_hours}")
        return

    hour_to_mark = now.hour if not force else (14 if now.hour >= 14 else 10)
    job_key = f"team_distribution_{hour_to_mark}"
    
    if not force and await db.is_job_run(job_key, today):
        logger.debug(f"[DISTRIBUTION] Skipping: Job {job_key} already run today.")
        return

    logger.info(f"[DISTRIBUTION] Starting {hour_to_mark}:00 lead assignment cycle (Force={force})...")
    
    from src.services.core.mission_control import MissionControl
    from src.services.core.enterprise_reporter import EnterpriseReporter
    from src.services.core.crm_service import CRMService
    
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

    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    group_id = getattr(config, "TEAM_GROUP_ID", getattr(config, "CRM_GROUP_ID", None))
    thread_id = getattr(config, "TOPIC_GENERAL_ID", None)

    if bot_token and group_id:
        bot = Bot(token=bot_token)
        try:
            await bot.send_message(chat_id=group_id, text=msg, parse_mode="HTML", disable_web_page_preview=True, message_thread_id=thread_id)
            await db.mark_job_run(job_key, today)
            logger.info(f"[DISTRIBUTION] Cycle {now.hour}:00 completed.")
        except Exception as e:
            logger.error(f"[XATO] Team Distribution: {e}")

async def _legacy_check_amocrm_stagnation_direct():
    """AmoCRM stagnatsiya siyosatini tekshirish va AI bilan maslahat berish."""
    from src.database import Database
    import src.config as config
    from src.settings import settings
    
    # [GOD MODE] Cooldown & Schedule Check (Optimization)
    db = Database()
    now = get_local_now()
    today = now.strftime('%Y-%m-%d')
    
    # 1. Check if already sent today
    if await db.is_job_run("stagnation_alert", today):
        return

    # 2. Schedule Check (Fire at 10:00 AM UZT)
    if now.hour != 10:
        return

    logger.info("[STAGNATION] Time to audit! Checking AmoCRM...")
    from src.services.core.amocrm_sync import AmoCRMSync
    amo = AmoCRMSync(config.AMOCRM_SUBDOMAIN, config.AMOCRM_CLIENT_ID, config.AMOCRM_CLIENT_SECRET, config.AMOCRM_REDIRECT_URL)
    stagnated = amo.check_stagnated_leads(hours=24)
    
    if stagnated:
        bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
        group_id = getattr(config, "CRM_GROUP_ID", None)
        owner_id = getattr(config, "OWNER_ID", None)
        if not (bot_token and (group_id or owner_id)): 
            return
        
        bot = Bot(token=bot_token)
        
        # [ENTERPRISE] Daily Memory: Ensure it fires 3 times per day (10:00, 14:00, 18:00)
        db = Database()
        now = get_local_now()
        today = now.strftime('%Y-%m-%d')
        target_hours = [10, 14, 18] # 3 times a day
        
        # 1. Schedule Check
        if now.hour not in target_hours:
            return

        # 2. Check if this specific hour was already sent today
        job_key = f"stagnation_alert_{now.hour}"
        if await db.is_job_run(job_key, today):
            return

        # 1. Guruh uchun umumiy ogohlantirish
        msg = "🚨 <b>STAGNATION ALERT (24h+)</b>\n\nQuyidagi bitimlar harakatsiz qolmoqda:\n"
        for lead in stagnated[:5]:
            msg += f"• <a href='https://{config.AMOCRM_SUBDOMAIN}.amocrm.ru/leads/detail/{lead.get('id')}'>{lead.get('name')}</a>\n"
        
        msg += "\n@Oydin_JonBranding, @Inomjon_JonBranding va @jonbranding_pm, iltimos statusni tekshiring."
        
        # Target topic for CRM alerts
        thread_id = getattr(config, "TOPIC_CRM_ID", None)
        
        try:
            await bot.send_message(chat_id=group_id, text=msg, parse_mode="HTML", disable_web_page_preview=True, message_thread_id=thread_id)
            await db.mark_job_run(job_key, today) # Mark this specific hour as done
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
    from src.services.core.airtable_sync import AirtableSync # type: ignore
    import src.config as config
    
    sync = AirtableSync()
    upcoming = sync.get_upcoming_deadlines(hours=24)
    
    if upcoming:
        bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
        group_id = getattr(config, "PROJECTS_GROUP_ID", None)
        if not (bot_token and group_id): return
        
        bot = Bot(token=bot_token)
        
        msg = "⏳ **URGENT PROJECT DEADLINE (24h)**\n\nQuyidagi topshiriqlar muddati tugashiga 1 kun qoldi:\n"
        for p in upcoming[:5]:
            fields = p.get("fields", {})
            from src.services.core.airtable_sync import AirtableSync as _AT # type: ignore
            p_name = _AT._get_field(fields, "project_name") or "Nomsiz"
            stage = _AT._get_field(fields, "stage") or "?"
            deadline = _AT._get_field(fields, "deadline") or "?"
            msg += f"- {p_name} (Bosqich: {stage}, Muddat: {deadline})\n"
            
        try:
            await bot.send_message(chat_id=group_id, text=msg, parse_mode="Markdown")
            logger.info(f"[PROACTIVE] {len(upcoming)} ta loyiha deadline'i yaqin.")
        except Exception as e:
            logger.error(f"[XATO] Airtable deadline alert: {e}")
            
async def _legacy_check_airtable_stagnation():
    """Airtable loyihalar stagnatsiyasini tekshirish va Inomjonga eslatma yuborish."""
    logger.info("Airtable stagnation check started...")
    from src.services.core.airtable_sync import AirtableSync # type: ignore
    import src.config as config
    from src.database import Database
    
    # [ENTERPRISE] Daily Memory: Ensure it fires 3 times per day (10:00, 14:00, 18:00)
    db = Database()
    now = get_local_now()
    today = now.strftime('%Y-%m-%d')
    target_hours = [10, 14, 18] # 3 times a day
    
    # 1. Schedule Check
    if now.hour not in target_hours:
        return

    # 2. Check if this specific hour was already sent today
    job_key = f"airtable_stagnation_{now.hour}"
    if await db.is_job_run(job_key, today):
        return

    sync = AirtableSync()
    overdue = sync.get_overdue_projects()
    
    if overdue:
        bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
        group_id = getattr(config, "PROJECTS_GROUP_ID", None)
        # Target topic for tasks/projects
        thread_id = getattr(config, "TOPIC_TASKS_ID", None)
        
        if not (bot_token and group_id): return
        
        bot = Bot(token=bot_token)
        
        msg = "🏗 **AIRTABLE STAGNATION ALERT** 🏗\n\n"
        
        pm_mentions = set()
        for p in overdue[:5]:
            fields = p.get("fields", {})
            from src.services.core.airtable_sync import AirtableSync as _AT # type: ignore
            p_name = _AT._get_field(fields, "project_name") or "Nomsiz"
            stage = _AT._get_field(fields, "stage") or "Noma'lum"
            deadline = _AT._get_field(fields, "deadline") or "Belgilanmagan"
            
            pm_value = _AT._get_field(fields, "manager")
            pm_mention = _AT.resolve_pm_handle(pm_value)
            pm_mentions.add(pm_mention)
            
            msg += f"• <b>{p_name}</b> (Bosqich: {stage}, Muddat: {deadline}) — PM: {pm_mention}\n"
            
        if pm_mentions:
            mentions_str = ", ".join(sorted(pm_mentions))
            msg = msg.replace("🏗 **AIRTABLE STAGNATION ALERT** 🏗\n\n", f"🏗 **AIRTABLE STAGNATION ALERT** 🏗\n\n📢 {mentions_str}, quyidagi loyihalar qotib qolgan:\n\n")
            
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

        await db.mark_job_run(job_key, today)

async def _legacy_check_amocrm_stagnation_mixed():
    """Qotib qolgan leadlarni topib, menejerlarga conversion push yuborish."""
    import src.config as config

    db = Database()
    now = get_local_now()
    today = now.strftime("%Y-%m-%d")
    target_hours = [12, 16]

    if now.hour not in target_hours or now.minute > 10:
        return

    job_key = f"sales_conversion_push_{now.hour}"
    if await db.is_job_run(job_key, today):
        return

    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    group_id = getattr(config, "CRM_GROUP_ID", None)
    thread_id = getattr(config, "TOPIC_CRM_ID", None) or getattr(config, "TOPIC_REPORTS_ID", None)
    if not (bot_token and group_id):
        return

    logger.info("[STAGNATION] Checking AmoCRM for stalled conversion opportunities...")
    from src.services.core.amocrm_sync import AmoCRMSync

    amo = AmoCRMSync(
        config.AMOCRM_SUBDOMAIN,
        config.AMOCRM_CLIENT_ID,
        config.AMOCRM_CLIENT_SECRET,
        config.AMOCRM_REDIRECT_URL,
    )
    registry = build_default_tool_registry(bot_token=bot_token, amocrm=amo)
    amocrm_tool = registry.get("amocrm_leads")
    telegram_tool = registry.get("telegram")
    stagnated = await amocrm_tool.fetch_stagnated_leads(hours=24)
    if not stagnated:
        return

    grouped: Dict[int, List[Dict[str, Any]]] = {}
    now_ts = int(now.timestamp())
    for lead in stagnated:
        responsible_id = int(lead.get("responsible_user_id") or 0)
        grouped.setdefault(responsible_id, []).append(lead)

    total_value = sum(int(lead.get("price") or 0) for lead in stagnated)
    lines = [
        "🚨 <b>Sales Conversion Push</b>",
        f"24 soatdan oshgan leadlar: <b>{len(stagnated)}</b> ta",
        f"Risk ostidagi summa: <b>{total_value:,.0f} so'm</b>".replace(",", " "),
        "",
    ]

    manager_names: Dict[int, str] = {}
    for responsible_id, leads in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True):
        if responsible_id not in manager_names:
            manager_names[responsible_id] = await amocrm_tool.get_user_name(responsible_id)
        manager_name = escape(_safe_text(manager_names[responsible_id], "Sotuv menejeri"))
        lines.append(f"👤 <b>{manager_name}</b> — {len(leads)} ta lid")
        for lead in sorted(
            leads,
            key=lambda item: (_lead_idle_hours(item, now_ts), int(item.get("price") or 0)),
            reverse=True,
        )[:3]:
            idle_hours = _lead_idle_hours(lead, now_ts)
            lead_name = escape(_safe_text(lead.get("name")))
            amount = int(lead.get("price") or 0)
            lead_link = f"https://{config.AMOCRM_SUBDOMAIN}.amocrm.ru/leads/detail/{lead.get('id')}"
            lines.append(
                "• "
                f"<a href='{lead_link}'>{lead_name}</a> — {_format_idle_text(idle_hours)}, "
                f"{_sales_action_for_lead(lead)}"
                + (f" <b>({amount:,.0f} so'm)</b>".replace(",", " ") if amount else "")
            )
        lines.append(f"  📌 Bugungi fokus: {_sales_manager_playbook(leads)}")
        lines.append("")

    lines.append("Talab: har bir qotib qolgan lid uchun bugun next step, sabab va keyingi sana CRMga yozilsin.")
    message = "\n".join(lines).strip()
    manager_ids = list(getattr(config, "SALES_MANAGER_IDS", []) or [])
    task = AgentTask(
        task_id=f"{job_key}:{today}",
        kind="sales_conversion_push",
        goal="CRMdagi qotib qolgan leadlarni conversionga qaytarish",
        payload={
            "group_id": group_id,
            "thread_id": thread_id,
            "manager_ids": manager_ids,
            "lead_count": len(stagnated),
            "risk_sum": total_value,
        },
        planner_notes=[
            "Qotib qolgan leadlar menejer bo'yicha guruhlanadi",
            "CRM threadga conversion push yuboriladi",
            "Sales managerlarga DM orqali follow-up bosimi beriladi",
        ],
        requested_by="scheduler",
    )

    async def executor(agent_task: AgentTask) -> Dict[str, Any]:
        bot = Bot(token=bot_token)
        dm_sent = 0
        dm_failed: List[Dict[str, Any]] = []

        await bot.send_message(
            chat_id=group_id,
            text=message,
            parse_mode="HTML",
            disable_web_page_preview=True,
            message_thread_id=thread_id,
        )

        if manager_ids:
            dm_text = (
                "🚨 <b>Sales Conversion Push</b>\n"
                "CRMda qotib qolgan leadlar bo'yicha guruhga report tashlandi.\n"
                "Bugun har bir lead uchun: 1) kontakt, 2) sabab, 3) next step sanasi yozilsin."
            )
            for manager_id in manager_ids:
                try:
                    await bot.send_message(chat_id=manager_id, text=dm_text, parse_mode="HTML")
                    dm_sent += 1
                except Exception as exc:
                    logger.warning(f"[STAGNATION] Could not DM sales manager {manager_id}: {exc}")
                    dm_failed.append({"user_id": manager_id, "error": str(exc)})

        return {
            "success": True,
            "group_sent": True,
            "sent_count": 1 + dm_sent,
            "dm_sent": dm_sent,
            "dm_failed": dm_failed,
            "lead_count": agent_task.payload.get("lead_count"),
            "risk_sum": agent_task.payload.get("risk_sum"),
        }

    result = await _run_notification_agent(db, task, executor)
    if not result.success:
        logger.error(f"[STAGNATION] Conversion push delivery failed: {result.verification}")
        return

    await db.mark_job_run(job_key, today)
    logger.info(f"[STAGNATION] Conversion push sent for hour {now.hour}.")

async def _deprecated_check_airtable_stagnation_direct():
    """Qimirlamay qolgan loyihalarni topib, PMga keyingi stage bo'yicha push yuborish."""
    logger.info("Airtable stagnation check started...")
    from telegram import Bot
    from src.services.core.airtable_sync import AirtableSync # type: ignore
    from src.services.core.airtable_sync import AirtableSync # type: ignore as AirtableSync
    import src.config as config

    db = Database()
    now = get_local_now()
    today = now.strftime("%Y-%m-%d")
    target_hours = [11, 15, 18]

    if now.hour not in target_hours or now.minute > 10:
        return

    job_key = f"project_stage_push_{now.hour}"
    if await db.is_job_run(job_key, today):
        return

    sync = AirtableSync()
    projects = sync.get_projects()
    stalled_projects: List[Dict[str, Any]] = []

    for project in projects:
        fields = project.get("fields", {})
        stage = _safe_text(AirtableSync._get_field(fields, "stage"), "")
        if stage in AirtableSync.DONE_STAGES:
            continue

        deadline = AirtableSync._get_field(fields, "deadline")
        manager_name = _safe_text(AirtableSync._get_field(fields, "manager"), "PM")
        age_days = _project_age_days(project)
        is_overdue = False
        if deadline:
            try:
                deadline_dt = datetime.datetime.strptime(str(deadline), "%Y-%m-%d")
                is_overdue = deadline_dt.date() < now.date()
            except ValueError:
                is_overdue = False

        if age_days >= 3 or is_overdue:
            next_stage, unblock_action = _project_stage_recommendation(stage)
            stalled_projects.append(
                {
                    "name": _safe_text(AirtableSync._get_field(fields, "project_name")),
                    "stage": stage or "Noma'lum",
                    "manager": manager_name,
                    "deadline": deadline or "Belgilanmagan",
                    "age_days": age_days,
                    "is_overdue": is_overdue,
                    "next_stage": next_stage,
                    "action": unblock_action,
                }
            )

    if not stalled_projects:
        return

    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    group_id = getattr(config, "PROJECTS_GROUP_ID", None)
    thread_id = getattr(config, "TOPIC_TASKS_ID", None)
    if not (bot_token and group_id):
        return

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for project in stalled_projects:
        grouped.setdefault(project["manager"], []).append(project)

    lines = [
        "🏗 <b>PM Stage Push</b>",
        f"Qimirlamay qolgan loyiha: <b>{len(stalled_projects)}</b> ta",
        "Talab: bugun status yangilanadi yoki keyingi etapga o'tish sanasi qo'yiladi.",
        "",
    ]

    for manager_name, manager_projects in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True):
        lines.append(f"👤 <b>{escape(manager_name)}</b> — {len(manager_projects)} ta loyiha")
        for project in sorted(
            manager_projects,
            key=lambda item: (item["is_overdue"], item["age_days"]),
            reverse=True,
        )[:4]:
            risk_text = "deadline o'tgan" if project["is_overdue"] else f"{project['age_days']} kun qimirlamagan"
            lines.append(
                "• "
                f"<b>{escape(project['name'])}</b> — {escape(project['stage'])}, {risk_text}. "
                f"Keyingi stage: <b>{escape(project['next_stage'])}</b>."
            )
            lines.append(f"  📌 Bugungi qadam: {escape(project['action'])}")
        lines.append("")

    bot = Bot(token=bot_token)
    await bot.send_message(
        chat_id=group_id,
        text="\n".join(lines).strip(),
        parse_mode="HTML",
        message_thread_id=thread_id,
    )

    pm_user = db.get_user_by_role("pm")
    if pm_user and pm_user.get("user_id"):
        try:
            await bot.send_message(
                chat_id=pm_user["user_id"],
                text=(
                    "🏗 <b>PM Stage Push</b>\n"
                    "Airtable'da qimirlamay qolgan loyihalar bo'yicha report guruhga yuborildi.\n"
                    "Bugun har bir loyiha uchun keyingi stage yoki blocker yozilsin."
                ),
                parse_mode="HTML",
            )
        except Exception as exc:
            logger.warning(f"[AIRTABLE STAGNATION] Could not DM PM: {exc}")

    await db.mark_job_run(job_key, today)
    logger.info(f"[AIRTABLE STAGNATION] Project stage push sent for hour {now.hour}.")

async def _legacy_check_airtable_stagnation_mixed():
    """Qimirlamay qolgan loyihalarni topib, PMga keyingi stage bo'yicha push yuborish."""
    logger.info("Airtable stagnation check started...")
    from telegram import Bot
    from src.services.core.airtable_sync import AirtableSync # type: ignore
    from src.services.core.airtable_sync import AirtableSync # type: ignore as AirtableSync
    import src.config as config

    db = Database()
    now = get_local_now()
    today = now.strftime("%Y-%m-%d")
    target_hours = [11, 15, 18]

    if now.hour not in target_hours or now.minute > 10:
        return

    job_key = f"project_stage_push_{now.hour}"
    if await db.is_job_run(job_key, today):
        return

    sync = AirtableSync()
    projects = sync.get_projects()
    stalled_projects: List[Dict[str, Any]] = []

    for project in projects:
        fields = project.get("fields", {})
        stage = _safe_text(AirtableSync._get_field(fields, "stage"), "")
        if stage in AirtableSync.DONE_STAGES:
            continue

        deadline = AirtableSync._get_field(fields, "deadline")
        manager_name = _safe_text(AirtableSync._get_field(fields, "manager"), "PM")
        age_days = _project_age_days(project)
        is_overdue = False
        if deadline:
            try:
                deadline_dt = datetime.datetime.strptime(str(deadline), "%Y-%m-%d")
                is_overdue = deadline_dt.date() < now.date()
            except ValueError:
                is_overdue = False

        if age_days >= 3 or is_overdue:
            next_stage, unblock_action = _project_stage_recommendation(stage)
            stalled_projects.append(
                {
                    "name": _safe_text(AirtableSync._get_field(fields, "project_name")),
                    "stage": stage or "Noma'lum",
                    "manager": manager_name,
                    "deadline": deadline or "Belgilanmagan",
                    "age_days": age_days,
                    "is_overdue": is_overdue,
                    "next_stage": next_stage,
                    "action": unblock_action,
                }
            )

    if not stalled_projects:
        return

    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    group_id = getattr(config, "PROJECTS_GROUP_ID", None)
    thread_id = getattr(config, "TOPIC_TASKS_ID", None)
    if not (bot_token and group_id):
        return

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for project in stalled_projects:
        grouped.setdefault(project["manager"], []).append(project)

    lines = [
        "🏗 <b>PM Stage Push</b>",
        f"Qimirlamay qolgan loyiha: <b>{len(stalled_projects)}</b> ta",
        "Talab: bugun status yangilanadi yoki keyingi etapga o'tish sanasi qo'yiladi.",
        "",
    ]

    for manager_name, manager_projects in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True):
        lines.append(f"👤 <b>{escape(manager_name)}</b> — {len(manager_projects)} ta loyiha")
        for project in sorted(
            manager_projects,
            key=lambda item: (item["is_overdue"], item["age_days"]),
            reverse=True,
        )[:4]:
            risk_text = "deadline o'tgan" if project["is_overdue"] else f"{project['age_days']} kun qimirlamagan"
            lines.append(
                "• "
                f"<b>{escape(project['name'])}</b> — {escape(project['stage'])}, {risk_text}. "
                f"Keyingi stage: <b>{escape(project['next_stage'])}</b>."
            )
            lines.append(f"  📌 Bugungi qadam: {escape(project['action'])}")
        lines.append("")

    message = "\n".join(lines).strip()
    pm_user = db.get_user_by_role("pm")
    task = AgentTask(
        task_id=f"{job_key}:{today}",
        kind="pm_stage_push",
        goal="Airtabledagi qimirlamay qolgan loyihalarni keyingi stagega surish",
        payload={
            "group_id": group_id,
            "thread_id": thread_id,
            "project_count": len(stalled_projects),
            "pm_user_id": pm_user.get("user_id") if pm_user else None,
        },
        planner_notes=[
            "Stalled loyihalar manager bo'yicha guruhlanadi",
            "PM threadga status push yuboriladi",
            "Mas'ul PMga shaxsiy DM bilan next-step talab qilinadi",
        ],
        requested_by="scheduler",
    )

    async def executor(agent_task: AgentTask) -> Dict[str, Any]:
        bot = Bot(token=bot_token)
        dm_sent = 0
        dm_failed: List[Dict[str, Any]] = []

        await bot.send_message(
            chat_id=group_id,
            text=message,
            parse_mode="HTML",
            message_thread_id=thread_id,
        )

        if pm_user and pm_user.get("user_id"):
            try:
                await bot.send_message(
                    chat_id=pm_user["user_id"],
                    text=(
                        "🏗 <b>PM Stage Push</b>\n"
                        "Airtable'da qimirlamay qolgan loyihalar bo'yicha report guruhga yuborildi.\n"
                        "Bugun har bir loyiha uchun keyingi stage yoki blocker yozilsin."
                    ),
                    parse_mode="HTML",
                )
                dm_sent += 1
            except Exception as exc:
                logger.warning(f"[AIRTABLE STAGNATION] Could not DM PM: {exc}")
                dm_failed.append({"user_id": pm_user['user_id'], "error": str(exc)})

        return {
            "success": True,
            "group_sent": True,
            "sent_count": 1 + dm_sent,
            "dm_sent": dm_sent,
            "dm_failed": dm_failed,
            "project_count": agent_task.payload.get("project_count"),
        }

    result = await _run_notification_agent(db, task, executor)
    if not result.success:
        logger.error(f"[AIRTABLE STAGNATION] Project stage push delivery failed: {result.verification}")
        return

    await db.mark_job_run(job_key, today)
    logger.info(f"[AIRTABLE STAGNATION] Project stage push sent for hour {now.hour}.")


async def send_daily_report():
    """Kunlik umumiy statistika va jamoa samaradorligi hisoboti."""
    logger.info("Daily report job started...")
    from src.services.core.amocrm_sync import AmoCRMSync
    from src.services.core.airtable_sync import AirtableSync # type: ignore
    from src.services.core.enterprise_reporter import EnterpriseReporter
    from src.services.core.crm_service import CRMService
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
    today = get_local_now().strftime('%Y-%m-%d')
    if await db.is_job_run("daily_report", today):
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
            import re
            clean_text = re.sub(r'<[^>]+>', '', report_msg)
            await bot.send_message(chat_id=group_id, text=clean_text, parse_mode=None, message_thread_id=thread_id)
        
        # 2. Owner-ga (Baxtiyor aka) yuborish
        owner_id = getattr(config, "OWNER_ID", None)
        if owner_id and str(owner_id) != str(group_id):
            try:
                await bot.send_message(chat_id=owner_id, text=report_msg, parse_mode="HTML")
                logger.info(f"[DAILY REPORT] Owner-ga ({owner_id}) yuborildi.")
            except Exception as e:
                logger.warning(f"[DAILY REPORT] Owner-ga HTML yuborishda xato, Plain-ga o'tildi: {e}")
                import re
                clean_text = re.sub(r'<[^>]+>', '', report_msg)
                await bot.send_message(chat_id=owner_id, text=clean_text, parse_mode=None)
            
        # Vazifani bajarilgan deb belgilash
        await db.mark_job_run("daily_report", today)
        
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
    today = get_local_now().strftime('%Y-%m-%d')
    if await db.is_job_run("morning_briefing", today):
        logger.info("[MORNING BRIEFING] Allaqachon bugun yuborilgan. Skip.")
        return

    from src.services.core.crm_service import CRMService
    from src.services.core.enterprise_reporter import EnterpriseReporter
    
    crm = CRMService()
    reporter = EnterpriseReporter(db, crm)
    
    # 1. Get Hard Audit Data
    hard_audit = await reporter.get_real_numbers_audit()
    
    # 2. Get Priority Tasks
    priorities = await db.get_priority_tasks(limit=3)
    priority_text = ""
    if priorities:
        priority_text = "\n\n📌 <b>Bugungi ustuvor vazifalar:</b>\n"
        for p in priorities:
            name = p.get('name') or p.get('username') or "Unknown"
            priority_text += f"• {p['title']} — <i>{name}</i>\n"

    # 3. AI Intro Generation (Human touch based on Audit)
    prompt = (
        f"Siz Oisha-OS (COO) xizmatisiz. Quyidagi CRM audit natijalari asosida jamoaga 100 ta so'zdan oshmaydigan, "
        f"shafqatsiz darajada aniq va faqat operatsion kamchiliklarga qaratilgan tahlil yozing. \n\nAUDIT:\n{hard_audit}\n\n"
        "Hech qanday maqtov va 'paxta' bo'lmasin. Faqat anomaliyalarga e'tibor qarating. HTML formatda bo'lsin."
    )

    
    from src.services.core.proactive_worker import generate_ai_message
    ai_intro = await generate_ai_message(999, prompt)
    
    # Combined Briefing
    full_briefing = f"{ai_intro}\n\n{hard_audit}{priority_text}"
    
    try:
        from telegram import Bot
        bot = Bot(token=bot_token)
        
        # HTML Sanitizatsiya (Oisha Stable)
        clean_briefing = full_briefing.replace("<p>", "").replace("</p>", "\n")
        clean_briefing = clean_briefing.replace("<ul>", "").replace("</ul>", "")
        clean_briefing = clean_briefing.replace("<li>", "• ").replace("</li>", "\n")
        
        try:
            await bot.send_message(chat_id=group_id, text=clean_briefing, parse_mode="HTML", message_thread_id=thread_id)
            logger.info(f"[MORNING BRIEFING] Jamoa guruhiga ({group_id}) yuborildi.")
        except Exception as html_err:
            logger.warning(f"[MORNING BRIEFING] Dastlabki yuborishda xato, fallback ishga tushmoqda: {html_err}")
            try:
                # Fallback: Plain text and no thread_id
                await bot.send_message(chat_id=group_id, text=full_briefing, parse_mode=None)
                logger.info("[MORNING BRIEFING] Fallback muvaffaqiyatli.")
            except Exception as final_err:
                logger.error(f"[MORNING BRIEFING] Fallback ham muvaffaqiyatsiz: {final_err}")
                return

        # Vazifani bajarilgan deb belgilash
        await db.mark_job_run("morning_briefing", today)


    except Exception as e:
        logger.error(f"[XATO] Morning Briefing yuborishda: {e}", exc_info=True)

async def send_overdue_nudges():
    """Vazifasi kechikayotgan xodimlarni guruhda (tagging) ogohlantirish."""
    db = Database()
    today = get_local_now().strftime('%Y-%m-%d')
    if await db.is_job_run("overdue_nudges", today):
        logger.info("[NUDGES] Allaqachon bugun yuborilgan. Skip.")
        return

    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    # Using specific Group ID for projects/tasks
    group_id = getattr(config, "PROJECTS_GROUP_ID", None)
    # Target topic for tasks/nudges
    thread_id = getattr(config, "TOPIC_TASKS_ID", None)
    if not (bot_token and group_id): return

    overdue = await db.get_overdue_tasks()
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
        await db.mark_job_run("overdue_nudges", today)
        logger.info(f"[PROACTIVE] Public nudges sent for {len(by_user)} users.")
    except Exception as e:
        logger.error(f"[XATO] Public Nudge yuborishda: {e}")

async def send_lunch_reminder():
    """Tushlik vaqtida ertalabki vazifalar haqida eslatish."""
    logger.info("Lunch reminder job started...")
    from src.services.core.enterprise_reporter import EnterpriseReporter
    from src.services.core.crm_service import CRMService
    import src.config as config
    
    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    group_id = getattr(config, "TEAM_GROUP_ID", config.CRM_GROUP_ID)
    thread_id = getattr(config, "TOPIC_GENERAL_ID", None)
    
    if not (bot_token and group_id): 
        logger.warning("[LUNCH] Bot token yoki Group ID topilmadi.")
        return
    
    db = Database()
    today = get_local_now().strftime('%Y-%m-%d')
    
    # Bir marta yuborishni tekshirish
    if await db.is_job_run("lunch_reminder", today):
        logger.info("[LUNCH] Allaqachon bugun yuborilgan. Skip.")
        return
    
    try:
        # Ertalabki rejani tekshirish
        morning_plan = await db.get_daily_plan(today)
        
        if not morning_plan:
            # Reja yo'q - talab qilish
            msg = (
                f"🍽 <b>TUSHLIK VAQTI ({get_local_now().strftime('%H:%M')})</b>\n\n"
                "📢 <b>DIQQAT!</b> Hali ham rejalar topshirilmagan.\n\n"
                "🎯 <b>ERTALAB TOPSHIRILGAN VAZIFALAR:</b>\n"
                "• Vazifalar rejalashtirilmagan\n\n"
                "✍️ <b>HOZIR TOPSHIRING:</b>\n"
                "<code>PLAN: 1) Asosiy vazifa 2) Bugun yopiladigan ish 3) Kerakli yordam</code>\n\n"
                "⏰ <b>KECHGA QOLDIRMANGLAR!</b>"
            )
        else:
            # Reja bor - eslatish
            completed = sum(1 for p in morning_plan if p.get('status') == 'completed')
            total = len(morning_plan)
            
            msg = (
                f"🍽 <b>TUSHLIK VAQTI ({get_local_now().strftime('%H:%M')})</b>\n\n"
                "☀️ <b>ERTALABKI REJALAR ESLOMATI:</b>\n"
                f"• Jami vazifalar: <b>{total} ta</b>\n"
                f"• Bajarilgan: <b>{completed} ta</b>\n"
                f"• Qoldi: <b>{total - completed} ta</b>\n\n"
            )
            
            if completed < total:
                msg += (
                    "💪 <b>BAJARILMAGAN VAZIFALARNI TUGATING!</b>\n"
                    "Kechki hisobotga tayyorlaning.\n\n"
                )
            else:
                msg += (
                    "🌟 <b>A'LO!</b> Barcha vazifalar bajarilgan.\n"
                    "Shu ruhda davom eting!\n\n"
                )
            
            msg += (
                "📝 <b>HISOBOT FORMATI (KECH 20:00):</b>\n"
                "<code>REPORT: 1) Bajarilgan ishlar 2) Natijalar 3) Ertaga rejalar</code>\n\n"
                "👑 <b>@baxtiyorjong_gaziyev</b> kuzatib turibdi."
            )
        
        from telegram import Bot
        bot = Bot(token=bot_token)
        await bot.send_message(chat_id=group_id, text=msg, parse_mode="HTML", message_thread_id=thread_id)
        await db.mark_job_run("lunch_reminder", today)
        logger.info("[LUNCH] Eslatma yuborildi.")
        
    except Exception as e:
        logger.error(f"[XATO] Lunch Reminder: {e}")

async def send_evening_fact_report():
    """Kechki Plan-Fakt natijalarini audit qilish va guruhga yuborish."""
    logger.info("Evening Fact report job started...")
    from src.services.core.enterprise_reporter import EnterpriseReporter
    from src.services.core.crm_service import CRMService
    import src.config as config
    
    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    group_id = getattr(config, "TEAM_GROUP_ID", config.CRM_GROUP_ID)
    thread_id = getattr(config, "TOPIC_REPORTS_ID", None)
    
    if not (bot_token and group_id): return
    
    db = Database()
    today = get_local_now().strftime('%Y-%m-%d')
    if await db.is_job_run("evening_fact", today):
        logger.info("[EVENING FACT] Allaqachon bugun yuborilgan. Skip.")
        return

    try:
        crm_service = CRMService()
        reporter = EnterpriseReporter(db, crm_service)
        report_msg = await reporter.generate_plan_fact_report()
        
        from telegram import Bot
        bot = Bot(token=bot_token)
        await bot.send_message(chat_id=group_id, text=report_msg, parse_mode="HTML", message_thread_id=thread_id)
        await db.mark_job_run("evening_fact", today)
        logger.info("[EVENING FACT] Sent successfully.")
    except Exception as e:
        logger.error(f"[XATO] Evening Fact: {e}")


async def _execute_telegram_notification(
    registry,
    *,
    group_id: int,
    message: str,
    thread_id: Optional[int] = None,
    direct_messages: Optional[List[Dict[str, Any]]] = None,
    disable_web_page_preview: bool = False,
) -> Dict[str, Any]:
    telegram_tool = registry.get("telegram")
    group_result = await telegram_tool.send_group_message(
        group_id,
        message,
        thread_id=thread_id,
        disable_web_page_preview=disable_web_page_preview,
    )
    dm_result = await telegram_tool.send_direct_messages(direct_messages or [])
    return {
        "success": group_result.success,
        "group_sent": group_result.success,
        "group_result": group_result.to_payload(),
        "dm_result": dm_result.to_payload(),
        "sent_count": group_result.sent_count + dm_result.sent_count,
        "dm_sent": dm_result.sent_count,
        "dm_attempted": dm_result.metadata.get("attempted", 0),
        "dm_failed": dm_result.failed_targets,
        "tools_used": registry.list_names(),
    }


async def check_amocrm_stagnation():
    """Qotib qolgan leadlarni topib, menejerlarga conversion push yuborish."""
    import src.config as config
    from src.services.core.amocrm_sync import AmoCRMSync

    db = Database()
    now = get_local_now()
    today = now.strftime("%Y-%m-%d")
    target_hours = [12, 16]

    if now.hour not in target_hours or now.minute > 10:
        return

    job_key = f"sales_conversion_push_{now.hour}"
    if await db.is_job_run(job_key, today):
        return

    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    group_id = getattr(config, "CRM_GROUP_ID", None)
    thread_id = getattr(config, "TOPIC_CRM_ID", None) or getattr(config, "TOPIC_REPORTS_ID", None)
    if not (bot_token and group_id):
        return

    amo = AmoCRMSync(
        config.AMOCRM_SUBDOMAIN,
        config.AMOCRM_CLIENT_ID,
        config.AMOCRM_CLIENT_SECRET,
        config.AMOCRM_REDIRECT_URL,
    )
    registry = build_default_tool_registry(bot_token=bot_token, amocrm=amo)
    amocrm_tool = registry.get("amocrm_leads")
    stagnated = await amocrm_tool.fetch_stagnated_leads(hours=24)
    if not stagnated:
        return

    grouped: Dict[int, List[Dict[str, Any]]] = {}
    now_ts = int(now.timestamp())
    for lead in stagnated:
        responsible_id = int(lead.get("responsible_user_id") or 0)
        grouped.setdefault(responsible_id, []).append(lead)

    total_value = sum(int(lead.get("price") or 0) for lead in stagnated)
    lines = [
        "ðŸš¨ <b>Sales Conversion Push</b>",
        f"24 soatdan oshgan leadlar: <b>{len(stagnated)}</b> ta",
        f"Risk ostidagi summa: <b>{total_value:,.0f} so'm</b>".replace(",", " "),
        "",
    ]

    manager_names: Dict[int, str] = {}
    for responsible_id, leads in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True):
        if responsible_id not in manager_names:
            manager_names[responsible_id] = await amocrm_tool.get_user_name(responsible_id)
        manager_name = escape(_safe_text(manager_names[responsible_id], "Sotuv menejeri"))
        lines.append(f"👤 <b>{manager_name}</b> — {len(leads)} ta lid")
        for lead in sorted(
            leads,
            key=lambda item: (_lead_idle_hours(item, now_ts), int(item.get("price") or 0)),
            reverse=True,
        )[:3]:
            idle_hours = _lead_idle_hours(lead, now_ts)
            lead_name = escape(_safe_text(lead.get("name")))
            amount = int(lead.get("price") or 0)
            lead_link = f"https://{config.AMOCRM_SUBDOMAIN}.amocrm.ru/leads/detail/{lead.get('id')}"
            lines.append(
                "• "
                f"<a href='{lead_link}'>{lead_name}</a> — {_format_idle_text(idle_hours)}, "
                f"{_sales_action_for_lead(lead)}"
                + (f" <b>({amount:,.0f} so'm)</b>".replace(",", " ") if amount else "")
            )
        lines.append(f"  ðŸ“Œ Bugungi fokus: {_sales_manager_playbook(leads)}")
        lines.append("")

    lines.append("Talab: har bir qotib qolgan lid uchun bugun next step, sabab va keyingi sana CRMga yozilsin.")
    message = "\n".join(lines).strip()
    manager_ids = list(getattr(config, "SALES_MANAGER_IDS", []) or [])
    direct_messages = [
        {
            "user_id": manager_id,
            "text": (
                "ðŸš¨ <b>Sales Conversion Push</b>\n"
                "CRMda qotib qolgan leadlar bo'yicha guruhga report tashlandi.\n"
                "Bugun har bir lead uchun: 1) kontakt, 2) sabab, 3) next step sanasi yozilsin."
            ),
            "parse_mode": "HTML",
        }
        for manager_id in manager_ids
    ]
    task = AgentTask(
        task_id=f"{job_key}:{today}",
        kind="sales_conversion_push",
        goal="CRMdagi qotib qolgan leadlarni conversionga qaytarish",
        payload={
            "group_id": group_id,
            "thread_id": thread_id,
            "manager_ids": manager_ids,
            "lead_count": len(stagnated),
            "risk_sum": total_value,
        },
        planner_notes=[
            "Qotib qolgan leadlar menejer bo'yicha guruhlanadi",
            "CRM threadga conversion push yuboriladi",
            "Sales managerlarga DM orqali follow-up bosimi beriladi",
        ],
        requested_by="scheduler",
    )

    async def executor(agent_task: AgentTask) -> Dict[str, Any]:
        execution = await _execute_telegram_notification(
            registry,
            group_id=group_id,
            message=message,
            thread_id=thread_id,
            direct_messages=direct_messages,
            disable_web_page_preview=True,
        )
        execution.update(
            {
                "lead_count": agent_task.payload.get("lead_count"),
                "risk_sum": agent_task.payload.get("risk_sum"),
            }
        )
        return execution

    result = await _run_notification_agent(db, task, executor)
    if not result.success:
        logger.error(f"[STAGNATION] Conversion push delivery failed: {result.verification}")
        return

    await db.mark_job_run(job_key, today)
    logger.info(f"[STAGNATION] Conversion push sent for hour {now.hour}.")


async def check_airtable_stagnation():
    """Qimirlamay qolgan loyihalarni topib, PMga keyingi stage bo'yicha push yuborish."""
    logger.info("Airtable stagnation check started...")
    from src.services.core.airtable_sync import AirtableSync # type: ignore
    import src.config as config

    db = Database()
    now = get_local_now()
    today = now.strftime("%Y-%m-%d")
    target_hours = [11, 15, 18]

    if now.hour not in target_hours or now.minute > 10:
        return

    job_key = f"project_stage_push_{now.hour}"
    if await db.is_job_run(job_key, today):
        return

    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    group_id = getattr(config, "PROJECTS_GROUP_ID", None)
    thread_id = getattr(config, "TOPIC_TASKS_ID", None)
    if not (bot_token and group_id):
        return

    sync = AirtableSync()
    registry = build_default_tool_registry(bot_token=bot_token, airtable=sync)
    airtable_tool = registry.get("airtable_projects")
    projects = await airtable_tool.fetch_projects()
    stalled_projects: List[Dict[str, Any]] = []

    for project in projects:
        fields = project.get("fields", {})
        stage = _safe_text(AirtableSync._get_field(fields, "stage"), "")
        if stage in AirtableSync.DONE_STAGES:
            continue

        deadline = AirtableSync._get_field(fields, "deadline")
        manager_name = _safe_text(AirtableSync._get_field(fields, "manager"), "PM")
        age_days = _project_age_days(project)
        is_overdue = False
        if deadline:
            try:
                deadline_dt = datetime.datetime.strptime(str(deadline), "%Y-%m-%d")
                is_overdue = deadline_dt.date() < now.date()
            except ValueError:
                is_overdue = False

        if age_days >= 3 or is_overdue:
            next_stage, unblock_action = _project_stage_recommendation(stage)
            stalled_projects.append(
                {
                    "name": _safe_text(AirtableSync._get_field(fields, "project_name")),
                    "stage": stage or "Noma'lum",
                    "manager": manager_name,
                    "deadline": deadline or "Belgilanmagan",
                    "age_days": age_days,
                    "is_overdue": is_overdue,
                    "next_stage": next_stage,
                    "action": unblock_action,
                }
            )

    if not stalled_projects:
        return

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for project in stalled_projects:
        grouped.setdefault(project["manager"], []).append(project)

    lines = [
        "ðŸ— <b>PM Stage Push</b>",
        f"Qimirlamay qolgan loyiha: <b>{len(stalled_projects)}</b> ta",
        "Talab: bugun status yangilanadi yoki keyingi etapga o'tish sanasi qo'yiladi.",
        "",
    ]

    for manager_name, manager_projects in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True):
        lines.append(f"👤 <b>{escape(manager_name)}</b> — {len(manager_projects)} ta loyiha")
        for project in sorted(
            manager_projects,
            key=lambda item: (item["is_overdue"], item["age_days"]),
            reverse=True,
        )[:4]:
            risk_text = "deadline o'tgan" if project["is_overdue"] else f"{project['age_days']} kun qimirlamagan"
            lines.append(
                "• "
                f"<b>{escape(project['name'])}</b> — {escape(project['stage'])}, {risk_text}. "
                f"Keyingi stage: <b>{escape(project['next_stage'])}</b>."
            )
            lines.append(f"  ðŸ“Œ Bugungi qadam: {escape(project['action'])}")
        lines.append("")

    message = "\n".join(lines).strip()
    pm_user = db.get_user_by_role("pm")
    direct_messages = []
    if pm_user and pm_user.get("user_id"):
        direct_messages.append(
            {
                "user_id": pm_user["user_id"],
                "text": (
                    "ðŸ— <b>PM Stage Push</b>\n"
                    "Airtable'da qimirlamay qolgan loyihalar bo'yicha report guruhga yuborildi.\n"
                    "Bugun har bir loyiha uchun keyingi stage yoki blocker yozilsin."
                ),
                "parse_mode": "HTML",
            }
        )

    task = AgentTask(
        task_id=f"{job_key}:{today}",
        kind="pm_stage_push",
        goal="Airtabledagi qimirlamay qolgan loyihalarni keyingi stagega surish",
        payload={
            "group_id": group_id,
            "thread_id": thread_id,
            "project_count": len(stalled_projects),
            "pm_user_id": pm_user.get("user_id") if pm_user else None,
        },
        planner_notes=[
            "Stalled loyihalar manager bo'yicha guruhlanadi",
            "PM threadga status push yuboriladi",
            "Mas'ul PMga shaxsiy DM bilan next-step talab qilinadi",
        ],
        requested_by="scheduler",
    )

    async def executor(agent_task: AgentTask) -> Dict[str, Any]:
        execution = await _execute_telegram_notification(
            registry,
            group_id=group_id,
            message=message,
            thread_id=thread_id,
            direct_messages=direct_messages,
        )
        execution.update({"project_count": agent_task.payload.get("project_count")})
        return execution

    result = await _run_notification_agent(db, task, executor)
    if not result.success:
        logger.error(f"[AIRTABLE STAGNATION] Project stage push delivery failed: {result.verification}")
        return

    await db.mark_job_run(job_key, today)
    logger.info(f"[AIRTABLE STAGNATION] Project stage push sent for hour {now.hour}.")


async def check_client_journey_excellence():
    """Mijoz yo'li bo'yicha wow-service signal va mikromanagement push yuborish."""
    import src.config as config
    from src.services.core.airtable_sync import AirtableSync # type: ignore
    from src.services.core.amocrm_sync import AmoCRMSync

    db = Database()
    now = get_local_now()
    today = now.strftime("%Y-%m-%d")
    target_hours = [11, 17]

    if now.hour not in target_hours or now.minute > 10:
        return False

    job_key = f"client_journey_excellence_{now.hour}"
    if await db.is_job_run(job_key, today):
        return False

    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    group_id = (
        getattr(config, "TEAM_GROUP_ID", None)
        or getattr(config, "CRM_GROUP_ID", None)
        or getattr(config, "PROJECTS_GROUP_ID", None)
    )
    thread_id = (
        getattr(config, "TOPIC_GENERAL_ID", None)
        or getattr(config, "TOPIC_REPORTS_ID", None)
        or getattr(config, "TOPIC_TASKS_ID", None)
    )
    if not (bot_token and group_id):
        return False

    amo = AmoCRMSync(
        config.AMOCRM_SUBDOMAIN,
        config.AMOCRM_CLIENT_ID,
        config.AMOCRM_CLIENT_SECRET,
        config.AMOCRM_REDIRECT_URL,
    )
    airtable = AirtableSync()
    registry = build_default_tool_registry(bot_token=bot_token, amocrm=amo, airtable=airtable)
    amocrm_tool = registry.get("amocrm_leads")
    airtable_tool = registry.get("airtable_projects")

    leads = await amocrm_tool.fetch_leads(limit=100)
    projects = await airtable_tool.fetch_projects()
    owner_lookup: Dict[int, str] = {}
    responsible_ids = sorted(
        {
            int(lead.get("responsible_user_id") or 0)
            for lead in leads
            if int(lead.get("responsible_user_id") or 0) > 0
        }
    )
    for responsible_id in responsible_ids:
        owner_lookup[responsible_id] = await amocrm_tool.get_user_name(responsible_id)

    sales_signals = assess_sales_pipeline(
        leads,
        owner_lookup=lambda user_id: owner_lookup.get(user_id, "Sales"),
    )
    project_signals = assess_project_portfolio(projects)
    if not sales_signals and not project_signals:
        return False

    team_members = await db.get_team_roles()
    message = render_excellence_report(sales_signals, project_signals)
    direct_messages = build_department_direct_messages(team_members, sales_signals, project_signals)

    task = AgentTask(
        task_id=f"{job_key}:{today}",
        kind="client_journey_excellence",
        goal="Lead first-touchdan tortib referralgacha wow-service mikromanagementini ushlash",
        payload={
            "group_id": group_id,
            "thread_id": thread_id,
            "sales_signal_count": len(sales_signals),
            "project_signal_count": len(project_signals),
            "direct_message_count": len(direct_messages),
        },
        planner_notes=[
            "AmoCRM lidlari va Airtable loyihalari wow-service risklari bo'yicha baholanadi",
            "Jamoa guruhiga umumiy excellence report yuboriladi",
            "Sales va PM rollarga mos ravishda alohida DM mikromanagement push beriladi",
        ],
        requested_by="scheduler",
    )

    async def executor(agent_task: AgentTask) -> Dict[str, Any]:
        execution = await _execute_telegram_notification(
            registry,
            group_id=group_id,
            message=message,
            thread_id=thread_id,
            direct_messages=direct_messages,
        )
        execution.update(
            {
                "sales_signal_count": agent_task.payload.get("sales_signal_count"),
                "project_signal_count": agent_task.payload.get("project_signal_count"),
            }
        )
        return execution

    result = await _run_notification_agent(db, task, executor)
    if not result.success:
        logger.error(f"[CLIENT JOURNEY] Excellence report delivery failed: {result.verification}")
        return False

    await db.mark_job_run(job_key, today)
    logger.info(
        "[CLIENT JOURNEY] Excellence report sent. sales=%s projects=%s",
        len(sales_signals),
        len(project_signals),
    )
    return True
    
async def run_crm_offload():
    """CLI orqali AmoCRM fayllarini offload qilish."""
    import src.config as config
    from src.services.core.amocrm_sync import AmoCRMSync
    from src.services.core.gdrive import GoogleDriveSync
    from src.services.core.crm_file_offloader import CRMFileOffloader
    from src.settings import settings

    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    if not bot_token:
        logger.error("BOT_TOKEN not found.")
        return

    amo = AmoCRMSync(
        config.AMOCRM_SUBDOMAIN,
        config.AMOCRM_CLIENT_ID,
        config.AMOCRM_CLIENT_SECRET,
        config.AMOCRM_REDIRECT_URL,
    )
    gdrive = GoogleDriveSync(settings.GSHEET_CREDS_FILE)
    offloader = CRMFileOffloader(amo, gdrive)
    
    # CLI orqali chaqirilganda dry_run=False bo'lishi mumkin (manual trigger)
    await offloader.run(dry_run=False)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Proactive AI Worker")
    parser.add_argument("--job", choices=["followup", "report", "briefing", "stagnation", "deadlines", "distribute", "fact", "lunch", "journey", "offload"], default="followup", help="Kaysi vazifani bajarish kerak?")
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
    elif args.job == "lunch":
        asyncio.run(send_lunch_reminder())
    elif args.job == "journey":
        asyncio.run(check_client_journey_excellence())
    elif args.job == "offload":
        asyncio.run(run_crm_offload())
