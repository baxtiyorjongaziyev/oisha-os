import sys
import os

# Set project root to sys.path for absolute imports and backward compatibility
sys.path.append(os.getcwd())

import asyncio
import logging
from telethon import TelegramClient, events
from src.settings import settings
from src.services.safe_responder import SafeResponder
from src.services.action_parser import ActionParser
from src.services.lead_scraper import LeadScraper
from src.services.enterprise_reporter import EnterpriseReporter
from src.controllers.message_controller import MessageController
from src.services.scouter import Scouter
from src.services.advisor_agent import AdvisorAgent
from src.services.auto_lead_agent import AutoLeadAgent
from src.services.activity_monitor import ActivityMonitor
from src.services.audit_agent import AuditAgent
import threading
import src.config as config
from src.services.session_manager import SessionManager
from src.services.chat_bridge import ChatBridge
from src.api_server import app as api_app
import uvicorn
from telethon import functions, types
import random
import time
from src.services.admin_bot import AdminBot
from src.services.access_manager import AccessManager
from src.proxy_manager import ProxyManager

# Loglarni sozlash
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
# TN5 Group Config
TN5_GROUP_ID = -1003820339529
TN5_TOPIC_ID = 7 # Ishtirokchilar ma'lumotlari

# API Kalitlarni yig'ish
api_keys = {
    "gemini": settings.GEMINI_API_KEY.get_secret_value(),
    "deepseek": settings.DEEPSEEK_API_KEY.get_secret_value() if settings.DEEPSEEK_API_KEY else None
}

# Controller va Parserlarni to'g'ri init qilish
msg_controller = MessageController(api_keys=api_keys)
# ActionParser uchun kerakli xizmatlarni controller ichidan olamiz
# Telethon Client yaratish - session faylini writable joyga (/tmp) ko'chiramiz
SESSION_PATH = 'data/userbot_session'

# Agar BOT_TOKEN mavjud bo'lsa, bot sifatida ishlaymiz (session kerak emas)
BOT_TOKEN = getattr(settings, 'BOT_TOKEN', None)
if BOT_TOKEN:
    # SecretStr dan oddiy string ga o'tkazamiz
    token_str = BOT_TOKEN.get_secret_value() if hasattr(BOT_TOKEN, 'get_secret_value') else str(BOT_TOKEN)
    client = TelegramClient('data/bot_session', api_id=settings.API_ID, api_hash=settings.API_HASH)
    BOT_TOKEN_STR = token_str  # Save for later use in main()
else:
    client = TelegramClient(SESSION_PATH, settings.API_ID, settings.API_HASH)
    BOT_TOKEN_STR = None

# Admin Bot Client initialization (Dual-Head)
if config.ADMIN_BOT_TOKEN:
    # [AUDIT: DEVOPS] Unique session name to avoid persistence ghosting
    ADMIN_SESSION = 'data/oisha_admin_v2'
    bot_client = TelegramClient(ADMIN_SESSION, settings.API_ID, settings.API_HASH)
    # Tokenni start() metodida ishlatamiz keyinroq
else:
    bot_client = None
    logger.warning("ADMIN_BOT_TOKEN topilmadi. Admin interfeysi ishlamaydi.")

# LeadScraper init (client va DB ni ham uzatamiz)
lead_scraper = LeadScraper(
    google_service=msg_controller.google, 
    db=msg_controller.db, 
    client=client,
    amocrm=msg_controller.crm.amocrm
)

action_parser = ActionParser(
    db=msg_controller.db,
    gcontacts=msg_controller.google.contacts,
    gcalendar=msg_controller.google.calendar,
    invoicer=None,
    amocrm=msg_controller.crm.amocrm,
    config=config,
    lead_scraper=lead_scraper
)

# Advisor Agent init
advisor_agent = AdvisorAgent(
    api_key=api_keys["gemini"],
    db=msg_controller.db,
    action_parser=action_parser
)

# Auto Lead Agent init
auto_lead_agent = AutoLeadAgent(api_key=api_keys["gemini"])

# Safe Responder init
safe_responder = SafeResponder()

from src.services.workflow_manager import WorkflowManager

# Activity Monitoring & Audit init
activity_monitor = ActivityMonitor(db=msg_controller.db)
audit_agent = AuditAgent(api_key=api_keys["gemini"], db=msg_controller.db)

