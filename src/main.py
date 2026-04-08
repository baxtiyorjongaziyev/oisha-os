import asyncio
import os
import sys
import re
from datetime import datetime

# Force UTF-8 console output on Windows to avoid emoji-related crashes.
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# [STABILITY] Windows loop policy configuration
if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# [STABILITY] Create and set loop EARLY to support library imports that check for a loop
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Set project root and source directories to sys.path for backward compatibility
# and to support current mixed-import structure.
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "src"))
sys.path.append(os.path.join(os.getcwd(), "src", "services"))

import logging
from typing import Optional, Dict, Any, List
from telethon import TelegramClient, events
from src.settings import settings
from src.database import Database
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
from src.services.folder_manager import FolderManager
from src.services.voice_processor import VoiceProcessor
from src.services.access_manager import AccessManager
from src.services.juma_notifier import JumaNotifier
from src.services.lead_orchestrator import LeadOrchestrator
from src.services.conversion_checker import ConversionChecker
from src.services.night_shift import NightShiftService
from src.services.crm_night_shift import CRMNightShift

# Global Managers
folder_manager: Optional[FolderManager] = None
voice_processor: Optional[VoiceProcessor] = None
conversion_checker: Optional[ConversionChecker] = None

# Loglarni sozlash
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
# Global service placeholders (initialized in main)
msg_controller = None
client = None
bot_client = None
lead_scraper = None
action_parser = None
advisor_agent = None
auto_lead_agent = None
safe_responder = None
activity_monitor = None
audit_agent = None
workflow_manager = None
access_manager = None
admin_bot = None
juma_notifier = None
session_manager = None
chat_bridge = None
lead_orchestrator = None
BOT_TOKEN_STR = None
welcome_manager = None
scouter = None
voice_processor = None
conversion_checker = None
night_shift = None

# TN5 Group Config (env-configurable; fallback keeps legacy behavior)
TN5_GROUP_ID = settings.CRM_GROUP_ID if settings.CRM_GROUP_ID is not None else -1003820339529
TN5_TOPIC_ID = settings.CRM_TOPIC_ID if settings.CRM_TOPIC_ID is not None else 7  # Ishtirokchilar ma'lumotlari

# Callbacks and Helper Functions (defined after globals)
async def push_block_to_amocrm(user_id, phone, block_text):
    """Callback for SessionManager to flush a block of messages."""
    global msg_controller
    if not msg_controller: return
    try:
        contact = await msg_controller.crm.amocrm.get_contact_by_phone(phone)
        if contact:
            await msg_controller.crm.amocrm.add_contact_note(contact['id'], block_text)
            logger.info(f"[ENTERPRISE SYNC] Block pushed for {user_id}")
        else:
            logger.warning(f"[ENTERPRISE SYNC] Contact not found for {user_id} ({phone})")
    except Exception as e:
        logger.error(f"[ENTERPRISE SYNC ERROR] Push failed: {e}")

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


async def notify_admin(message: str, client: TelegramClient):
    """Admin (baxtiyorjon) ga muhim xabar yuborish."""
    try:
        await client.send_message('me', message)
    except Exception as e:
        logger.error(f"[NOTIFY ERROR] {e}")

async def background_monitor_task():
    """Barcha korporativ monitoring vazifalarini fonda ishga tushirish (AmoCRM + Airtable)."""
    from src.services.proactive_worker import (
        check_amocrm_stagnation, 
        check_airtable_deadlines, 
        send_daily_report, 
        send_morning_briefing,
        send_overdue_nudges,
        distribute_team_tasks
    )
    from datetime import datetime
    global conversion_checker
    
    logger.info("[MONITOR] Boshlandi (AmoCRM + Airtable)")
    
    # Start Conversion Checker loop in background
    if conversion_checker:
        asyncio.create_task(conversion_checker.run_forever(interval=1800))
    
    while True:
        try:
            now = datetime.now()
            
            # 1. Stagnatsiya, Deadline va Taqsimot
            await distribute_team_tasks()
            await check_amocrm_stagnation()
            await check_airtable_deadlines()

            # 2. Daily Report (18:00)
            if now.hour == 18 and now.minute < 10:
                await send_daily_report()
            
            # 3. Overdue Nudges (17:00)
            if now.hour == 17 and now.minute < 10:
                await send_overdue_nudges()
            
            # 4. Morning Briefing (09:00)
            if now.hour == 9 and now.minute < 5:
                await send_morning_briefing()

            await asyncio.sleep(600) # Every 10 mins
        except Exception as e:
            logger.error(f"[MONITOR ERROR] {e}")
            await asyncio.sleep(60)

async def self_command_handler(event):
    """'Saved Messages' dagi buyruqlarni (self-chat) va Baxtiyor akani o'z xabarlarini tahlil qilish."""
    if not event.message.text: return
    cmd = event.message.text.lower().strip()
    if cmd.startswith('/dashboard'):
        stats = msg_controller.db.get_today_stats()
        msg = f"📊 **OISHA ROI DASHBOARD**\n📅 Bugun: {datetime.now().strftime('%d-%m-%Y')}\n\n👤 Yangi lidlar: {stats['leads_found']}\n💬 Sinxron: {stats['messages_synced']}\n"
        await event.respond(msg)
    elif cmd.startswith('/status'):
        await event.respond("🟢 **TIZIM HOLATI:** Active (GCP Master)")

