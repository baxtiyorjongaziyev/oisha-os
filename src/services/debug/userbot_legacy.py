import os
import asyncio
import re
import json
import datetime
import logging
import time
import sys
import html
from typing import Optional, cast, Dict, Any, List
from google import genai  # type: ignore
from google.genai import types  # type: ignore
from telegram import (  # type: ignore
    Update, 
    LabeledPrice, 
    PreCheckoutQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
    MenuButtonWebApp,
)
from telegram.ext import ( # type: ignore
    Application,
    CommandHandler,
    MessageHandler,
    BusinessConnectionHandler,
    PreCheckoutQueryHandler,
    InlineQueryHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from dotenv import load_dotenv # type: ignore

# Load environment variables immediately
load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config  # type: ignore
from database import Database  # type: ignore
from gsheets import GoogleSheetsSync  # type: ignore
from gcontacts import GoogleContactsSync  # type: ignore
from gcalendar import GoogleCalendarSync  # type: ignore
from amocrm_sync import AmoCRMSync  # type: ignore
from invoicing import InvoiceGenerator  # type: ignore
import tts_engine  # type: ignore
import learning_engine  # type: ignore
from scouter import Scouter # type: ignore
from scorer import Scorer # type: ignore
from osint_explorer import OSINTExplorer # type: ignore
from task_manager import TaskManager # type: ignore
from agent_orchestrator import AgentOrchestrator # type: ignore
from cbu_api import CBUApi # type: ignore
from global_services import GlobalServices # type: ignore
from omni_services import OmniServices # type: ignore
from crm_integration import CRMIntegration # type: ignore
from opensource_hub import OpenSourceHub # type: ignore
from agentic_era import AgenticEra # type: ignore
from ai_sync_hub import AISyncHub # type: ignore
from automation_portal import AutomationBridge, AIPortal # type: ignore
from free_comm import FreeComm # type: ignore
from global_super_hub import GlobalSuperAI, GiantResourceHub # type: ignore
from singularity_core import ProactiveWorker, SelfEvolution # type: ignore
from branding_mastery import BrandingMastery, TeamIntegrator # type: ignore
from controllers.message_controller import MessageController # type: ignore


# Force type identity for engines to help linter
TTSEngine = tts_engine.TTSEngine
LearningEngine = learning_engine.LearningEngine
# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Get credentials
bot_token = os.getenv("BOT_TOKEN")

# Xavfsizlik: Bot ishga tushgan vaqt
# Bu orqali biz bot o'chganda yig'ilib qolgan eskirgan xabarlarni filtrlashimiz mumkin
BOT_START_TIME = datetime.datetime.now(datetime.timezone.utc)

gemini_key = os.getenv("GEMINI_API_KEY")

# CRM & Database init
db = Database()
gsheet = GoogleSheetsSync(config.GSHEET_ID, config.GSHEET_CREDS_FILE)
gcontacts = GoogleContactsSync(config.GSHEET_CREDS_FILE)
gcalendar = GoogleCalendarSync(config.GSHEET_CREDS_FILE)
amocrm = AmoCRMSync(
    config.AMOCRM_SUBDOMAIN,
    config.AMOCRM_CLIENT_ID,
    config.AMOCRM_CLIENT_SECRET,
    config.AMOCRM_REDIRECT_URL
)
invoicer = InvoiceGenerator()
tts = TTSEngine(voice="uz-UZ-MadinaNeural") # Qiz bola ovozi (Madina)
# AI API Keys collection
api_keys = {
    "gemini": gemini_key,
    "groq": os.getenv("GROQ_API_KEY", ""),
    "hf": os.getenv("HF_API_TOKEN", "")
}

tts = TTSEngine(voice="uz-UZ-MadinaNeural") # Qiz bola ovozi (Madina)
learner = LearningEngine(api_keys, db)
scouter = Scouter() 
scorer = Scorer()
osint = OSINTExplorer()
task_mgr = TaskManager(db)
# MessageController barcha agentlar va orkestratorni o'z ichiga oladi
msg_controller = MessageController(api_keys, db=db)

# Validate required env vars
if not bot_token:
    raise ValueError("[ERROR] BOT_TOKEN topilmadi! .env faylni tekshiring.")

# AI Session Storage (per user context)
sessions: dict = {}

# Business connections storage
business_connections: Dict[str, Any] = {}

# Security: Rate limiting storage
last_activity: Dict[int, float] = {}

# Rejimlar: Silent mode va xabarnomalar uchun global o'zgaruvchilar
silent_mode: Dict[int, float] = {}
last_conflict_notify: float = 0.0

# Configure AI
ai_client = None
training_data_text = ""

if config.ENABLE_AI and gemini_key:
    try:
        ai_client = genai.Client(api_key=gemini_key)
        logger.info(f"[OK] AI model yuklandi: gemini-2.0-flash")

        # Digital Twin: Training data yuklash
        if os.path.exists("training_data.txt"):
            logger.info("Training data topildi. Matn sifatida o'qilmoqda...")
            try:
                with open("training_data.txt", "r", encoding="utf-8") as f:
                    training_data_text = f.read()
                logger.info(f"[OK] Knowledge Base yuklandi ({len(training_data_text)} belgi)")
            except Exception as e:
                logger.error(f"[ERROR] Knowledge Base o'qishda xato: {e}")
        else:
            logger.info("Training data ('training_data.txt') topilmadi. Oddiy rejimda ishlaydi.")

    except Exception as e:
        logger.error(f"AI ulanishda xato: {e}")
else:
    logger.warning("[WARN] AI o'chirilgan yoki API key yo'q")

AI_MODEL = "gemini-2.0-flash"


def is_working_hour() -> bool:
    """Ish vaqtida ekanligini tekshirish."""
    start = config.WORKING_HOURS.get("start")
    end = config.WORKING_HOURS.get("end")
    if start is None or end is None:
        return True
    hour = datetime.datetime.now().hour
    if start <= end:
        return start <= hour < end
    else:
        return hour >= start or hour < end


def clean_html(text: str) -> str:
    """Telegram qo'llab-quvvatlaydigan HTML taglarini qoldirib, qolganlarini tozalash."""
    # 0. Eng avval ```html yoki ``` ko'rinishidagi blocklarni tozalash
    text = re.sub(r'```(?:html)?\n?(.*?)\n?```', r'\1', text, flags=re.DOTALL)
    
    # 1. "HTML formatida..." yoki "HTML:" kabi AI meta-matnlarini tozalash (agarda instruksiya buzilsa)
    text = re.sub(r'^(?:Mana|HTML formatida|HTML:|HTML|Sizga|Javob:).*?javob:?\s*\n*', '', text, flags=re.IGNORECASE | re.MULTILINE)
    
    # Qo'shimcha: Agar matn faqat "HTML" bilan boshlansa (label bo'lib kelsa)
    text = re.sub(r'^HTML\s*\n*', '', text, flags=re.IGNORECASE)
    
    # MARKDOWN to HTML (Telegram display fix)
    # Qalin matnlar: **matn** -> <b>matn</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Qiya matnlar (ixtiyoriy, agar muammo bo'lsa): *matn* -> <i>matn</i> (Faqatgina ro'yxat bo'lmaganda)
    # text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    
    # AI ba'zan "Aisha/Oisha bilan suhbat\n\n" deb boshlaydi — uni o'chirish
    text = re.sub(r'^(?:Aisha|Oisha) bilan suhbat\s*\n*', '', text, flags=re.IGNORECASE)
    
    # Telegram ruxsat bergan taglar ro'yxati
    allowed_tags = ['b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del', 'a', 'code', 'pre']
    
    def replace_tag(match):
        tag_full = match.group(0)
        tag_name_match = re.match(r'</?([a-zA-Z1-6]+)', tag_full)
        if tag_name_match:
            tag_name = tag_name_match.group(1).lower()
            if tag_name in allowed_tags:
                return tag_full
        return ""

    # Barcha <...> ko'rinishidagi taglarni tekshirib, ruxsat berilmaganlarini o'chirish
    cleaned_text = re.sub(r'<[^>]+>', replace_tag, text)
    return cleaned_text.strip()

async def forward_to_crm(context: ContextTypes.DEFAULT_TYPE, user_info: dict, message_text: str, reply_text: Optional[str] = None, quality: str = "Unknown"):
    """Mijoz xabarini va bot javobini CRM guruhiga yuborish."""
    if not config.CRM_GROUP_ID:
        return
        
    try:
        username = user_info.get('username') or "yo'q"
        crm_msg = (
            f"🎯 <b>YANGI PREMIUM LEAD</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Mijoz:</b> {user_info.get('name')} (@{username})\n"
            f"🆔 <b>ID:</b> <code>{user_info.get('id')}</code>\n"
            f"📞 <b>Telefon:</b> {user_info.get('phone', '—')}\n"
            f"💎 <b>Sifati:</b> #{quality}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💬 <b>Oxirgi so'rovi:</b>\n<i>{message_text}</i>\n"
        )
        if reply_text:
            crm_msg += f"\n🤖 <b>AI Javobi:</b>\n<i>{reply_text}</i>"
            
        # Mavzuni tekshirish (Support for Forum Topics)
        thread_id = getattr(config, 'CRM_TOPIC_ID', None)
        
        await context.bot.send_message(
            chat_id=config.CRM_GROUP_ID,
            text=crm_msg,
            parse_mode="HTML",
            message_thread_id=thread_id
        )
    except Exception as e:
        logger.error(f"[CRM ERROR] Guruhga yuborishda xato: {e}")

async def get_reply(sender_id: int, sender_name: str, message_text: str, image_data: Optional[bytes] = None, video_data: Optional[bytes] = None, audio_data: Optional[bytes] = None, username: Optional[str] = None, phone: Optional[str] = None, image_mime: str = 'image/jpeg') -> str:
    """Xabarga javob tayyorlash: CRM logging, keyword yoki AI (Multimodal Image/Video/Audio)."""
    # 0. CRM Update
    asyncio.create_task(asyncio.to_thread(db.upsert_user, sender_id, sender_name, username, phone=phone))
    asyncio.create_task(asyncio.to_thread(gsheet.sync_user, sender_id, sender_name, username, phone=phone))

    # 1. Whitelist
    if sender_id in config.WHITELIST_IDS:
        logger.info(f"[SKIP] Whitelist: {sender_name}")
        return ""

    # 2. Working hours
    # 3. Keyword match (faqat matn bo'lsa)
    if message_text:
        lower_text = message_text.lower()
        for keyword, response in config.KEYWORDS.items():
            if keyword in lower_text:
                logger.info(f"[KEYWORD] Topildi: {keyword}")
                return response

    # 4. AI reply (Yangi modulli Controller orqali)
    if ai_client:
        try:
            reply_text = await msg_controller.get_response(sender_id, sender_name, message_text)
            
            # Teglarni tozalash (Bot display fix)
            reply_text = clean_html(reply_text)
            
            # DB logging
            asyncio.create_task(asyncio.to_thread(db.log_message, sender_id, reply_text, is_ai=True))
            return reply_text
        except Exception as e:
            logger.error(f"[AI CONTROLLER ERROR] {e}")
            return config.DEFAULT_MESSAGE

    return config.DEFAULT_MESSAGE


# ==================== HANDLERS ====================

async def analyze_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """2025-yildan beri bo'lgan barcha shaxsiy suhbatlarni tahlil qilish (Owner only)."""
    if str(update.effective_user.id) != str(config.OWNER_ID):
        return

    await update.message.reply_text("🕵️‍♂️ 2025-yildan beri bo'lgan barcha shaxsiy suhbatlarni tahlil qilish boshlandi. Bu jarayon bir oz vaqt olishi mumkin...")
    
    async def run_deep_learning():
        try:
            # Scouter bog'langanini tekshirish
            connected = await scouter.connect()
            if not connected:
                logger.error("[LEARN] Scouter connect failed.")
                return

            start_date = datetime.datetime(2025, 1, 1)
            logger.info(f"[LEARN] Start scanning from {start_date}...")
            
            processed_count = 0
            async for dialog in scouter.client.iter_dialogs():
                if not dialog.is_user: continue
                
                user_id = dialog.id
                user_name = dialog.name
                
                chat_context = []
                # Oxirgi 100 ta xabarni olish (sharoitga qarab limitni o'zgartirish mumkin)
                async for msg in scouter.client.iter_messages(dialog.id, limit=100):
                    if msg.date.replace(tzinfo=None) < start_date:
                        break
                    
                    role = "user" if msg.out else "client"
                    sender_name = "Baxtiyorjon" if msg.out else user_name
                    chat_context.append(f"{sender_name}: {msg.text}")
                
                if chat_context:
                    chat_context.reverse()
                    context_str = "\n".join(chat_context)
                    
                    logger.info(f"[LEARN] Analyzing chat with {user_name} ({user_id})...")
                    # LearningEngine orqali o'rganish
                    await learner.analyze_and_learn(user_id, context_str)
                    processed_count += 1
                    
                    # Telegram serverlariga yuklama tushmasligi uchun tanaffus
                    await asyncio.sleep(2)
            
            logger.info(f"[LEARN DONE] {processed_count} ta chat tahlil qilindi.")
            await context.bot.send_message(chat_id=config.OWNER_ID, text=f"✅ <b>Tarixiy tahlil yakunlandi!</b>\n{processed_count} ta shaxsiy suhbat o'rganib chiqildi. Bot endi sizning uslubingizni yaxshiroq biladi.", parse_mode="HTML")
            
        except Exception as e:
            logger.error(f"[LEARN CRITICAL] {e}")

    # Backgroundda ishga tushirish
    asyncio.create_task(run_deep_learning())

async def post_init(application: Application) -> None:
    """Bot ishga tushganda Menu Button-ni bir marta va aniq sozlash."""
    try:
        await application.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Portfolio 🎨",
                web_app=WebAppInfo(url=config.WEBAPP_URL)
            )
        )
        logger.info("[BOT] Menu button successfully set in post_init.")
    except Exception as e:
        logger.error(f"[BOT] Failed to set menu button: {e}")
    
    # [FIX] Proactive Worker ni loop boshlanganidan keyin ishga tushirish
    try:
        logger.info("Setting up Proactive Worker in post_init...")
        worker = ProactiveWorker()
        asyncio.create_task(worker.start_loop())
        logger.info("[OK] Proactive Worker task created.")
    except Exception as we:
        logger.error(f"[WORKER ERROR] post_init da worker boshlashda xato: {we}")