# Workflow Manager init
workflow_manager = WorkflowManager(
    crm=msg_controller.crm.amocrm,
    db=msg_controller.db,
    client=client
)

# Admin Bot initialization
access_manager = AccessManager(owner_id=config.OWNER_ID)
admin_bot = None
if bot_client:
    admin_bot = AdminBot(client=bot_client, db=msg_controller.db, msg_controller=msg_controller, access_manager=access_manager)

# LeadScraper-ga Admin Botni ulash (Proactive xabarlar uchun)
if admin_bot:
    lead_scraper.notify_callback = admin_bot.notify_lead

# Enterprise Services Initialization
async def push_block_to_amocrm(user_id, phone, block_text):
    """Callback for SessionManager to flush a block of messages."""
    contact = await msg_controller.crm.amocrm.get_contact_by_phone(phone)
    if contact:
        await msg_controller.crm.amocrm.add_contact_note(contact['id'], block_text)
        logger.info(f"[ENTERPRISE SYNC] Block pushed for {user_id}")
    else:
        logger.warning(f"[ENTERPRISE SYNC] Contact not found for {user_id} ({phone})")

session_manager = SessionManager(sync_callback=push_block_to_amocrm)
chat_bridge = ChatBridge(
    amocrm_subdomain=config.AMOCRM_SUBDOMAIN,
    amocrm_token=msg_controller.crm.amocrm.access_token or ""
)

# Global Search State (Memory-based for simplicity)
last_deep_search_time = 0

async def global_phone_lookup(phone: str) -> Optional[Dict[str, Any]]:
    """Butun Telegramdan raqam orqali qidirib topish (Xavfsiz rejimda)."""
    # Raqamni tozalash
    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    if not clean_phone.startswith('998'): 
        # Agar O'zbekiston raqami bo'lsa va + bo'lmasa, qo'shib qo'yamiz
        if len(clean_phone) == 9: clean_phone = '998' + clean_phone

    try:
        # 1. Vaqtinchalik kontakt yaratish
        contact = types.InputPhoneContact(
            client_id=random.randrange(-2**63, 2**63),
            phone=clean_phone,
            first_name='Oisha Search',
            last_name=''
        )
        
        # 2. Import so'rovi
        result = await client(functions.contacts.ImportContactsRequest(contacts=[contact]))
        
        if result.users:
            user = result.users[0]
            user_data = {
                "user_id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name
            }
            
            # 3. Bazaga saqlab qo'yamiz (Keyingi safar tekin bo'lishi uchun)
            msg_controller.db.upsert_user(
                user_id=user.id,
                first_name=user.first_name,
                username=user.username,
                phone=clean_phone,
                last_name=user.last_name
            )
            
            # 4. Kontaktni darhol o'chirib tashlaymiz
            await client(functions.contacts.DeleteContactsRequest(id=[user.id]))
            return user_data
        
        return None
    except Exception as e:
        logger.error(f"[GLOBAL SEARCH ERROR] {e}")
        return None

async def notify_admin(message: str):
    """Admin (baxtiyorjon) ga muhim xabar yuborish."""
    try:
        # 'me' - Saved Messages ga yuboradi
        await client.send_message('me', message)
    except Exception as e:
        logger.error(f"[NOTIFY ERROR] {e}")

async def background_monitor_task():
    """Barcha korporativ monitoring vazifalarini fonda ishga tushirish (AmoCRM + Airtable)."""
    from src.services.proactive_worker import check_amocrm_stagnation, check_airtable_deadlines, send_daily_report
    from datetime import datetime
    
    logger.info("[MONITOR] Boshlandi (Interval: 5 daqiqa)")
    
    while True:
        try:
            # 1. Stagnatsiya va Deadline tekshirish
            await check_amocrm_stagnation()
            await check_airtable_deadlines()

            # 2. Kunlik hisobotni 18:00 da yuborish
            now = datetime.now()
            if now.hour == 18 and now.minute < 10:
                # Faqat bir marta yuborish uchun tekshiruv (Memory check or simple delay)
                await send_daily_report()
                logger.info("[MONITOR] Kunlik hisobot yuborildi.")
            
            # 3. Har 4 soatda "Hushyor" xabari (09:00 - 21:00 orasi)
            if now.hour in [9, 13, 17, 21] and now.minute <= 5:
                await notify_admin("👸 **Oisha hushyor!**\nBarcha tizimlar (AmoCRM, Airtable, GCloud) barqaror ishlamoqda.")

            # Intervalni 5 daqiqaga tushirdik (300 soniya)
            await asyncio.sleep(300)
        except Exception as e:
            logger.error(f"[MONITOR ERROR] {e}")
            await asyncio.sleep(60)