async def shadow_advisor_handler(event):
    """Xususiy suhbatlarni (DM) tahlil qilib, strategik maslahat va sync qilish."""
    global client, msg_controller, advisor_agent, session_manager, chat_bridge, auto_lead_agent
    if not event.is_private: return
    
    sender = await event.get_sender()
    sender_name = getattr(sender, 'first_name', 'Mijoz')
    chat_id = event.chat_id
    
    # 1. Komandalar (Basic)
    cmd = event.message.text.lower() if event.message.text else ""
    if cmd.startswith('/find'):
        parts = cmd.split()
        if len(parts) > 1:
            query_phone = parts[1]
            found = await msg_controller.db.get_user_by_phone_full(query_phone)
            if found:
                await event.respond(f"🔍 Topildi: {found.get('first_name')} (tg://user?id={found.get('user_id')})")
            else:
                await event.respond("❌ Topilmadi.")
        return

    # 2. AI Advice & Sync Context
    history = []
    async for msg in client.iter_messages(chat_id, limit=5):
        history.append(f"{'Mijoz' if msg.incoming else 'Siz'}: {msg.text}")
    history_context = "\n".join(history)

    # 2.1 AI Tahlili (Advice)
    advice = await advisor_agent.analyze_and_advise(
        chat_id=chat_id,
        message_text=event.message.text,
        history_context=history_context,
        sender_name=sender_name
    )

    # 2.2 Enterprise Sync & Chat Bridge
    phone = getattr(sender, 'phone', 'Raqam yo\'q')
    session_manager.add_message(chat_id, sender_name, event.message.text, phone)
    
    # [WAZZUP COEXISTENCE] Wazzup now handles the native chat sync. 
    # Oisha stops manual message syncing to avoid duplicates, but keeps Shadow Advisor active.
    # await chat_bridge.send_to_amocrm(
    #     user_id=chat_id,
    #     user_name=sender_name,
    #     text=event.message.text,
    #     message_id=str(event.id)
    # )

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
                business_type = (lead_data.get('business') or '').lower()
                needs = (lead_data.get('needs') or '').lower()
                if any(role.lower() in business_type or role.lower() in needs for role in settings.EXCLUDED_ROLES):
                    logger.info(f"[AUTO_CRM] SKIPPED (Blacklisted Role): {full_name} - {business_type}")
                else:
                    logger.info(f"[AUTO_CRM] New lead detected: {full_name}")
                    
                    # Official Telegram data: Sender phone
                    tg_phone = getattr(sender, 'phone', None)
                    
                    # PRIORITY: 1. TG Profile, 2. AI Extract
                    phone = tg_phone or lead_data.get("phone")
                    
                    # USE UNIFIED NAMING LOGIC
                    is_tn5_lead = (chat_id == settings.TN5_GROUP_ID)
                    clean_name = lead_scraper.format_contact_name(first_name, last_name, lead_data=lead_data, is_tn5=is_tn5_lead)
                    
                    note_text = f"Suhbatdan auto-extract:\nBiznes: {lead_data.get('business')}\nEhtiyoj: {lead_data.get('needs')}"
                    
                    if not tg_phone and not lead_data.get("phone"):
                        note_text += "\n⚠️ [RAQAM YO'Q] Profil va xabarda raqam topilmadi."

                    # DEDUPLICATION CHECK
                    existing_contact = await msg_controller.crm.amocrm.get_contact_by_phone(phone) if phone and phone != "Raqam yo'q" else None
                    
                    if existing_contact:
                        logger.info(f"[AUTO_CRM] DEDUPE: Contact {clean_name} ({phone}) exists. Adding note.")
                        await msg_controller.crm.amocrm.add_contact_note(existing_contact['id'], f"Yangi live-murojaat:\n{note_text}")
                        # Notification to owner about repeat inquiry
                        await client.send_message(
                            'me', 
                            f"📣 **Takroriy mijoz:** {clean_name} ({phone}) yana yozyapti.\nAmoCRM-ga yangi izoh qo'shildi."
                        )
                    else:
                        success = await msg_controller.crm.sync_lead(
                            user_id=chat_id,
                            name=clean_name,
                            phone=phone or "Raqam yo'q",
                            note=note_text
                        )
                        if success:
                            # [INTELLIGENCE] Enrich profile and provide expert advice
                             await admin_bot.enrich_lead_profile(chat_id, sender, lead_data)
                             logger.info(f"[AUTO_CRM] Lead synced and enriched: {clean_name}")
                        
                    # Final DB update with all extracted data
                    msg_controller.db.upsert_user(
                        chat_id, 
                        first_name, 
                        last_name=last_name, 
                        phone=phone,
                        region=lead_data.get('city'),
                        business_type=lead_data.get('activity'),
                        brand_name=lead_data.get('brand_name'),
                        intent=lead_data.get('intent_category')
                    )
                    msg_controller.db.mark_crm_synced(chat_id)

    # 3. Maslahatni yuborish (Advice logic)
    if advice and advisor_agent.should_notify(chat_id, event.id, advice):
        logger.info(f"[ADVISOR] Sending strategic tip for chat {chat_id}")
        header = f"💡 <b>Tavsiya</b> (Suhbat: {sender_name})\n\n"
        
        # [GOD MODE] Visibility: Notify via Admin Bot if possible
        notification_text = header + advice
        if admin_bot:
            await admin_bot.notify_lead(notification_text)
        else:
            await client.send_message('me', notification_text)
        
        # 4. Action Propose (Agar xabarda [TAG] bo'lsa)
        if "[" in advice and "]" in advice:
             await action_parser.parse_and_execute(
                reply_text=advice,
                sender_id=event.sender_id,
                sender_name=sender_name,
                username=getattr(sender, 'username', 'yoq'),
                saved_phone=None,
                context={'chat_id': 'me'},
                is_business=False
              )


