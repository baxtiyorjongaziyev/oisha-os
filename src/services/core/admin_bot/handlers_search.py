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

def register_search_handlers(self):
        @self.bot_client.on(events.NewMessage())
        async def phone_handler(event):
            sender_id = event.sender_id

            # Check if user is in active searches mode
            is_active = sender_id in self.active_searches
            if is_active:
                if (datetime.now() - self.active_searches[sender_id]).total_seconds() > 300:
                    del self.active_searches[sender_id]
                    is_active = False

            # If not in active searches, only allow direct lookup in private chat for admins
            if not is_active:
                if event.is_private and self.access_manager.is_admin(sender_id):
                    pass
                else:
                    return

            import re

            text = (event.text or "").strip()
            # Bare phone number — contact_card_handler handles it, skip here
            if re.fullmatch(
                r"(\+?998|8)?[\s\-\(\)]*(\d{2})[\s\-]*(\d{3})[\s\-]*(\d{2})[\s\-]*(\d{2})",
                text,
            ):
                return

            phone_match = re.search(
                r"(\+?998|8)?\s?\(?\d{2}\)?\s?\d{3}\s?\d{2}\s?\d{2}", text
            )
            if phone_match:
                phone = phone_match.group(0)
                if sender_id in self.active_searches:
                    del self.active_searches[sender_id]

                wait_msg = await event.respond(f"🔍 **{phone}** qidirilmoqda...")
                try:
                    data = await self._perform_global_lookup(phone)
                    if data:
                        res_msg = (
                            f"✅ **Mijoz topildi!**\n\n"
                            f"👤 **Ism:** {data['first_name']} {data.get('last_name', '') or ''}\n"
                            f"🆔 **ID:** [{data['user_id']}](tg://user?id={data['user_id']})\n"
                            f"🔗 **Profil:** [Link](tg://user?id={data['user_id']})\n"
                        )
                        if data.get("username"):
                            res_msg += f"📱 **Username:** @{data['username']}\n"
                        await wait_msg.edit(res_msg)
                    else:
                        await wait_msg.edit(f"❌ **{phone}** raqami bo'yicha hech kim topilmadi.")
                except Exception as e:
                    logger.error(f"❌ [SEARCH ERROR] {e}")
                    await wait_msg.edit(f"⚠️ Qidiruvda xatolik yuz berdi: `{str(e)}`")

        @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/search(?:\s+(.+))?"))
        async def manual_search_command_handler(event):
            sender_id = event.sender_id
            if not self.access_manager.is_admin(sender_id):
                return

            import re
            match_arg = event.pattern_match.group(1)
            if not match_arg:
                # If they just type /search, activate active_searches mode
                self.active_searches[sender_id] = datetime.now()
                await event.respond(
                    "🔍 **Qidiruv rejimiga xush kelibsiz!**\n\n"
                    "Qidirmoqchi bo'lgan **telefon nomeringizni** yozing (masalan: `+998991234567`).\n"
                    "Oisha Telegram tarmog'idan ushbu mijozni topib beradi. 👸🛡️"
                )
                return

            phone = match_arg.strip()
            wait_msg = await event.respond(f"🔍 **{phone}** qidirilmoqda...")
            try:
                data = await self._perform_global_lookup(phone)
                if data:
                    res_msg = (
                        f"✅ **Mijoz topildi!**\n\n"
                        f"👤 **Ism:** {data['first_name']} {data.get('last_name', '') or ''}\n"
                        f"🆔 **ID:** [{data['user_id']}](tg://user?id={data['user_id']})\n"
                        f"🔗 **Profil:** [Link](tg://user?id={data['user_id']})\n"
                    )
                    if data.get("username"):
                        res_msg += f"📱 **Username:** @{data['username']}\n"
                    await wait_msg.edit(res_msg)
                else:
                    await wait_msg.edit(f"❌ **{phone}** raqami bo'yicha hech kim topilmadi.")
            except Exception as e:
                logger.error(f"❌ [SEARCH ERROR] {e}")
                await wait_msg.edit(f"⚠️ Qidiruvda xatolik yuz berdi: `{str(e)}`")

        @self.bot_client.on(events.InlineQuery())
        async def inline_search_handler(event):
            import re, uuid
            from telethon.tl.types import (
                InputBotInlineResult,
                InputBotInlineMessageMediaContact,
            )

            query = event.text.strip()
            if not query:
                return

            # Telefon raqam bo'lsa — kontakt kartochkasi qaytaramiz
            phone_match = re.fullmatch(
                r"(\+?998|8)?[\s\-\(\)]*(\d{2})[\s\-]*(\d{3})[\s\-]*(\d{2})[\s\-]*(\d{2})",
                query,
            )
            if phone_match:
                digits = re.sub(r"\D", "", query)
                if not digits.startswith("998"):
                    digits = "998" + digits[-9:]
                normalized = "+" + digits

                first_name = digits[-4:]
                last_name = ""
                try:
                    user_data = await self._perform_global_lookup(normalized)
                    if user_data:
                        first_name = user_data.get("first_name") or first_name
                        last_name = user_data.get("last_name") or ""
                except Exception as exc:
                    logger.debug("[ADMIN_BOT] inline_search: global lookup failed for %s", normalized, exc_info=True)

                contact_result = InputBotInlineResult(
                    id=str(uuid.uuid4()),
                    type="contact",
                    title=f"{first_name} {last_name}".strip(),
                    description=normalized,
                    send_message=InputBotInlineMessageMediaContact(
                        phone_number=normalized,
                        first_name=first_name,
                        last_name=last_name,
                        vcard="",
                    ),
                )
                await event.answer([contact_result])
                return

            # DB dan qidirish
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
                    f"📞 **Tel:** `{phone or 'Nomaʼlum'}`\n"
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