@client.on(events.NewMessage(chats='me'))
async def self_command_handler(event):
    """'Saved Messages' dagi buyruqlarni (self-chat) va Baxtiyor akani o'z xabarlarini tahlil qilish."""
    if not event.message.text: return
    
    cmd = event.message.text.lower().strip()
    logger.info(f"[SELF-COMMAND DEBUG] Cmd: {cmd}")

    # 1. Komandani tekshirish
    if cmd.startswith('/dashboard'):
        stats = msg_controller.db.get_today_stats()
        msg = (
            "📊 **OISHA ROI DASHBOARD**\n"
            f"📅 Bugun: {datetime.now().strftime('%d-%m-%Y')}\n\n"
            f"👤 **Yangi lidlar:** {stats['leads_found']} ta\n"
            f"💬 **Sinxron chatlar:** {stats['messages_synced']} ta\n"
            f"👥 **Kontaktlar (Mass):** {stats['contacts_added']} ta\n"
            f"🤝 **DM Lidar:** {stats['private_chats']} ta\n\n"
            "✅ *Oisha hozirda fonda muvaffaqiyatli ishlamoqda.*"
        )
        await event.respond(msg)
        return

    if cmd.startswith('/status'):
        status_msg = (
            "🖥 **TIZIM HOLATI:**\n"
            "🟢 Bot Engine: Active\n"
            "🟢 Database: Connected\n"
            "🟢 AmoCRM API: Authorized\n"
            f"🛰 Server: GCP (GCE Master Node)"
        )
        await event.respond(status_msg)
        return

    if cmd.startswith('/find'):
        # /find logikasi shadow_advisor_handler bilan bir xil, shuning uchun uni chaqirish yoki takrorlash mumkin
        await shadow_advisor_handler(event)
        return