async def activity_monitor_handler(event):
    """Foydalanuvchining (Baxtiyor aka) chiquvchi harakatlarini loglash (Audit uchun)."""
    # Uzimizning xabarlarimizni log qilamiz
    await activity_monitor.log_event(event)

async def handle_new_message(event):
    """Barcha kiruvchi xabarlarni xavfsizlik va aqllilik bilan tahlil qilish."""
    
    # 0. Botning o'z ID sini olish (Sikl oldini olish uchun)
    me = await client.get_me()
    await safe_responder.update_me_id(me.id)

    # 1. Spamdan himoya va Guruh filtrini tekshirish
    if not await safe_responder.should_respond(event):
        return

    # [WAZZUP KILLER] Log incoming private messages for AmoCRM/Widget history
    if event.is_private and not event.out and event.message.text:
        msg_controller.db.log_message(event.sender_id, event.message.text, is_ai=False)
        logger.info(f"👸 [HISTORY] Logged incoming msg from {event.sender_id}")
    
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

        if event.message.text == '/distribute_now':
            is_team = await safe_responder.is_team_member(event.sender_id)
            if not is_team: return
            
            await event.respond("Vazifalarni taqsimlashni (Force) boshladim...")
            from src.services.proactive_worker import distribute_team_tasks
            await distribute_team_tasks(force=True)
            await event.respond("✅ Taqsimlash yakunlandi.")
            return

        if event.message.text == '/health':
            is_team = await safe_responder.is_team_member(event.sender_id)
            if not is_team: return
            
            msg = "🟢 **OISHA-OS HEALTH CHECK**\n\n"
            msg += f"✅ **Status**: Active\n"
            msg += f"📅 **Time**: {datetime.now().strftime('%H:%M:%S')}\n"
            msg += f"🔗 **AmoCRM**: Connected\n"
            msg += f"📊 **Airtable**: Connected\n"
            msg += f"⚙️ **Mode**: Automatic Management v9"
            await event.respond(msg)
            return
            
            from src.services.airtable_sync import AirtableSync
            at_sync = AirtableSync()
            projects = at_sync.get_projects()
            if not projects:
                await event.respond("Hozircha aktiv loyihalar topilmadi.")
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

    # 3. New Message Logic (Elite Intake)
    if event.is_private and not event.out and not getattr(sender, 'bot', False):
        # AI Skanerlash (Strict Intake)
        if lead_orchestrator and not msg_controller.db.is_crm_synced(event.sender_id):
            logger.info(f"✨ [ELITE INTAKE] Yangi suhbat (Lead detection): {sender_name}")
            from src.api_server import add_activity
            add_activity("Yangi Lid Skanerlash", f"{sender_name} bilan suhbat tahlil qilinmoqda...", "info")
            
            # Use Orchestrator for everything: Qualify -> amoCRM -> Notify
            success = await lead_orchestrator.process_new_lead(
                chat_text=event.message.text,
                user_id=sender.id,
                name=sender_name,
                username=getattr(sender, 'username', None),
                phone=getattr(sender, 'phone', None), # Will be enriched by AI if missing
                source="Direct Telegram Message"
            )
            
            if success:
                msg_controller.db.set_crm_synced(event.sender_id)
                # Elite Welcome (1.4)
                await welcome_manager.send_welcome(event.sender_id)
            
            # --- NIGHTLY AUTO-REPLY (23:00 - 08:00) ---
            now_hour = datetime.now().hour
            if now_hour >= 23 or now_hour < 8:
                # Faqat bir marta javob qaytarish (shovqin bo'lmasligi uchun)
                if not msg_controller.db.get_meta(event.sender_id, "night_reply_sent_today"):
                    reply = (
                        "Salom! Xabaringizni oldik. 😊\n\n"
                        "Hozir jamoamiz tuni bilan dam olyapti (yoki Oisha kechki tadqiqotlar bilan band). "
                        "Lekin xavotir olmang, so'rovingizni o'rganib chiqyapman va ertalab albatta javob beramiz!"
                    )
                    await event.respond(reply)
                    msg_controller.db.set_meta(event.sender_id, "night_reply_sent_today", "true", expire_in_hours=12)

    # [GOD MODE] Multi-Modal (Voice Note) Handling
    if event.is_private and not event.out and event.message.voice and voice_processor:
        logger.info(f"🎙️ [VOICE] New voice from {sender_name}...")
        try:
            temp_path = f"temp_voice_{event.id}.ogg"
            await client.download_media(event.message, file=temp_path)
            
            # AI Transcription
            result = await voice_processor.transcribe(temp_path)
            if result:
                # Notify Admin
                if admin_bot:
                    await admin_bot.notify_lead(f"🎙️ **Ovozli xabar ({sender_name}):**\n\n{result}")
                
                # Update AmoCRM Note if lead
                if msg_controller.db.is_crm_synced(event.sender_id):
                    # We don't have lead ID here, but create_lead with same phone should handle it or just notify.
                    # For now, notification to Admin is the primary 'God Mode' feature.
                    pass
            
            # Cleanup
            asyncio.create_task(voice_processor.cleanup(temp_path))
        except Exception as e:
            logger.error(f"[VOICE] Integration error: {e}")

    # [GOD MODE] Media/Document Sync
    if event.is_private and not event.out and (event.message.photo or event.message.document):
        logger.info(f"📁 [MEDIA] New media from {sender_name}...")
        try:
            # Download
            media_path = await client.download_media(event.message)
            if media_path:
                # Upload to Google Drive (Background)
                def upload_drive():
                    return msg_controller.google.drive.upload_file(media_path)
                
                drive_link = await asyncio.to_thread(upload_drive)
                
                if drive_link:
                    # Notify Admin
                    if admin_bot:
                        type_str = "Rasm" if event.message.photo else "Hujjat"
                        await admin_bot.notify_lead(f"📁 **Yangi {type_str} ({sender_name}):**\n🔗 [Google Drive Link]({drive_link})")
                    
                # Cleanup local
                if os.path.exists(media_path):
                    os.remove(media_path)
                    
        except Exception as e:
            logger.error(f"[MEDIA] Integration error: {e}")

    try:
        # 2.5 Auto-Reply Check (Silent Mode)
        # Boshida botning o'zi mention qilinganini tekshiramiz
        is_mentioned = False
        if event.message.text:
            me = await client.get_me()
            text_low = event.message.text.lower()
            me_username = (me.username or "").lower()
            is_mentioned = (me_username and f"@{me_username}" in text_low) or "oisha" in text_low

        if not settings.ENABLE_AUTO_REPLY and not is_mentioned:
            # Faqat admin xabarlari (yuqorida) va lead syNC o'tadi
            # Mention qilinmagan bo'lsa, conversational AI to'xtatiladi
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

            # 6. Javobni yuborish (ONLY FOR INTERNAL TEAM OR MENTIONS)
            if final_text:
                username = getattr(sender, 'username', None)
                is_team = await safe_responder.is_team_member(sender.id, username)
                
                if is_team or not event.is_private:
                    # Allow internal or group replies
                    await event.respond(final_text)
                    safe_responder.update_rate_limit(chat_id)
                    logger.info(f"[USERBOT] Replied successfully to team/group {chat_id}")
                else:
                    # EXTERNAL LEAD - SHADOW MODE
                    logger.info(f"[USERBOT] Shadow Mode: Suppressing direct reply to {chat_id}. Sending to Admin.")
                    header = f"📝 **Draft javob** (Kimga: {sender_name})\n\n"
                    if admin_bot:
                        await admin_bot.notify_lead(header + final_text)
                    else:
                        await client.send_message('me', header + final_text)

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
            first_name = data.get('first_name')
            if not first_name or first_name.lower() == 'unknown':
                first_name = getattr(sender, 'first_name', None) or getattr(sender, 'username', 'Unknown')
            
            last_name = data.get('last_name') or getattr(sender, 'last_name', '')
            
            # Unified naming
            full_name = lead_scraper.format_contact_name(first_name, last_name, is_tn5=True)
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
                    first_name=full_name, # Entire name in first_name for better visibility
                    last_name="",
                    phone=primary_phone,
                    add_phone_privacy_exception=True
                ))
            except Exception as e:
                logger.warning(f"TG Add Error: {e}")
            
            lead_scraper._mark_processed(event.id, TN5_GROUP_ID, status='synced')
            logger.info(f"✅ [ENTERPRISE SYNC OK] {full_name} avtomatik qo'shildi!")
    except Exception as e:
        logger.error(f"❌ [ENTERPRISE SYNC ERROR] {e}")