async def portfolio_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Portfolio Mini App-ni yuborish."""
    keyboard = [[
        InlineKeyboardButton(
            "Portfelni ochish 🎨", 
            web_app=WebAppInfo(url=config.PORTFOLIO_URL)
        )
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Mening ijodiy ishlarim bilan tanishish uchun pastdagi tugmani bosing:",
        reply_markup=reply_markup
    )

async def branding_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Branding haqida ma'lumot."""
    if update.effective_user.id != config.OWNER_ID:
        return
    await update.message.reply_text(" Branding bo'limi tez orada ishga tushadi.")

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Botning holatini tekshirish uchun."""
    await update.message.reply_text("🏓 Pong! Bot ishlamoqda. \nHolat: ✅ Aktiv")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command with a premium Aisha welcome."""
    await update.message.reply_text(
        "Va alaykum assalom! 🌟\n\n"
        "Yaxshimisiz? Sizni ko'rib turganimdan juda xursandman. "
        "Men <b>Oishaman</b> — Baxtiyorjon Gaziyevning sun'iy intellektli yordamchisi.\n\n"
        "Sizga brending, logotip dizayni yoki biznesingiz vizual qiyofasini yaratishda yordam beraman. "
        "Siz bilan yaqindan tanishishni juda xohlayman. Ayting-chi, <b>ismingiz nima?</b> 😊\n\n"
        "📌 <i>Buyruqlar:</i>\n"
        "/start - Botni ishga tushirish\n"
        "/register [rol] - Jamoa a'zosi sifatida ro'yxatdan o'tish\n"
        "/invoice - Invoys yaratish\n"
        "/portfolio — Ishlarimizni ko'rish\n"
        "/status — Bot holati",
        parse_mode="HTML"
    )


async def task_conf_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Avtonom aniqlangan topshiriqlarni tasdiqlash."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data == "task_ignore":
        await query.edit_message_text("❌ Topshiriq rad etildi.")
        return
    
    if data.startswith("task_conf:"):
        # Format: task_conf:title|who
        payload = data.replace("task_conf:", "")
        if "|" in payload:
            title, who = payload.split("|", 1)
            # Bazaga qo'shish
            task_id = db.add_task(assigned_to=who, description=title, deadline="Tez orada")
            if task_id:
                await query.edit_message_text(
                    f"✅ <b>TPSHIRIQ TASDIQLANDI</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📝 <b>Vazifa:</b> {title}\n"
                    f"👤 <b>Mas'ul:</b> {who}\n"
                    f"🆔 <b>Task ID:</b> {task_id}\n\n"
                    f"Jamoaga xabar berildi.",
                    parse_mode="HTML"
                )
                logger.info(f"[PROACTIVE OK] Autonomous task confirmed: {title}")
            else:
                await query.edit_message_text("❌ Xatolik: Vazifani bazaga saqlab bo'lmadi.")


async def strat_conf_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Strategik takliflarni tasdiqlash va ijro etish."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data == "strat_ignore":
        await query.edit_message_text("❌ Strategik taklif rad etildi.")
        return
    
    if data.startswith("strat_conf:"):
        # Format: strat_conf:action|target
        payload = data.replace("strat_conf:", "")
        if "|" in payload:
            parts = payload.split("|")
            action = parts[0]
            target = parts[1] if len(parts) > 1 else "Unknown"
            
            if action == "recruit":
                await query.edit_message_text(f"📢 <b>RECRUITER ON:</b> '{target}' uchun vakansiya matni tayyorlandi va kanallarga yuborishga shay.", parse_mode="HTML")
            elif action == "ai_agent":
                 await query.edit_message_text(f"🤖 <b>AI AGENT ON:</b> '{target}' vazifasini bajaruvchi yangi AI Agent prototipi yaratilmoqda.", parse_mode="HTML")
            elif action == "assign":
                # Vazifa sifatida qo'shish
                task_id = db.add_task(assigned_to=target, description=f"STRATEGIC: {target} uchun yangi vazifa", deadline="7 kun")
                await query.edit_message_text(f"✅ <b>STRATEGIYA TASDIQLANDI:</b> Vazifa {target} ga biriktirildi. (ID: {task_id})", parse_mode="HTML")
            elif action == "assign_checklist":
                # Message textidan checklist elementlarini ajratib olish
                msg_text = query.message.text or ""
                items = []
                if "📋 Checklist:" in msg_text:
                    items_part = msg_text.split("📋 Checklist:")[1].strip()
                    items = [i.strip("- ").strip() for i in items_part.split("\n") if i.strip()]
                
                if not items:
                    items = ["1-bosqich: Tahlil", "2-bosqich: Amal", "3-bosqich: Hisobot"] # Fallback

                # Telegram Poll (Checklist) yuborish
                await context.bot.send_poll(
                    chat_id=query.message.chat_id,
                    question=f"📋 TOPSHIRIQ: {target}",
                    options=items[:10], # Maksimal 10 ta
                    is_anonymous=False,
                    allows_multiple_answers=True,
                    type="regular" # "quiz" emas
                )
                await query.edit_message_text(f"✅ <b>STRATEGIK CHECKLIST YUBORILDI!</b>\nNishon: {target}", parse_mode="HTML")
            
            logger.info(f"[PROACTIVE OK] Strategic action confirmed: {action} for {target}")

    elif data.startswith("lead_save:"):
        # Format: lead_save:username|name
        payload = data.replace("lead_save:", "")
        if "|" in payload:
            username, name = payload.split("|", 1)
            # Google Contacts-ga qo'shish
            from singularity_core import gcontacts # Import inside to avoid circular or use shared
            success = gcontacts.create_contact(first_name=name, note=f"Telegram: @{username}. Added via Oisha AI.")
            
            if success:
                await query.edit_message_text(f"✅ <b>KONTAKT SAQLANDI!</b>\n{name} Google Contacts ro'yxatiga qo'shildi.")
            else:
                await query.edit_message_text("❌ Google Contacts ulanishida xatolik bo'ldi.")



async def register_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Jamoa a'zosini ro'yxatdan o'tkazish (e.g. /register owner)."""
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❌ Iltimos, rolni ko'rsating.\nMasalan: `/register owner`", parse_mode="Markdown")
        return

    role = context.args[0].lower()
    
    # Faqat haqiqiy owner o'zini owner qilib ro'yxatdan o'tkaza oladi
    if role == "owner" and user_id != config.OWNER_ID:
        await update.message.reply_text("❌ Siz bot egasi emassiz.")
        return

    success = db.set_user_role(user_id, role)
    if success:
        await update.message.reply_text(f"✅ Siz muvaffaqiyatli **{role}** sifatida ro'yxatdan o'tdingiz!", parse_mode="Markdown")
        logger.info(f"[HR] User {user_id} registered as {role}")
    else:
        # Agar user bazada bo'lmasa, avval upsert qilamiz
        db.upsert_user(user_id, update.effective_user.first_name, update.effective_user.username)
        if db.set_user_role(user_id, role):
             await update.message.reply_text(f"✅ Siz muvaffaqiyatli **{role}** sifatida ro'yxatdan o'tdingiz!", parse_mode="Markdown")
        else:
             await update.message.reply_text("❌ Ro'yxatdan o'tishda xatolik yuz berdi.")

async def unregister_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Rolni o'chirish."""
    user_id = update.effective_user.id
    if db.set_user_role(user_id, None):
        await update.message.reply_text("✅ Sizning rolingiz muvaffaqiyatli o'chirildi.")
    else:
        await update.message.reply_text("❌ Rolni o'chirishda xatolik.")