@client.on(events.NewMessage(incoming=True))
async def shadow_advisor_handler(event):
    """Xususiy suhbatlarni (DM) tahlil qilib, faqat Baxtiyorga strategik maslahat berish."""
    # 0. Faqat shaxsiy suhbatlar (DM) va Saved Messages
    if not event.is_private:
        return

    # DEBUG: Handler trigger bo'lganini ko'rish
    if event.message.text:
       logger.info(f"[HANDLER DEBUG] Msg: {event.message.text[:50]} (In: {event.incoming}, Out: {event.outgoing})")

    # 1. Komandani tekshirish (/find, /dashboard, /status)
    cmd = event.message.text.lower() if event.message.text else ""
    
    # O'zimizni o'zimiz xabarlarimizdan (agar komanda bo'lmasa) saqlaymiz (Loop stop)
    if event.outgoing and not cmd.startswith('/'):
        return

    # 2. Kontekstni yig'ish (Oxirgi 10 ta xabar)
    chat_id = event.chat_id
    messages = []
    async for msg in client.iter_messages(chat_id, limit=10):
        sender = "Mijoz" if msg.incoming else "Siz (Baxtiyor)"
        messages.append(f"[{sender}]: {msg.text}")
    
    history_context = "\n".join(reversed(messages))
    sender = await event.get_sender()
    sender_name = getattr(sender, 'first_name', 'Mijoz')

    # 1. Komandani tekshirish (/find, /dashboard, /status)
    cmd = event.message.text.lower() if event.message.text else ""
    
    if cmd.startswith('/dashboard'):
        stats = msg_controller.db.get_today_stats()
        msg = (
            "📊 **OISHA ROI DASHBOARD**\n"
            f"📅 Bugun: {datetime.now().strftime('%d-%m-%Y')}\n\n"
            f"👤 **Yangi lidlar:** {stats['leads_found']} ta\n"
            f"💬 **Sinxron chatlar:** {stats['messages_synced']} ta\n"
            f"👥 **Kontaktlar (Mass):** {stats['contacts_added']} ta\n"
            f"🤝 **DM Lidar:** {stats['private_chats']} ta\n\n"
            "✅ *Oisha hozirda fonda muvaffaqiyatli ishlamoqda.*"
        )
        await event.respond(msg)
        return

    if cmd.startswith('/status'):
        status_msg = (
            "🖥 **TIZIM HOLATI:**\n"
            "🟢 Bot Engine: Active\n"
            "🟢 Database: Connected\n"
            "🟢 AmoCRM API: Authorized\n"
            f"🛰 Server: GCP (GCE Master Node)"
        )
        await event.respond(status_msg)
        return

    if cmd.startswith('/find'):
        parts = event.message.text.split()
        if len(parts) > 1:
            query_phone = parts[1]
            is_deep = "deep" in event.message.text.lower()
            
            # A. Ichki bazadan qidiramiz
            found_user = await msg_controller.db.get_user_by_phone_full(query_phone)
            
            # B. Agar topilmasa yoki 'deep' buyrug'i bo'lsa (va bazada yo'q bo'lsa)
            if not found_user and is_deep:
                global last_deep_search_time
                now = time.time()
                
                # Check Cooldown (2 daqiqa)
                if now - last_deep_search_time < 120:
                    await event.respond(f"⏳ **Xavfsizlik cheklovi!**\n\nAkkauntingiz bloklanmasligi uchun har bir chuqur qidiruv orasida 2 daqiqa tanaffus bo'lishi kerak.\nQolgan vaqt: {int(120 - (now - last_deep_search_time))} soniya.")
                    return
                
                status_msg = await event.respond("🔍 **Chuqur qidiruv boshlandi...**\n(Telegramdan ma'lumot qidirilyapti, biroz kuting)")
                found_user = await global_phone_lookup(query_phone)
                last_deep_search_time = time.time()
                await status_msg.delete()

            if found_user:
                username = found_user.get('username')
                user_id = found_user.get('user_id')
                name = found_user.get('first_name', 'Mijoz')
                
                link = f"https://t.me/{username}" if username else f"tg://user?id={user_id}"
                await event.respond(f"🔍 **Topildi!**\n\n👤 Ism: {name}\n🔗 Profil: {link}")
            else:
                if not is_deep:
                    await event.respond("❌ Bazada topilmadi.\n\nButun Telegramdan qidirish uchun raqamdan keyin `deep` so'zini qo'shing.\nMisol: `/find 998901234567 deep`")
                else:
                    await event.respond("❌ Kechirasiz, bu raqamli foydalanuvchi butun Telegramda ham topilmadi yoki maxfiylik sozlamalari orqali yashiringan.")
        else:
            await event.respond("ℹ️ Iltimos, raqamni kiriting.\nMisol: `/find 998901234567` (Bazada qidirish)\n`/find 998901234567 deep` (Globally)")
        return

    # 2. AI Tahlili
    advice = await advisor_agent.analyze_and_advise(
        chat_id=chat_id,
        message_text=event.message.text,
        history_context=history_context,
        sender_name=sender_name
    )

    # 2.2 Enterprise Sync & Chat Bridge
    phone = getattr(sender, 'phone', 'Raqam yo\'q')
    session_manager.add_message(chat_id, sender_name, event.message.text, phone)
    
    # Real-time for Chat Widget
    await chat_bridge.send_to_amocrm(
        user_id=chat_id,
        user_name=sender_name,
        text=event.message.text,
        message_id=str(event.id)
    )

    # 2.5 Avtomatik AmoCRM Sync (Agar yangi mijoz bo'lsa)
    if not msg_controller.db.is_crm_synced(chat_id):
        first_name = getattr(sender, 'first_name', 'Mijoz')
        last_name = getattr(sender, 'last_name', '')
        full_name = f"{first_name} {last_name}".strip()
        
        # BLACKLIST CHECK (Name)
        if any(name.lower() in full_name.lower() for name in settings.EXCLUDED_NAMES):
            logger.info(f"[AUTO_CRM] SKIPPED (Blacklisted Name): {full_name}")
        else:
            user_profile = {
                "id": chat_id,
                "first_name": first_name,
                "username": getattr(sender, 'username', 'yoq')
            }
            lead_data = await auto_lead_agent.extract_lead_info(event.message.text, user_profile)
            
            if lead_data and lead_data.get("is_lead"):
                # DESIGNER/ROLE CHECK
                business_type = lead_data.get('business', '').lower()
                needs = lead_data.get('needs', '').lower()
                if any(role.lower() in business_type or role.lower() in needs for role in settings.EXCLUDED_ROLES):
                    logger.info(f"[AUTO_CRM] SKIPPED (Blacklisted Role): {full_name} - {business_type}")
                else:
                    logger.info(f"[AUTO_CRM] New lead detected: {full_name}")
                    
                    # Official Telegram data: Sender phone
                    tg_phone = getattr(sender, 'phone', None)
                    
                    # PRIORITY: 1. TG Profile, 2. AI Extract
                    phone = tg_phone or lead_data.get("phone")
                    name = f"{lead_data.get('first_name', first_name)} {lead_name}".strip() if (lead_name := lead_data.get('last_name', '')) else name
                    # Note mapping:
                    clean_name = f"{lead_data.get('first_name', first_name)} {lead_data.get('last_name', '')}".strip()
                    note_text = f"Suhbatdan auto-extract:\nBiznes: {lead_data.get('business')}\nEhtiyoj: {lead_data.get('needs')}"
                    
                    if not tg_phone and not lead_data.get("phone"):
                        note_text += "\n⚠️ [RAQAM YO'Q] Profil va xabarda raqam topilmadi."

                    # DEDUPLICATION CHECK
                    existing_contact = await msg_controller.crm.amocrm.get_contact_by_phone(phone) if phone and phone != "Raqam yo'q" else None
                    
                    if existing_contact:
                        logger.info(f"[AUTO_CRM] DEDUPE: Contact {clean_name} ({phone}) exists. Adding note.")
                        await msg_controller.crm.amocrm.add_contact_note(existing_contact['id'], f"Yangi live-murojaat:\n{note_text}")
                        # Notification to owner about repeat inquiry
                        await event.client.send_message(
                            'me', 
                            f"📣 **Takroriy mijoz:** {clean_name} ({phone}) yana yozyapti.\nAmoCRM-ga yangi izoh qo'shildi."
                        )
                        msg_controller.db.mark_crm_synced(chat_id)
                    else:
                        success = await msg_controller.crm.sync_lead(
                            user_id=chat_id,
                            name=clean_name,
                            phone=phone or "Raqam yo'q",
                            note=note_text
                        )
                        if success:
                            # Notify owner of new lead
                            await event.client.send_message(
                                'me',
                                f"👸🛡️ **Yangi Lid (AmoCRM):**\n👤 {clean_name}\n📞 {phone or 'Raqam yo''q'}\n🎯 {lead_data.get('business')}"
                            )
            
            # Bazada belgilab qo'yamiz (spamdan himoya)
            msg_controller.db.mark_crm_synced(chat_id)
            
            # Egasi (Siz) uchun xabar
            sync_notify = f"👸 **Oisha-OS: Yangi Lid aniqlandi!** 👸🛡️\n\n"
            sync_notify += f"👤 **Mijoz:** {name}\n"
            if phone: sync_notify += f"📞 **Tel:** {phone}\n"
            sync_notify += f"🏢 **Biznes:** {lead_data.get('business')}\n"
            sync_notify += f"📝 **Ehtiyoj:** {lead_data.get('needs')}\n\n"
            sync_notify += "✅ AmoCRM-da yangi bitim yaratildi."
            await client.send_message('me', sync_notify)

    if advice and advisor_agent.should_notify(chat_id, event.id, advice):
        logger.info(f"[ADVISOR] Sending strategic tip for chat {chat_id}")
        
        # 3. Maslahatni yuborish (Faqat Baxtiyorga - Saved Messages)
        header = f"👸 **Oisha-OS Strategik Maslahati** (Suhbat: {sender_name})\n\n"
        await client.send_message('me', header + advice)
        
        # 4. Action Propose (Agar xabarda [TAG] bo'lsa)
        if "[" in advice and "]" in advice:
             # Maslahatni parserdan o'tkazamiz (Side-effectlar uchun)
             await action_parser.parse_and_execute(
                reply_text=advice,
                sender_id=event.sender_id,
                sender_name=sender_name,
                username=getattr(sender, 'username', 'yoq'),
                saved_phone=None,
                context={'chat_id': 'me'}, # Side effectlar sodir bo'ladi, lekin javob 'me' ga ketadi
                 is_business=False
              )

