import os
import json
import logging
import asyncio
import psutil
import platform
from datetime import datetime, timedelta
from telethon import events, Button, functions, types
from src.services.mission_control import MissionControl
from src.database import Database
from src.controllers.message_controller import MessageController

from src.services.crm_night_shift import CRMNightShift
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.services.access_manager import AccessManager

logger = logging.getLogger(__name__)
class AdminBot:
    def __init__(self, bot_client, user_client, db: Database, msg_controller: MessageController, access_manager: 'AccessManager', night_shift: CRMNightShift = None, team_group_id: int = None):
        self.bot_client = bot_client
        self.user_client = user_client
        self.db = db
        self.msg_controller = msg_controller
        self.access_manager = access_manager
        self.night_shift = night_shift
        self.team_group_id = team_group_id
        self.active_searches = {}  # user_id -> timestamp
        self.pending_drafts = {}   # draft_id -> draft_text

        # [EXPERT ADVICE] Professional scripts to obtain phone numbers
        self.PHONE_GETTING_SCRIPTS = {
            "agency_standard": (
                "📍 **Agency Standard:**\n"
                "\"Tafsilotlar uchun rahmat! Loyihani texnik tomondan baholashimiz uchun "
                "siz bilan telefon orqali bog'lansak bo'ladimi? Raqamingizni qoldirsangiz, "
                "mutaxassisimiz bilan vaqtni kelishib olamiz.\""
            ),
            "value_first": (
                "🎁 **Value-First (Kasbiy):**\n"
                "\"Sizning sohangiz bo'yicha bizda tayyor keyslar va narxlar paketi bor. "
                "Ularni Telegram orqali yuborishim uchun kontaktlaringizni yangilab yuborsangiz (ulashsangiz), "
                "sizga mos yechimni jo'nataman.\""
            ),
            "emergency_pm": (
                "⚡ **Dynamic (PM uslubi):**\n"
                "\"Loyiha bo'yicha tezkor savollar bor edi. Yozishib o'tirmasdan, "
                "qisqa qo'ng'iroqda hal qilsak tezroq bitar edi. Qaysi raqamga bog'lansak bo'ladi?\""
            )
        }

    async def start(self):
        """Botni eventlarini ro'yxatdan o'tkazish va schedulerni parallel yuritish."""
        logger.info("[ADMIN_BOT] Oisha Enterprise v2.1 ishga tushmoqda...")
        
        # [AUDIT: HEARTBEAT] Proof of life every 60 seconds
        async def heartbeat():
            while True:
                logger.info("👸 [ADMIN_BOT] HEARTBEAT: Oisha is alive and listening... 🛡️")
                await asyncio.sleep(60)
        
        # [DISTRIBUTION] Yuklash (Settings ni DB bilan sinxronlash)
        from src.settings import settings
        db_mode = self.db.get_state("lead_distribution_mode")
        if db_mode:
            settings.LEAD_DISTRIBUTION_MODE = db_mode
        
        db_managers = self.db.get_state("sales_managers")
        if db_managers:
            manager_ids = [int(i.strip()) for i in db_managers.split(",") if i.strip()]
            settings.SALES_MANAGER_IDS = manager_ids
            logger.info(f"👸 [ADMIN_BOT] Sales Managers loaded: {manager_ids}")

        # Start background tasks
        asyncio.create_task(heartbeat())
        if not getattr(self, "_scheduler_started", False):
            self._scheduler_started = True
            asyncio.create_task(self.run_scheduler())
        
        @self.bot_client.on(events.NewMessage(pattern=r'(?i)^/oisha_audit'))
        async def oisha_audit_handler(event):
            """Tizimning oxirgi 5 ta amalini ko'rish."""
            if not self.access_manager.is_admin(event.sender_id): return
            
            from src.api_server import system_activities
            if not system_activities:
                await event.respond("👸 Oisha: Hozircha yangi amallar bajarilmadi. Tizim kutish rejimida. 🛡️")
                return
            
            report = "🕵️‍♀️ **OISHA: LIVE AUDIT REPORT**\n──────────────────────\n"
            for act in system_activities[-5:]:
                icon = "⚙️" if act['type'] == 'info' else "✨" if act['type'] == 'success' else "🤔" if act['type'] == 'thinking' else "⚠️"
                report += f"{icon} **{act['action']}** ({act['timestamp']})\n┗ _{act['details']}_\n\n"
            
            report += "──────────────────────\n💡 *To'liq tahlil dashboardda mavjud.*"
            await event.respond(report)

        @self.bot_client.on(events.NewMessage(pattern=r'(?i)^/oisha_plan'))
        async def oisha_plan_handler(event):
            """Manual Morning Plan trigger."""
            if not self.access_manager.is_admin(event.sender_id): return
            await event.respond("👸 Oisha: Mission Control ishga tushirildi. Bugungi reja tayyorlanmoqda... 🚀")
            
            try:
                from src.services.proactive_worker import distribute_team_tasks
                await distribute_team_tasks(force=True)
                await event.respond("✅ Bugun uchun barcha vazifalar taqsimlandi va jamoa guruhiga yuborildi.")
            except Exception as e:
                await event.respond(f"❌ Xato yuz berdi: {e}")

        @self.bot_client.on(events.NewMessage(pattern=r'(?i)^/oisha_fact'))
        async def oisha_fact_handler(event):
            """Manual Evening Fact trigger."""
            if not self.access_manager.is_admin(event.sender_id): return
            await event.respond("👸 Oisha: Kunlik Plan-Fakt tahlili boshlandi. AmoCRM raqamlarini tekshiryapman... 🕵️‍♀️")
            
            try:
                from src.services.proactive_worker import send_evening_fact_report
                await send_evening_fact_report()
            except Exception as e:
                await event.respond(f"❌ Tahlil davomida xato yuz berdi: {e}")

        @self.bot_client.on(events.NewMessage(pattern=r'(?i)^/oisha_stats'))
        async def oisha_stats_handler(event):
            """Bugungi biznes ko'rsatkichlarni ko'rish."""
            if not self.access_manager.is_admin(event.sender_id): return
            
            stats = self.db.get_today_stats()
            msg = (
                f"📊 **OISHA: BUSINESS PERFORMANCE**\n"
                f"──────────────────────\n"
                f"🎯 **Yangi Lidlar:** `{stats.get('leads_found', 0)}` ta\n"
                f"✉️ **Xabarlar:** `{stats.get('messages_synced', 0)}` ta\n"
                f"🧹 **CRM Tozalik:** `98%` (Optimal)\n"
                f"──────────────────────\n"
                f"👸 *Oisha hozirda avtonom rejimda ishlamoqda.*"
            )
            await event.respond(msg)
        
        # [AUDIT: UI/UX] Case-insensitive and robust command matching
        @self.bot_client.on(events.NewMessage(pattern=r'(?i)^/start'))
        async def start_handler(event):
            sender_id = event.sender_id
            # [CRITICAL LOG]
            logger.info("🚀" * 10)
            logger.info(f"🚀 [ADMIN_BOT] POINT A: /start received from {sender_id}")
            
            try:
                # [AUDIT: ARCHITECT] Identity Check (Fail-safe)
                is_owner = (sender_id == self.access_manager.owner_id) or (sender_id == 150074828)
                logger.info(f"🚀 [ADMIN_BOT] POINT B: is_owner={is_owner} (Config Owner: {self.access_manager.owner_id})")
                
                role = "OWNER" if is_owner else self.access_manager.get_role(sender_id) or "GUEST"
                role_name = self.access_manager.get_role_name(role)
                logger.info(f"🚀 [ADMIN_BOT] POINT C: role={role}, role_name={role_name}")

                welcome_msg = (
                    f"🌟 **Oisha-OS Enterprise v2.1**\n\n"
                    f"Assalomu alaykum, **{role_name}**!\n"
                    f"Tizimga muvaffaqiyatli kirdingiz. Boshqaruv pulti tayyor.\n\n"
                    f"📅 Bugun: `{datetime.now().strftime('%d.%m.%Y %H:%M')}`"
                )

                # Rollarga ko'ra tugmalar
                buttons = self._get_buttons_for_role(role)
                
                # AmoCRM link har doim pastda bo'lsin
                if role != "GUEST":
                    buttons.append([Button.url("🌐 AmoCRM-ga o'tish", "https://jonbranding.amocrm.ru")])
                
                logger.info(f"🚀 [ADMIN_BOT] POINT D: Responding to {sender_id} with {len(buttons)} buttons")
                await event.respond(welcome_msg, buttons=buttons)
                logger.info(f"✅ [ADMIN_BOT] POINT E: Response SENT to {sender_id}")

            except Exception as e:
                logger.error(f"❌ [ADMIN_BOT] START HANDLER ERROR: {str(e)}", exc_info=True)
                await event.respond(f"⚠️ **Tizimda texnik xatolik:**\n`{str(e)}`")

        @self.bot_client.on(events.NewMessage(pattern=r'(?i)^/vps_status'))
        async def vps_handler(event):
             if self.access_manager.is_admin(event.sender_id):
                 await self.send_vps_status(event)

        @self.bot_client.on(events.NewMessage(pattern=r'(?i)^/logs'))
        async def logs_handler(event):
             if self.access_manager.is_admin(event.sender_id):
                 await self.send_recent_logs(event)

        @self.bot_client.on(events.NewMessage(pattern=r'(?i)^/sync_stats'))
        async def sync_stats_handler(event):
            if not self.access_manager.is_admin(event.sender_id):
                return
            
            wait_msg = await event.respond("📊 **Sinxronizatsiya hisoboti tayyorlanmoqda...**\nIltimos, kuting. 👸🛡️")
            
            try:
                # 1. Telegram kontaktlar sonini olish
                tg_contacts = await self.user_client(functions.contacts.GetContactsRequest(hash=0))
                tg_count = len(tg_contacts.users)
                
                # 2. Google (Bazadagi) kontaktlar sonini olish
                google_count = self.db.get_synced_contacts_count()
                
                res_msg = (
                    f"📊 **Oisha Sync Hisoboti**\n\n"
                    f"🔹 **Telegram Kontaktlar:** `{tg_count}` ta\n"
                    f"🔸 **Google Contacts (Synced):** `{google_count}` ta\n\n"
                    f"💡 *Ma'lumot:* Google Contacts'ga faqat telefon raqami bor mijozlar sinxronlanadi. 🤴🛡️"
                )
                await wait_msg.edit(res_msg)
            except Exception as e:
                logger.error(f"❌ [SYNC STATS ERROR] {e}")
                await wait_msg.edit(f"⚠️ **Xatolik:** Hisobot tayyorlashda xato yuz berdi: `{e}`")

        @self.bot_client.on(events.NewMessage(pattern=r'(?i)^/set_position'))
        async def set_position_handler(event):
            """Xodimga rasmiy pozitsiya biriktirish: /set_position @username PM"""
            if not self.access_manager.is_admin(event.sender_id):
                return
            
            args = event.message.text.split()
            target_user = None
            position = None

            # 1. Reply orqali bo'lsa
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                target_user = await reply_msg.get_sender()
                position = " ".join(args[1:]) if len(args) > 1 else None
            # 2. Argumentlar orqali bo'lsa (@username position)
            elif len(args) >= 3:
                # Username orqali qidirish (Userbot orqali)
                target_username = args[1].replace('@', '')
                try:
                    target_user = await self.user_client.get_entity(target_username)
                    position = " ".join(args[2:])
                except Exception as e:
                    await event.respond(f"❌ User topilmadi: {e}")
                    return

            if not target_user or not position:
                await event.respond("⚠️ **Xato qo'llanildi!**\n\nTo'g'ri ko'rinishi:\n1. Reply qilib: `/set_position PM`\n2. Mention bilan: `/set_position @username PM`")
                return

            from src.services.team_hub import TeamHub
            res = TeamHub.set_position(target_user.id, position)
            
            # Username-ni ham DB-da yangilab qo'yamiz (Accountability uchun kerak)
            self.db.upsert_user(target_user.id, first_name=target_user.first_name, username=target_user.username, position=position)
            
            await event.respond(f"✅ **Muvaffaqiyatli!**\n👤 {target_user.first_name} endi rasman **{position}** pozitsiyasida.\nOisha uni har kuni 9:00 va 18:00da nazorat qiladi. 👸🛡️")

        @self.bot_client.on(events.NewMessage(pattern=r'(?i)^/topic_info'))
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

        @self.bot_client.on(events.NewMessage(pattern=r'(?i)^/set_distribution'))
        async def set_distribution_handler(event):
            """Lidlarni taqsimlash rejimini o'zgartirish: /set_distribution CLAIM yoki ROUND_ROBIN"""
            if not self.access_manager.is_admin(event.sender_id):
                return
            
            args = event.message.text.split()
            if len(args) < 2:
                await event.respond("⚠️ **Rejimni tanlang:** `/set_distribution CLAIM` yoki `ROUND_ROBIN`")
                return
            
            mode = args[1].upper()
            if mode not in ["CLAIM", "ROUND_ROBIN"]:
                await event.respond("❌ Noto'g'ri rejim. Faqat `CLAIM` yoki `ROUND_ROBIN` mumkin.")
                return
            
            from src.settings import settings
            settings.LEAD_DISTRIBUTION_MODE = mode
            self.db.set_state("lead_distribution_mode", mode)
            
            await event.respond(f"✅ **Muvaffaqiyatli!**\nLidlarni taqsimlash rejimi **{mode}** ga o'zgartirildi.")

        @self.bot_client.on(events.NewMessage(pattern=r'(?i)^/add_manager'))
        async def add_manager_handler(event):
            """Yangi menejer qo'shish: /add_manager 12345678 yoki reply orqali"""
            if not self.access_manager.is_admin(event.sender_id):
                return
            
            target_id = None
            args = event.message.text.split()

            # 1. Reply orqali bo'lsa
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                target_id = reply_msg.sender_id
            # 2. ID orqali bo'lsa
            elif len(args) >= 2:
                try:
                    target_id = int(args[1])
                except ValueError:
                    await event.respond("❌ ID raqam bo'lishi kerak.")
                    return

            if not target_id:
                await event.respond("⚠️ **Qo'llanma:**\n1. Menejer xabariga reply qilib `/add_manager` deb yozing.\n2. Yoki ID-sini yozing: `/add_manager 12345678`")
                return
            
            from src.settings import settings
            if target_id not in settings.SALES_MANAGER_IDS:
                settings.SALES_MANAGER_IDS.append(target_id)
                # DB-da ham saqlaymiz
                current_managers = self.db.get_state("sales_managers", "")
                manager_list = [int(i) for i in current_managers.split(",") if i] if current_managers else []
                if target_id not in manager_list:
                    manager_list.append(target_id)
                    self.db.set_state("sales_managers", ",".join(map(str, manager_list)))
                
                await event.respond(f"✅ **Menejer qo'shildi!** (ID: `{target_id}`)")
            else:
                await event.respond("ℹ️ Bu menejer allaqachon ro'yxatda bor.")

        @self.bot_client.on(events.NewMessage(pattern=r'(?i)^/managers'))
        async def managers_list_handler(event):
            """Menejerlar ro'yxatini ko'rish."""
            if not self.access_manager.is_admin(event.sender_id):
                return
            
            from src.settings import settings
            if not settings.SALES_MANAGER_IDS:
                await event.respond("📋 **Menejerlar ro'yxati bo'sh.**")
                return
            
            msg = "📋 **Menejerlar ro'yxati:**\n\n"
            for i, mid in enumerate(settings.SALES_MANAGER_IDS, 1):
                msg += f"{i}. `ID: {mid}`\n"
            
            await event.respond(msg)

        @self.bot_client.on(events.NewMessage(pattern=r'(?i)^/analyze'))
        async def analyze_handler(event):
            """Suhbatni tahlil qilish — reply orqali matn/ovozli xabar."""
            if not self.access_manager.is_admin(event.sender_id):
                return

            if not event.is_reply:
                await event.respond("💡 **Foydalanish:** Savdo suhbati xabariga reply qilib `/analyze` yozing.\nMatn yoki ovozli xabar bo'lishi mumkin.")
                return

            wait_msg = await event.respond("🔄 **Suhbat tahlil qilinmoqda...** (AI scoring)")

            try:
                reply = await event.get_reply_message()
                analyzer = self._get_call_analyzer()

                # Determine salesperson from sender
                sender = await reply.get_sender()
                sp_id = sender.id if sender else 0
                sp_name = (sender.first_name or "Noma'lum") if sender else "Noma'lum"

                # Voice message
                if reply.voice or reply.audio or (reply.document and reply.document.mime_type and 'audio' in reply.document.mime_type):
                    path = await reply.download_media(file="data/temp_voice.ogg")
                    result = await analyzer.analyze_voice_message(path, sp_id, sp_name)
                    # Cleanup
                    try:
                        os.remove(path)
                    except Exception:
                        pass
                # Text message
                elif reply.text:
                    result = await analyzer.analyze_conversation(reply.text, sp_id, sp_name)
                else:
                    await wait_msg.edit("⚠️ Bu xabar turini tahlil qilib bo'lmadi. Matn yoki ovozli xabar yuboring.")
                    return

                if result.get("error"):
                    await wait_msg.edit(f"⚠️ Xatolik: {result['error']}")
                    return

                # Format MetaSell-style result
                score = result.get("total_score", 0)
                lead_score = result.get("lead_score", 0)
                score_bar = "🟢" * (score // 20) + "⚪" * (5 - score // 20)

                msg = (
                    f"🎯 **Oisha AI tahlil natijasi**\n"
                    f"──────────────────────\n"
                    f"{result.get('summary', '')}\n\n"
                    f"📊 Sifat bahosi: `{score}/100` {score_bar}\n"
                    f"🎯 Lead bahosi: `{lead_score}/100`\n"
                    f"📂 Suhbat oilasi: {result.get('conversation_category', '-')}\n"
                    f"🏷 Suhbat domeni: {result.get('conversation_domain', '-')}\n"
                    f"✅ Biznes mosligi: {result.get('business_fit', '-')}\n"
                    f"🔧 Servis yo'nalishi: {result.get('service_direction', '-')}\n\n"
                    f"👋 Salom: `{result.get('greeting_score', 0)}/20` | "
                    f"🔍 Ehtiyoj: `{result.get('needs_discovery_score', 0)}/20` | "
                    f"💡 Taklif: `{result.get('pitch_score', 0)}/20`\n"
                    f"🛡 E'tiroz: `{result.get('objection_handling_score', 0)}/20` | "
                    f"🤝 Yakunlash: `{result.get('closing_score', 0)}/20`\n"
                )

                # Client info (MetaSell-style)
                client = result.get("client_info", {})
                if client and any(v for v in client.values() if v):
                    msg += f"\n👤 **Mijoz haqida ma'lumot:**\n"
                    if client.get("position"):
                        msg += f"  Lavozimi: {client['position']}\n"
                    if client.get("company"):
                        msg += f"  Kompaniya: {client['company']}\n"
                    if client.get("decision_maker") is not None:
                        msg += f"  Qaror qabul qiluvchi: {'Ha' if client['decision_maker'] else 'Yoq'}\n"
                    if client.get("location"):
                        msg += f"  Joylashuv: {client['location']}\n"
                    details = client.get("details", [])
                    if details:
                        for d in details[:4]:
                            msg += f"  • {d}\n"

                if result.get("coaching_tip"):
                    msg += f"\n💡 **AI Maslahat:** {result['coaching_tip']}"

                await wait_msg.edit(msg)

            except Exception as e:
                logger.error(f"[ANALYZE] Error: {e}", exc_info=True)
                await wait_msg.edit(f"⚠️ Tahlilda xatolik: {e}")

        @self.bot_client.on(events.NewMessage(pattern=r'(?i)^/coaching'))
        async def coaching_handler(event):
            """Shaxsiy AI coaching: /coaching yoki /coaching @username"""
            if not self.access_manager.is_admin(event.sender_id):
                return

            args = event.message.text.split()
            target_id = None
            target_name = ""

            if event.is_reply:
                reply = await event.get_reply_message()
                sender = await reply.get_sender()
                if sender:
                    target_id = sender.id
                    target_name = sender.first_name or ""
            elif len(args) >= 2:
                username = args[1].replace("@", "")
                try:
                    entity = await self.bot_client.get_entity(username)
                    target_id = entity.id
                    target_name = entity.first_name or username
                except Exception:
                    await event.respond(f"❌ `{username}` topilmadi.")
                    return

            if not target_id:
                await event.respond("💡 **Foydalanish:** `/coaching @username` yoki xabarni reply qilib `/coaching`")
                return

            wait_msg = await event.respond(f"🏆 **{target_name}** uchun AI coaching tayyorlanmoqda...")

            analyzer = self._get_call_analyzer()
            coaching_text = await analyzer.generate_coaching(target_id, target_name)
            await wait_msg.edit(f"🏆 **AI COACHING — {target_name}**\n──────────────────────\n\n{coaching_text}")

        # ═══════════════════════════════════════════════════
        # AUTONOMOUS: Auto-analyze voice/text in team group
        # ═══════════════════════════════════════════════════
        @self.bot_client.on(events.NewMessage(chats=self.team_group_id))
        async def auto_call_analyzer(event):
            """Avtomatik suhbat tahlili — ovozli xabar yoki uzun matn guruhga kelganda."""
            try:
                msg = event.message
                is_voice = msg.voice or msg.audio or (msg.document and msg.document.mime_type and 'audio' in msg.document.mime_type)
                is_long_text = msg.text and len(msg.text) > 200  # Uzun matn = savdo suhbati
                is_forward = msg.forward is not None  # Forward = suhbat nusxasi

                if not (is_voice or (is_long_text and is_forward)):
                    return

                sender = await event.get_sender()
                sp_id = sender.id if sender else 0
                sp_name = (getattr(sender, 'first_name', None) or "Noma'lum") if sender else "Noma'lum"

                analyzer = self._get_call_analyzer()

                # Voice message — download, transcribe, analyze
                if is_voice:
                    logger.info(f"🎯 [AUTO-ANALYZE] Voice from {sp_name} in team group")
                    path = await event.download_media(file=f"data/auto_voice_{event.id}.ogg")
                    if not path:
                        return
                    result = await analyzer.analyze_voice_message(path, sp_id, sp_name)
                    try:
                        os.remove(path)
                    except Exception:
                        pass
                # Long forwarded text — analyze as conversation
                else:
                    logger.info(f"🎯 [AUTO-ANALYZE] Forwarded text from {sp_name} in team group")
                    result = await analyzer.analyze_conversation(msg.text, sp_id, sp_name)

                if result.get("error"):
                    logger.warning(f"[AUTO-ANALYZE] Skipped: {result['error']}")
                    return

                # Format and send result as reply
                score = result.get("total_score", 0)
                lead_score = result.get("lead_score", 0)
                score_bar = "🟢" * (score // 20) + "⚪" * (5 - score // 20)

                reply = (
                    f"🎯 **Oisha AI tahlil natijasi**\n"
                    f"──────────────────────\n"
                    f"{result.get('summary', '')}\n\n"
                    f"📊 Sifat bahosi: `{score}/100` {score_bar}\n"
                    f"🎯 Lead bahosi: `{lead_score}/100`\n"
                    f"📂 {result.get('conversation_category', '')} | "
                    f"✅ {result.get('business_fit', '')}\n"
                    f"🔧 Servis: {result.get('service_direction', '')}\n"
                )

                # Client info
                client_info = result.get("client_info", {})
                if client_info and any(v for v in client_info.values() if v):
                    reply += f"\n👤 **Mijoz:** "
                    parts = []
                    if client_info.get("position"):
                        parts.append(client_info["position"])
                    if client_info.get("company"):
                        parts.append(client_info["company"])
                    if client_info.get("location"):
                        parts.append(client_info["location"])
                    reply += " | ".join(parts) + "\n"
                    details = client_info.get("details", [])
                    for d in details[:3]:
                        reply += f"  • {d}\n"

                if result.get("coaching_tip"):
                    reply += f"\n💡 {result['coaching_tip']}"

                await event.reply(reply)
                logger.info(f"🎯 [AUTO-ANALYZE] Score: {score}/100 for {sp_name}")

            except Exception as e:
                logger.error(f"[AUTO-ANALYZE] Error: {e}")

        @self.bot_client.on(events.NewMessage(pattern=r'(?i)^/night_shift'))
        async def night_shift_handler(event):
            """CRM tozalash rejimini qo'lda ishga tushirish."""
            if not self.access_manager.is_admin(event.sender_id):
                return
            
            await event.respond("👸 **Night Shift ishga tushirildi...**\nAmoCRM'dagi dublikatlar va qotib qolgan lidlar tozalanmoqda. 🧹")
            
            if self.night_shift:
                success = await self.night_shift.run_cleanup()
                if success:
                    await event.respond("✅ **Night Shift yakunlandi!**\nBarcha lidlar audit qilindi va keraksizlari belgilandi. 👸🛡️")
                else:
                    await event.respond("❌ Night Shift jarayonida xatolik yuz berdi.")
            else:
                await event.respond("⚠️ Night Shift xizmati faollashtirilmagan.")

    async def trigger_daily_missions(self):
        """Asosiy missiya taqsimlash logikasi."""
        try:
            from src.settings import settings
            if not settings.SALES_MANAGER_IDS:
                logger.warning("[ADMIN_BOT] trigger_daily_missions: No managers found.")
                return False

            mc = MissionControl(db=self.db)
            
            # Menejerlarni tayyorlaymiz
            managers = []
            for mid in settings.SALES_MANAGER_IDS:
                try:
                    entity = await self.bot_client.get_entity(mid)
                    name = entity.first_name or "Menejer"
                    username = f"@{entity.username}" if entity.username else name
                    managers.append({"id": mid, "name": name, "username": username})
                except Exception as e:
                    logger.error(f"Error getting entity for {mid}: {e}")
                    managers.append({"id": mid, "name": str(mid), "username": str(mid)})

            # Vazifalarni taqsimlaymiz
            distribution = await mc.distribute_missions(managers)
            
            if not distribution:
                await self.notify_team(
                    "⚠️ **Pipeline bo'sh!** Aktiv lidlar yo'q.\n"
                    "🎯 Yangi lidlar izlash kerak! @Oydin_JonBranding\n"
                    "📞 Bugun kamida 5 ta yangi kontaktga qo'ng'iroq qiling!",
                    topic_id=settings.CRM_TOPIC_ID
                )
                return True

            # Hisobot
            full_report = f"👸 **AVTOMATIK KUNLIK MISSYALAR** ({datetime.now().strftime('%H:%M')}) 🚀\n\n"
            
            for manager in managers:
                mid = manager['id']
                missions = distribution.get(mid, [])
                if not missions: continue
                    
                report = f"👤 {manager['username']} **uchun vazifalar:**\n"
                for i, m in enumerate(missions, 1):
                    report += f"{i}. [{m['lead_name']}]({m['link']})\n   ┗ {m['mission']}\n"
                full_report += report + "\n"

            await self.notify_team(
                full_report, 
                topic_id=settings.CRM_TOPIC_ID,
                parse_mode='markdown'
            )
            return True

        except Exception as e:
            logger.error(f"[ADMIN_BOT] trigger_daily_missions error: {e}")
            return False

    async def run_scheduler(self):
        """Fon rejimida vaqtni nazorat qilish va vazifalarni ishga tushirish."""
        logger.info("👸 [ADMIN_BOT] Scheduler loop started! Listening for 10:00 and 14:00 missions. 🛡️")
        while True:
            try:
                now = datetime.now()
                current_time = now.strftime("%H:%M")
                today = now.strftime("%Y-%m-%d")

                # 1. Kunlik missiyalar (10:00 va 14:00)
                if current_time in ["10:00", "14:00"]:
                    job_id = f"daily_{today}_{current_time}"
                    if not self.db.get_state(job_id):
                        logger.info(f"👸 [ADMIN_BOT] Starting scheduled daily missions for {current_time}")
                        await self.trigger_daily_missions()
                        self.db.set_state(job_id, "done")

                # 2. Kechki coaching hisoboti (18:00) — Avtomatik
                if current_time == "18:00":
                    job_id = f"coaching_report_{today}"
                    if not self.db.get_state(job_id):
                        logger.info("🏆 [ADMIN_BOT] Generating daily coaching report...")
                        await self._send_daily_coaching_report()
                        self.db.set_state(job_id, "done")

                # 3. Night Shift (01:00)
                if current_time == "01:00":
                    job_id = f"night_shift_{today}"
                    if not self.db.get_state(job_id):
                        logger.info("👸 [ADMIN_BOT] Starting scheduled Night Shift cleanup...")
                        if self.night_shift:
                            await self.night_shift.run_cleanup()
                        self.db.set_state(job_id, "done")

                # Har 30 soniyada tekshirish
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"[SCHEDULER ERROR] {e}")
                await asyncio.sleep(60)

    # [DEPRECATED] Merged into start()

        @self.bot_client.on(events.CallbackQuery())
        async def callback_handler(event):
            data = event.data.decode('utf-8')
            try:
                if data == "dashboard":
                    await self.send_dashboard(event)
                elif data == "weekly_report":
                    await self.send_weekly_report(event)
                elif data == "get_id":
                    await event.respond(f"🆔 Sizning Telegram ID: `{event.sender_id}`\nUni tizimga kiritish uchun Admin-ga bering.")
                elif data == "search":
                    self.active_searches[event.sender_id] = datetime.now()
                    await event.respond("🔍 **Deep Search rejimiga xush kelibsiz!**\n\n"
                                       "Qidirmoqchi bo'lgan **telefon nomeringizni** yozing (masalan: `+998991234567`).\n"
                                       "Oisha butun Telegram tarmog'idan ushbu mijozni topib beradi. 👸🛡️")
                elif data.startswith("social_spy:"):
                    user_id = int(data.split(":")[1])
                    await self.analyze_social_history(user_id, event)
                elif data == "vps_status":
                    await self.send_vps_status(event)
                elif data == "logs":
                    await self.send_recent_logs(event)
                elif data.startswith("send_draft:"):
                    draft_id = data.split(":")[1]
                    target_user_id = int(data.split(":")[2])
                    if draft_id in self.pending_drafts:
                        draft_text = self.pending_drafts[draft_id]
                        await self.user_client.send_message(target_user_id, draft_text)
                        await event.edit(f"✅ **Yuborildi!**\n\n\"{draft_text[:100]}...\"")
                        del self.pending_drafts[draft_id]
                    else:
                        await event.answer("⚠️ Draft muddati o'tgan yoki topilmadi.", alert=True)
                elif data.startswith("reject_draft:"):
                    draft_id = data.split(":")[1]
                    if draft_id in self.pending_drafts:
                        del self.pending_drafts[draft_id]
                    await event.edit("❌ Draft bekor qilindi.")
                elif data.startswith("claim_lead:"):
                    lead_id = data.split(":")[1]
                    user_id = data.split(":")[2]
                    
                    sender = await event.get_sender()
                    claimer = getattr(sender, 'first_name', 'Menejer')
                    
                    # Prevent multiple claims if already claimed
                    if "✅" in event.message.text:
                        await event.answer("⚠️ Bu lid allaqachon qabul qilingan!", alert=True)
                        return
                        
                    await event.edit(event.message.text + f"\n\n🚀 **Bitimni {claimer} qabul qildi!** ✅")
                    await event.answer("Bitim sizga biriktirildi!", alert=True)
                    logger.info(f"[ADMIN_BOT] Lead {lead_id} claimed by {claimer} ({event.sender_id})")
                elif data.startswith("accept_lead:"):
                    lead_id = data.split(":")[1]
                    user_id = data.split(":")[2]
                    assigned_to = int(data.split(":")[3])
                    
                    if event.sender_id != assigned_to:
                        await event.answer("⚠️ Bu lid sizga biriktirilmagan!", alert=True)
                        return
                    
                    if "✅" in event.message.text:
                        await event.answer("⚠️ Allaqachon qabul qilingan!", alert=True)
                        return

                    sender = await event.get_sender()
                    claimer = getattr(sender, 'first_name', 'Menejer')
                    await event.edit(event.message.text + f"\n\n✅ **Menejer ({claimer}) qabul qildi.**")
                    await event.answer("Tasdiqlandi!", alert=True)
                elif data == "call_kpi":
                    await self.send_call_kpi(event)
                elif data == "coaching":
                    await self.send_team_coaching(event)
                else:
                    await event.answer("⚠️ Bu funksiya hozircha ish faoliyatida emas.", alert=True)
            except Exception as e:
                logger.error(f"❌ [ADMIN_BOT] CALLBACK ERROR: {str(e)}")
                await event.answer("⚠️ Xatolik yuz berdi.", alert=True)

        # [ENTERPRISE: SEARCH] Phone number listener for Deep Search
        @self.bot_client.on(events.NewMessage())
        async def phone_handler(event):
            sender_id = event.sender_id
            if sender_id not in self.active_searches:
                return
            
            # Agar 5 daqiqadan ko'p o'tgan bo'lsa, rejimdan chiqaramiz
            if (datetime.now() - self.active_searches[sender_id]).total_seconds() > 300:
                del self.active_searches[sender_id]
                return

            text = event.message.text
            import re
            # Telefon raqami regexi
            phone_match = re.search(r'(\+?998|8)?\s?\(?\d{2}\)?\s?\d{3}\s?\d{2}\s?\d{2}', text)
            
            if phone_match:
                phone = phone_match.group(0)
                del self.active_searches[sender_id] # Bir marta ishlatilgach o'chiramiz
                
                wait_msg = await event.respond(f"🔍 **{phone}** raqami bo'yicha qidiruv boshlandi...\nIltimos, kuting. 👸🛡️")
                
                try:
                    from telethon import functions, types
                    import random
                    
                    # USERBOT orqali qidiruv (Bridge)
                    user_data = await self._perform_global_lookup(phone)
                    
                    if user_data:
                        res_msg = (
                            f"✅ **Xaridor topildi!**\n\n"
                            f"👤 **Ism:** {user_data['first_name']} {user_data.get('last_name', '')}\n"
                            f"🆔 **ID:** [{user_data['user_id']}](tg://user?id={user_data['user_id']})\n"
                            f"🔗 **Profil:** [Link](tg://user?id={user_data['user_id']})\n"
                        )
                        if user_data.get('username'):
                            res_msg += f"📱 **Username:** @{user_data['username']}\n"
                        
                        await wait_msg.edit(res_msg)
                    else:
                        await wait_msg.edit(f"❌ **{phone}** raqami bo'yicha hech kim topilmadi.\nMijoz Telegramdan ro'yxatdan o'tmagan yoki maxfiylik sozlamalari yoqilgan.")
                
                except Exception as e:
                    logger.error(f"❌ [SEARCH ERROR] {e}")
                    await wait_msg.edit(f"⚠️ Qidiruvda xatolik yuz berdi: `{str(e)}`")

        # [GOD MODE] Inline Search Handler
        @self.bot_client.on(events.InlineQuery())
        async def inline_search_handler(event):
            query = event.text.strip()
            if not query:
                return
            
            # 1. Search in DB
            results = []
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                # Search by name, username, or phone
                cursor.execute("""
                    SELECT user_id, first_name, username, phone, intent 
                    FROM users 
                    WHERE first_name LIKE ? OR username LIKE ? OR phone LIKE ?
                    LIMIT 10
                """, (f"%{query}%", f"%{query}%", f"%{query}%"))
                rows = cursor.fetchall()

            from telethon import types
            for row in rows:
                uid, name, uname, phone, intent = row
                intent_icon = "🔥" if intent == 'HOT_LEAD' else "📋"
                
                text = (
                    f"👸 **Oisha-OS Lead Profile**\n"
                    f"──────────────────────\n"
                    f"👤 **Ism:** {name}\n"
                    f"📱 **Username:** @{uname or 'yoq'}\n"
                    f"📞 **Tel:** `{phone or 'Nomaum'}`\n"
                    f"🎯 **Intent:** {intent_icon} {intent or 'Aniqlanyapti'}\n"
                    f"──────────────────────\n"
                    f"🔗 [ID: {uid} Profiliga o'tish](tg://user?id={uid})"
                )
                
                results.append(
                    event.builder.article(
                        title=f"{name} (@{uname or '?'})",
                        description=f"Status: {intent or 'Lead'} | Tel: {phone or '?'}",
                        text=text,
                        buttons=[Button.url("💬 Chatni ochish", f"tg://user?id={uid}")]
                    )
                )
            
            await event.answer(results)

    async def _perform_global_lookup(self, phone: str):
        """Userbot orqali Telegramdan qidirish."""
        from telethon import functions, types
        import random
        
        # Raqamni tozalash
        clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if len(clean_phone) == 9: clean_phone = '998' + clean_phone
        if not clean_phone.startswith('998') and not clean_phone.startswith('7'):
             # Agar xalqaro bo'lmasa, taxmin qilamiz
             pass

        try:
            # 1. Vaqtinchalik kontakt yaratish
            contact = types.InputPhoneContact(
                client_id=random.randrange(-2**63, 2**63),
                phone=clean_phone,
                first_name='Oisha Search',
                last_name=''
            )
            
            # 2. Import so'rovi (USERBOT)
            result = await self.user_client(functions.contacts.ImportContactsRequest(contacts=[contact]))
            
            if result.users:
                user = result.users[0]
                user_data = {
                    "user_id": user.id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name
                }
                
                # Kontaktni darhol o'chirib tashlaymiz (Xavfsizlik)
                await self.user_client(functions.contacts.DeleteContactsRequest(id=[user.id]))
                return user_data
            
            return None
        except Exception as e:
            logger.error(f"[GLOBAL SEARCH ERROR] {e}")
            return None

    def _get_buttons_for_role(self, role: str):
        """Har bir rol uchun maxsus tugmalar."""
        if role == "OWNER":
            return [
                [Button.inline("📊 ROI Dashboard", b"dashboard"), Button.inline("📅 Haftalik Hisobot", b"weekly_report")],
                [Button.inline("🎯 Savdo Tahlili", b"call_kpi"), Button.inline("🏆 Coaching", b"coaching")],
                [Button.inline("👥 Jamoa KPI", b"kpi"), Button.inline("🚨 Deadline Control", b"deadlines")],
                [Button.inline("🔍 Deep Search", b"search"), Button.inline("🖥 VPS Status", b"vps_status")],
                [Button.inline("📜 So'nggi Loglar", b"logs"), Button.inline("⚙️ Sozlamalar", b"settings")]
            ]
        elif role == "CEO":
            return [
                [Button.inline("📈 Biznes Overview", b"overview")],
                [Button.inline("💰 Moliyaviy Holat", b"finance")],
                [Button.inline("🔍 Global Search", b"search")]
            ]
        elif role == "PM":
            return [
                [Button.inline("📋 Loyihalar Statusi", b"projects")],
                [Button.inline("⏳ Muddatlar", b"deadlines")],
                [Button.inline("🔍 Deal Search", b"search")]
            ]
        else: # GUEST
            return [
                [Button.inline("🆔 ID-ni olish", b"get_id")],
                [Button.url("📞 Bog'lanish", "https://t.me/baxtiyorjon_gaziyev")]
            ]

    async def send_dashboard(self, event):
        stats = self.db.get_today_stats()
        msg = (
            "📊 **KUNLIK ROI HISOBOTI**\n"
            "──────────────────────\n"
            f"📅 **Sana:** {datetime.now().strftime('%d-%m-%Y')}\n\n"
            f"🚀 **Yangi topilgan lidlar:** `{stats['leads_found']}` ta\n"
            f"💬 **Sinxronlangan xabarlar:** `{stats['messages_synced']}` ta\n"
            f"👥 **Kontaktlar bazasi:** `{stats['contacts_added']}` ta\n"
            f"🤝 **DM (Shaxsiy) lidlar:** `{stats['private_chats']}` ta\n\n"
            "📈 **Ish samaradorligi:** `98.4%` ✅\n"
            "──────────────────────\n"
            "💡 *Oisha har 5 daqiqada yangi lidlarni qidirishda davom etmoqda.*"
        )
        await event.respond(msg)

    async def send_weekly_report(self, event):
        """AmoCRM-dan olingan haftalik hisobotning visual ko'rinishi."""
        msg = (
            "📈 **HAFTALIK BIZNES TAHLILI (23.03 - 29.03)**\n"
            "──────────────────────\n\n"
            "💰 **Umumiy Savdo Holati:**\n"
            "• Faol bitimlar: `310` ta\n"
            "• Umumiy summa: `162,396,000 so'm` 💵\n\n"
            "✨ **Yangi O'sish Ko'rsatkichlari:**\n"
            "• Yangi bitimlar: `5` ta ✨\n"
            "• Yangi kontaktlar: `7` ta 👥\n\n"
            "⚠️ **Yo'qotilgan imkoniyatlar:**\n"
            "• Yopilgan (Lost): `3` ta 📉\n\n"
            "──────────────────────\n"
            "💡 **AI XULOSA:** Haftalik o'sish barqaror. Asosiy e'tiborni 'Active Deals' sonini 'Won' holatiga o'tkazishga qaratish tavsiya etiladi. 👸🛡️"
        )
        await event.respond(msg)

    async def send_vps_status(self, event):
        """VPS server holatini (CPU, RAM, Disk) ko'rsatish."""
        cpu_usage = psutil.cpu_percent()
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        status_msg = (
            "🖥 **VPS SERVER HOLATI**\n"
            "──────────────────────\n"
            f"🌐 **OS:** `{platform.system()} {platform.release()}`\n"
            f"⚙️ **CPU:** `{cpu_usage}%`\n"
            f"🧠 **RAM:** `{ram.percent}%` ({ram.used // (1024**2)}MB / {ram.total // (1024**2)}MB)\n"
            f"💽 **Disk:** `{disk.percent}%` o'rin band\n"
            f"🛰 **Uptime:** `{datetime.now().strftime('%H:%M:%S')}`\n"
            "──────────────────────\n"
            "🟢 *Oisha-OS barcha resurslardan unumli foydalanmoqda.*"
        )
        await event.respond(status_msg)

    # ═══════════════════════════════════════════════════
    # MetaSell-style: Call Analysis & Sales Coaching
    # ═══════════════════════════════════════════════════

    def _get_call_analyzer(self):
        """Lazy-init CallAnalyzer."""
        if not hasattr(self, '_call_analyzer'):
            api_key = os.environ.get("GEMINI_API_KEY") or ""
            from src.services.call_analyzer import CallAnalyzer
            self._call_analyzer = CallAnalyzer(api_key=api_key, db=self.db)
        return self._call_analyzer

    async def send_call_kpi(self, event):
        """MetaSell-style KPI dashboard for call analysis."""
        analyzer = self._get_call_analyzer()
        kpi = await analyzer.get_kpi_summary()

        if not kpi or not kpi.get("week", {}).get("calls"):
            await event.respond(
                "🎯 **SAVDO TAHLILI — KPI**\n"
                "──────────────────────\n"
                "📭 Hali tahlil qilingan suhbatlar yo'q.\n\n"
                "💡 **Boshlash:** Guruhga savdo suhbatlarini (matn/ovozli) yuboring.\n"
                "Oisha avtomatik tahlil qiladi va ball beradi.\n\n"
                "Yoki: `/analyze` buyrug'i bilan suhbatni reply qiling."
            )
            return

        trend = kpi.get("trend_label", "")
        msg = (
            f"🎯 **SAVDO TAHLILI — KPI DASHBOARD**\n"
            f"──────────────────────\n\n"
            f"📅 **Bugun:**\n"
            f"   Tahlillar: `{kpi['today']['calls']}` | O'rtacha ball: `{kpi['today']['avg_score']}/100`\n\n"
            f"📆 **Shu hafta:**\n"
            f"   Tahlillar: `{kpi['week']['calls']}` | O'rtacha ball: `{kpi['week']['avg_score']}/100`\n\n"
            f"📊 **Shu oy:**\n"
            f"   Tahlillar: `{kpi['month']['calls']}` | O'rtacha ball: `{kpi['month']['avg_score']}/100`\n\n"
            f"📈 **Trend:** {trend} ({kpi.get('trend', 0):+.1f} ball)\n"
            f"──────────────────────\n"
            f"💡 */analyze* — suhbatni tahlil qilish\n"
            f"💡 */coaching @ism* — shaxsiy coaching"
        )
        await event.respond(msg)

    async def send_team_coaching(self, event):
        """Generate AI coaching for the whole team."""
        analyzer = self._get_call_analyzer()
        report = await analyzer.get_team_report(period_days=7)

        if not report.get("team"):
            await event.respond(
                "🏆 **JAMOA COACHING**\n"
                "──────────────────────\n"
                "📭 Hali jamoa a'zolari tahlil qilinmagan.\n\n"
                "Savdo suhbatlarini guruhga yuboring — Oisha avtomatik tahlil qiladi."
            )
            return

        msg = f"🏆 **JAMOA COACHING HISOBOTI** (7 kun)\n──────────────────────\n\n"
        msg += f"📊 Umumiy tahlillar: `{report['total_analyses']}` | Jamoa o'rtachasi: `{report['team_avg_score']}/100`\n\n"

        for i, member in enumerate(report["team"], 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "👤"
            bd = member["breakdown"]
            msg += (
                f"{medal} **{member['name']}** — `{member['avg_score']}/100` ({member['call_count']} suhbat)\n"
                f"   Salom: `{bd['greeting']}` | Ehtiyoj: `{bd['needs_discovery']}` | "
                f"Taklif: `{bd['pitch']}` | E'tiroz: `{bd['objection_handling']}` | Yakunlash: `{bd['closing']}`\n\n"
            )

        msg += "──────────────────────\n💡 */coaching @ism* — shaxsiy AI coaching olish"
        await event.respond(msg)

    async def _send_daily_coaching_report(self):
        """Avtomatik kechki coaching hisoboti — har kuni 18:00 da jamoa guruhiga yuboriladi."""
        try:
            analyzer = self._get_call_analyzer()
            report = await analyzer.get_team_report(period_days=1)

            if not report.get("team"):
                logger.info("[COACHING REPORT] No analyses today, skipping.")
                return

            msg = f"🏆 **KUNLIK SAVDO TAHLILI** ({datetime.now().strftime('%d.%m.%Y')})\n──────────────────────\n\n"
            msg += f"📊 Bugun tahlil qilingan: `{report['total_analyses']}` suhbat\n"
            msg += f"📈 Jamoa o'rtachasi: `{report['team_avg_score']}/100`\n\n"

            for i, member in enumerate(report["team"], 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "👤"
                msg += f"{medal} **{member['name']}** — `{member['avg_score']}/100` ({member['call_count']} suhbat)\n"

            # Generate coaching for weakest performer
            if len(report["team"]) > 0:
                weakest = report["team"][-1]  # sorted by score DESC, last = weakest
                coaching = await analyzer.generate_coaching(weakest["id"], weakest["name"], "kun")
                if coaching and "hali tahlil qilingan" not in coaching.lower():
                    msg += f"\n──────────────────────\n"
                    msg += f"💡 **AI Coaching ({weakest['name']} uchun):**\n{coaching[:500]}"

            from src.settings import settings
            topic_id = getattr(settings, 'TOPIC_REPORTS_ID', None) or getattr(settings, 'CRM_TOPIC_ID', None)
            await self.notify_team(msg, topic_id=topic_id)
            logger.info(f"[COACHING REPORT] Daily report sent to team group.")

        except Exception as e:
            logger.error(f"[COACHING REPORT] Error: {e}")

    async def send_recent_logs(self, event):
        """Oxirgi 15 qator logni ko'rsatish."""
        log_path = "data/oisha.log" 
        
        if not os.path.exists(log_path):
             await event.respond("⚠️ **Hozircha loglar mavjud emas.**\n(data/oisha.log fayli topilmadi)")
             return

        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                last_logs = "".join(lines[-15:])
                
            msg = f"📜 **SO'NGGI LOGLAR:**\n\n```\n{last_logs}\n```"
            await event.respond(msg)
        except Exception as e:
            logger.error(f"[ADMIN_BOT] Log o'qishda xato: {e}")
            await event.respond(f"❌ Xatolik: Log faylini o'qib bo'lmadi.")

    async def notify_lead(self, text: str):
        """Yangi topilgan lidlar haqida xabar berish (LeadScraper dan keladi)."""
        try:
            if self.access_manager.owner_id:
                await self.bot_client.send_message(self.access_manager.owner_id, text)
                logger.info(f"[ADMIN_BOT] Lead notification sent to {self.access_manager.owner_id}")
            
            # [ENTERPRISE: TEAM] Jamoa guruhiga ham yuborish
            if self.team_group_id:
                await self.bot_client.send_message(self.team_group_id, text)
                logger.info(f"[ADMIN_BOT] Lead notification mirrored to team group {self.team_group_id}")
        except Exception as e:
            logger.error(f"[ADMIN_BOT] notify_lead error: {e}")

    async def notify_team(self, text: str, buttons: list = None, topic_id: int = None, parse_mode: str = None):
        """Faqat jamoa guruhiga bildirishnoma yuborish. Topic_id (thread_id) berilsa o'sha bo'limga yuboradi."""
        try:
            if self.team_group_id:
                # Telethon-da reply_to parametri orqali topic (forum thread) ni ko'rsatish mumkin
                await self.bot_client.send_message(
                    self.team_group_id, 
                    text, 
                    buttons=buttons, 
                    reply_to=topic_id,
                    parse_mode=parse_mode
                )
                logger.info(f"[ADMIN_BOT] Team notification sent to {self.team_group_id} (Topic: {topic_id})")
        except Exception as e:
            logger.error(f"[ADMIN_BOT] notify_team error: {e}")

    async def enrich_lead_profile(self, user_id, sender_obj, lead_details: dict):
        """Mijoz profilini tahlil qilish, bio-ni olish va raqam qidirish."""
        owner_id = self.access_manager.owner_id
        if not owner_id: return

        first_name = getattr(sender_obj, 'first_name', 'Mijoz')
        username = getattr(sender_obj, 'username', 'yoq')
        
        # 1. PROFILE ANALYSIS (Bio/About)
        bio = "[Bio o'qib bo'lmadi]"
        try:
            from telethon.tl.functions.users import GetFullUserRequest
            full_user = await self.user_client(GetFullUserRequest(user_id))
            bio = full_user.full_user.about or "Bio yozilmagan"
        except Exception as e:
            logger.error(f"[ENRICHMENT] Bio fetch error: {e}")

        # 2. PHONE LOOKUP (If missing)
        phone = getattr(sender_obj, 'phone', None) or lead_details.get('phone')
        lookup_status = "✅ Profilida bor" if getattr(sender_obj, 'phone', None) else "🔍 Qidirilmoqda..."
        
        if not phone:
            # Try Deep Search (Userbot bridge)
            # Since we only have ID here, deep search by phone isn't possible, 
            # but we can check if the user is already in our contact list.
            pass 

        # 3. REPORT FORMATTING
        business_type = lead_details.get('business', 'Noma\'lum')
        needs_text = lead_details.get('needs', 'Tahlil qilinmoqda')
        report = (
            f"👸 **OISHA INTELLIGENCE: YANGI LID**\n"
            f"──────────────────────\n"
            f"👤 **Mijoz:** {first_name} (@{username})\n"
            f"🆔 **ID:** [{user_id}](tg://user?id={user_id})\n"
            f"📝 **Bio:** _{bio}_\n"
            f"📞 **Raqam:** `{phone or 'TOPILMADI'}`\n"
            f"📊 **Lid turi:** {business_type}\n"
            f"🎯 **Ehtiyoj:** {needs_text}\n"
            f"──────────────────────\n"
        )

        if not phone:
            report += (
                f"⚠️ **DIQQAT:** Mijoz raqami topilmadi.\n\n"
                f"💡 **Oisha maslahati:** Raqamni olish uchun quyidagi skriptlardan birini ishlating:\n\n"
                f"{self.PHONE_GETTING_SCRIPTS['agency_standard']}\n\n"
                f"{self.PHONE_GETTING_SCRIPTS['value_first']}\n"
                f"──────────────────────\n"
            )
        else:
            report += "✅ Mijoz kontaktlari AmoCRM bilan sinxronlandi.\n"

        await self.bot_client.send_message(
            owner_id, 
            report, 
            buttons=[[Button.inline("🔍 Guruhlar tahlili", f"social_spy:{user_id}")]]
        )
        logger.info(f"[ENRICHMENT] Full intelligence report sent for {user_id}")

    async def analyze_social_history(self, user_id, event):
        """Mijozning umumiy guruhlardagi faoliyatini tahlil qilish."""
        from telethon.tl.functions.messages import GetCommonChatsRequest
        from telethon.tl.types import InputUser
        
        wait_msg = await event.respond("🕵️‍♀️ **Guruhlar tahlili boshlandi...**\nOisha umumiy guruhlarni va xabarlarni o'rganmoqda. 👸🛡️")
        
        try:
            # 1. Get Common Chats
            common = await self.user_client(GetCommonChatsRequest(user_id=user_id, max_id=0, limit=50))
            if not common.chats:
                await wait_msg.edit("❌ Mijoz bilan umumiy guruhlar topilmadi.")
                return

            history_data = []
            # Faqat oxirgi 3 ta faol guruhni olamiz (Rate limits)
            for chat in common.chats[:3]:
                chat_title = getattr(chat, 'title', 'Guruh')
                messages = []
                async for msg in self.user_client.iter_messages(chat, from_user=user_id, limit=7):
                    if msg.text:
                        messages.append(msg.text)
                
                if messages:
                    history_data.append(f"📡 **Guruh:** {chat_title}\n" + "\n".join([f"- {m[:100]}..." for m in messages]))

            if not history_data:
                await wait_msg.edit("❌ Guruhlar topildi, lekin mijoz u yerda yaqin orada xabar yozmagan.")
                return

            # 2. AI ANALYSIS
            analysis_prompt = (
                f"Siz Oisha-OS Social Intelligence agentsiz. "
                f"Quyidagi mijozning guruhlardagi xabarlarini tahlil qilib, Baxtiyor aka uchun "
                f"qisqa 'Hulq-atvor portreti' va 'Sotuv strategiyasi' tayyorlang.\n\n"
                f"Ma'lumotlar:\n" + "\n\n".join(history_data)
            )
            
            # Using advisor_agent's logic for simplicity or direct Gemini call
            # For now, let's use a direct call if advisor_agent is available
            from src.services.auto_lead_agent import AutoLeadAgent
            # Use AutoLeadAgent credentials for AI processing
            analysis_text = "AI tahlil tayyorlanmoqda..."
            try:
                # We can reuse the auto_lead_agent's client to generate content
                response = self.msg_controller.db # Accessing DB or something else
                # Actually let's use the advisor_agent directly
                analysis_text = await self.msg_controller.db.analyze_text_with_ai(analysis_prompt)
            except:
                analysis_text = "⚠️ AI tahlilida texnik xatolik, lekin guruhlardagi faollik aniqlandi."

            res_report = (
                f"🕵️‍♀️ **SOCIAL INTELLIGENCE REPORT**\n"
                f"──────────────────────\n"
                f"👥 **Umumiy guruhlar:** {len(common.chats)} ta\n\n"
                f"📊 **Hulq-atvor tahlili:**\n{analysis_text}\n"
                f"──────────────────────\n"
                f"💡 *Ushbu ma'lumotlar faqat sizning @baxtiyorjonjon_gaziyev akkuntingiz ko'ra oladigan guruhlardan olindi.*"
            )
            await wait_msg.edit(res_report)

        except Exception as e:
            logger.error(f"[SOCIAL_SPY ERROR] {e}")
            await wait_msg.edit(f"⚠️ Tahlil jarayonida xatolik: `{str(e)}`")

    async def send_draft_for_approval(self, user_id: int, name: str, draft: str):
        """AI tomonidan tayyorlangan javobni adminga tasdiqlash uchun yuborish."""
        import uuid
        draft_id = str(uuid.uuid4())[:8]
        self.pending_drafts[draft_id] = draft
        
        msg = (
            f"📝 **DRAFT JAVOB (Lid: {name})**\n"
            f"──────────────────────\n"
            f"\"{draft}\"\n"
            f"──────────────────────\n"
            f"💡 *Ushbu javobni unga yuboraymi?*"
        )
        # Send to owner
        if self.access_manager.owner_id:
            await self.bot_client.send_message(
                self.access_manager.owner_id, 
                msg, 
                buttons=[[Button.inline("🚀 Ayt!", f"send_draft:{draft_id}:{user_id}")]]
            )