async def amofix_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /amofix command to set initial AmoCRM code."""
    if update.effective_user.id != config.OWNER_ID:
        return

    if not context.args:
        await update.message.reply_text("❌ Iltimos, AmoCRM kodini yuboring.\nFormat: `/amofix KOD`", parse_mode="Markdown")
        return

    # Safely get the auth code from args
    args = context.args
    auth_code = str(args[0])
    await update.message.reply_text("⏳ AmoCRM avtorizatsiya qilinmoqda...")
    
    success = amocrm.authorize_initial(auth_code)
    if success:
        await update.message.reply_text("✅ AmoCRM muvaffaqiyatli ulandi! Endi leadlar avtomatik yuboriladi.")
    else:
        await update.message.reply_text("❌ Avtorizatsiyada xato! Kod eskirgan yoki xato bo'lishi mumkin. Iltimos, yangi kod olib qayta urinib ko'ring.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    keywords_list = "\n".join(
        [f"  • {k}" for k in config.KEYWORDS.keys()]
    )
    await update.message.reply_text(
        "🤖 Bot haqida:\n\n"
        "Bu bot sizning biznes chatlaringizda avtomatik javob beradi.\n\n"
        f"📝 Kalit so'zlar:\n{keywords_list}\n\n"
        "🕐 Ish vaqti: "
        f"{config.WORKING_HOURS.get('start', '—')}:00 — "
        f"{config.WORKING_HOURS.get('end', '—')}:00",
        parse_mode="HTML"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command."""
    ai_status = "✅ Yoniq" if ai_client else "❌ O'chiq"
    connections_count = len(business_connections)
    sessions_count = len(sessions)
    stats = db.get_stats()

    await update.message.reply_text(
        "📊 Bot holati:\n\n"
        f"🤖 AI: {ai_status}\n"
        f"🔗 Business ulanishlar: {connections_count}\n"
        f"💬 Faol sessiyalar: {sessions_count}\n"
        f"👥 Umumiy mijozlar: {stats['total_users']}\n"
        f"📑 Jami xabarlar: {stats['total_messages']}\n"
        f"🕐 Ish vaqti: "
        f"{config.WORKING_HOURS.get('start', '—')}:00 — "
        f"{config.WORKING_HOURS.get('end', '—')}:00",
        parse_mode="HTML"
    )