@client.on(events.NewMessage(outgoing=True))
async def activity_monitor_handler(event):
    """Foydalanuvchining (Baxtiyor aka) chiquvchi harakatlarini loglash (Audit uchun)."""
    # Uzimizning xabarlarimizni log qilamiz
    await activity_monitor.log_event(event)

@client.on(events.NewMessage)
async def handle_new_message(event):
    """Barcha kiruvchi xabarlarni xavfsizlik va aqllilik bilan tahlil qilish."""
    
    # 0. Botning o'z ID sini olish (Sikl oldini olish uchun)
    me = await client.get_me()
    await safe_responder.update_me_id(me.id)

    # 1. Spamdan himoya va Guruh filtrini tekshirish
    if not await safe_responder.should_respond(event):
        return
    
    # 1.5 Real-time Lead Sync (Automatic for TN5 Topic 7)
    if event.chat_id == TN5_GROUP_ID and getattr(event.message.reply_to, 'reply_to_msg_id', None) == TN5_TOPIC_ID:
        logger.info(f"[ENTERPRISE SYNC] New lead detected from Topic 7! MessageID: {event.id}")
        # Run sync in parallel using the unified LeadScraper logic
        asyncio.create_task(sync_single_lead(event))
        return 

    # 1.6 Admin Commands
    if event.is_private and event.message.text.startswith('/'):
        if event.message.text == '/sync_backlog':
            await event.respond("👸 Oisha-OS: O'tmishdagi (Backlog) xabarlarni skanerlashni boshladim... 👸🛡️")
            # Run backlog sync in background
            asyncio.create_task(lead_scraper.sync_topic_to_contacts(
                client=client, 
                group_id=TN5_GROUP_ID, 
                topic_id=TN5_TOPIC_ID,
                limit=50 # Enterprise backlog limit
            ))
            return
            
        if event.message.text == '/force_sync_all':
            await event.respond("👸 Oisha-OS: Guruhning barcha a'zolarini ommaviy saqlash rejimini tasdiqladim!\nBu jarayon kunlab davom etishi mumkin. Orqa fonda (parallel) xavfsiz tezlikda saqlayman... 🐢🛡️")
            # Run mass sync in background
            asyncio.create_task(lead_scraper.sync_all_group_members(
                client=client, 
                group_id=TN5_GROUP_ID
            ))
            return
            
        if event.message.text == '/efficiency' or event.message.text == '/report':
            from src.services.airtable_sync import AirtableSync
            at_sync = AirtableSync()
            msg_controller.enterprise_reporter.airtable = at_sync
            
            report = await msg_controller.enterprise_reporter.get_team_efficiency_report()
            await event.respond(report, parse_mode='html')
            return
            
            from src.services.airtable_sync import AirtableSync
            at_sync = AirtableSync()
            projects = at_sync.get_projects()
            if not projects:
                await event.respond("👸 Oisha-OS: Hozircha aktiv loyihalar topilmadi. 🤷‍♀️")
                return
            
            text = "🏗 **Aktiv Loyihalar (Airtable):**\n\n"
            for p in projects[:10]:
                f = p.get('fields', {})
                stage = f.get('Stage', 'Nomalum')
                text += f"• {f.get('Project Name', 'Nomsiz')} — <b>{stage}</b>\n"
            await event.respond(text, parse_mode='html')
            return
            
        if event.message.text == '/audit':
            await event.respond("👸 Oisha-OS: Oxirgi harakatlaringizni tahlil qilyapman, bir oz kutib turing... 👸📈📊")
            report = await audit_agent.generate_audit_report(limit=100)
            await event.respond(report)
            return

        if event.message.text == '/audit_leads':
            await event.respond("👸 Oisha-OS: Oxirgi 100 ta dialogni audit qilyapman, shaffoflik hisoboti tayyor bo'lishi bilan yuboraman... 👸🛡️")
            
            audit_report = "👸 **Oisha-OS Lead Audit (Transparency Report)** 👸\n\n"
            async for dialog in client.iter_dialogs(limit=100):
                if not dialog.is_user or dialog.entity.bot: continue
                
                name = getattr(dialog.entity, 'first_name', 'User')
                # Check messages
                messages = []
                async for msg in client.iter_messages(dialog.id, limit=5):
                    if msg.text: messages.append(msg.text)
                
                if not messages: continue
                
                lead_data = await auto_lead_agent.extract_lead_info("\n".join(reversed(messages)), {"id": dialog.id, "first_name": name})
                
                if lead_data and lead_data.get("is_lead"):
                    audit_report += f"✅ **{name}** — Lead deb topildi. ({lead_data.get('business', 'Noʻmalum')})\n"
                else:
                    audit_report += f"❌ **{name}** — Shaxsiy/Irrelevant deb topildi.\n"
                
                if len(audit_report) > 3500: # Telegram message limit
                    await event.respond(audit_report)
                    audit_report = ""
            
            if audit_report:
                await event.respond(audit_report)
            return

        if event.message.text == '/sync_today':
            await event.respond("👸 Oisha-OS: Kecha va bugungi shaxsiy suhbatlarni (DM) skanerlashni boshladim... 👸🛡️")
            # Run retro sync in background
            asyncio.create_task(lead_scraper.sync_private_dialogs(
                client=client, 
                limit=100
            ))
            return
    
    # 2. Xabar matnini olish
    message_text = event.message.message
    chat_id = event.chat_id
    sender = await event.get_sender()
    sender_name = getattr(sender, 'first_name', 'User')

    logger.info(f"[USERBOT] Processing message from {sender_name} in {chat_id}: {message_text[:50]}...")

    try:
        # 2.5 Auto-Reply Check (Silent Mode)
        if not settings.ENABLE_AUTO_REPLY:
            # Faqat admin xabarlari (yuqorida) va lead syNC o'tadi
            # Conversational AI bu yerda to'xtatiladi
            return

        # 3. Odamdek tutilish (Delay + Typing...)
        # 3.1. Super-Analitika: Scouter orqali mijoz profilini tahlil qilish
        dosye = await scouter.get_user_dosye(sender.id)
        
        await safe_responder.prepare_to_reply(event, client)
        
        # 4. AI orqali javob tayyorlash (Gemini 2.0 Flash)
        ai_raw_response = await msg_controller.get_response(
            user_id=sender.id,
            user_name=sender_name,
            message=message_text,
            context={
                'chat_id': chat_id, 
                'is_group': not event.is_private,
                'dosye': dosye
            }
        )

        if ai_raw_response:
            # 5. Harakatlarni bajarish (Action Parsing)
            final_text = await action_parser.parse_and_execute(
                reply_text=ai_raw_response,
                sender_id=sender.id,
                sender_name=sender_name,
                username=getattr(sender, 'username', 'yoq'),
                saved_phone=None,
                context=None,
                is_business=False
            )

            # 6. Javobni yuborish
            if final_text:
                await event.respond(final_text)
                safe_responder.update_rate_limit(chat_id)
                logger.info(f"[USERBOT] Replied successfully to {chat_id}")

    except Exception as e:
        logger.error(f"[USERBOT] Error while handling message: {e}")