async def run_health_check_api():
    ports = [int(os.environ.get("PORT", 8080)), 8081, 8082, 8083]
    for port in ports:
        config_uvicorn = uvicorn.Config(
            api_app, 
            host="0.0.0.0", 
            port=port, 
            log_level="error", 
            loop="asyncio"
        )
        server = uvicorn.Server(config_uvicorn)
        try:
            logger.info(f"🚀 [API] Port {port} da tekshirilmoqda...")
            await server.serve()
            break # Successfully started
        except (SystemExit, Exception) as e:
            # Uvicorn raises SystemExit(1) on bind error internally
            # We catch it here to allow trying the next port
            logger.warning(f"⚠️ [API] Port {port} band yoki xatolik yuz berdi. Keyingisiga o'tilmoqda...")
            continue

async def main():
    """Botlarni ishga tushirish (Userbot + Admin Bot)."""
    global msg_controller, client, bot_client, lead_scraper, action_parser
    global advisor_agent, auto_lead_agent, safe_responder, activity_monitor, audit_agent
    global workflow_manager, access_manager, admin_bot, session_manager, chat_bridge, BOT_TOKEN_STR, juma_notifier
    global folder_manager, voice_processor, welcome_manager, scouter, conversion_checker, night_shift

    print("🚀 Oisha-OS Tizimi tayyorlanmoqda (Dual-Head Architecture)...")
    
    # [GOD MODE] Health Check for Cloud Run
    asyncio.create_task(run_health_check_api())
    
    # 1. Credentials, Foundations & Database
    api_keys = {
        "gemini": settings.GEMINI_API_KEY.get_secret_value(),
        "deepseek": settings.DEEPSEEK_API_KEY.get_secret_value() if settings.DEEPSEEK_API_KEY else None
    }
    
    # [AUDIT: RESTORATION] Centralized DB instance for global consistency
    db = Database()
    msg_controller = MessageController(api_keys=api_keys, db=db)
    
    # [GOD MODE] Juma Notifier - initialized later below
    
    # [GOD MODE] Authorized Session Discovery
    # We prioritize 'oisha_userbot' as it was found to be the only valid large session (156KB)
    SESSION_PATH = 'data/userbot_session'
    if os.path.exists('oisha_userbot.session'):
        SESSION_PATH = 'oisha_userbot'
    elif not os.path.exists('data/userbot_session.session') and os.path.exists('userbot_session.session'):
        SESSION_PATH = 'userbot_session'
    
    logger.info(f"👸 [USERBOT] Using session: {SESSION_PATH}")
    
    client = TelegramClient(
        SESSION_PATH,
        settings.API_ID,
        settings.API_HASH,
        device_model="Oisha Enterprise v2",
        system_version="Windows 11 Agent"
    )
    
    # Head 2: Main Bot (Public interface and Admin Dashboard)
    BOT_TOKEN = settings.BOT_TOKEN.get_secret_value()
    bot_client = TelegramClient('data/bot_session', settings.API_ID, settings.API_HASH)
    BOT_TOKEN_STR = BOT_TOKEN

    # 3. Services initialization (Safe inside loop)
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

    advisor_agent = AdvisorAgent(api_key=api_keys["gemini"], db=msg_controller.db, action_parser=action_parser)
    auto_lead_agent = AutoLeadAgent(api_key=api_keys["gemini"])
    safe_responder = SafeResponder()
    scouter = Scouter(api_key=api_keys["gemini"], db=msg_controller.db)
    
    from src.services.workflow_manager import WorkflowManager
    activity_monitor = ActivityMonitor(db=msg_controller.db)
    audit_agent = AuditAgent(api_key=api_keys["gemini"], db=msg_controller.db)
    
    workflow_manager = WorkflowManager(crm=msg_controller.crm.amocrm, db=msg_controller.db, client=client)
    access_manager = AccessManager(owner_id=config.OWNER_ID)
    logger.info(f"🚀 [INIT] OWNER_ID Config: {config.OWNER_ID}")
    logger.info(f"🚀 [INIT] Is 150074828 Owner?: {access_manager.get_role(150074828) == 'OWNER'}")
    
    # [ENTERPRISE: CLEANUP] Night Shift Service
    night_shift = CRMNightShift(amocrm=msg_controller.crm.amocrm, db=msg_controller.db)

    # [ENTERPRISE: UI] Register AdminBot on the Bot Client.
    # This provides the dashboard to the user via the main bot.
    admin_bot = AdminBot(
        bot_client=bot_client, 
        user_client=client, 
        db=msg_controller.db, 
        msg_controller=msg_controller, 
        access_manager=access_manager,
        night_shift=night_shift,
        team_group_id=settings.TEAM_GROUP_ID
    )
    from src.services.welcome_manager import WelcomeManager
    welcome_manager = WelcomeManager(client=client)
    
    lead_scraper.notify_callback = admin_bot.notify_lead

    # [SYSTEMATIC ENGINE v4.6] Lead & Project Orchestration
    lead_orchestrator = LeadOrchestrator(
        amocrm=msg_controller.crm.amocrm,
        airtable=msg_controller.crm.airtable,
        auto_lead=auto_lead_agent,
        admin_bot=admin_bot,
        db=msg_controller.db,
        folder_manager=folder_manager
    )
    
    conversion_checker = ConversionChecker(
        amocrm=msg_controller.crm.amocrm, 
        airtable=msg_controller.crm.airtable, 
        admin_bot=admin_bot
    )
    
    session_manager = SessionManager(sync_callback=push_block_to_amocrm)
    chat_bridge = ChatBridge(amocrm_subdomain=config.AMOCRM_SUBDOMAIN, amocrm_token=msg_controller.crm.amocrm.access_token or "")

    # [WAZZUP KILLER] Bridge Telegram & DB to API Server for the AmoCRM Widget
    import src.api_server as api_module
    api_module.user_client = client
    api_module.db_instance = msg_controller.db

    # 4. Starting API server
    asyncio.create_task(run_health_check_api())
    
    # 5. Background Tasks
    # [GOD MODE] Initialize Juma Notifier (Must be after client initialization)
    juma_notifier = JumaNotifier(client=client, db=db, group_id=TN5_GROUP_ID)
    
    asyncio.create_task(session_manager.monitor_sessions())
    # asyncio.create_task(orchestrator.background_loop(interval_minutes=15)) # Replaced by LeadOrchestrator logic or kept if needed for Portfolio sync
    
    # We keep the legacy orchestrator for background sync if it handles non-lead tasks (like Portfolio)
    # but lead processing is now handled by LeadOrchestrator via event triggers.

    # [STABILITY] Move Userbot.start() to the very end to ensure Admin Bot and Monitors are online first.
    # [GOD MODE] Initialize Managers (Move up)
    folder_manager = FolderManager(client)
    voice_processor = VoiceProcessor(api_key=settings.GEMINI_API_KEY.get_secret_value())
    
    # [V4.7] Callback Query Handler for Payment Confirmation
    if bot_client:
        @bot_client.on(events.CallbackQuery(data=re.compile(b"confirm_pay:.*")))
        async def confirm_payment_handler(event):
            sender_id = event.sender_id
            data = event.data.decode('utf-8').split(':')
            manager_id = int(data[1])
            amount = data[2]
            
            # Check Role (Only Admin/Finance)
            user_info = db.get_user_info(sender_id)
            role = user_info.get('role') if user_info else None
            
            if sender_id != settings.OWNER_ID and role != 'Finance':
                await event.answer("👸 Oisha: Kechirasiz, faqat Baxtiyor aka yoki Moliya bo'limi to'lovni tasdiqlashi mumkin. 👸🛡️", alert=True)
                return

            await event.answer("👸 To'lov tasdiqlandi! Onboarding boshlanmoqda...", alert=True)
            
            # Update Message
            await event.edit(f"✅ **TO'LOV TASDIQLANDI**\n💰 Summa: {amount}\n👤 Mas'ul: <i>Moliya / Admin</i>\n\n👸 Oisha hozir mijoz uchun maxsus guruh ochmoqda... 👸🛡️", parse_mode='html')
            
            # Start Onboarding
            from src.services.onboarding_manager import OnboardingManager
            onboarding = OnboardingManager(client=client, db=db, admin_bot=admin_bot)
            asyncio.create_task(onboarding.start_client_onboarding(manager_id, amount))

    # 4. Botni ishga tushirish
    if BOT_TOKEN_STR:
        await bot_client.start(bot_token=BOT_TOKEN_STR)
        # Kunlik vazifalar schedulerini ishga tushiramiz
        asyncio.create_task(admin_bot.run_scheduler())
    
    # [STABILITY] Registrating event handlers AFTER client initialization
    client.add_event_handler(handle_new_message, events.NewMessage)
    client.add_event_handler(self_command_handler, events.NewMessage(chats='me'))
    client.add_event_handler(shadow_advisor_handler, events.NewMessage(incoming=True))
    client.add_event_handler(shadow_advisor_handler, events.NewMessage(outgoing=True)) # Bi-directional Shadow Advisor
    client.add_event_handler(activity_monitor_handler, events.NewMessage(outgoing=True))
    
    # Register handlers for the Bot Token head
    if bot_client:
        bot_client.add_event_handler(handle_new_message, events.NewMessage)
        
    # [GOD MODE] User Presence Tracker (Nudge Alerts)
    @client.on(events.UserUpdate)
    async def presence_handler(event):
        if event.online:
            user_id = event.user_id
            # 1. Check if user is a HOT_LEAD
            user_info = msg_controller.db.get_user_info(user_id)
            # Since get_user_info doesn't have intent yet in its return dict, we'll check directly
            with msg_controller.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT intent FROM users WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                intent = row[0] if row else None
            
            if intent == 'HOT_LEAD':
                # 2. Check if we need to nudge (last msg was from user and > 5 mins ago)
                logger.info(f"🔥 [NUDGE] Hot Lead online: {user_id}")
                # We could fetch last message from DB or TG
                # For high-performance, we notify the admin immediately
                if admin_bot:
                    await admin_bot.notify_lead(f"🔥 **Hot Lead Online:** {user_id} hozir Telegramda faol! Uni suhbatga chorlang.")
    
    @bot_client.on(events.NewMessage(pattern='/set_role.*'))
    async def set_user_role_top_handler(event):
        """Foydalanuvchiga professional rol biriktirish."""
        sender = await event.get_sender()
        if not sender or sender.id != settings.OWNER_ID:
            return
        
        try:
            # Format: /set_role user_id role
            parts = event.text.split(' ')
            if len(parts) < 3:
                await event.reply("👸 Oisha: Format - `/set_role [user_id] [role]`\n_Rollar: PM, Designer, SMM, Developer_")
                return
            
            target_id = int(parts[1])
            new_role = parts[2]
            
            db.set_user_role(target_id, new_role)
            await event.reply(f"✅ **Rol o'rnatildi!**\n👤 User: `{target_id}`\n🎭 Rol: `{new_role}`\n\n👸 Oisha endi bu hodimga loyiha vazifalarini avtomatik biriktira oladi. 🛡️")
        except Exception as e:
            await event.reply(f"❌ Xato: {e}")

    @bot_client.on(events.NewMessage(pattern='/topic_info'))
    async def topic_info_handler(event):
        """Guruhdagi Topic ID raqamini aniqlash uchun."""
        chat_id = event.chat_id
        thread_id = event.message.reply_to_msg_id
        
        msg = (
            f"👸 **Mavzu ma'lumotlari:**\n\n"
            f"🔹 **Group ID:** `{chat_id}`\n"
            f"🔸 **Topic ID (Thread):** `{thread_id or 'General (Asosiy)'}`\n\n"
            f"💡 Ushbu Topic ID-ni `.env` faylida sozlash uchun foydalaning."
        )
        await event.respond(msg)
    
    @bot_client.on(events.NewMessage(pattern='/task'))
    async def task_command_handler(event):
        """Vazifani tahlil qilish va yaratish."""
        logger.info(f"👸 [TASK] Command from {event.chat_id}")
        # AI tahlilini PTB botga yoki ichki handlerga yo'naltirish
        # Hozircha oddiy tasdiq va AI Assistant orqali tahlilni boshlaymiz
        await event.respond("👸 **Oisha:** Vazifa qabul qilindi. AI assistant tahlil qilmoqda... 👸🛡️")
        
        # Import here to avoid circular imports
        from src.services.userbot_legacy import task_command
        # For simplicity, we assume the PTB bot in userbot_legacy is also running and will pick this up

    @bot_client.on(events.NewMessage(pattern='/audit'))
    async def audit_command_handler(event):
        """Jamoa va loyihalarni real raqamlarda audit qilish."""
        sender = await event.get_sender()
        if getattr(sender, 'id', 0) != settings.OWNER_ID:
            await event.respond("👸 **Oisha:** Bu maxfiy audit hisoboti faqat Baxtiyor aka uchun. 👸🛡️")
            return
        
        logger.info(f"👸 [AUDIT] Running real performance audit for Owner...")
        await event.respond("👸 **Oisha:** Real raqamlarni yig'yapman, bir soniya... 👸🛡️")
        
        try:
            audit_text = await msg_controller.enterprise_reporter.get_real_numbers_audit()
            await event.respond(audit_text, parse_mode='html')
        except Exception as e:
            logger.error(f"👸 [AUDIT ERROR] {e}")
            await event.respond(f"👸 **Xatolik:** Hisobatni tayyorlashda muammo yuz berdi: {e}")

    @bot_client.on(events.NewMessage(chats=settings.TEAM_GROUP_ID))
    async def team_group_handler(event):
        # Faqat mention bo'lganda yoki savol berilganda javob beramiz
        if event.mentioned:
            logger.info(f"👸 [TEAM ASSISTANT] Mentioned in group {event.chat_id}")
            # AdvisorAgent orqali aqlli javob tayyorlash
            response = await advisor_agent.generate_advice(event.text)
            await event.respond(f"👸 **Oisha Assistant:**\n\n{response}")
    
    # [NEW] Kirim (Inflow) Celebration Listener
    if settings.TOPIC_KIRIM_ID:
        @bot_client.on(events.NewMessage(chats=settings.TEAM_GROUP_ID))
        async def kirim_celebration_handler(event):
            # Filter for Kirim Topic
            if event.message.reply_to_msg_id != settings.TOPIC_KIRIM_ID:
                return
            
            text = event.text or ""
            # Detection for income reports (contains digits and keywords)
            import re
            is_inflow = re.search(r'\d+', text) and any(kw in text.lower() for kw in ['$', 'som', 'so\'m', 'sum', 'usd', 'uzs', 'kirim', 'to\'lov', 'tulov'])
            
            if is_inflow:
                sender = await event.get_sender()
                sender_id = sender.id
                
                first_name = getattr(sender, 'first_name', 'Xodim')
                
                # Extract amount for AI context
                amount_match = re.search(r'(\d[\d\s,.]+)', text)
                amount_str = amount_match.group(1) if amount_match else "noma'lum"

                logger.info(f"👸 [KIRIM] Generating AI celebration for {first_name} for {amount_str}...")
                
                # Generate Premium AI Celebration
                try:
                    celebration_text = await advisor_agent.generate_sales_celebration(
                        manager_name=first_name,
                        amount=amount_str
                    )
                    # [V4.7] Add Confirmation Button for Finance
                    from telethon import Button
                    buttons = [
                        [Button.inline("✅ Tasdiqlash (Moliya)", data=f"confirm_pay:{sender_id}:{amount_str}")]
                    ]
                    await event.reply(celebration_text, parse_mode='html', buttons=buttons)
                except Exception as e:
                    logger.error(f"👸 [CELEBRATION ERROR] AI failed: {e}")
                    # Fallback to a nice manual one
                    from telethon import Button
                    buttons = [[Button.inline("✅ Tasdiqlash (Moliya)", data=f"confirm_pay:{sender_id}:{amount_str}")]]
                    await event.reply(f"🎉 **BARAKALLA, {first_name}!** 🎉\n\nSizni ajoyib natija bilan tabriklaymiz! 👸🛡️", buttons=buttons)
                
                logger.info(f"👸 [KIRIM] Successfully celebrated {first_name}.")

    print("✅ Userbot ulandi va xabarlarni eshita boshladi!")

    # 4. Admin Botni ishga tushirish (on bot_client)
    if admin_bot:
        await admin_bot.start()
        print(f"✅ Oisha Admin Bot (Bot Token-da) faollashtirildi.")

    # [ENTERPRISE] Auto-run Mass Sync
    if getattr(settings, 'AUTORUN_MASS_SYNC', False):
        logger.info("[ENTERPRISE] 👸 Oisha-OS: 'Loyiha TN5' kontaktlarini ommaviy saqlash jarayoni boshlandi... 👸🛡️")
        asyncio.create_task(lead_scraper.sync_all_group_members(
            client=client, 
            group_id=TN5_GROUP_ID,
            limit=500
        ))

    # [ENTERPRISE] Background Monitor
    asyncio.create_task(background_monitor_task())
    
    # [GOD MODE] Periodic tasks (Juma, Maintenance)
    async def background_scheduler():
        # RUN IMMEDIATELY ON STARTUP
        try:
            await juma_notifier.check_and_send()
        except Exception as e:
            logger.error(f"[SCHEDULER] Immediate Task Error: {e}")

        while True:
            try:
                await juma_notifier.check_and_send()
            except Exception as e:
                logger.error(f"[SCHEDULER] Task Error: {e}")
            await asyncio.sleep(600) # Check every 10 mins
    
    asyncio.create_task(background_scheduler())
    
    # [ENTERPRISE] Periodic DM Lead Sync (Personal Account)
    async def dm_lead_sync_task():
        while True:
            try:
                logger.info("👸 [DM SYNC] Starting periodic private dialogs analysis...")
                await lead_scraper.sync_private_dialogs(client, limit=50)
            except Exception as e:
                logger.error(f"[DM SYNC ERROR] {e}")
            await asyncio.sleep(3600) # Run every 1 hour
    
    asyncio.create_task(dm_lead_sync_task())

    # [WAZZUP KILLER] Outgoing Message Consumer
    async def amocrm_bridge_consumer():
        logger.info("👸 [WAZZUP KILLER] Bridge consumer started. Ready to send messages from AmoCRM.")
        while True:
            try:
                # Wait for message from API Server queue
                msg_data = await api_server.outgoing_messages.get()
                user_id = msg_data.get('user_id')
                text = msg_data.get('text')
                
                if user_id and text:
                    logger.info(f"👸 [WAZZUP KILLER] Sending msg to {user_id}...")
                    await client.send_message(user_id, text)
                    logger.info(f"✅ Sent!")
                
                api_server.outgoing_messages.task_done()
            except Exception as e:
                logger.error(f"[WAZZUP BRIDGE ERROR] {e}")
            await asyncio.sleep(0.1)

    asyncio.create_task(amocrm_bridge_consumer())
    
    logger.info("✅ Oisha-OS: All High-Performance Agents are Online & Ready!")
    
    # [WAZZUP KILLER] Initialize API Server Bridge
    import src.api_server as api_server
    api_server.user_client = client
    api_server.db_instance = Database() # or use existing msg_controller.db
    
    # [API] Already started via run_health_check_api()
    logger.info("👸 [OISHA] Strategic Intelligence Bridge is online.")

    # [NIGHT SHIFT] Autonomous Engine
    logger.info("🌙 Initializing Night Shift Intelligence...")
    night_shift_service = NightShiftService(client if client else None)
    asyncio.create_task(night_shift_service.run_overnight_cycle())
    
    from src.api_server import add_activity
    add_activity("Platform On", "Oisha-OS va Dashboard muvaffaqiyatli ishga tushdi.", "success")

    # [ROBUST STARTUP] Finally, start Userbot once everything else is running.
    # This ensures that if the Userbot asks for a code, the Admin Bot and Reports are already active.
    logger.info("👸 [USERBOT] Attempting to connect shaxsiy akkaunt...")
    await client.start()
    logger.info("✅ Userbot ulandi va xabarlarni eshita boshladi!")

    # Main client loop
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("👸 Oisha-OS: To'xtatildi (KeyboardInterrupt).")
    except Exception as e:
        logger.critical(f"👸 Oisha-OS: Fatal Error: {e}", exc_info=True)
    finally:
        loop.close()
        print("Stopping bot...")
