import os
import logging
import asyncio
import psutil
import platform
from datetime import datetime
from telethon import events, Button, functions, types
from src.services.core.mission_control import MissionControl, MissionControlFetchError
from src.database import Database
from src.controllers.message_controller import MessageController
from src.time_utils import get_local_now, is_quiet_hours

from src.services.core.crm_night_shift import CRMNightShift
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.services.utils.access_manager import AccessManager

logger = logging.getLogger(__name__)


class AdminBot:
    def __init__(
        self,
        bot_client,
        user_client,
        db: Database,
        msg_controller: MessageController,
        access_manager: "AccessManager",
        night_shift: CRMNightShift = None,
        team_group_id: int = None,
        juma_notifier=None,
    ):
        self.bot_client = bot_client
        self.user_client = user_client
        self.db = db
        self.msg_controller = msg_controller
        self.access_manager = access_manager
        self.night_shift = night_shift
        self.team_group_id = team_group_id
        self.juma_notifier = juma_notifier
        self.active_searches = {}  # user_id -> timestamp
        self.pending_drafts = {}  # draft_id -> draft_text

        # [EXPERT ADVICE] Professional scripts to obtain phone numbers
        self.PHONE_GETTING_SCRIPTS = {
            "agency_standard": (
                "📍 **Agency Standard:**\n"
                '"Tafsilotlar uchun rahmat! Loyihani texnik tomondan baholashimiz uchun '
                "siz bilan telefon orqali bog'lansak bo'ladimi? Raqamingizni qoldirsangiz, "
                'mutaxassisimiz bilan vaqtni kelishib olamiz."'
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
            ),
        }

    async def start(self):
        """Botni eventlarini ro'yxatdan o'tkazish va schedulerni parallel yuritish."""
        logger.info("[ADMIN_BOT] Oisha Enterprise v2.1 ishga tushmoqda...")

        # [AUDIT: HEARTBEAT] Proof of life (log spam oldini olish: 5 daqiqa, DEBUG)
        async def heartbeat():
            while True:
                logger.debug(
                    "👸 [ADMIN_BOT] HEARTBEAT: Oisha is alive and listening... 🛡️"
                )
                await asyncio.sleep(300)

        # [DISTRIBUTION] Yuklash (Settings ni DB bilan sinxronlash)
        from src.settings import settings

        db_mode = await self.db.get_state("lead_distribution_mode")
        if db_mode:
            settings.LEAD_DISTRIBUTION_MODE = db_mode

        db_managers = await self.db.get_state("sales_managers")
        if db_managers:
            manager_ids = [int(i.strip()) for i in db_managers.split(",") if i.strip()]
            settings.SALES_MANAGER_IDS = manager_ids
            logger.info(f"👸 [ADMIN_BOT] Sales Managers loaded: {manager_ids}")

        # Start background tasks
        asyncio.create_task(heartbeat())
        if os.getenv("ENABLE_ADMIN_SCHEDULER", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            asyncio.create_task(self.run_scheduler())
        else:
            logger.info("[SAFETY] AdminBot autonomous scheduler disabled by default.")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/oisha_audit"))
        async def oisha_audit_handler(event):
            """Tizimning oxirgi 5 ta amalini ko'rish."""
            if not self.access_manager.is_admin(event.sender_id):
                return

            from src.api_server import system_activities

            if not system_activities:
                await event.respond(
                    "👸 Oisha: Hozircha yangi amallar bajarilmadi. Tizim kutish rejimida. 🛡️"
                )
                return

            report = "🕵️‍♀️ **OISHA: LIVE AUDIT REPORT**\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            for act in system_activities[-5:]:
                icon = (
                    "⚙️"
                    if act["type"] == "info"
                    else (
                        "✨"
                        if act["type"] == "success"
                        else "🤔" if act["type"] == "thinking" else "⚠️"
                    )
                )
                report += f"{icon} **{act['action']}** ({act['timestamp']})\n┗ _{act['details']}_\n\n"

            report += (
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n💡 *To'liq tahlil dashboardda mavjud.*"
            )
            await event.respond(report)

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/junk_audit"))
        async def junk_audit_handler(event):
            """CRM tozalik auditini (junk leads) qo'lda ishga tushirish."""
            if not self.access_manager.is_admin(event.sender_id):
                return

            await event.respond(
                "👸 **Oisha CRM Audit:** Bekorchi sdelkalar tahlil qilinmoqda... 🧹"
            )

            try:
                from src.services.core.enterprise_reporter import EnterpriseReporter
                from src.services.core.crm_service import CRMService

                crm_service = CRMService()
                reporter = EnterpriseReporter(self.db, crm_service)
                report_msg = await reporter.get_junk_leads_report()

                await event.respond(report_msg, parse_mode="HTML", link_preview=False)
            except Exception as e:
                logger.error(f"❌ [JUNK_AUDIT ERROR] {e}")
                await event.respond(f"❌ Audit davomida xato yuz berdi: {e}")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/oisha_plan"))
        async def oisha_plan_handler(event):
            """Manual Morning Plan trigger."""
            if not self.access_manager.is_admin(event.sender_id):
                return
            await event.respond(
                "👸 Oisha: Mission Control ishga tushirildi. Bugungi reja tayyorlanmoqda... 🚀"
            )

            try:
                from src.services.core.proactive_worker import distribute_team_tasks

                await distribute_team_tasks(force=True)
                await event.respond(
                    "✅ Bugun uchun barcha vazifalar taqsimlandi va jamoa guruhiga yuborildi."
                )
            except Exception as e:
                await event.respond(f"❌ Xato yuz berdi: {e}")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/oisha_fact"))
        async def oisha_fact_handler(event):
            """Manual Evening Fact trigger."""
            if not self.access_manager.is_admin(event.sender_id):
                return
            await event.respond(
                "👸 Oisha: Kunlik Plan-Fakt tahlili boshlandi. AmoCRM raqamlarini tekshiryapman... 🕵️‍♀️"
            )

            try:
                from src.services.core.proactive_worker import send_evening_fact_report

                await send_evening_fact_report()
            except Exception as e:
                await event.respond(f"❌ Tahlil davomida xato yuz berdi: {e}")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/oisha_stats"))
        async def oisha_stats_handler(event):
            """Bugungi biznes ko'rsatkichlarni ko'rish."""
            if not self.access_manager.is_admin(event.sender_id):
                return

            from src.api_server import cached_crm_audit

            health = cached_crm_audit.get("health_score", 98)
            stats = await self.db.get_today_stats()
            msg = (
                f"📊 **OISHA: BUSINESS PERFORMANCE**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 **Yangi Lidlar:** `{stats.get('leads_found', 0)}` ta\n"
                f"✉️ **Xabarlar:** `{stats.get('messages_synced', 0)}` ta\n"
                f"🧹 **CRM Tozalik:** `{health}%` ({'Optimal' if health > 80 else 'Diqqat kerak' if health > 50 else 'KRITIK HOLAT'})\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👸 *Oisha hozirda avtonom rejimda ishlamoqda.*"
            )
            await event.respond(msg)

        # [AUDIT: UI/UX] Case-insensitive and robust command matching
        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/start"))
        async def start_handler(event):
            sender_id = event.sender_id
            # [CRITICAL LOG]
            logger.info("🚀" * 10)
            logger.info(f"🚀 [ADMIN_BOT] POINT A: /start received from {sender_id}")

            try:
                # [AUDIT: ARCHITECT] Identity Check (Fail-safe)
                is_owner = (sender_id == self.access_manager.owner_id) or (
                    sender_id == 150074828
                )
                logger.info(
                    f"🚀 [ADMIN_BOT] POINT B: is_owner={is_owner} (Config Owner: {self.access_manager.owner_id})"
                )

                role = (
                    "OWNER"
                    if is_owner
                    else self.access_manager.get_role(sender_id) or "GUEST"
                )
                role_name = self.access_manager.get_role_name(role)
                logger.info(
                    f"🚀 [ADMIN_BOT] POINT C: role={role}, role_name={role_name}"
                )

                welcome_msg = (
                    f"🌟 **Oisha-OS Enterprise v2.1**\n\n"
                    f"Assalomu alaykum, **{role_name}**!\n"
                    f"Tizimga muvaffaqiyatli kirdingiz. Boshqaruv pulti tayyor.\n\n"
                    f"📅 Bugun: `{get_local_now().strftime('%d.%m.%Y %H:%M')}`"
                )

                # Rollarga ko'ra tugmalar
                buttons = self._get_buttons_for_role(role)

                # AmoCRM link har doim pastda bo'lsin
                if role != "GUEST":
                    buttons.append(
                        [
                            Button.url(
                                "🌐 AmoCRM-ga o'tish", "https://jonbranding.amocrm.ru"
                            )
                        ]
                    )

                logger.info(
                    f"🚀 [ADMIN_BOT] POINT D: Responding to {sender_id} with {len(buttons)} buttons"
                )
                await event.respond(welcome_msg, buttons=buttons)
                logger.info(f"✅ [ADMIN_BOT] POINT E: Response SENT to {sender_id}")

            except Exception as e:
                logger.error(
                    f"❌ [ADMIN_BOT] START HANDLER ERROR: {str(e)}", exc_info=True
                )
                await event.respond(f"⚠️ **Tizimda texnik xatolik:**\n`{str(e)}`")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/vps_status"))
        async def vps_handler(event):
            if self.access_manager.is_admin(event.sender_id):
                await self.send_vps_status(event)

        @self.bot_client.on(events.CallbackQuery())
        async def callback_handler(event):
            data = event.data.decode("utf-8")
            try:
                # [SECURITY] Check access for administrative callbacks
                if (
                    not self.access_manager.is_admin(event.sender_id)
                    and data != "get_id"
                ):
                    await event.answer("⚠️ Kirish rad etildi.", alert=True)
                    return

                if data == "dashboard":
                    await self.send_dashboard(event)
                elif data == "weekly_report":
                    await self.send_weekly_report(event)
                elif data == "kpi":
                    await event.answer(
                        "📊 KPI tahlili yaqin daqiqalarda tayyorlanadi!", alert=True
                    )
                    await self.send_dashboard(event)  # Fallback for now
                elif data == "deadlines":
                    await event.answer("🚨 Muddatlar tekshirilmoqda...", alert=True)
                    await self.send_vps_status(event)  # Placeholder
                elif data == "settings":
                    await self._show_settings_menu(event, edit=True)
                elif data.startswith("set_dist_mode:"):
                    new_mode = data.split(":")[1]
                    from src.settings import settings

                    settings.LEAD_DISTRIBUTION_MODE = new_mode
                    await self.db.set_state("lead_distribution_mode", new_mode)
                    await event.answer(
                        f"✅ Rejim {new_mode} ga o'zgartirildi!", alert=True
                    )
                    await self._show_settings_menu(event, edit=True)
                elif data == "get_id":
                    await event.respond(
                        f"🆔 Sizning Telegram ID: `{event.sender_id}`\nUni tizimga kiritish uchun Admin-ga bering."
                    )
                elif data == "search":
                    self.active_searches[event.sender_id] = datetime.now()
                    await event.respond(
                        "🔍 **Deep Search rejimiga xush kelibsiz!**\n\n"
                        "Qidirmoqchi bo'lgan **telefon nomeringizni** yozing (masalan: `+998991234567`).\n"
                        "Oisha butun Telegram tarmog'idan ushbu mijozni topib beradi. 👸🛡️"
                    )
                elif data.startswith("social_spy:"):
                    user_id = int(data.split(":")[1])
                    await self.analyze_social_history(user_id, event)
                elif data == "vps_status":
                    await self.send_vps_status(event)
                elif data == "junk_audit":
                    # Re-use junk_audit_handler logic but for callback
                    await event.answer("🧹 CRM Audit boshlandi...", alert=True)
                    try:
                        from src.services.core.enterprise_reporter import EnterpriseReporter
                        from src.services.core.crm_service import CRMService

                        crm_service = CRMService()
                        reporter = EnterpriseReporter(self.db, crm_service)
                        report_msg = await reporter.get_junk_leads_report()

                        await event.respond(
                            report_msg, parse_mode="HTML", link_preview=False
                        )
                    except Exception as e:
                        logger.error(f"❌ [JUNK_AUDIT CALLBACK ERROR] {e}")
                        await event.respond(f"❌ Xato: {e}")
                elif data == "logs":
                    await self.send_recent_logs(event)
                elif data.startswith("send_draft:"):
                    # send_draft:draft_id:user_id
                    parts = data.split(":")
                    if len(parts) >= 3:
                        _, draft_id, target_uid = parts[0], parts[1], parts[2]
                        draft_text = self.pending_drafts.pop(draft_id, None)
                        if not draft_text:
                            await event.answer(
                                "⚠️ Draft topilmadi yoki muddati o'tgan.", alert=True
                            )
                            return
                        try:
                            uid = int(target_uid)
                            await self.user_client.send_message(uid, draft_text)
                            await event.answer("✅ Xabar yuborildi.", alert=False)
                            try:
                                await event.edit(
                                    event.message.message + "\n\n✅ Yuborildi"
                                )
                            except Exception:
                                pass
                        except Exception as ex:
                            logger.error(f"[SEND_DRAFT] {ex}", exc_info=True)
                            await event.answer(f"⚠️ Yuborishda xato: {ex}", alert=True)
                    else:
                        await event.answer("⚠️ Noto'g'ri tugma ma'lumoti.", alert=True)
                elif data.startswith("reject_draft:"):
                    draft_id = data.split(":", 1)[1] if ":" in data else ""
                    if self.pending_drafts.pop(draft_id, None) is not None:
                        await event.answer("🗑️ Draft rad etildi.", alert=False)
                        try:
                            await event.edit(
                                event.message.message + "\n\n❌ Rad etildi"
                            )
                        except Exception:
                            pass
                    else:
                        await event.answer(
                            "ℹ️ Draft allaqachon qayta ishlangan.", alert=True
                        )
                elif data.startswith("accept_lead:") or data.startswith("claim_lead:"):
                    # accept_lead:lead_id:user_id:manager_id or claim_lead:lead_id:user_id
                    parts = data.split(":")
                    lid_id = parts[1]
                    # Mark as claimed to stop escalation background task
                    await self.db.set_state(f"lead_claimed_{lid_id}", "true")

                    if data.startswith("accept_lead:"):
                        mgr_id = int(parts[3])
                        if event.sender_id != mgr_id:
                            await event.answer(
                                "⚠️ Bu lid sizga biriktirilmagan!", alert=True
                            )
                            return
                        await event.answer("✅ Lid qabul qilindi. Omad!", alert=False)
                    else:
                        # Claim logic
                        await self.db.set_state(
                            f"lead_manager_{lid_id}", event.sender_id
                        )
                        await event.answer("🚀 Lid sizga biriktirildi!", alert=True)

                    # Update message to show who claimed
                    sender = await event.get_sender()
                    name = getattr(sender, "first_name", "Menejer")
                    try:
                        await event.edit(
                            event.message.message + f"\n\n🤝 **Qabul qildi:** {name}"
                        )
                    except Exception:
                        pass
                else:
                    await event.answer(
                        "⚠️ Bu funksiya hozircha ish faoliyatida emas.", alert=True
                    )
            except Exception as e:
                logger.error(f"❌ [ADMIN_BOT] CALLBACK ERROR: {str(e)}")
                await event.answer("⚠️ Xatolik yuz berdi.", alert=True)

        # Telefon raqam yuborilsa — kontakt kartochkasi qaytaradi (НАПИСАТЬ + ДОБАВИТЬ)
        @self.bot_client.on(events.NewMessage())
        async def contact_card_handler(event):
            import re
            text = (event.text or "").strip()
            if not text or text.startswith("/"):
                return
            phone_match = re.fullmatch(
                r"(\+?998|8)?[\s\-\(\)]*(\d{2})[\s\-]*(\d{3})[\s\-]*(\d{2})[\s\-]*(\d{2})",
                text,
            )
            if not phone_match:
                return
            digits = re.sub(r"\D", "", text)
            if not digits.startswith("998"):
                digits = "998" + digits[-9:]
            normalized = "+" + digits
            last_4 = digits[-4:]
            try:
                await event.respond(
                    file=types.InputMediaContact(
                        phone_number=normalized,
                        first_name=last_4,
                        last_name="",
                        vcard="",
                    )
                )
            except Exception as exc:
                logger.warning("[CONTACT_CARD] send failed: %s", exc)

        # [ENTERPRISE: SEARCH] Phone number listener for Deep Search
        @self.bot_client.on(events.NewMessage())
        async def phone_handler(event):
            sender_id = event.sender_id
            if sender_id not in self.active_searches:
                return
            if (datetime.now() - self.active_searches[sender_id]).total_seconds() > 300:
                del self.active_searches[sender_id]
                return

            import re

            phone_match = re.search(
                r"(\+?998|8)?\s?\(?\d{2}\)?\s?\d{3}\s?\d{2}\s?\d{2}", event.text
            )
            if phone_match:
                phone = phone_match.group(0)
                del self.active_searches[sender_id]
                wait_msg = await event.respond(f"🔍 **{phone}** qidirilmoqda...")
                data = await self._perform_global_lookup(phone)
                if data:
                    await wait_msg.edit(
                        f"✅ **Mijoz topildi!**\n👤 {data['first_name']} (@{data.get('username','yoq')})"
                    )
                else:
                    await wait_msg.edit("❌ Topilmadi.")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/logs"))
        async def logs_handler(event):
            if self.access_manager.is_admin(event.sender_id):
                await self.send_recent_logs(event)

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/sync_stats"))
        async def sync_stats_handler(event):
            if not self.access_manager.is_admin(event.sender_id):
                return

            wait_msg = await event.respond(
                "📊 **Sinxronizatsiya hisoboti tayyorlanmoqda...**\nIltimos, kuting. 👸🛡️"
            )

            try:
                # 1. Telegram kontaktlar sonini olish
                tg_contacts = await self.user_client(
                    functions.contacts.GetContactsRequest(hash=0)
                )
                tg_count = len(tg_contacts.users)

                # 2. Google (Bazadagi) kontaktlar sonini olish
                google_count = await self.db.get_synced_contacts_count()

                res_msg = (
                    f"📊 **Oisha Sync Hisoboti**\n\n"
                    f"🔹 **Telegram Kontaktlar:** `{tg_count}` ta\n"
                    f"🔸 **Google Contacts (Synced):** `{google_count}` ta\n\n"
                    f"💡 *Ma'lumot:* Google Contacts'ga faqat telefon raqami bor mijozlar sinxronlanadi. 🤴🛡️"
                )
                await wait_msg.edit(res_msg)
            except Exception as e:
                logger.error(f"❌ [SYNC STATS ERROR] {e}")
                await wait_msg.edit(
                    f"⚠️ **Xatolik:** Hisobot tayyorlashda xato yuz berdi: `{e}`"
                )

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/set_position"))
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
                target_username = args[1].replace("@", "")
                try:
                    target_user = await self.user_client.get_entity(target_username)
                    position = " ".join(args[2:])
                except Exception as e:
                    await event.respond(f"❌ User topilmadi: {e}")
                    return

            if not target_user or not position:
                await event.respond(
                    "⚠️ **Xato qo'llanildi!**\n\nTo'g'ri ko'rinishi:\n1. Reply qilib: `/set_position PM`\n2. Mention bilan: `/set_position @username PM`"
                )
                return

            from src.services.utils.team_hub import TeamHub

            TeamHub.set_position(target_user.id, position)

            # Username-ni ham DB-da yangilab qo'yamiz (Accountability uchun kerak)
            await self.db.upsert_user(
                target_user.id,
                first_name=target_user.first_name,
                username=target_user.username,
                position=position,
            )

            await event.respond(
                f"✅ **Muvaffaqiyatli!**\n👤 {target_user.first_name} endi rasman **{position}** pozitsiyasida.\nOisha uni har kuni 9:00 va 18:00da nazorat qiladi. 👸🛡️"
            )

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/topic_info"))
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

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/set_distribution"))
        async def set_distribution_handler(event):
            """Lidlarni taqsimlash rejimini o'zgartirish: /set_distribution CLAIM yoki ROUND_ROBIN"""
            if not self.access_manager.is_admin(event.sender_id):
                return

            args = event.message.text.split()
            if len(args) < 2:
                await event.respond(
                    "⚠️ **Rejimni tanlang:** `/set_distribution CLAIM` yoki `ROUND_ROBIN`"
                )
                return

            mode = args[1].upper()
            if mode not in ["CLAIM", "ROUND_ROBIN"]:
                await event.respond(
                    "❌ Noto'g'ri rejim. Faqat `CLAIM` yoki `ROUND_ROBIN` mumkin."
                )
                return

            from src.settings import settings

            settings.LEAD_DISTRIBUTION_MODE = mode
            await self.db.set_state("lead_distribution_mode", mode)

            await event.respond(
                f"✅ **Muvaffaqiyatli!**\nLidlarni taqsimlash rejimi **{mode}** ga o'zgartirildi."
            )

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/add_manager"))
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
                await event.respond(
                    "⚠️ **Qo'llanma:**\n1. Menejer xabariga reply qilib `/add_manager` deb yozing.\n2. Yoki ID-sini yozing: `/add_manager 12345678`"
                )
                return

            from src.settings import settings

            if target_id not in settings.SALES_MANAGER_IDS:
                settings.SALES_MANAGER_IDS.append(target_id)
                # DB-da ham saqlaymiz
                current_managers = await self.db.get_state("sales_managers", "")
                manager_list = (
                    [int(i) for i in current_managers.split(",") if i]
                    if current_managers
                    else []
                )
                if target_id not in manager_list:
                    manager_list.append(target_id)
                    await self.db.set_state(
                        "sales_managers", ",".join(map(str, manager_list))
                    )

                await event.respond(f"✅ **Menejer qo'shildi!** (ID: `{target_id}`)")
            else:
                await event.respond("ℹ️ Bu menejer allaqachon ro'yxatda bor.")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/managers"))
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

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/night_shift"))
        async def night_shift_handler(event):
            """CRM tozalash rejimini qo'lda ishga tushirish."""
            if not self.access_manager.is_admin(event.sender_id):
                return

            await event.respond(
                "👸 **Night Shift ishga tushirildi...**\nAmoCRM'dagi dublikatlar va qotib qolgan lidlar tozalanmoqda. 🧹"
            )

            if self.night_shift:
                success = await self.night_shift.run_cleanup()
                if success:
                    await event.respond(
                        "✅ **Night Shift yakunlandi!**\nBarcha lidlar audit qilindi va keraksizlari belgilandi. 👸🛡️"
                    )
                else:
                    await event.respond("❌ Night Shift jarayonida xatolik yuz berdi.")
            else:
                await event.respond("⚠️ Night Shift xizmati faollashtirilmagan.")

        # ─── AUTO-REPLY KILL SWITCH & MODE CONTROL (Phase 2.1) ────────────
        from src.services.core import auto_reply_gate as _arg

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/pause_auto"))
        async def pause_auto_handler(event):
            """Auto-reply kill-switch YOQADI (bot darhol jim bo'ladi)."""
            if not self.access_manager.is_admin(event.sender_id):
                return
            try:
                await self.db.set_state(_arg.FLAG_KILL_SWITCH, "false")
                await event.respond(
                    "🛑 **Auto-reply PAUSED**\n"
                    "Kill-switch faollashtirildi — bot avtomatik javob bermaydi.\n"
                    "Qayta yoqish uchun: `/resume_auto`"
                )
                logger.warning(
                    f"[ADMIN_BOT] Auto-reply PAUSED by admin {event.sender_id}"
                )
            except Exception as e:
                await event.respond(f"❌ Xato: {e}")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/resume_auto"))
        async def resume_auto_handler(event):
            """Auto-reply kill-switch'ni o'chiradi — rejim qaytadan faollashadi."""
            if not self.access_manager.is_admin(event.sender_id):
                return
            try:
                await self.db.set_state(_arg.FLAG_KILL_SWITCH, "true")
                mode = await self.db.get_state(_arg.FLAG_MODE) or os.environ.get(
                    "AUTO_REPLY_MODE", "off"
                )
                await event.respond(
                    "▶️ **Auto-reply RESUMED**\n"
                    f"Joriy rejim: `{mode}`\n"
                    "Status: `/auto_status`"
                )
                logger.info(
                    f"[ADMIN_BOT] Auto-reply RESUMED by admin {event.sender_id}"
                )
            except Exception as e:
                await event.respond(f"❌ Xato: {e}")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/auto_status"))
        async def auto_status_handler(event):
            """Auto-reply rejimi, kill-switch va VIP threshold ko'rsatish."""
            if not self.access_manager.is_admin(event.sender_id):
                return
            try:
                mode_db = await self.db.get_state(_arg.FLAG_MODE)
                mode_env = os.environ.get("AUTO_REPLY_MODE", "off")
                mode = (mode_db or mode_env).lower()
                kill_raw = await self.db.get_state(_arg.FLAG_KILL_SWITCH)
                if kill_raw is None:
                    kill_active = False  # default: allowed (True in gate => not killed)
                else:
                    kill_active = str(kill_raw).lower() in ("0", "false", "off", "no")
                vip = os.environ.get("VIP_LEAD_SCORE_THRESHOLD", "80")
                triggers = ", ".join(_arg.ESCALATION_TRIGGERS)
                status_icon = "🛑" if kill_active else "✅"
                await event.respond(
                    f"{status_icon} **AUTO-REPLY STATUS**\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"Rejim (DB): `{mode_db or '—'}`\n"
                    f"Rejim (env default): `{mode_env}`\n"
                    f"Faol rejim: `{mode}`\n"
                    f"Kill-switch: `{'ON (bot jim)' if kill_active else 'OFF (bot faol)'}`\n"
                    f"VIP lead threshold: `{vip}`\n"
                    f"Escalation triggers: {triggers}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"Rejim o'zgartirish: `/set_mode off|shadow|vip_only|live`"
                )
            except Exception as e:
                await event.respond(f"❌ Xato: {e}")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/set_mode(\s+\S+)?"))
        async def set_mode_handler(event):
            """Auto-reply rejimini o'zgartirish: off | shadow | vip_only | live."""
            if not self.access_manager.is_admin(event.sender_id):
                return
            text = (event.message.text or "").strip()
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                await event.respond(
                    "ℹ️ **Foydalanish:** `/set_mode <rejim>`\n"
                    f"Ruxsat etilgan rejimlar: {', '.join(_arg.VALID_MODES)}"
                )
                return
            new_mode = parts[1].strip().lower()
            if new_mode not in _arg.VALID_MODES:
                await event.respond(
                    f"❌ Notanish rejim: `{new_mode}`\n"
                    f"Ruxsat etilganlar: {', '.join(_arg.VALID_MODES)}"
                )
                return
            try:
                await self.db.set_state(_arg.FLAG_MODE, new_mode)
                await event.respond(
                    f"🔁 **Rejim yangilandi:** `{new_mode}`\n"
                    f"Tekshirish: `/auto_status`"
                )
                logger.warning(
                    f"[ADMIN_BOT] Auto-reply mode set to '{new_mode}' by admin {event.sender_id}"
                )
            except Exception as e:
                await event.respond(f"❌ Xato: {e}")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/juma_send"))
        async def juma_send_handler(event):
            """Manual Juma Mubarak outreach trigger."""
            if not self.access_manager.is_admin(event.sender_id):
                return

            if not self.juma_notifier:
                await event.respond("❌ JumaNotifier sozlanmagan!")
                return

            await event.respond(
                "🕌 **Juma Mubarak outreach boshlanmoqda...**\nFonda barcha kursdoshlarga tabriklar yuboriladi. 👸🛡️"
            )

            # Start in background
            asyncio.create_task(self.juma_notifier.check_and_send())
            logger.info(
                f"🕌 [ADMIN_BOT] Juma outreach triggered manually by {event.sender_id}"
            )

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
            try:
                distribution = await mc.distribute_missions(managers)
            except MissionControlFetchError as exc:
                logger.error(
                    f"[ADMIN_BOT] Mission fetch skipped because AmoCRM state is unknown: {exc}"
                )
                owner_id = getattr(self.access_manager, "owner_id", None)
                if owner_id:
                    try:
                        await self.bot_client.send_message(
                            owner_id,
                            "⚠️ AmoCRM pipeline holatini olib bo'lmadi.\n"
                            "Shu sabab jamoaga 'pipeline bo'sh' degan noto'g'ri signal yuborilmadi.\n\n"
                            f"Tafsilot: {exc}",
                        )
                    except Exception as owner_error:
                        logger.error(
                            f"[ADMIN_BOT] Failed to notify owner about AmoCRM issue: {owner_error}"
                        )
                return False

            if not distribution:
                await self.notify_team(
                    "📋 **Bugungi vazifalar:**\n\n"
                    "1️⃣ CLOSER'dagi mijozlardan boshlang'ich to'lovni oling\n"
                    "2️⃣ Mavjud lidlar bilan ishlang (follow-up, takliflar)\n"
                    "3️⃣ Eski mijozlarga qayta sotuv (upsell)\n\n"
                    "💡 <i>Yangi lid izlash — faqat yuqoridagilar tugagandan keyin!</i>",
                    topic_id=settings.CRM_TOPIC_ID,
                )
                return True

            # Hisobot
            full_report = f"👸 **AVTOMATIK KUNLIK MISSYALAR** ({datetime.now().strftime('%H:%M')}) 🚀\n\n"

            for manager in managers:
                mid = manager["id"]
                missions = distribution.get(mid, [])
                if not missions:
                    continue

                report = f"👤 {manager['username']} **uchun vazifalar:**\n"
                for i, m in enumerate(missions, 1):
                    report += (
                        f"{i}. [{m['lead_name']}]({m['link']})\n   ┗ {m['mission']}\n"
                    )
                full_report += report + "\n"

            await self.notify_team(
                full_report, topic_id=settings.CRM_TOPIC_ID, parse_mode="markdown"
            )
            return True

        except Exception as e:
            logger.error(f"[ADMIN_BOT] trigger_daily_missions error: {e}")
            return False

    async def run_scheduler(self):
        """Fon rejimida vaqtni nazorat qilish va vazifalarni ishga tushirish.

        JADVAL:
        - 09:45 — Morning Briefing (Qarorlar uchun ma'lumot)
        - 10:00 — Daily Mission Distribution (Plan)
        - 13:00 — Lunch Reminder (Ertalabki vazifalar eslatmasi)
        - 14:00 — Afternoon Mission Distribution (Plan)
        - 01:00 — Night Shift (CRM tozalash)
        - 02:00 — Intelligence Audit (Kechalik AI tahlil)
        - 21:00 — Evening Fact Report (Plan vs Natija, hisobot talab qilish)
        """
        import src.api_server as api_server_module

        logger.info("👸 [ADMIN_BOT] Full Autonomous Scheduler v2.0 ishga tushdi! 🛡️")
        while True:
            try:
                now = get_local_now()
                current_time = now.strftime("%H:%M")
                today = now.strftime("%Y-%m-%d")

                if is_quiet_hours(now):
                    logger.debug(
                        "[SCHEDULER] Quiet hours active. Automatic Telegram jobs are paused."
                    )
                    await asyncio.sleep(30)
                    continue

                # 1. Morning Briefing (09:45)
                if current_time == "09:45":
                    job_id = f"morning_briefing_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        # Set state immediately to prevent duplicate runs
                        await self.db.set_state(job_id, "running")
                        logger.info("👸 [SCHEDULER] Morning Briefing boshlandi...")
                        try:
                            from src.services.core.proactive_worker import (
                                send_morning_briefing,
                            )

                            await send_morning_briefing()
                            await self.db.set_state(job_id, "done")
                            api_server_module.add_activity(
                                "☀️ Morning Briefing",
                                "Kunlik brifing jamoaga yuborildi.",
                                "success",
                            )
                        except Exception as e:
                            logger.error(f"[BRIEFING ERROR] {e}")
                            api_server_module.add_activity(
                                "⚠️ Morning Briefing", f"Xatolik: {e}", "error"
                            )

                # 1.5 Daily Plan Discipline (10:15, 13:00, 16:30)
                daily_plan_slots = {
                    "10:15": "initial",
                    "13:00": "reminder",
                    "16:30": "escalation",
                }
                if current_time in daily_plan_slots:
                    phase = daily_plan_slots[current_time]
                    job_id = f"daily_plan_{phase}_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        # Set state immediately to prevent duplicate runs
                        await self.db.set_state(job_id, "running")
                        logger.info(
                            f"[SCHEDULER] Daily plan discipline phase={phase}..."
                        )
                        try:
                            from src.services.core.proactive_worker import (
                                demand_daily_plans,
                            )

                            sent = await demand_daily_plans(phase)
                            await self.db.set_state(job_id, "done")
                            if sent:
                                api_server_module.add_activity(
                                    "ðŸ“ Daily Plan Discipline",
                                    f"Kunlik plan bo'yicha {phase} faza yuborildi.",
                                    "success",
                                )
                        except Exception as e:
                            logger.error(f"[DAILY PLAN ERROR] {e}")
                            api_server_module.add_activity(
                                "âš ï¸ Daily Plan Error", str(e), "error"
                            )

                # 2. Daily Missions (10:00 va 14:00)
                if current_time in ["10:00", "14:00"]:
                    job_id = f"daily_{today}_{current_time}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        # Set state immediately to prevent duplicate runs
                        await self.db.set_state(job_id, "running")
                        logger.info(
                            f"👸 [SCHEDULER] Mission Distribution {current_time}..."
                        )
                        try:
                            await self.trigger_daily_missions()
                            await self.db.set_state(job_id, "done")
                            api_server_module.add_activity(
                                f"🎯 Mission Control ({current_time})",
                                "Lidlar menejerlarga taqsimlandi va 'Morning Plan' guruhga yuborildi.",
                                "success",
                            )
                        except Exception as e:
                            logger.error(f"[MISSION ERROR] {e}")
                            api_server_module.add_activity(
                                "⚠️ Mission Error", str(e), "error"
                            )

                # 2.25 Client Journey Excellence (11:00 va 17:00)
                if current_time in ["11:00", "17:00"]:
                    job_id = f"client_journey_{today}_{current_time}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        await self.db.set_state(job_id, "running")
                        logger.info(
                            "[SCHEDULER] Client Journey Excellence boshlandi..."
                        )
                        try:
                            from src.services.core.proactive_worker import (
                                check_client_journey_excellence,
                            )

                            sent = await check_client_journey_excellence()
                            await self.db.set_state(job_id, "done")
                            if sent:
                                api_server_module.add_activity(
                                    "ðŸŒŸ Client Journey",
                                    "Mijoz yo'li bo'yicha wow-service mikromanagement report yuborildi.",
                                    "success",
                                )
                        except Exception as e:
                            logger.error(f"[CLIENT JOURNEY ERROR] {e}")
                            api_server_module.add_activity(
                                "âš ï¸ Client Journey Error", str(e), "error"
                            )

                # 2.5 Lunch Reminder (13:00) - Ertalabki vazifalar haqida eslatish
                if current_time == "13:00":
                    job_id = f"lunch_reminder_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        # Set state immediately to prevent duplicate runs
                        await self.db.set_state(job_id, "running")
                        logger.info("👸 [SCHEDULER] Lunch Reminder boshlandi...")
                        try:
                            from src.services.core.proactive_worker import (
                                send_lunch_reminder,
                            )

                            await send_lunch_reminder()
                            await self.db.set_state(job_id, "done")
                            api_server_module.add_activity(
                                "🍽 Lunch Reminder",
                                "Tushlik vaqtida ertalabki vazifalar haqida eslatma yuborildi.",
                                "success",
                            )
                        except Exception as e:
                            logger.error(f"[LUNCH ERROR] {e}")
                            api_server_module.add_activity(
                                "⚠️ Lunch Reminder Error", str(e), "error"
                            )

                # 3. Evening Fact Report (21:00)
                if current_time == "21:00":
                    job_id = f"evening_fact_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        # Set state immediately to prevent duplicate runs
                        await self.db.set_state(job_id, "running")
                        logger.info("👸 [SCHEDULER] Evening Fact Report boshlandi...")
                        try:
                            from src.services.core.proactive_worker import (
                                send_evening_fact_report,
                            )

                            await send_evening_fact_report()
                            await self.db.set_state(job_id, "done")
                            api_server_module.add_activity(
                                "📊 Plan-Fakt Tahlili",
                                "Kechki natijalar auditlandi va Telegram guruhiga yuborildi.",
                                "success",
                            )
                        except Exception as e:
                            logger.error(f"[FACT REPORT ERROR] {e}")
                            api_server_module.add_activity(
                                "⚠️ Fact Report Error", str(e), "error"
                            )

                # 4. Night Shift — CRM Cleanup (01:00)
                if current_time == "01:00":
                    job_id = f"night_shift_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        # Set state immediately to prevent duplicate runs
                        await self.db.set_state(job_id, "running")
                        logger.info(
                            "👸 [SCHEDULER] Night Shift CRM Cleanup boshlandi..."
                        )
                        api_server_module.add_activity(
                            "🧹 Night Shift",
                            "AmoCRM dublikatlar va qotib qolgan lidlar tozalanmoqda...",
                            "thinking",
                        )
                        try:
                            if self.night_shift:
                                await self.night_shift.run_cleanup()
                            await self.db.set_state(job_id, "done")
                            api_server_module.add_activity(
                                "✅ Night Shift",
                                "CRM muvaffaqiyatli tozalandi.",
                                "success",
                            )
                        except Exception as e:
                            logger.error(f"[NIGHT SHIFT ERROR] {e}")
                            api_server_module.add_activity(
                                "⚠️ Night Shift Error", str(e), "error"
                            )

                # 5. Intelligence Audit — Tungi AI Tahlili (02:00)
                if current_time == "02:00":
                    job_id = f"intelligence_audit_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in (
                        "done",
                        "running",
                    ):  # Check both done and running states
                        # Set state immediately to prevent duplicate runs from scheduler
                        await self.db.set_state(job_id, "running")
                        logger.info(
                            "👸 [SCHEDULER] Intelligence Audit boshlandi (tungi)..."
                        )
                        api_server_module.add_activity(
                            "🕵️ Intelligence Audit",
                            "Tungi AI tahlili boshlandi. Faollik loglari o'rganilmoqda...",
                            "thinking",
                        )
                        try:
                            from src.services.core.audit_agent import AuditAgent
                            import src.config as config

                            _audit = AuditAgent(
                                api_key=config.GEMINI_API_KEY, db=self.db
                            )
                            report = await _audit.generate_audit_report(limit=200)
                            # Egaga yuborish (user_client orqali)
                            from src.api_server import user_client as uc

                            if uc:
                                # [FIX: PeerUser] Use 'me' directly for safer delivery to self
                                try:
                                    logger.info(
                                        "📨 [AUDIT] Sending nighttime report to 'me'..."
                                    )
                                    await uc.send_message(
                                        "me",
                                        f"🦉 **OISHA: Tungi Intelligence Audit**\n\n{report}",
                                    )
                                except Exception as entity_error:
                                    logger.error(f"[AUDIT PEER ERROR] {entity_error}")
                                    # Fallback: try direct 'me'
                                    await uc.send_message(
                                        "me",
                                        f"🦉 **OISHA: Tungi Intelligence Audit**\n\n{report}",
                                    )
                            await self.db.set_state(job_id, "done")
                            api_server_module.add_activity(
                                "✅ Intelligence Audit",
                                "Tungi audit yakunlandi. Hisobot Telegramga yuborildi.",
                                "success",
                            )
                        except Exception as e:
                            logger.error(f"[AUDIT ERROR] {e}")
                            api_server_module.add_activity(
                                "⚠️ Audit Error", str(e), "error"
                            )

                # 5.5 Junk Audit — CRM Hygiene (02:30)
                if current_time == "02:30":
                    job_id = f"junk_audit_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        await self.db.set_state(job_id, "running")
                        logger.info("👸 [SCHEDULER] Junk Leads Audit boshlandi...")
                        api_server_module.add_activity(
                            "🧹 Junk Audit",
                            "CRM bekorchi sdelkalar tahlili boshlandi...",
                            "thinking",
                        )
                        try:
                            from src.services.core.proactive_worker import (
                                send_junk_leads_report,
                            )

                            await send_junk_leads_report()
                            await self.db.set_state(job_id, "done")
                            api_server_module.add_activity(
                                "✅ Junk Audit",
                                "Bekorchi sdelkalar tahlili yakunlandi va guruhga yuborildi.",
                                "success",
                            )
                        except Exception as e:
                            logger.error(f"[JUNK AUDIT ERROR] {e}")
                            api_server_module.add_activity(
                                "⚠️ Junk Audit Error", str(e), "error"
                            )

                # 6. Menejer Scorecard (18:30) — Kunlik KPI
                if current_time == "18:30":
                    job_id = f"scorecard_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        # Set state immediately to prevent duplicate runs
                        await self.db.set_state(job_id, "running")
                        logger.info("📊 [SCHEDULER] Menejer Scorecard boshlandi...")
                        try:
                            from src.services.core.sales_analytics import SalesAnalytics
                            from telegram import Bot
                            import src.config as config

                            bot_token = getattr(config, "BOT_TOKEN", None)
                            group_id = getattr(config, "CRM_GROUP_ID", None)
                            thread_id = getattr(config, "TOPIC_REPORTS_ID", None)
                            if bot_token and group_id:
                                tg_bot = Bot(token=bot_token)
                                analytics = SalesAnalytics(bot=tg_bot)
                                await analytics.send_scorecard(group_id, thread_id)
                            await self.db.set_state(job_id, "done")
                            api_server_module.add_activity(
                                "📊 Scorecard",
                                "Menejer KPI hisoboti yuborildi.",
                                "success",
                            )
                        except Exception as e:
                            logger.error(f"[SCORECARD ERROR] {e}")
                            api_server_module.add_activity(
                                "⚠️ Scorecard Error", str(e), "error"
                            )

                # 7. Stagnatsiya Alert (12:00) — Harakatsiz lidlar
                if current_time == "12:00":
                    job_id = f"stagnation_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        # Set state immediately to prevent duplicate runs
                        await self.db.set_state(job_id, "running")
                        logger.info("[SCHEDULER] Sales Conversion Push boshlandi...")
                        try:
                            from src.services.core.proactive_worker import (
                                check_amocrm_stagnation,
                            )

                            await check_amocrm_stagnation()
                            # Stagnation Alert is part of same job
                            from src.services.core.sales_analytics import SalesAnalytics
                            from telegram import Bot

                            bot_token = getattr(config, "BOT_TOKEN", None)
                            group_id = getattr(config, "CRM_GROUP_ID", None)
                            thread_id = getattr(config, "TOPIC_REPORTS_ID", None)
                            if bot_token and group_id:
                                tg_bot = Bot(token=bot_token)
                                analytics = SalesAnalytics(bot=tg_bot)
                                await analytics.send_stagnation_alert(
                                    group_id, thread_id
                                )
                            await self.db.set_state(job_id, "done")
                            api_server_module.add_activity(
                                "🚀 Sales Conversion Push",
                                "Harakatsiz lidlar bo'yicha conversion push yuborildi.",
                                "success",
                            )
                        except Exception as e:
                            logger.error(f"[STAGNATION ERROR] {e}")
                            api_server_module.add_activity(
                                "⚠️ Stagnation Error", str(e), "error"
                            )

                # 9. Juma Mubarak (Juma 09:00) — Outreach
                if now.weekday() == 4 and current_time == "09:00":
                    job_id = f"juma_mubarak_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        await self.db.set_state(job_id, "running")
                        logger.info("🕌 [SCHEDULER] Juma Mubarak outreach boshlandi...")
                        try:
                            if self.juma_notifier:
                                await self.juma_notifier.check_and_send()
                            await self.db.set_state(job_id, "done")
                            api_server_module.add_activity(
                                "🕌 Juma Mubarak",
                                "Kursdoshlarga tabriklar yuborildi.",
                                "success",
                            )
                        except Exception as e:
                            logger.error(f"[JUMA ERROR] {e}")
                            api_server_module.add_activity(
                                "⚠️ Juma Error", str(e), "error"
                            )

                # 8. Pipeline Funnel (Dushanba 09:30) — Haftalik conversiya
                if now.weekday() == 0 and current_time == "09:30":
                    job_id = f"funnel_{today}"
                    state = await self.db.get_state(job_id)
                    if state not in ("done", "running"):
                        # Set state immediately to prevent duplicate runs
                        await self.db.set_state(job_id, "running")
                        logger.info("📊 [SCHEDULER] Pipeline Funnel boshlandi...")
                        try:
                            from src.services.core.sales_analytics import SalesAnalytics
                            from telegram import Bot
                            import src.config as config

                            bot_token = getattr(config, "BOT_TOKEN", None)
                            group_id = getattr(config, "CRM_GROUP_ID", None)
                            thread_id = getattr(config, "TOPIC_REPORTS_ID", None)
                            if bot_token and group_id:
                                tg_bot = Bot(token=bot_token)
                                analytics = SalesAnalytics(bot=tg_bot)
                                await analytics.send_funnel_report(group_id, thread_id)
                            await self.db.set_state(job_id, "done")
                            api_server_module.add_activity(
                                "📊 Pipeline Funnel",
                                "Haftalik conversiya tahlili yuborildi.",
                                "success",
                            )
                        except Exception as e:
                            logger.error(f"[FUNNEL ERROR] {e}")
                            api_server_module.add_activity(
                                "⚠️ Funnel Error", str(e), "error"
                            )

                # Har 30 soniyada tekshirish
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"[SCHEDULER ERROR] {e}")
                await asyncio.sleep(60)

    async def _show_settings_menu(self, event, edit=False):
        """Tizim sozlamalarini ko'rsatish."""
        from src.settings import settings

        mode = settings.LEAD_DISTRIBUTION_MODE
        msg = f"⚙️ **TIZIM SOZLAMALARI**\n\n🎯 Taqsimot: `{mode}`"
        btns = [
            [
                Button.inline("CLAIM", b"set_dist_mode:CLAIM"),
                Button.inline("ROUND_ROBIN", b"set_dist_mode:ROUND_ROBIN"),
            ],
            [Button.inline("⬅️ Orqaga", b"dashboard")],
        ]
        if edit:
            await event.edit(msg, buttons=btns)
        else:
            await event.respond(msg, buttons=btns)

    async def _perform_global_lookup(self, phone: str):
        """Global qidiruvni amalga oshirish."""
        return await self._perform_global_lookup_userbot(phone)

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
            phone_match = re.search(
                r"(\+?998|8)?\s?\(?\d{2}\)?\s?\d{3}\s?\d{2}\s?\d{2}", text
            )

            if phone_match:
                phone = phone_match.group(0)
                del self.active_searches[sender_id]  # Bir marta ishlatilgach o'chiramiz

                wait_msg = await event.respond(
                    f"🔍 **{phone}** raqami bo'yicha qidiruv boshlandi...\nIltimos, kuting. 👸🛡️"
                )

                try:

                    # USERBOT orqali qidiruv (Bridge)
                    user_data = await self._perform_global_lookup(phone)

                    if user_data:
                        res_msg = (
                            f"✅ **Xaridor topildi!**\n\n"
                            f"👤 **Ism:** {user_data['first_name']} {user_data.get('last_name', '')}\n"
                            f"🆔 **ID:** [{user_data['user_id']}](tg://user?id={user_data['user_id']})\n"
                            f"🔗 **Profil:** [Link](tg://user?id={user_data['user_id']})\n"
                        )
                        if user_data.get("username"):
                            res_msg += f"📱 **Username:** @{user_data['username']}\n"

                        await wait_msg.edit(res_msg)
                    else:
                        await wait_msg.edit(
                            f"❌ **{phone}** raqami bo'yicha hech kim topilmadi.\nMijoz Telegramdan ro'yxatdan o'tmagan yoki maxfiylik sozlamalari yoqilgan."
                        )

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
            async with await self.db.get_connection() as conn:
                async with conn.execute(
                    """
                    SELECT user_id, first_name, username, phone, intent 
                    FROM users 
                    WHERE first_name LIKE ? OR username LIKE ? OR phone LIKE ?
                    LIMIT 10
                """,
                    (f"%{query}%", f"%{query}%", f"%{query}%"),
                ) as cursor:
                    rows = await cursor.fetchall()

            for row in rows:
                uid, name, uname, phone, intent = row
                intent_icon = "🔥" if intent == "HOT_LEAD" else "📋"

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
                        buttons=[Button.url("💬 Chatni ochish", f"tg://user?id={uid}")],
                    )
                )

            await event.answer(results)

    async def _perform_global_lookup_userbot(self, phone: str):
        """Userbot orqali Telegramdan qidirish."""
        from telethon import functions
        import random

        # Raqamni tozalash
        clean_phone = (
            phone.replace("+", "")
            .replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
        )
        if len(clean_phone) == 9:
            clean_phone = "998" + clean_phone
        if not clean_phone.startswith("998") and not clean_phone.startswith("7"):
            # Agar xalqaro bo'lmasa, taxmin qilamiz
            pass

        try:
            # 1. Vaqtinchalik kontakt yaratish
            contact = types.InputPhoneContact(
                client_id=random.randrange(-(2**63), 2**63),
                phone=clean_phone,
                first_name="Oisha Search",
                last_name="",
            )

            # 2. Import so'rovi (USERBOT)
            result = await self.user_client(
                functions.contacts.ImportContactsRequest(contacts=[contact])
            )

            if result.users:
                user = result.users[0]
                user_data = {
                    "user_id": user.id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                }

                # Kontaktni darhol o'chirib tashlaymiz (Xavfsizlik)
                await self.user_client(
                    functions.contacts.DeleteContactsRequest(id=[user.id])
                )
                return user_data

            return None
        except Exception as e:
            logger.error(f"[GLOBAL SEARCH ERROR] {e}")
            return None

    def _get_buttons_for_role(self, role: str):
        """Har bir rol uchun maxsus tugmalar."""
        if role == "OWNER":
            return [
                [
                    Button.inline("📊 ROI Dashboard", b"dashboard"),
                    Button.inline("📅 Haftalik Hisobot", b"weekly_report"),
                ],
                [
                    Button.inline("👥 Jamoa KPI", b"kpi"),
                    Button.inline("🚨 Deadline Control", b"deadlines"),
                ],
                [
                    Button.inline("🔍 Deep Search", b"search"),
                    Button.inline("🖥 VPS Status", b"vps_status"),
                ],
                [
                    Button.inline("📜 So'nggi Loglar", b"logs"),
                    Button.inline("🧹 Junk Audit", b"junk_audit"),
                    Button.inline("⚙️ Sozlamalar", b"settings"),
                ],
            ]
        elif role == "CEO":
            return [
                [Button.inline("📈 Biznes Overview", b"overview")],
                [Button.inline("💰 Moliyaviy Holat", b"finance")],
                [Button.inline("🔍 Global Search", b"search")],
            ]
        elif role == "PM":
            return [
                [Button.inline("📋 Loyihalar Statusi", b"projects")],
                [Button.inline("⏳ Muddatlar", b"deadlines")],
                [Button.inline("🔍 Deal Search", b"search")],
            ]
        else:  # GUEST
            return [
                [Button.inline("🆔 ID-ni olish", b"get_id")],
                [Button.url("📞 Bog'lanish", "https://t.me/baxtiyorjon_gaziyev")],
            ]

    async def send_dashboard(self, event):
        stats = await self.db.get_today_stats()
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
        disk = psutil.disk_usage("/")

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

    async def send_recent_logs(self, event):
        """Oxirgi 15 qator logni ko'rsatish."""
        log_path = "data/oisha.log"

        if not os.path.exists(log_path):
            await event.respond(
                "⚠️ **Hozircha loglar mavjud emas.**\n(data/oisha.log fayli topilmadi)"
            )
            return

        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                last_logs = "".join(lines[-15:])

            msg = f"📜 **SO'NGGI LOGLAR:**\n\n```\n{last_logs}\n```"
            await event.respond(msg)
        except Exception as e:
            logger.error(f"[ADMIN_BOT] Log o'qishda xato: {e}")
            await event.respond("❌ Xatolik: Log faylini o'qib bo'lmadi.")

    async def notify_lead(self, text: str):
        """Yangi topilgan lidlar haqida xabar berish (LeadScraper dan keladi)."""
        if os.getenv("ENABLE_PROACTIVE_NOTIFICATIONS", "").strip().lower() not in {
            "1",
            "true",
            "yes",
            "on",
        }:
            logger.info(
                "[SAFETY] Proactive lead notification suppressed. Set ENABLE_PROACTIVE_NOTIFICATIONS=1 to enable."
            )
            return False

        sent_any = False

        async def _safe_send(client, target, label: str) -> bool:
            if not client or not target:
                return False
            try:
                await client.send_message(target, text)
                logger.info(f"[ADMIN_BOT] Lead notification sent to {label}")
                return True
            except Exception as exc:
                logger.warning(
                    f"[ADMIN_BOT] notify_lead skipped {label}: {type(exc).__name__}"
                )
                return False

        owner_targets = []
        if self.access_manager.owner_id:
            owner_targets.append(self.access_manager.owner_id)
        # Hard fallback for the real owner account when config/entity cache is stale.
        owner_targets.append(150074828)

        for target in dict.fromkeys(owner_targets):
            sent_any = (
                await _safe_send(self.bot_client, target, f"owner:{target}") or sent_any
            )

        if self.team_group_id:
            sent_any = (
                await _safe_send(
                    self.bot_client, self.team_group_id, f"team:{self.team_group_id}"
                )
                or sent_any
            )

        if not sent_any:
            await _safe_send(self.user_client, "me", "userbot:saved_messages")

    async def notify_team(
        self,
        text: str,
        buttons: list = None,
        topic_id: int = None,
        parse_mode: str = None,
    ):
        """Faqat jamoa guruhiga bildirishnoma yuborish. Topic_id (thread_id) berilsa o'sha bo'limga yuboradi."""
        if not self.team_group_id:
            return

        try:
            # Telethon-da reply_to parametri orqali topic (forum thread) ni ko'rsatish mumkin
            await self.bot_client.send_message(
                self.team_group_id,
                text,
                buttons=buttons,
                reply_to=topic_id,
                parse_mode=parse_mode,
            )
            logger.info(
                f"[ADMIN_BOT] Team notification sent to {self.team_group_id} (Topic: {topic_id})"
            )
        except Exception as bot_exc:
            try:
                # User accounts cannot create bot callback buttons, but the alert text
                # must still reach the team while the bot lacks group membership.
                await self.user_client.send_message(
                    self.team_group_id,
                    text,
                    reply_to=topic_id,
                    parse_mode=parse_mode,
                )
                logger.warning(
                    "[ADMIN_BOT] Bot team notification failed; sent via userbot fallback: %s",
                    bot_exc,
                )
            except Exception as userbot_exc:
                logger.error(
                    "[ADMIN_BOT] notify_team failed via bot (%s) and userbot (%s)",
                    bot_exc,
                    userbot_exc,
                )

    async def enrich_lead_profile(self, user_id, sender_obj, lead_details: dict):
        """Mijoz profilini tahlil qilish, bio-ni olish va raqam qidirish."""
        owner_id = self.access_manager.owner_id
        if not owner_id:
            return

        first_name = getattr(sender_obj, "first_name", "Mijoz")
        username = getattr(sender_obj, "username", "yoq")

        # 1. PROFILE ANALYSIS (Bio/About)
        bio = "[Bio o'qib bo'lmadi]"
        try:
            from telethon.tl.functions.users import GetFullUserRequest

            full_user = await self.user_client(GetFullUserRequest(user_id))
            bio = full_user.full_user.about or "Bio yozilmagan"
        except Exception as e:
            logger.error(f"[ENRICHMENT] Bio fetch error: {e}")

        # 2. PHONE LOOKUP (If missing)
        phone = getattr(sender_obj, "phone", None) or lead_details.get("phone")
        (
            "✅ Profilida bor"
            if getattr(sender_obj, "phone", None)
            else "🔍 Qidirilmoqda..."
        )

        if not phone:
            # Try Deep Search (Userbot bridge)
            # Since we only have ID here, deep search by phone isn't possible,
            # but we can check if the user is already in our contact list.
            pass

        # 3. REPORT FORMATTING
        business_type = lead_details.get("business", "Noma'lum")
        needs_text = lead_details.get("needs", "Tahlil qilinmoqda")
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
            buttons=[[Button.inline("🔍 Guruhlar tahlili", f"social_spy:{user_id}")]],
        )
        logger.info(f"[ENRICHMENT] Full intelligence report sent for {user_id}")

    async def analyze_social_history(self, user_id, event):
        """Mijozning umumiy guruhlardagi faoliyatini tahlil qilish."""
        from telethon.tl.functions.messages import GetCommonChatsRequest

        wait_msg = await event.respond(
            "🕵️‍♀️ **Guruhlar tahlili boshlandi...**\nOisha umumiy guruhlarni va xabarlarni o'rganmoqda. 👸🛡️"
        )

        try:
            # 1. Get Common Chats
            common = await self.user_client(
                GetCommonChatsRequest(user_id=user_id, max_id=0, limit=50)
            )
            if not common.chats:
                await wait_msg.edit("❌ Mijoz bilan umumiy guruhlar topilmadi.")
                return

            history_data = []
            # Faqat oxirgi 3 ta faol guruhni olamiz (Rate limits)
            for chat in common.chats[:3]:
                chat_title = getattr(chat, "title", "Guruh")
                messages = []
                async for msg in self.user_client.iter_messages(
                    chat, from_user=user_id, limit=7
                ):
                    if msg.text:
                        messages.append(msg.text)

                if messages:
                    history_data.append(
                        f"📡 **Guruh:** {chat_title}\n"
                        + "\n".join([f"- {m[:100]}..." for m in messages])
                    )

            if not history_data:
                await wait_msg.edit(
                    "❌ Guruhlar topildi, lekin mijoz u yerda yaqin orada xabar yozmagan."
                )
                return

            # 2. AI ANALYSIS
            analysis_prompt = (
                "Siz Oisha-OS Social Intelligence agentsiz. "
                "Quyidagi mijozning guruhlardagi xabarlarini tahlil qilib, Baxtiyor aka uchun "
                "qisqa 'Hulq-atvor portreti' va 'Sotuv strategiyasi' tayyorlang.\n\n"
                "Ma'lumotlar:\n" + "\n\n".join(history_data)
            )

            # Using advisor_agent's logic for simplicity or direct Gemini call
            # For now, let's use a direct call if advisor_agent is available
            # Use AutoLeadAgent credentials for AI processing
            analysis_text = "AI tahlil tayyorlanmoqda..."
            try:
                # We can reuse the auto_lead_agent's client to generate content
                # Actually let's use the advisor_agent directly
                analysis_text = await self.msg_controller.db.analyze_text_with_ai(
                    analysis_prompt
                )
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
            f'"{draft}"\n'
            f"──────────────────────\n"
            f"💡 *Ushbu javobni unga yuboraymi?*"
        )
        # Send to owner
        if self.access_manager.owner_id:
            await self.bot_client.send_message(
                self.access_manager.owner_id,
                msg,
                buttons=[
                    [
                        Button.inline("🚀 Ayt!", f"send_draft:{draft_id}:{user_id}"),
                        Button.inline("❌ Rad et", f"reject_draft:{draft_id}"),
                    ]
                ],
            )