async def sync_single_lead(event):
    """Single leadni avtomatik tahlil qilish va qo'shish."""
    # Shunchaki LeadScraper dagi markaziy logikadan foydalanamiz
    # Bu qayta ishlanganligini bazada tekshiradi va marklaydi
    if not event.message.text: return
    
    # Biz scraper metodini bitta xabar uchun ishlatamiz
    # Lekin iter_messages o'rniga to'g'ridan-to'g'ri parse qilamiz
    try:
        data = await lead_scraper.parse_intro_with_ai(event.message.text)
        
        # RELEVANCE FILTER
        if not data or not data.get('is_relevant'):
            reason = data.get('relevance_reason') if data else 'AI Xatosi'
            logger.info(f"🚫 [SKIP] Relevant emas: {reason}")
            lead_scraper._mark_processed(event.id, TN5_GROUP_ID, status='irrelevant', reason=reason)
            return

        if data and data.get('phone'):
            phones = data.get('phone')
            if isinstance(phones, str):
                phones = [p.strip() for p in phones.replace(',', ' ').replace('/', ' ').split() if p.strip()]
            
            primary_phone = phones[0] if phones else None
            if not primary_phone:
                lead_scraper._mark_processed(event.id, TN5_GROUP_ID, status='skipped', reason='No phone')
                return

            sender = await event.get_sender()
            name = data.get('first_name')
            if not name or name.lower() == 'unknown':
                name = getattr(sender, 'first_name', None) or getattr(sender, 'username', 'Unknown')
            
            surname = data.get('last_name') or getattr(sender, 'last_name', '')
            full_name = f"{name} {surname} TN5 Gr".strip()
            bio = f"Biznes: {data.get('business', 'Noʻmalum')}\nEhtiyoj: {data.get('needs', 'Noʻmalum')}\n\n[AUTO-SYNCED]"
            
            # 1. Save to Google Contacts
            await msg_controller.google.save_contact(full_name, phones, notes=bio)
            
            # 2. Save to AmoCRM (Enterprise Automation)
            try:
                msg_controller.crm.amocrm.create_lead(name=full_name, phone=primary_phone, note=bio)
                logger.info(f"[ENTERPRISE] AmoCRM Lead created: {full_name}")
            except Exception as amo_ex:
                logger.warning(f"[ENTERPRISE] AmoCRM Sync Error: {amo_ex}")
            
            # 3. Save to Telegram
            try:
                from telethon import functions
                await client(functions.contacts.AddContactRequest(
                    id=event.sender_id,
                    first_name=name,
                    last_name=f"{surname} TN5 Gr",
                    phone=primary_phone,
                    add_phone_privacy_exception=True
                ))
            except Exception as e:
                logger.warning(f"TG Add Error: {e}")
            
            lead_scraper._mark_processed(event.id, TN5_GROUP_ID, status='synced')
            logger.info(f"✅ [ENTERPRISE SYNC OK] {full_name} avtomatik qo'shildi!")
    except Exception as e:
        logger.error(f"❌ [ENTERPRISE SYNC ERROR] {e}")

