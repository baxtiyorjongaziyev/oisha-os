import os
import io
import time
import json
import logging
import structlog
import asyncio
import psutil
import platform
from datetime import datetime
from telethon import events, Button, functions, types
from src.database import Database
from src.controllers.message_controller import MessageController
from src.time_utils import get_local_now, is_quiet_hours
from src.services.core.mission_control import MissionControl, MissionControlFetchError
from src.services.core.crm.crm_night_shift import CRMNightShift
from src.services.core.admin_command_router import (
    build_chatid_response,
    build_command_center_response,
    build_finance_risks_response,
    build_oisha_stats_response,
    build_project_risks_response,
    build_sales_priorities_response,
    build_start_response,
    build_team_capacity_response,
    resolve_start_role,
)
from src.services.core.business_command_center import (
    collect_business_command_snapshot,
    collect_finance_project_risks,
    collect_project_delivery_risks,
    collect_sales_today_priorities,
    collect_team_capacity_snapshot,
)
from src.services.core.telegram.bot_runtime import BotRuntimePort, TelethonBotRuntime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from src.services.utils.access_manager import AccessManager

logger = structlog.get_logger()


def _register_sync_and_positions_handlers(self):
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

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/sync_contacts_tg"))
        async def sync_contacts_tg_handler(event):
            sender_id = event.sender_id
            if not self.access_manager.is_admin(sender_id):
                return

            wait_msg = await event.respond(
                "🔍 **Google Contacts sinxronizatsiyasi boshlandi...**\n"
                "Iltimos, kuting. Oisha barcha kontaktlarni yuklamoqda va Telegram akkauntlari bilan taqqoslamoqda. 👸🛡️"
            )

            # Run as a background task to prevent blocking the main Telegram thread
            asyncio.create_task(self._run_gcontacts_telegram_sync(event, wait_msg))

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
                    logger.error("Exception handled in %s", __name__, exc_info=True)
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



def _register_distribution_and_managers_handlers(self):
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



def _register_automation_control_handlers(self):
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
                logger.error("Exception handled in %s", __name__, exc_info=True)
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
                logger.error("Exception handled in %s", __name__, exc_info=True)
                await event.respond(f"❌ Xato: {e}")



def _register_mode_and_juma_handlers(self):
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
                logger.error("Exception handled in %s", __name__, exc_info=True)
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
                logger.error("Exception handled in %s", __name__, exc_info=True)
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


def register_settings_handlers(self):
    _register_sync_and_positions_handlers(self)
    _register_distribution_and_managers_handlers(self)
    _register_automation_control_handlers(self)
    _register_mode_and_juma_handlers(self)
