"""Sync stats and employee position command handlers for AdminBot."""
from __future__ import annotations

import asyncio
from typing import Any
import structlog
from telethon import events, functions

logger = structlog.get_logger()


def _register_sync_and_positions_handlers(self: Any) -> None:
    """Sinxronizatsiya va xodimlar pozitsiyasini boshqarish handlerlari."""

    @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/sync_stats"))
    async def sync_stats_handler(event: Any) -> None:
        if not self.access_manager.is_admin(event.sender_id):
            return

        wait_msg = await event.respond(
            "📊 **Sinxronizatsiya hisoboti tayyorlanmoqda...**\nIltimos, kuting. 👸🛡️"
        )
        try:
            tg_contacts = await self.user_client(
                functions.contacts.GetContactsRequest(hash=0)
            )
            tg_count = len(tg_contacts.users)
            google_count = await self.db.get_synced_contacts_count()
            res_msg = (
                f"📊 **Oisha Sync Hisoboti**\n\n"
                f"🔹 **Telegram Kontaktlar:** `{tg_count}` ta\n"
                f"🔸 **Google Contacts (Synced):** `{google_count}` ta\n\n"
                f"💡 *Ma'lumot:* Google Contacts'ga faqat telefon raqami bor mijozlar sinxronlanadi. 🤴🛡️"
            )
            await wait_msg.edit(res_msg)
        except Exception as e:
            logger.error("❌ [SYNC STATS ERROR] %s", e)
            await wait_msg.edit(
                f"⚠️ **Xatolik:** Hisobot tayyorlashda xato yuz berdi: `{e}`"
            )

    @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/sync_contacts_tg"))
    async def sync_contacts_tg_handler(event: Any) -> None:
        if not self.access_manager.is_admin(event.sender_id):
            return
        wait_msg = await event.respond(
            "🔍 **Google Contacts sinxronizatsiyasi boshlandi...**\n"
            "Iltimos, kuting. Oisha barcha kontaktlarni yuklamoqda va Telegram akkauntlari bilan taqqoslamoqda. 👸🛡️"
        )
        asyncio.create_task(self._run_gcontacts_telegram_sync(event, wait_msg))

    @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/set_position"))
    async def set_position_handler(event: Any) -> None:
        """Xodimga rasmiy pozitsiya biriktirish: /set_position @username PM"""
        if not self.access_manager.is_admin(event.sender_id):
            return

        args = event.message.text.split()
        target_user = None
        position = None

        if event.is_reply:
            reply_msg = await event.get_reply_message()
            target_user = await reply_msg.get_sender()
            position = " ".join(args[1:]) if len(args) > 1 else None
        elif len(args) >= 3:
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
    async def topic_info_handler(event: Any) -> None:
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