async def task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /task command with Smart AI Parsing."""
    user_id = update.effective_user.id
    if not db.is_team_member(user_id) and user_id not in config.WHITELIST_IDS:
        await update.message.reply_text("❌ Kechirasiz, ushbu funksiya faqat jamoa a'zolari uchun.")
        return

    if not context.args:
        await update.message.reply_text("❌ Foydalanish: `/task [vazifa tafsiloti]`\nMasalan: `/task Ertaga Baxtiyor akaga loyiha hisobotini topshirish`", parse_mode="Markdown")
        return

    raw_text = " ".join(context.args)
    
    # 🎯 Smart Parsing via Gemini
    query = (
        "Siz Oisha ismli aqlli yordamchisiz. Quyidagi matndan topshiriq tafsilotlarini ajratib oling:\n"
        f"Matn: {raw_text}\n\n"
        "Qoidalar:\n"
        "1. 'who' - vazifa kimga topshirilgani (masalan: @username, 'Oydin', 'Ruslan'). Agar matnda aniq ism/mention bo'lmasa, 'O'zi' deb yozing.\n"
        "2. 'task' - vazifaning mazmuni. 'Xodim' yoki 'Muddat' so'zlarini vazifa ichiga qo'shib yubormang.\n"
        "3. 'deadline' - muddat. Agar ko'rsatilmagan bo'lsa, 'Bugun' yoki 'Tez orada' deb yozing.\n"
        "4. Matndagi birinchi so'zlarni shunchaki 'who' ga yopishtirmang!\n\n"
        "Javobni FAQAT JSON formatida qaytaring:\n"
        "{\"who\": \"string\", \"task\": \"string\", \"deadline\": \"string\"}"
    )

    try:
        from google import genai
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=query,
            config={'response_mime_type': 'application/json'}
        )
        import json
        data = json.loads(response.text)
        
        who = data.get("who", "Belgilanmagan")
        task_desc = data.get("task", raw_text)
        deadline = data.get("deadline", "Belgilanmagan")

        # Bazaga qo'shish
        task_id = db.add_task(assigned_to=who, description=task_desc, deadline=deadline)
        
        # Forward to Tasks topic if configured
        target_chat = update.effective_chat.id
        thread_id = getattr(config, 'TOPIC_TASKS_ID', None) or update.message.message_thread_id
        
        await context.bot.send_message(
            chat_id=target_chat,
            text=(
                f"📌 <b>YANGI VAZIFA [#{task_id}]</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>Mas'ul:</b> {who}\n"
                f"📅 <b>Muddat:</b> {deadline}\n"
                f"📝 <b>Vazifa:</b> {task_desc}\n\n"
                "Vazifa ro'yxatga olindi va nazoratga qo'yildi. ✅"
            ),
            parse_mode="HTML",
            message_thread_id=thread_id
        )
        logger.info(f"[TASK] New task created via command: {task_id}")

    except Exception as e:
        logger.error(f"[TASK ERROR] Parsing error: {e}")
        # Fallback to simple add
        task_id = db.add_task(assigned_to="Unknown", description=raw_text, deadline="Surtilishi kerak")
        await update.message.reply_text(f"✅ Vazifa saqlandi (ID: {task_id}), lekin tahlilda xatolik bo'ldi.")
        logger.info(f"[TASK] New task created via fallback: {task_id}")

async def topic_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the current message_thread_id for topic discovery."""
    thread_id = update.message.message_thread_id
    chat_id = update.message.chat_id
    
    await update.message.reply_text(
        f"📊 <b>MAVZU MA'LUMOTLARI:</b>\n\n"
        f"🆔 <b>Chat ID:</b> <code>{chat_id}</code>\n"
        f"🧵 <b>Topic ID (Thread):</b> <code>{thread_id if thread_id else 'General (Asosiy)'}</code>\n\n"
        "Ushbu ID ni <code>.env</code> faylida mos topic uchun sozlab qo'ying.",
        parse_mode="HTML"
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Administrator uchun statistika."""
    sender_id = update.effective_user.id
    # Faqat whitelistdagilarga ruxsat (owner)
    if sender_id not in config.WHITELIST_IDS:
        return
        
    stats = db.get_stats()
    task_stats = db.get_task_completion_stats(days=7)
    
    task_report = "\n".join([f"📊 {s['username']}: {s['completed']}/{s['total']}" for s in task_stats])

    await update.message.reply_text(
        "📈 <b>AGENTLIK STATISTIKASI (Haftalik)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Foydalanuvchilar: {stats['total_users']}\n"
        f"📨 Xabarlar: {stats['total_messages']}\n\n"
        f"✅ <b>Vazifalar ijrosi:</b>\n{task_report}",
        parse_mode="HTML"
    )


async def pay_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """To'lov invoice yuborish (namuna)."""
    if not config.PROVIDER_TOKEN:
        await update.message.reply_text(
            "⚠️ <b>To'lov tizimi ulanmagan.</b>\n"
            "Iltimos, BotFather dan token oling va configga qo'shing.",
            parse_mode="HTML"
        )
        return

    chat_id = update.message.chat_id
    title = "Xizmat to'lovi"
    description = "Biznes bot xizmatlaridan foydalanish uchun to'lov (Namuna)"
    payload = "bot-service-payment"
    currency = "UZS"
    price = 5000000  # 50,000 UZS (Telegramda tiyinlarda: 50000 * 100)
    prices = [LabeledPrice("Premium Xizmat", price)]

    await context.bot.send_invoice(
        chat_id, title, description, payload, config.PROVIDER_TOKEN, currency, prices
    )


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """To'lovdan oldin tekshirish."""
    query = update.pre_checkout_query
    await query.answer(ok=True)


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """To'lov muvaffaqiyatli o'tganda."""
    payment = update.message.successful_payment
    user_id = update.effective_user.id
    payload = payment.invoice_payload
    
    if payload.startswith("stars_pay_"):
        product_id = payload.replace("stars_pay_", "")
        db.complete_purchase(user_id, product_id)
        
        # Mahsulot ma'lumotlari
        p_info = config.DIGITAL_PRODUCTS.get(product_id, {})
        product_title = p_info.get("title", "Mahsulot")
        price = p_info.get("price", 0)
        
        # 🧾 Hisob-faktura yaratish
        try:
            invoice_path = invoicer.generate_invoice(
                user_name=update.effective_user.first_name,
                product_name=product_title,
                price_stars=price,
                purchase_id=product_id
            )
            
            # PDF yuborish
            with open(invoice_path, "rb") as pdf_file:
                await update.message.reply_document(
                    document=pdf_file,
                    caption=f"✅ **To'lov tasdiqlandi!**\n\nSizning '{product_title}' uchun hisob-fakturangiz biriktirildi. Rahmat!",
                    parse_mode="HTML"
                )
        except Exception as ie:
            logger.error(f"[INVOICE ERROR] {ie}")
            await update.message.reply_text(
                f"<b>Tabriklaymiz! ✨</b>\n\n"
                f"Siz '{product_title}' mahsulotini muvaffaqiyatli sotib oldingiz.\n"
                f"Tez orada Baxtiyorjon siz bilan bog'lanib, kerakli materiallarni yuboradi.",
                parse_mode="HTML"
            )
        
        logger.info(f"[STARS OK] Purchase completed & Invoice sent for {user_id}: {product_id}")
    elif payload.startswith("invoice_pay_"):
        amount_uzs = payment.total_amount // 100
        invoice_id = payload.replace("invoice_pay_", "")
        
        # Mijozga rahmatnomani yuborish
        await update.message.reply_text(
            f"✅ <b>To'lov tasdiqlandi!</b>\n\n"
            f"Sizning <b>{amount_uzs:,} UZS</b> miqdoridagi to'lovingiz qabul qilindi.\n"
            f"Tez orada mutaxassislarimiz ishga kirishadi. Rahmat!",
            parse_mode="HTML"
        )
        
        # CRM Guruhni xabardor qilish
        if config.CRM_GROUP_ID:
            crm_payment_msg = (
                f"💰 <b>YANGI TO'LOV QABUL QILINDI!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>Mijoz:</b> {update.effective_user.first_name}\n"
                f"💵 <b>Summa:</b> {amount_uzs:,} UZS\n"
                f"🏷 <b>To'lov ID:</b> #{invoice_id}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<i>(To'lov Click/Payme orqali muvaffaqiyatli o'tdi)</i>"
            )
            asyncio.create_task(context.bot.send_message(chat_id=config.CRM_GROUP_ID, text=crm_payment_msg, parse_mode="HTML"))
            
        logger.info(f"[PAYMENT OK] {user_id} dan {amount_uzs} UZS qabul qilindi.")
    else:
        await update.message.reply_text("Rahmat! To'lov muvaffaqiyatli qabul qilindi. ✅")


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Administrator barcha foydalanuvchilarga xabar yuborishi uchun."""
    sender_id = update.effective_user.id
    if sender_id not in config.WHITELIST_IDS:
        return
        
    if not context.args:
        await update.message.reply_text("Xabar matnini kiriting: /broadcast [matn]", parse_mode="HTML")
        return
        
    broadcast_text = " ".join(context.args)
    users = db.get_all_users()
    
    count = 0
    status_msg = await update.message.reply_text(f"🚀 {len(users)} ta foydalanuvchiga xabar yuborish boshlandi...")
    
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=broadcast_text, parse_mode="HTML")
            count += 1
            await asyncio.sleep(0.05) # Telegram cheklovlari uchun
        except Exception:
            continue
            
    await status_msg.edit_text(f"✅ Xabar {count} ta foydalanuvchiga muvaffaqiyatli yetkazildi.")


async def task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xodimlarga vazifa berish. Format: /task @username YYYY-MM-DD Vazifa matni"""
    sender_id = update.effective_user.id
    if sender_id not in config.WHITELIST_IDS and sender_id != config.OWNER_ID:
        return

    args = context.args
    if not args or len(args) < 3:
        await update.message.reply_text("Namuna: /task @xodim_username 2026-12-31 Logotip chizish")
        return

    assigned_to = args[0]
    deadline = args[1]
    description = " ".join(args[2:])

    task_id = db.add_task(assigned_to, description, deadline)
    if task_id:
        msg = f"📌 <b>YANGI VAZIFA [#{task_id}]</b>\n<b>Xodim:</b> {assigned_to}\n<b>Muddat:</b> {deadline}\n<b>Vazifa:</b> {description}"
        await update.message.reply_text(msg, parse_mode="HTML")
    else:
        await update.message.reply_text("❌ Vazifani saqlashda xatolik yuz berdi.")

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xodimlar vazifani tugatganda. Format: /done [task_id]"""
    if not context.args:
        await update.message.reply_text("Namuna: /done 12")
        return

    try:
        task_id = int(context.args[0])
        success = db.complete_task(task_id)
        if success:
            await update.message.reply_text(f"✅ <b>[#{task_id}] vazifa BAJARILDI deb belgilandi!</b> Rahmat.", parse_mode="HTML")
        else:
            await update.message.reply_text("❌ Bunday vazifa topilmadi yoki allaqachon bajarilgan.", parse_mode="HTML")
    except ValueError:
        await update.message.reply_text("Task ID raqam bo'lishi kerak. Namuna: /done 12")


async def branding_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """AI orqali branding materiallari yaratish."""
    sender_id = update.effective_user.id
    if sender_id != config.OWNER_ID:
        return

    if not context.args:
        await update.message.reply_text(
            "🎨 **Branding Generator**\n\n"
            "Iltimos, yaratmoqchi bo'lgan narsangizni tavsiflang:\n"
            "`/branding [tavsif]`\n\n"
            "Masalan: `/branding vintage logo for coffee shop`",
            parse_mode="HTML"
        )
        return

    prompt = " ".join(context.args)
    status_msg = await update.message.reply_text("⏳ **AI tasvir yaratmoqda...** Iltimos, kuting.")
    
    if not ai_client:
        await status_msg.edit_text("⚠️ **AI tizimi ulanmagan.** Iltimos, administratorga murojaat qiling.")
        return

    try:
        # Correct SDK call: client.models.generate_image
        # Note: In some versions it's generate_images or requires specific model name
        logger.info(f"[BRANDING] Tasvir yaratilmoqda: {prompt}")
        
        response = ai_client.models.generate_image(
            model="imagen-3.0-generate-001",
            prompt=prompt,
            config=types.GenerateImageConfig(
                number_of_images=1,
                include_rai_reason=True,
                output_mime_type="image/jpeg"
            )
        )
        
        if response.generated_images:
            image_bytes = response.generated_images[0].image.image_bytes
            await update.message.reply_photo(
                photo=image_bytes,
                caption=f"🎨 **Branding Generator**\n\nTavsif: _{prompt}_",
                parse_mode="HTML"
            )
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ Tasvir yaratib bo'lmadi (Unknown sabab).")
            
    except Exception as e:
        logger.error(f"[BRANDING ERROR] {e}")
        # Secondary attempt with generic model name if specific fails
        try:
             response = ai_client.models.generate_image(
                model="imagen-3",
                prompt=prompt,
                config=types.GenerateImageConfig(
                    number_of_images=1,
                    output_mime_type="image/jpeg"
                )
            )
             if response.generated_images:
                image_bytes = response.generated_images[0].image.image_bytes
                await update.message.reply_photo(
                    photo=image_bytes,
                    caption=f"🎨 **Branding Generator** (Fallback)\n\nTavsif: _{prompt}_",
                    parse_mode="HTML"
                )
                await status_msg.delete()
                return
        except: pass
        await status_msg.edit_text(f"❌ Tasvir yaratishda xato: {e}")


async def handle_business_connection(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Biznes akkaunt ulanganda yoki uzilganda chaqiriladi."""
    conn = update.business_connection
    user = conn.user
    conn_id = conn.id

    if conn.is_enabled:
        # can_reply attribute nomi ba'zan can_reply_to bo'lishi mumkin (versiya bog'liqligi)
        can_reply_val = getattr(conn, 'can_reply', getattr(conn, 'can_reply_to', False))
        business_connections[conn_id] = {
            "user_id": user.id,
            "user_name": user.first_name,
            "can_reply": can_reply_val,
        }
        logger.info(
            f"[BUSINESS] Yangi ulanish: {user.first_name} (ID: {user.id}), "
            f"connection_id: {conn_id}, can_reply: {can_reply_val}"
        )
        # Biznes egasiga xabar
        if conn.user_chat_id:
            try:
                ai_label = "Yoniq" if ai_client else "O'chiq"
                wh_start = config.WORKING_HOURS.get("start", "—")
                wh_end = config.WORKING_HOURS.get("end", "—")
                
                keyboard = [[
                    InlineKeyboardButton(
                        "Portfelni ko'rish 🎨", 
                        web_app=WebAppInfo(url=config.WEBAPP_URL)
                    )
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await context.bot.send_message(
                    chat_id=conn.user_chat_id,
                    text=(
                        f"✨ <b>Premium Business Assistant Faollashdi</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"Sizning shaxsiy yordamchingiz mijozlar bilan muloqotga tayyor.\n\n"
                        f"🤖 <b>AI Holati:</b> {ai_label}\n"
                        f"🕐 <b>Ish vaqti:</b> {wh_start}:00 — {wh_end}:00\n\n"
                        f"💡 <i>Mijozlar bilan sifatli muloqot va leadlar uchun barcha tizimlar shay!</i>"
                    ),
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"[BUSINESS] Xabar yuborishda xato: {e}")
    else:
        business_connections.pop(conn_id, None)
        logger.info(
            f"[BUSINESS] Ulanish uzildi: {user.first_name} (ID: {user.id})"
        )


async def process_message_logic(update: Update, context: ContextTypes.DEFAULT_TYPE, is_business: bool = False) -> None:
    """Xabarlarni qayta ishlashning umumiy mantiqi (Matn + Multimodal)."""
    # Security: Restricted Commands Filter
    if update.message and update.message.text:
        text = update.message.text
        if text.startswith("/") and update.effective_user.id != config.OWNER_ID:
            # Check if it's a sensitive management command
            sensitive_cmds = ["/broadcast", "/amofix", "/branding", "/stats", "/status"]
            if any(text.startswith(cmd) for cmd in sensitive_cmds):
                logger.warning(f"[SECURITY] Unauthorized access attempt by {update.effective_user.id}")
                return

    msg = update.business_message if is_business else update.message
    if not msg:
        return
        
    # NEW: Eski (qolib ketgan/ochilmagan) xabarlarni e'tiborsiz qoldirish
    # Agar xabar 24 soatdan (86400 soniya) eskirgan bo'lsa, javob berilmaydi
    # Yoki bot ishga tushgan vaqtdan juda uzoq bo'lsa.
    if msg.date:
        msg_date = msg.date
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        if (now_utc - msg_date).total_seconds() > 86400:
            # logger.info("[SKIP] Eski xabar e'tiborsiz qoldirildi.")
            return
    
    # NEW: Skip messages from the CRM Group
    if str(msg.chat.id) == str(config.CRM_GROUP_ID):
        # logger.info(f"[SKIP] Message from CRM Group ({msg.chat.id}) ignored.")
        return
    
    # Security: Rate Limiting (Flood Protection)
    user_id = update.effective_user.id
    now = time.time()
    
    # Store last activity in a simple dict
    global last_activity
    if 'last_activity' not in globals():
        last_activity = {}
        
    last_user_time = last_activity.get(user_id, 0)
    if now - last_user_time < 0.5: # 0.5 soniyadan tez xabar yuborsa
        logger.warning(f"[SECURITY] Rate limit triggered by {user_id}")
        return
    last_activity[user_id] = now

    # Bot o'zi yuborgan xabarlarni skip qilish
    if msg.from_user and msg.from_user.is_bot:
        return

    sender = msg.from_user
    if not sender:
        return

    sender_id = sender.id
    sender_name = sender.first_name or "User"
    username = sender.username
    text = msg.text or msg.caption or ""
    
    # 🧠 UZLUKSIZ TA'LIM VA "SILENCE" MODE (Owner Aralashuvi)
    # Agar bot egasi (Baxtiyorjon) mijozga o'zi xabar yuborsa (Business bot orqali)
    try:
        if is_business and int(sender_id) == int(config.OWNER_ID):
            client_chat_id = msg.chat.id
            if text:
                # Xabarni xuddi AI yozgandek log qilib qo'yish (O'qitish uchun)
                asyncio.create_task(asyncio.to_thread(db.log_message, client_chat_id, text, is_ai=True))
                logger.info(f"[LEARNING TRIGGER] Baxtiyorjon {client_chat_id} mijoziga aralashdi.")
                
                # AI yana tasodifan shaloq gapirib yubormasligi uchun 
                # AI ning shu mijozga javob berishini ma'lum vaqt (masalan 15 daqiqa) bloklab qo'yamiz.
                global silent_mode
                if 'silent_mode' not in globals():
                    silent_mode = {}
                silent_mode[client_chat_id] = now + 900 # 15 daqiqa (900 soniya) jimitish
                
                # Darhol analiz qilish (Learning)
                try:
                    msgs = db.get_recent_messages(client_chat_id, limit=6)
                    if msgs:
                        asyncio.create_task(learner.analyze_and_learn(client_chat_id, msgs))
                except Exception as le:
                    logger.error(f"[LEARNING ERROR] {le}")
            return
    except Exception as oe:
        logger.error(f"[OWNER FILTER ERROR] {oe}")
        
    # SILENCE TEKSHIRUVI (Agar Owner yaqinda yozgan bo'lsa AI aralashmaydi)
    if 'silent_mode' in globals() and sender_id in silent_mode:
        if now < silent_mode[sender_id]:
            logger.info(f"[SILENT MODE] Baxtiyorjon yaqinda yozgani uchun AI aralashmadi: {sender_name}")
            return
        else:
            silent_mode.pop(sender_id, None) # Vaqt o'tgan bo'lsa o'chiramiz
            
    # Har doim Ism va Usernameni bazaga yozib qo'yamiz
    db.upsert_user(sender_id, sender_name, username)
    logger.info(f"[TRACE] Start processing message from {sender_name}")

    # 🕵️‍♂️ DETEKTIV AI: Yangi mijoz tahlili
    user_info = db.get_user_info(sender_id)
    # Agar ijtimoiy tahlil hali qilinmagan bo'lsa
    if user_info and not user_info.get("social_analysis"):
        logger.info(f"[DETECTIVE] Yangi mijoz tahlil qilinmoqda: {sender_name}")
        try:
            # 1. Scouter orqali ma'lumot yig'ish
            dosye = await scouter.get_user_dosye(sender_id)
            if dosye:
                # 2. ResearcherAgent orqali detektiv tahlil
                researcher = msg_controller.agent_manager.get_agent("researcher")
                if researcher and hasattr(researcher, 'analyze_user_deep'):
                    analysis = await researcher.analyze_user_deep(
                        {"first_name": sender_name, "username": username}, 
                        dosye
                    )
                    # 3. Bazaga saqlash
                    db.upsert_user(
                        sender_id, sender_name, username,
                        bio=dosye.get("bio"),
                        social_analysis=json.dumps(analysis, ensure_ascii=False),
                        lead_score=scorer.calculate_score({"user_id": sender_id}, dosye),
                        role=analysis.get("role")
                    )
                    logger.info(f"[DETECTIVE OK] Mijoz tahlili yakunlandi: {analysis.get('role')}")
                    # Kontekstga detektiv tahlilini qo'shish (javob berishdan oldin)
                    text = f"[DETECTIVE ANALYSIS: {analysis.get('summary')}. Role: {analysis.get('role')}]\n{text}"
        except Exception as de:
            logger.error(f"[DETECTIVE ERROR] {de}")
    
    # 🤫 EGASI JAVOB BERGAN BO'LSA JIM TURISH (Silence Mode)
    # Agar mijoz eng oxirgi marta xabar yozgan va keyin unga AI emas xuddi Owner o'zi javob yozgan bo'lsa
    # yoki mijoz biror nima so'rasa-yu, Owner javob yozib ulgurgan bo'lsa, AI aralashmaydi.
    # Biz historydagi ohirgi rolni tekshiramiz. Ammo history AI ni va Ownerni birdek model deydi (chunk is_ai=1).
    # Shuning uchun asosan hozirgi xabarning o'zi eski va o'qilmagan bo'lsa bot javob qaytarmasligi yuqorida (BOT_START_TIME) filtri bilan hal qilingan.
    # Qolgan holatda, "Egasi javob bermagan bo'lsa davom etsin" degan shart, asosan bot o'chib qolganda o'qilmagan SMS lar uchun edi va u hal bo'ldi.
    # Lekin bot yoniq turgan paytda egasi javob yozsa, AI aralashmasligi ham kerak. Bu "Owner Reply Tracking" deyiladi.
    # Uni quyidagicha sodda yechamiz: Agar bot yoniq payti Baxtiyorjon mijozga nimadir yozsa, 
    # Mijozning navbatdagi 1 ta xabarida bot atay kutib turadi (ignoring). Yoki undan ham osoni, 
    # Owner yozgan paytda `last_activity` Ownerning ID sida emas, MIJOZNING ID sida yangilanib, 60 soniyaga bloklanadi.
    
    # Hozircha Sticker detection
    is_sticker = bool(msg.sticker)
    if is_sticker:
        emoji = msg.sticker.emoji or "✨"
        text += f"\n[User sent a sticker: {emoji}]"
        logger.info(f"[STICKER] {sender_name} yuborgan sticker: {emoji}")
    
    # Geolocation / Contact support
    phone = None
    if msg.location:
        text += f"\n[User sent location: {msg.location.latitude}, {msg.location.longitude}]"
    if msg.contact:
        phone = msg.contact.phone_number
        text += f"\n[User sent contact: {phone}]"
    
    is_voice_request = False
    if msg.voice or msg.audio or msg.video_note:
        is_voice_request = True
        text += "\n[User sent a voice/audio message. Please respond warmly.]"
    
    # Matndan ham raqam qidirish (keng regex — turli formatlar)
    if not phone and text:
        import re as _re  # Scope xatolarini oldini olish uchun
        phone_patterns = [
            r'\+?998\s?\(?\d{2}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',  # +998 XX XXX XX XX
            r'\b0\d{2}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b',             # 090 XXX XX XX
            r'\b\d{9}\b',                                                     # 9 raqamli (901234567)
        ]
        for pattern in phone_patterns:
            phone_match = _re.search(pattern, text)
            if phone_match:
                raw = phone_match.group(0).strip()
                digits = _re.sub(r'\D', '', raw)
                if len(digits) == 9:
                    phone = f"+998{digits}"
                elif len(digits) == 12 and digits.startswith("998"):
                    phone = f"+{digits}"
                elif len(digits) == 13 and digits.startswith("+998"):
                    phone = digits
                else:
                    phone = raw
                db.upsert_user(sender_id, sender_name, username, phone=str(phone))
                gsheet.sync_user(sender_id, sender_name, username, phone=str(phone))
                logger.info(f"[PHONE] Raqam topildi va saqlandi: {phone} ({sender_name})")
                break

    # 🕵️ Super-Analitika: Scouter orqali ma'lumot yig'ish
    user_info_db = db.get_user_info(sender_id)
    if not user_info_db or not user_info_db.get('bio'):
        logger.info(f"[SCOUTER] {sender_name} uchun detektiv tahlil boshlandi...")
        try:
            # Scouter async ishlagani uchun, biz uni process ichida tepadagi event loopda chaqiramiz
            dosye = await scouter.get_user_dosye(sender_id)
            if dosye:
                # 📊 Ball hisoblash
                score = scorer.calculate_score({'user_id': sender_id, 'username': username, 'phone': phone}, dosye)
                
                # 🕵️ OSINT: Ijtimoiy tarmoqlardan qidirish
                logger.info(f"[OSINT] {sender_name} uchun ijtimoiy qidiruv boshlandi...")
                social_profiles = osint.search_social_profiles(sender_name, username, phone)
                presence_summary = osint.analyze_presence(social_profiles)
                
                db.upsert_user(
                    sender_id, sender_name, username=username,
                    bio=dosye['bio'],
                    social_analysis=f"Guruhlar: {len(dosye['common_groups'])}. OSINT: {presence_summary}",
                    avatar_analysis=f"Profil rasmlari: {dosye['profile_photos_count']}",
                    lead_score=score
                )
                logger.info(f"[OSINT OK] {sender_name} uchun ijtimoiy qidiruv yakunlandi.")
                
                # 🚀 VIP Alert (Baxtiyorjonga xabar berish)
                if score >= 80:
                    tier = scorer.get_tier(score)
                    vip_msg = (
                        f"🔥 <b>VIP LEAD ALERT!</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"👤 <b>Mijoz:</b> {sender_name} (@{username if username else 'Noma’lum'})\n"
                        f"📊 <b>Score:</b> {score} / 100\n"
                        f"🌟 <b>Status:</b> {tier}\n"
                        f"📝 <b>Bio:</b> {dosye['bio'][:100]}...\n\n"
                        f"<i>Bu mijoz bilan shaxsan gaplashish tavsiya etiladi!</i>"
                    )
                    try:
                        await context.bot.send_message(chat_id=int(config.OWNER_ID), text=vip_msg, parse_mode="HTML")
                    except Exception as ve:
                        logger.error(f"[VIP NOTIFY ERROR] {ve}")
        except Exception as e:
            logger.error(f"[SCOUTER ERROR] {e}")

    # Multimodal: Rasm/Sticker yuklash
    image_data = None
    if msg.photo:
        photos = msg.photo
        try:
            logger.info(f"[MEDIA] Rasm yuklanmoqda: {sender_name}")
            photo_file = await context.bot.get_file(photos[-1].file_id)
            image_data = bytes(await photo_file.download_as_bytearray())
        except Exception as e:
            logger.error(f"[MEDIA ERROR] Rasm yuklashda xato: {e}")
    elif msg.sticker:
        if not msg.sticker.is_animated and not msg.sticker.is_video:
            try:
                logger.info(f"[MEDIA] Sticker yuklanmoqda (WebP): {sender_name}")
                sticker_file = await context.bot.get_file(msg.sticker.file_id)
                image_data = bytes(await sticker_file.download_as_bytearray())
            except Exception as e:
                logger.error(f"[MEDIA ERROR] Sticker yuklashda xato: {e}")
        else:
            logger.info(f"[MEDIA] Animatsiyali sticker - faqat matnli tahlil: {sender_name}")
            text += "\n[ESLATMA: Bu animatsiyali yoki video stiker. Siz uning harakatini ko'ra olmaysiz, faqat emojisini ko'ryapsiz. Iltimos, foydalanuvchiga buni (siz faqat statik rasmlarni ko'ra olishingizni) samimiy tushuntirib, emojiga mos javob bering.]"

    # Multimodal: Video yuklash (Video yoki Video Note)
    video_data = None
    if msg.video or msg.video_note:
        try:
            v_id = ""
            if msg.video:
                v_id = str(msg.video.file_id)
            elif msg.video_note:
                v_id = str(msg.video_note.file_id)
                
            if v_id:
                logger.info(f"[MEDIA] Video yuklanmoqda: {sender_name}")
                video_file = await context.bot.get_file(v_id)
                video_data = bytes(await video_file.download_as_bytearray())
        except Exception as e:
            logger.error(f"[MEDIA ERROR] Video yuklashda xato: {e}")

    audio_data = None
    if msg.voice or msg.audio:
        try:
            a_id = ""
            if msg.voice:
                a_id = str(msg.voice.file_id)
            elif msg.audio:
                a_id = str(msg.audio.file_id)
                
            if a_id:
                logger.info(f"[MEDIA] Audio yuklanmoqda: {sender_name}")
                audio_file = await context.bot.get_file(a_id)
                audio_data = bytes(await audio_file.download_as_bytearray())
        except Exception as e:
            logger.error(f"[MEDIA ERROR] Audio yuklashda xato: {e}")

    msg_text_display_str: str = str(text or "")
    msg_peek = msg_text_display_str[:50]
    logger.info(
        f"[{'BUSINESS' if is_business else 'DM'}] {sender_name} ({sender_id}): {msg_peek}"
    )

    # Javob tayyorlash
    image_mime = 'image/webp' if msg.sticker else 'image/jpeg'
    reply_text_raw = await get_reply(sender_id, sender_name, text, image_data=image_data, video_data=video_data, audio_data=audio_data, username=username, phone=phone, image_mime=image_mime)
    
    if not reply_text_raw:
        return
    
    reply_text = str(reply_text_raw)

    # Lead tahlili (Secret tag qidirish)
    lead_quality = None
    import re
    
    # Kengaytirilgan regex (probellar va katta-kichik harflar bilan)
    lead_match = re.search(r'\[LEAD_REPORT:\s*QUALITY\s*=\s*(.*?)\]', reply_text, re.IGNORECASE)
    if lead_match:
        lead_quality = str(lead_match.group(1)).strip().lower()
        logger.info(f"[CRM DEBUG] Lead sifati aniqlandi: {lead_quality}")
    
    # 🕵️ Fallback: Agar AI tagni unutsa, lekin "Rahmat! Baxtiyorjon..." desa — bu sifatli lead
    closing_phrase = "Baxtiyorjon tez orada siz bilan bog'lanadi"
    if closing_phrase in reply_text and not lead_quality:
        lead_quality = "sifatli"
        logger.info("[CRM] Closing phrase topildi, lead_quality='sifatli' ga o'zgartirildi.")

    # Kontaktni saqlash (Secret tag qidirish)
    contact_match = re.search(r'\[CONTACT_INFO:\s*(.*?)\]', reply_text, re.IGNORECASE)
    if contact_match:
        try:
            contact_raw = str(contact_match.group(1) or "")
            # name=...|phone=...|note=... formatini parse qilish
            c_data = {}
            contact_raw_str = str(contact_raw)
            for part in contact_raw_str.split('|'):
                if '=' in part:
                    k_v = part.split('=', 1)
                    if len(k_v) == 2:
                        k, v = k_v[0], k_v[1]
                        c_data[k.strip()] = v.strip() # type: ignore
            
            if c_data.get('name') or c_data.get('phone'):
                gcontacts.create_contact(
                    first_name=c_data.get('name', 'Noma\'lum'),
                    phone=c_data.get('phone', ''),
                    note=c_data.get('note', 'Telegram orqali avtomatik saqlandi')
                )
        except Exception as ce:
            logger.error(f"[GCONTACTS ERROR] Parsingda xato: {ce}")
        
        # Tegni o'chirish
        reply_text = re.sub(r'\[CONTACT_INFO:.*?\]', '', reply_text).strip()

    # Ma'lumotlarni bazaga saqlash (SAVE_INFO tag)
    save_info_matches = re.finditer(r'\[SAVE_INFO:\s*(.*?)\]', reply_text, re.IGNORECASE)
    has_updates = False
    update_data = {}
    for match in save_info_matches:
        try:
            info_raw = str(match.group(1) or "")
            if '=' in info_raw:
                k_v = info_raw.split('=', 1)
                if len(k_v) == 2:
                    k, v = k_v[0].strip().lower(), k_v[1].strip()
                    update_data[k] = v
                    has_updates = True
        except Exception as e:
            logger.error(f"[SAVE_INFO ERROR] Parsingda xato: {e}")
    
    if has_updates:
        # DB ni yangilash
        db.upsert_user(sender_id, sender_name, username=username, **update_data)
        logger.info(f"[DB UPDATE] {sender_name} ma'lumotlari yangilandi: {update_data}")
        # Tegni o'chirish
        reply_text = re.sub(r'\[SAVE_INFO:.*?\]', '', reply_text, flags=re.IGNORECASE).strip()

    # Kalendar tadbiri (Secret tag qidirish)
    calendar_match = re.search(r'\[CALENDAR_EVENT:\s*(.*?)\]', reply_text, re.IGNORECASE)
    if calendar_match:
        try:
            cal_raw = str(calendar_match.group(1) or "")
            cal_data = {}
            cal_raw_str = str(cal_raw)
            for part in cal_raw_str.split('|'):
                if '=' in part:
                    k_v = part.split('=', 1)
                    if len(k_v) == 2:
                        k, v = k_v[0], k_v[1]
                        cal_data[k.strip()] = v.strip() # type: ignore
            
            if cal_data.get('summary') and cal_data.get('start'):
                # Agar end vaqti bo'lmasa, 1 soat qo'shish
                start_str = cal_data.get('start')
                end_str = cal_data.get('end')
                
                if not end_str:
                    try:
                        import datetime as dt_mod
                        # start_str is str because we cast it above: cal_raw = str(...)
                        start_dt = dt_mod.datetime.fromisoformat(str(start_str))
                        end_str = (start_dt + dt_mod.timedelta(hours=1)).isoformat()
                    except:
                        end_str = start_str # Fallback
                
                gcalendar.create_event(
                    summary=cal_data.get('summary'),
                    start_time=start_str,
                    end_time=end_str,
                    description=cal_data.get('description', '')
                )
                
                # DB da uchrashuv vaqtini qayd etish
                db.update_meeting(sender_id, start_str)
                logger.info(f"[MEETING] {sender_name} bilan Google Calendar orqali uchrashuv belgilandi: {start_str}")
                
                # CRM Guruhni Xabardor Qilish
                if config.CRM_GROUP_ID:
                    user_info = db.get_user_info(sender_id) or {}
                    phone_val = user_info.get('phone') or 'Noma\'lum'
                    biz_val = user_info.get('business_type') or 'Noma\'lum'
                    region_val = user_info.get('region') or 'Noma\'lum'
                    brand_val = user_info.get('brand_name') or 'Noma\'lum'
                    service_val = user_info.get('service_type') or 'Noma\'lum'
                    
                    crm_msg = (
                        f"📅 <b>YANGI UCHRASHUV BELGILANDI!</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"👤 <b>Mijoz:</b> {sender_name} (@{username or 'yoq'})\n"
                        f"📱 <b>Telefon:</b> {phone_val}\n"
                        f"🏢 <b>Biznes:</b> {biz_val}\n"
                        f"🌍 <b>Hudud:</b> {region_val}\n"
                        f"🏷 <b>Brend:</b> {brand_val}\n"
                        f"🎨 <b>Xizmat:</b> {service_val}\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"🕒 <b>Vaqti:</b> {start_str}\n"
                        f"📝 <b>Mavzu:</b> {cal_data.get('summary', '...')} \n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"<i>(Tadbir to'g'ridan-to'g'ri Google Calendar'ga tushdi)</i>"
                    )
                    asyncio.create_task(context.bot.send_message(chat_id=config.CRM_GROUP_ID, text=crm_msg, parse_mode="HTML"))
                    
        except Exception as e:
            logger.error(f"[GCALENDAR ERROR] Parsingda xato: {e}")
            
        # Tegni o'chirish
        reply_text = re.sub(r'\[CALENDAR_EVENT:.*?\]', '', reply_text).strip()

    # Telegram Stars (SELL_STARS tag)
    stars_match = re.search(r'\[SELL_STARS:\s*(.*?)\]', reply_text, re.IGNORECASE)
    if stars_match:
        try:
            stars_raw = str(stars_match.group(1) or "")
            s_data = {}
            stars_raw_str: str = str(stars_raw)
            parts: List[str] = stars_raw_str.split('|')
            for part in parts:
                if '=' in part:
                    k_v: List[str] = part.split('=', 1)
                    if len(k_v) == 2:
                        k_str: str = k_v[0].strip()
                        v_str: str = k_v[1].strip()
                        s_data[k_str] = v_str
            
            p_id: Optional[str] = s_data.get('id')
            p_title: str = str(s_data.get('title', 'Raqamli mahsulot'))
            p_price: int = int(s_data.get('price', 0))
            
            if p_id and p_price > 0:
                # Log to DB as pending
                db.log_purchase(sender_id, p_id, p_price)
                
                # Send Stars Invoice
                await context.bot.send_invoice( # type: ignore
                    chat_id=sender_id, # type: ignore
                    title=p_title, # type: ignore
                    description=f"{p_title} uchun to'lov", # type: ignore
                    payload=f"stars_pay_{p_id}", # type: ignore
                    provider_token="", # type: ignore
                    currency="XTR", # type: ignore
                    prices=[LabeledPrice(p_title, p_price)] # type: ignore
                )
                logger.info(f"[STARS] Invoice sent to {sender_name}: {p_id} ({p_price} stars)") # type: ignore
        except Exception as e:
            logger.error(f"[STARS ERROR] Parsingda xato: {e}")
            
        # Tegni o'chirish
        reply_text = re.sub(r'\[SELL_STARS:.*?\]', '', reply_text).strip()

    # Avtomatik Hisob-faktura (Invoice) yaratish (GENERATE_INVOICE tag)
    invoice_match = re.search(r'\[GENERATE_INVOICE:\s*(.*?)\|?(.*?)?\]', reply_text, re.IGNORECASE)
    if invoice_match:
        try:
            inv_sum_raw = invoice_match.group(1).strip()
            inv_desc_raw = invoice_match.group(2) if invoice_match.group(2) else "Xizmatlar to'lovi"
            inv_desc = inv_desc_raw.strip() if inv_desc_raw else "Xizmatlar to'lovi"

            # Raqamlarni ajratib olish
            inv_sum = int(re.sub(r'\D', '', inv_sum_raw))
            
            # PDF yaratish
            import random
            random_id = str(random.randint(1000, 9999))
            
            invoice_path = invoicer.generate_invoice(
                user_name=sender_name,
                product_name=inv_desc,
                price_stars=f"{inv_sum:,} UZS", # UZS formati
                purchase_id=random_id
            )
            
            # Yuborish (PDF Invoysni)
            if is_business:
                chat_id_val = int(msg.chat.id)
                await context.bot.send_document(
                    chat_id=chat_id_val,
                    document=open(invoice_path, "rb"),
                    caption=f"🧾 **Sizning Hisob-fakturangiz**\nMijoz: {sender_name}\nXizmat: {inv_desc}\nSumma: {inv_sum:,} UZS\n\n_To'lovni ushbu hujjatdagi rekvizitlarga asosan amalga oshirishingiz mumkin._",
                    parse_mode="Markdown",
                    business_connection_id=msg.business_connection_id
                )
            else:
                chat_id_val = int(msg.chat.id)
                await context.bot.send_document(
                    chat_id=chat_id_val,
                    document=open(invoice_path, "rb"),
                    caption=f"🧾 **Sizning Hisob-fakturangiz**\nMijoz: {sender_name}\nXizmat: {inv_desc}\nSumma: {inv_sum:,} UZS\n\n_To'lovni ushbu hujjatdagi rekvizitlarga asosan amalga oshirishingiz mumkin._",
                    parse_mode="Markdown"
                )
                
            # Haqiqiy Telegram To'lov tugmasini (Click/Payme) yuborish
            if config.PROVIDER_TOKEN:
                # To'lov tugmasi biznes xabarlarda ishlamasligi mumkin, faqat direct bot chatda ishlaydi
                if not is_business:
                    await context.bot.send_invoice(
                        chat_id=chat_id_val,
                        title=f"{inv_desc}",
                        description=f"{sender_name} uchun {inv_desc} to'lovi",
                        payload=f"invoice_pay_{random_id}",
                        provider_token=config.PROVIDER_TOKEN,
                        currency="UZS",
                        prices=[LabeledPrice(inv_desc, inv_sum * 100)]
                    )
                else:
                    # Biznes ulanishda to'lov tugmasi yuborilmasligining ehtimoli hisobga olinib, oddiy havola yo'naltiramiz
                    logger.info("[NATIVE PAYMENT SKIP] Biznes bot rejimida Native To'lov tugmasi yuborilmadi. Yoki to'g'ridan to'g'ri bot profiliga o'tishi kerak.")
                    
            logger.info(f"[INVOICE OK] Hisob-faktura yuborildi: {sender_name} ({inv_sum} UZS)")
        except Exception as e:
            logger.error(f"[INVOICE ERROR] Invoice yuborishda xato: {e}")
            
        # Tegni o'chirish
        reply_text = re.sub(r'\[GENERATE_INVOICE:.*?\]', '', reply_text).strip()

    # Teglarni final javobdan tozalash
    final_reply = str(reply_text or "")
    # Har qanday [TAG:...] ko'rinishidagi maxfiy belgilarni o'chirish
    final_reply = re.sub(r'\[LEAD_REPORT:.*?\]', '', final_reply, flags=re.IGNORECASE).strip()
    final_reply = re.sub(r'\[CONTACT_INFO:.*?\]', '', final_reply, flags=re.IGNORECASE).strip()
    final_reply = re.sub(r'\[CALENDAR_EVENT:.*?\]', '', final_reply, flags=re.IGNORECASE).strip()
    final_reply = re.sub(r'\[SELL_STARS:.*?\]', '', final_reply, flags=re.IGNORECASE).strip()
    final_reply = re.sub(r'\[SAVE_INFO:.*?\]', '', final_reply, flags=re.IGNORECASE).strip()
    
    # Ortiqcha qatorlarni tozalash
    final_reply = re.sub(r'\n{3,}', '\n\n', final_reply).strip()

    # Javob yuborish
    try:
        if not final_reply:
            logger.warning("[SKIP] Final reply is empty after stripping tags.")
            return

        await asyncio.sleep(1)
        
        voice_sent = False
        # Ovozli javob yuborish (agar kerak bo'lsa)
        if is_voice_request:
            try:
                reply_text_for_tts = str(reply_text or "")
                unique_filename = f"response_{sender_id}_{int(time.time())}.mp3"
                audio_path = await tts.generate_audio(reply_text_for_tts, filename=unique_filename)
                if audio_path:
                    # Telegram voice caption limiti 1024 belgi. 
                    caption_text = final_reply
                    send_extra_text = False
                    if len(final_reply) > 1024:
                        caption_text = ""
                        send_extra_text = True
                        
                    if is_business:
                        chat_id_val = int(msg.chat.id)
                        await context.bot.send_voice(
                            chat_id=chat_id_val,
                            voice=open(audio_path, "rb"),
                            caption=caption_text,
                            parse_mode="HTML",
                            business_connection_id=msg.business_connection_id
                        )
                        if send_extra_text:
                            await context.bot.send_message(chat_id=chat_id_val, text=final_reply, business_connection_id=msg.business_connection_id, parse_mode="HTML")
                    else:
                        await msg.reply_voice(
                            voice=open(audio_path, "rb"),
                            caption=caption_text,
                            parse_mode="HTML"
                        )
                        if send_extra_text:
                            await msg.reply_text(final_reply, parse_mode="HTML")
                    
                    tts.cleanup(audio_path)
                    logger.info(f"[TTS] Voice response sent to {sender_name}")
                    voice_sent = True
            except Exception as te:
                logger.error(f"[TTS ERROR] Ovoz yuborishda xato: {te}")

        # Agar ovozli xabar yuborilmagan bo'lsa, odatiy matn yuborish
        if not voice_sent:
            if is_business:
                chat_id_val = int(msg.chat.id)
                await context.bot.send_message(
                    chat_id=chat_id_val,
                    text=final_reply,
                    business_connection_id=msg.business_connection_id,
                    parse_mode="HTML"
                )
            else:
                await msg.reply_text(final_reply, parse_mode="HTML")

        # AI Self-Learning (Background task)
        try:
            msgs = await asyncio.to_thread(db.get_recent_messages, sender_id, limit=6)
            msg_count = len(msgs)
            if msg_count >= 5 and msg_count % 5 == 0:
                asyncio.create_task(learner.analyze_and_learn(sender_id, msgs))
        except Exception as le:
            logger.error(f"[LEARNING ERROR] {le}")

        # Final logging and cleanup
        text_to_log: str = str(final_reply or "")
        peek = text_to_log[0:50] if text_to_log else ""
        logger.info(f"[OISHA GPT] -> {sender_name}: {peek}...")

        
        # CRM guruhiga Forward qilish (Ikki bosqichli lead)
        if lead_quality in ("sifatli", "oddiy"):
            # Bazadagi 'is_lead_forwarded' ni o'qish (hozir boolean 0/1 yoki string bo'lishi mumkin)
            # Ammo db.is_lead_forwarded(sender_id) funksiyasi qat'iy boolean qaytaradi, shuning uchun bazaga o'tishni optimallashtiramiz:
            forward_status = db.get_user_info(sender_id).get('is_lead_forwarded', 0) if db.get_user_info(sender_id) else 0
            
            should_forward = False
            if lead_quality == "oddiy" and str(forward_status) != "1" and str(forward_status) != "2":
                # Oddiy lead hali yuborilmagan
                should_forward = True
                new_status = 1  # 1 = Oddiy yuborildi
            elif lead_quality == "sifatli" and str(forward_status) != "2":
                # Sifatli lead hali yuborilmagan (hatto oddiy yuborilgan bo'lsa ham endi sifatli yuboriladi)
                should_forward = True
                new_status = 2  # 2 = Sifatli yuborildi

            if should_forward:
                logger.info(f"[CRM INFO] Lead aniqlandi ({sender_name}), quality={lead_quality}, forwarding...")
                # DB dan telefon raqamini olish
                saved_phone = db.get_user_phone(sender_id)
                user_info = {
                    "id": sender_id,
                    "name": sender_name,
                    "username": username,
                    "phone": saved_phone or "—"
                }
                
                # Agar oldin Oddiy lead yuborilgan bo'lsa, Sifatli ekanligini bildirish
                if lead_quality == "sifatli" and str(forward_status) == "1":
                    await forward_to_crm(context, user_info, f"Yangilanish: Mijoz barcha ma'lumotlarni to'ldirdi!\nOldingi xabar: {text}", reply_text, quality="Sifatli (Yangilangan)")
                else:
                    await forward_to_crm(context, user_info, text, reply_text, quality=lead_quality.capitalize())
                
                # [AGENTIC_ERA] - Kelajak poydevorini tekshirish (Phase 29)
                user_record = db.get_user_info(sender_id)
                if not user_record: # Yangi foydalanuvchi bo'lsa
                    try:
                        # Har bir foydalanuvchi uchun virtual hamyon yaratish (Foundation)
                        AgenticEra.initialize_wallet(sender_id)
                    except Exception as ae:
                        logger.error(f"[AGENTIC ERROR] {ae}")
                # Bazada holatni yangilash
                try:
                    with db.get_connection() as conn:
                        conn.cursor().execute("UPDATE users SET is_lead_forwarded=? WHERE user_id=?", (new_status, sender_id))
                        conn.commit()
                    logger.info(f"[CRM OK] {lead_quality.capitalize()} lead guruhga yuborildi va belgilandi (status={new_status}): {sender_name}")
                except Exception as e:
                    logger.error(f"[DB ERROR] Lead statusini yangilashda xato: {e}")
            
            # [SAVE_INFO] - Ma'lumotlarni bazaga va endi CRM (AmoCRM/Airtable) ga avtomat saqlash
            if "[SAVE_INFO:" in reply_text: # Assuming translated_text is now reply_text
                try:
                    info_content = reply_text.split("[SAVE_INFO:")[1].split("]")[0]
                    # Bazaga saqlash (Legacy logic)
                    import sqlite3 # Import moved here to avoid circular dependency if CRMIntegration is in another file
                    conn = sqlite3.connect("bot_memory.db")
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO learned_facts (user_id, fact) VALUES (?, ?)", (sender_id, info_content)) # user_id changed to sender_id
                    conn.commit()
                    conn.close()
                    logger.info(f"[AUTONOMY] Info saved for {sender_id}: {info_content}")

                    # AVTONOM CRM SYNC (Phase 27)
                    # Ma'lumotlarni parse qilish
                    info_dict = {}
                    for pair in info_content.split(","):
                        if "=" in pair:
                            k, v = pair.split("=", 1)
                            info_dict[k.strip().lower()] = v.strip()
                    
                    # AmoCRM integration (Agar tokenlar bo'lsa)
                    if hasattr(config, 'AMOCRM_TOKEN') and config.AMOCRM_TOKEN:
                        name = info_dict.get('ism', 'Noma\'lum')
                        phone = info_dict.get('tel', 'Noma\'lum')
                        # Assuming CRMIntegration is imported or defined elsewhere
                        # CRMIntegration.create_amocrm_lead(name, phone, domain=config.AMOCRM_DOMAIN, api_token=config.AMOCRM_TOKEN)
                        logger.info(f"[AMOCRM] Lead auto-created: {name}")

                    # Airtable integration (Agar tokenlar bo'lsa)
                    if hasattr(config, 'AIRTABLE_TOKEN') and config.AIRTABLE_TOKEN:
                        # Assuming CRMIntegration is imported or defined elsewhere
                        # CRMIntegration.save_to_airtable(config.AIRTABLE_BASE_ID, "Mijozlar", info_dict, api_token=config.AIRTABLE_TOKEN)
                        logger.info(f"[AIRTABLE] Entry auto-saved: {info_dict}")

                except Exception as e:
                    logger.error(f"[SAVE_INFO ERROR] {e}")

            # [STUDY_TRENDS] - GitHub/HuggingFace dan bilim olish (Phase 28)
            if "[STUDY_TRENDS:" in reply_text:
                try:
                    topic = reply_text.split("[STUDY_TRENDS:")[1].split("]")[0]
                    # GitHub Trends
                    github_info = OpenSourceHub.search_github_trending_ai(topic)
                    # HuggingFace Trends
                    hf_info = OpenSourceHub.search_huggingface_trending()
                    
                    combined_knowledge = f"OPEN-SOURCE INTEL ({topic}):\n{github_info}\n\n{hf_info}"
                    
                    # Bazaga bilim sifatida saqlash
                    conn = sqlite3.connect("bot_memory.db")
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO learned_facts (user_id, fact) VALUES (?, ?)", (0, combined_knowledge)) # 0 - System knowledge
                    conn.commit()
                    conn.close()
                    logger.info(f"[STUDY] Oisha learned about {topic} from Open Source")
                except Exception as e:
                    logger.error(f"[STUDY ERROR] {e}")

            # [CONSULT: platform=...] - Boshqa AI bilan maslahat
            if "[CONSULT:" in reply_text:
                try:
                    params = reply_text.split("[CONSULT:")[1].split("]")[0]
                    # platform=openai, query=Salom
                    p_dict = dict(item.split("=") for item in params.split(","))
                    platform = p_dict.get('platform', 'openai').lower()
                    api_key_name = f"{platform.upper()}_KEY"
                    api_key = getattr(config, api_key_name, None)
                    second_opinion = AIPortal.fast_consult(platform, p_dict.get('query', ''), api_key=api_key)
                    logger.info(f"[PROXY] Consulted {p_dict.get('platform')}: {second_opinion[:50]}")
                except Exception as ce:
                    logger.error(f"[CONSULT ERROR] {ce}")

            # [SMS: phone=..., msg=...] - Bepul SMS
            if "[SMS:" in reply_text:
                try:
                    params = reply_text.split("[SMS:")[1].split("]")[0]
                    p_dict = dict(item.split("=") for item in params.split(","))
                    FreeComm.send_free_sms_textbelt(p_dict.get('phone'), p_dict.get('msg'))
                    logger.info(f"[COMM] SMS sent to {p_dict.get('phone')}")
                except Exception as se:
                    logger.error(f"[SMS ACTION ERROR] {se}")

            # [WORLD_AI: platform=..., query=...] - Global Super AI Portal
            if "[WORLD_AI:" in reply_text:
                try:
                    params = reply_text.split("[WORLD_AI:")[1].split("]")[0]
                    p_dict = dict(item.split("=") for item in params.split(","))
                    platform = p_dict.get('platform', 'perplexity').lower()
                    api_key = getattr(config, f"{platform.upper()}_KEY", None)
                    
                    if platform == "perplexity": response = GlobalSuperAI.perplexity_search(p_dict.get('query'), api_key)
                    elif platform == "deepseek": response = GlobalSuperAI.deepseek_reasoning(p_dict.get('query'), api_key)
                    elif platform == "grok": response = GlobalSuperAI.grok_realtime(p_dict.get('query'), api_key)
                    else: response = "Unknown global platforma."
                    
                    logger.info(f"[WORLD_AI] {platform} response received.")
                except Exception as we:
                    logger.error(f"[WORLD AI ERROR] {we}")
            
            # [GIANT_SAVE: service=...] - Cloud Backup
            if "[GIANT_SAVE:" in reply_text:
                try:
                    service = reply_text.split("[GIANT_SAVE:")[1].split("]")[0]
                    if service == "gdrive": GiantResourceHub.google_drive_backup("bot_memory.db")
                    elif service == "s3": GiantResourceHub.aws_s3_storage("backup", "oisha-backup")
                    logger.info(f"[GIANT] Data synced to {service}")
                except Exception as ge:
                    logger.error(f"[GIANT HUB ERROR] {ge}")

            # [BRAND_IDEAS: niche=...] - Creative Strategy
            if "[BRAND_IDEAS:" in reply_text:
                try:
                    niche = reply_text.split("[BRAND_IDEAS:")[1].split("]")[0]
                    idea = BrandingMastery.suggest_innovative_idea(niche)
                    logger.info(f"[BRANDING] Idea generated for {niche}")
                    # Ideani javobga qo'shish yoki alohida yuborish logikasi
                except Exception as be:
                    logger.error(f"[BRANDING IDEA ERROR] {be}")

            # [PROJECT_PHASE: client_id=..., phase=...] - Project Tracking
            if "[PROJECT_PHASE:" in reply_text:
                try:
                    params = reply_text.split("[PROJECT_PHASE:")[1].split("]")[0]
                    p_dict = dict(item.split("=") for item in params.split(","))
                    BrandingMastery.track_project_phase(p_dict.get('client_id'), p_dict.get('phase'))
                    TeamIntegrator.notify_team(f"Project Phase Updated: {p_dict.get('phase')}")
                except Exception as pe:
                    logger.error(f"[PROJECT PHASE ERROR] {pe}")

            
            # AmoCRM Sync
            try:
                # Token borligini tekshirish, yo'q bo'sa yuklab ko'rish
                if not amocrm.access_token:
                    amocrm._load_token()
                
                if amocrm.access_token:
                    amo_reply_str: str = str(reply_text or "")
                    amo_peek = amo_reply_str[0:200]
                    amo_success = amocrm.create_lead(
                        name=sender_name,
                        phone=saved_phone or "Yo'q",
                        note=f"Telegram user: @{username if username else 'yo''q'}\nReply: {amo_peek}..."
                    )
                    if amo_success:
                        logger.info(f"[AMOCRM OK] Lead AmoCRM ga yuborildi: {sender_name}")
                    else:
                        logger.error(f"[AMOCRM ERROR] Lead yuborishda xato: {sender_name}")
                else:
                    logger.warning("[AMOCRM] Access token yo'q, lead yuborilmadi.")
            except Exception as ae:
                logger.error(f"[AMOCRM CRITICAL] Lead yuborishda kutilmagan xato: {ae}")
        
    except Exception as e:
        logger.error(f"[SEND ERROR] {e}")


async def handle_business_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Biznes chat orqali kelgan xabarlarni qayta ishlash."""
    await process_message_logic(update, context, is_business=True)

async def handle_edited_business_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner tahrirlagan xabarlardan o'rganish."""
    msg = update.edited_business_message
    if not msg:
        return
    
    sender = msg.from_user
    if sender and sender.id == config.OWNER_ID:
        text = msg.text or msg.caption or ""
        if text:
            # Xabarni o'rgatamiz
            client_chat_id = msg.chat.id
            logger.info(f"[LEARNING TRIGGER] Baxtiyorjon {client_chat_id} tarmog'idagi xabarni tahrirladi. O'rganish...")
            
            # AI yana tasodifan aralashib ketmasligi uchun jimitish (15 daqiqa)
            global silent_mode
            if 'silent_mode' not in globals():
                silent_mode = {}
            silent_mode[client_chat_id] = time.time() + 900
            
            # Matnni bazaga kiritib tahlil qilish
            asyncio.create_task(asyncio.to_thread(db.log_message, client_chat_id, text, is_ai=True))
            try:
                msgs = db.get_recent_messages(client_chat_id, limit=6)
                if msgs:
                    asyncio.create_task(learner.analyze_and_learn(client_chat_id, msgs))
            except Exception as le:
                logger.error(f"[LEARNING ERROR] {le}")

async def handle_direct_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Oddiy (to'g'ridan-to'g'ri) xabarlarni qayta ishlash."""
    await process_message_logic(update, context, is_business=False)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to the developer."""
    import traceback
    import html
    import json
    import datetime
    
    error_str = str(context.error)
    logger.error(f"Exception while handling an update: {error_str}")
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)
    
    # 🚨 Self-Healing / Auto-Response for Conflict
    if "Conflict: terminated by other getUpdates request" in error_str:
        logger.critical("[CONFLICT DETECTED] Attempting to notify and handle...")
        
        # Spamni oldini olish (oxirgi 5 daqiqa ichida bir marta yuborish)
        global last_conflict_notify
        
        now = time.time()
        if now - last_conflict_notify > 300: # 5 daqiqa
            conflict_msg = (
                "⚠️ <b>CONFLICT DETECTED!</b>\n"
                "Sizning botingiz boshqa joyda (masalan, shaxsiy kompyuteringizda) ham ishlayapti.\n"
                "Spamning oldini olish uchun loglarni o'chirib qo'yaman. Iltimos, barcha nusxalarni yopib, faqat bitta (VPS) qoldiring."
            )
            if config.OWNER_ID:
                try:
                    await context.bot.send_message(chat_id=int(config.OWNER_ID), text=conflict_msg, parse_mode="HTML")
                except Exception: pass
            last_conflict_notify = now
        return 

    # Structured Logging
    try:
        error_entry = {
            "timestamp": str(datetime.datetime.now()),
            "error": error_str,
            "traceback": tb_string,
            "solved": False,
            "update": str(update) if update else "N/A"
        }
        with open("ai_errors.json", "a", encoding="utf-8") as f:
            f.write(json.dumps(error_entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to log error to JSON: {e}")

    # Notify Owner
    if config.OWNER_ID:
        try:
            tb_trimmed = tb_string[-1000:]
            error_notify = (
                f"🚨 <b>BOTDA XATOLIK!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📝 <b>Xabar:</b> <code>{html.escape(error_str)}</code>\n\n"
                f"🛠 <b>Traceback:</b>\n<pre>{html.escape(tb_trimmed)}</pre>\n"
            )
            await context.bot.send_message(chat_id=int(config.OWNER_ID), text=error_notify, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")

# ==================== MAIN ====================


async def handle_inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inline querylarni qayta ishlash (Portfel uchun)."""
    iq = update.inline_query
    if not iq:
        return
    query_text = str(iq.query or "")
    results = [
        InlineQueryResultArticle(
            id="portfolio",
            title="Portfolio / Ishlarimiz",
            description="Biz amalga oshirgan loyihalar bilan tanishing",
            input_message_content=InputTextMessageContent(
                f"Sizni qiziqtirgan portfel: {config.WEBAPP_URL}"
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Ko'rish", url=config.WEBAPP_URL)]
            ])
        )
    ]
    await update.inline_query.answer(results, cache_time=300)

def main() -> None:
    """Bot ishga tushirish."""
    print("=" * 40)
    print("  Telegram Business Bot")
    print("=" * 40)

    print(f"[INFO] AI: {'ON' if ai_client else 'OFF'}")
    print(f"[INFO] Ish vaqti: {config.WORKING_HOURS}")
    print(f"[INFO] Kalit so'zlar: {len(config.KEYWORDS)}")
    print(f"[INFO] Whitelist: {config.WHITELIST_IDS}")
    logger.info(f"[BOOT] Whitelist IDs: {config.WHITELIST_IDS}")

    # Application yaratish
    app = Application.builder().token(bot_token).post_init(post_init).build()
    
    # MessageController ga bot_app ni bog'lash (Agentic Tools uchun)
    msg_controller.set_bot_app(app)

    # Command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("pay", pay_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("portfolio", portfolio_command))
    app.add_handler(CommandHandler("branding", branding_command))
    app.add_handler(CommandHandler("amofix", amofix_command))
    app.add_handler(CommandHandler("register", register_command))
    app.add_handler(CommandHandler("unregister", unregister_command))
    app.add_handler(CommandHandler("learn", analyze_history_command))
    app.add_handler(CommandHandler("task", task_command))
    app.add_handler(CommandHandler("topic_info", topic_info_command))

    # Inline query handler
    app.add_handler(InlineQueryHandler(handle_inline_query))
    
    # Callback query handler
    app.add_handler(CallbackQueryHandler(task_conf_callback, pattern="^task_"))
    app.add_handler(CallbackQueryHandler(strat_conf_callback, pattern="^strat_"))

    # Payment handlers
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    # Business handlers
    app.add_handler(BusinessConnectionHandler(handle_business_connection))
    app.add_handler(
        MessageHandler(filters.UpdateType.BUSINESS_MESSAGE, handle_business_message)
    )
    app.add_handler(
        MessageHandler(filters.UpdateType.EDITED_BUSINESS_MESSAGE, handle_edited_business_message)
    )

    # Error handler
    app.add_error_handler(error_handler)

    # Direct message handler (Mutlaqo hamma xabarlar uchun)
    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            handle_direct_message,
        )
    )

    print("[OK] Bot ishga tushdi! Ctrl+C bosib to'xtatish mumkin.")
    
    logger.info("Bot starting via run_polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
