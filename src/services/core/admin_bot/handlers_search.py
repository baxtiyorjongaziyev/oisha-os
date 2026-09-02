"""Search and inline lookup handlers for AdminBot."""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Dict
import structlog
from telethon import Button, events
from telethon.tl.types import InputBotInlineMessageMediaContact, InputBotInlineResult

logger = structlog.get_logger()


def _format_found_user(data: Dict[str, Any]) -> str:
    res = (
        f"✅ **Mijoz topildi!**\n\n"
        f"👤 **Ism:** {data['first_name']} {data.get('last_name', '') or ''}\n"
        f"🆔 **ID:** [{data['user_id']}](tg://user?id={data['user_id']})\n"
        f"🔗 **Profil:** [Link](tg://user?id={data['user_id']})\n"
    )
    if data.get("username"):
        res += f"📱 **Username:** @{data['username']}\n"
    return res


async def _handle_phone_search(self, event: Any, phone: str) -> None:
    wait_msg = await event.respond(f"🔍 **{phone}** qidirilmoqda...")
    try:
        data = await self._perform_global_lookup(phone)
        if data:
            await wait_msg.edit(_format_found_user(data))
        else:
            await wait_msg.edit(f"❌ **{phone}** raqami bo'yicha hech kim topilmadi.")
    except Exception as e:
        logger.error(f"❌ [SEARCH ERROR] {e}")
        await wait_msg.edit(f"⚠️ Qidiruvda xatolik yuz berdi: `{str(e)}`")


async def _handle_inline_phone(self, event: Any, query: str) -> None:
    digits = re.sub(r"\D", "", query)
    if not digits.startswith("998"):
        digits = "998" + digits[-9:]
    normalized = "+" + digits
    first_name, last_name = digits[-4:], ""
    try:
        user_data = await self._perform_global_lookup(normalized)
        if user_data:
            first_name = user_data.get("first_name") or first_name
            last_name = user_data.get("last_name") or ""
    except Exception:
        logger.debug("[ADMIN_BOT] inline_search: global lookup failed for %s", normalized, exc_info=True)

    contact_result = InputBotInlineResult(
        id=str(uuid.uuid4()), type="contact", title=f"{first_name} {last_name}".strip(), description=normalized,
        send_message=InputBotInlineMessageMediaContact(phone_number=normalized, first_name=first_name, last_name=last_name, vcard=""),
    )
    await event.answer([contact_result])


async def _handle_inline_db_query(self, event: Any, query: str) -> None:
    results = []
    async with await self.db.get_connection() as conn:
        async with conn.execute(
            "SELECT user_id, first_name, username, phone, intent FROM users WHERE first_name LIKE ? OR username LIKE ? OR phone LIKE ? LIMIT 10",
            (f"%{query}%", f"%{query}%", f"%{query}%"),
        ) as cursor:
            rows = await cursor.fetchall()

    for row in rows:
        uid, name, uname, phone, intent = row
        intent_icon = "🔥" if intent == "HOT_LEAD" else "📋"
        text = (
            f"👸 **Oisha-OS Lead Profile**\n──────────────────────\n"
            f"👤 **Ism:** {name}\n📱 **Username:** @{uname or 'yoq'}\n"
            f"📞 **Tel:** `{phone or 'Nomaʼlum'}`\n🎯 **Intent:** {intent_icon} {intent or 'Aniqlanyapti'}\n"
            f"──────────────────────\n🔗 [ID: {uid} Profiliga o'tish](tg://user?id={uid})"
        )
        results.append(
            event.builder.article(
                title=f"{name} (@{uname or '?'})", description=f"Status: {intent or 'Lead'} | Tel: {phone or '?'}",
                text=text, buttons=[Button.url("💬 Chatni ochish", f"tg://user?id={uid}")],
            )
        )
    await event.answer(results)


def register_search_handlers(self):
    """Qidiruv va inline qidiruv handlerlarini botga ulash."""

    @self.bot_client.on(events.NewMessage())
    async def phone_handler(event):
        sender_id = event.sender_id
        is_active = sender_id in self.active_searches
        if is_active and (datetime.now() - self.active_searches[sender_id]).total_seconds() > 300:
            del self.active_searches[sender_id]
            is_active = False
        if not is_active and not (event.is_private and self.access_manager.is_admin(sender_id)):
            return

        text = (event.text or "").strip()
        if re.fullmatch(r"(\+?998|8)?[\s\-\(\)]*(\d{2})[\s\-]*(\d{3})[\s\-]*(\d{2})[\s\-]*(\d{2})", text):
            return
        phone_match = re.search(r"(\+?998|8)?\s?\(?\d{2}\)?\s?\d{3}\s?\d{2}\s?\d{2}", text)
        if phone_match:
            phone = phone_match.group(0)
            if sender_id in self.active_searches:
                del self.active_searches[sender_id]
            await _handle_phone_search(self, event, phone)

    @self.bot_client.on(events.NewMessage(pattern=r"(?i)^/search(?:\s+(.+))?"))
    async def manual_search_command_handler(event):
        sender_id = event.sender_id
        if not self.access_manager.is_admin(sender_id):
            return
        match_arg = event.pattern_match.group(1)
        if not match_arg:
            self.active_searches[sender_id] = datetime.now()
            await event.respond("🔍 **Qidiruv rejimiga xush kelibsiz!**\n\nQidirmoqchi bo'lgan **telefon nomeringizni** yozing (masalan: `+998991234567`).\nOisha Telegram tarmog'idan ushbu mijozni topib beradi. 👸🛡️")
            return
        await _handle_phone_search(self, event, match_arg.strip())

    @self.bot_client.on(events.InlineQuery())
    async def inline_search_handler(event):
        query = event.text.strip()
        if not query:
            return
        if re.fullmatch(r"(\+?998|8)?[\s\-\(\)]*(\d{2})[\s\-]*(\d{3})[\s\-]*(\d{2})[\s\-]*(\d{2})", query):
            await _handle_inline_phone(self, event, query)
        else:
            await _handle_inline_db_query(self, event, query)