def run_health_check_api():
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🛰️ FastAPI Enterprise Server starting on port {port}")
    uvicorn.run(api_app, host="0.0.0.0", port=port)

async def main():
    """Botlarni ishga tushirish (Userbot + Admin Bot)."""
    print("🚀 Oisha-OS Tizimi tayyorlanmoqda (Dual-Head Architecture)...")
    
    # 1. FastAPI API serverni alohida thread da boshlaymiz
    threading.Thread(target=run_health_check_api, daemon=True).start()
    
    # 2. Session monitoringni boshlash
    asyncio.create_task(session_manager.monitor_sessions())

    # 3. Userbotni ishga tushirish
    await client.start()
    print("✅ Userbot ulandi!")

    # 4. Admin Botni ishga tushirish (Dual-Head)
    if bot_client:
        # [AUDIT: ARCHITECT] Explicitly delete webhook to ensure polling works
        from telethon.tl.functions.messages import GetBotCallbackAnswerRequest
        from telethon.tl.functions.contacts import ResolveUsernameRequest
        
        @bot_client.on(events.NewMessage())
        async def debug_all_handler(event):
            logger.info(f"🔍 [DEBUG BOT] Xabar keldi: {event.message.text} from {event.sender_id}")

        # [AUDIT: BACKEND] Fresh bot start
        await bot_client.start(bot_token=config.ADMIN_BOT_TOKEN)
        
        # Identity Verification
        me = await bot_client.get_me()
        logger.info(f"👑 [AUDIT: QA] Bot Identity Verified: @{me.username} (ID: {me.id})")
        
        await admin_bot.start()
        print(f"✅ Admin Bot (@{me.username}) ulandi! Boshqaruv pulti tayyor.")

    # [ENTERPRISE] Auto-run Mass Sync
    if getattr(settings, 'AUTORUN_MASS_SYNC', False):
        logger.info("[ENTERPRISE] 👸 Oisha-OS: 'Loyiha TN5' kontaktlarini ommaviy saqlash jarayoni boshlandi... 👸🛡️")
        asyncio.create_task(lead_scraper.sync_all_group_members(
            client=client, 
            group_id=TN5_GROUP_ID
        ))

    # [ENTERPRISE] Background Monitor
    asyncio.create_task(background_monitor_task())
    
    # Ikkala client ham o'chib qolmaguncha kutamiz
    if bot_client:
        await asyncio.gather(client.run_until_disconnected(), bot_client.run_until_disconnected())
    else:
        await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopping bot...")
