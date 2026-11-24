"""Native aiogram inline-query + phone-search handlers.

These two AdminBot surfaces cannot be carried by AiogramTelethonCompatClient:
- Telethon InlineQuery decorators are dropped by the compat bridge.
- The bare ``@bot_client.on(events.NewMessage())`` phone catch-all has no
  matcher, so the compat bridge would fire it on every message.
Both are reimplemented here on the aiogram Dispatcher, reusing AdminBot's
``_perform_global_lookup`` via an injected callable.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger("AdminAiogramInlineSearch")

PHONE_RE = r"(\+?998|8)?\s?\(?\d{2}\)?\s?\d{3}\s?\d{2}\s?\d{2}"
_STRICT_PHONE_RE = re.compile(
    r"(\+?998|8)?[\s\-\(\)]*(\d{2})[\s\-]*(\d{3})[\s\-]*(\d{2})[\s\-]*(\d{2})"
)


def _looks_like_phone(text: str) -> bool:
    return bool(_STRICT_PHONE_RE.fullmatch(text.strip()))


def register_inline_search_handlers(
    dp: Any,
    *,
    is_admin: Callable[[int], bool],
    perform_global_lookup: Callable[[str], Awaitable[Optional[dict]]],
    db: Any,
) -> None:
    from aiogram import F
    from aiogram.types import InlineQueryResultArticle, InputTextMessageContent

    @dp.inline_query()
    async def _inline_search(query: Any) -> None:
        sender = getattr(query, "from_user", None)
        sender_id = int(getattr(sender, "id", 0) or 0)
        if not is_admin(sender_id):
            await query.answer([], cache_time=1, is_personal=True)
            return

        text = (
            getattr(query, "query", "") or getattr(query, "text", "") or ""
        ).strip()
        if not text:
            await query.answer([], cache_time=1, is_personal=True)
            return

        if _looks_like_phone(text):
            digits = re.sub(r"\D", "", text)
            if not digits.startswith("998"):
                digits = "998" + digits[-9:]
            normalized = "+" + digits
            first_name, last_name = digits[-4:], ""
            try:
                data = await perform_global_lookup(normalized)
                if data:
                    first_name = data.get("first_name") or first_name
                    last_name = data.get("last_name") or ""
            except Exception:
                logger.debug(
                    "[INLINE] phone lookup failed for %s", normalized, exc_info=True
                )
            result = InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title=f"{first_name} {last_name}".strip() or normalized,
                description=normalized,
                input_message_content=InputTextMessageContent(
                    message_text=f"📞 {normalized}\n👤 {first_name} {last_name}".strip()
                ),
            )
            await query.answer([result], cache_time=1, is_personal=True)
            return

        results: list[Any] = []
        try:
            async with await db.get_connection() as conn:
                async with conn.execute(
                    "SELECT user_id, first_name, username, phone, intent FROM users "
                    "WHERE first_name LIKE ? OR username LIKE ? OR phone LIKE ? LIMIT 10",
                    (f"%{text}%", f"%{text}%", f"%{text}%"),
                ) as cursor:
                    rows = await cursor.fetchall()
            for row in rows:
                uid, name, uname, phone, intent = row
                icon = "🔥" if intent == "HOT_LEAD" else "📋"
                body = (
                    f"👤 {name}\n"
                    f"📱 @{uname or 'yoq'}\n"
                    f"📞 {phone or 'Nomaʼlum'}\n"
                    f"🎯 {icon} {intent or 'Lead'}\n"
                    f"tg://user?id={uid}"
                )
                results.append(
                    InlineQueryResultArticle(
                        id=str(uuid.uuid4()),
                        title=f"{name} (@{uname or '?'})",
                        description=f"{intent or 'Lead'} | {phone or '?'}",
                        input_message_content=InputTextMessageContent(
                            message_text=body
                        ),
                    )
                )
        except Exception:
            logger.debug("[INLINE] db query failed for %r", text, exc_info=True)
        await query.answer(results, cache_time=1, is_personal=True)

    @dp.message(F.text.regexp(PHONE_RE))
    async def _phone_search(message: Any) -> None:
        """Raqam -> Telegram kontakt kartasi (GET-LID analogi, limitsiz).

        Kartani bir bosib mijozga yozish mumkin, saqlash shart emas.
        """
        sender = getattr(message, "from_user", None)
        sender_id = int(getattr(sender, "id", 0) or 0)
        if not is_admin(sender_id):
            return
        text = (getattr(message, "text", "") or "").strip()
        match = re.search(PHONE_RE, text)
        if not match:
            return
        phone = normalize_uz_phone(match.group(0))
        try:
            data = await perform_global_lookup(phone)
        except Exception:
            logger.error("[INLINE] phone search failed", exc_info=True)
            data = None

        first_name = (data or {}).get("first_name") or phone
        last_name = (data or {}).get("last_name") or ""
        try:
            await message.answer_contact(
                phone_number=phone, first_name=first_name, last_name=last_name
            )
        except Exception:
            logger.warning("[INLINE] contact card send failed", exc_info=True)

        if not data:
            await message.answer(
                f"❌ {format_uz_phone(phone)} Telegramda topilmadi "
                "yoki raqami yashirilgan."
            )
            return

        body = f"✅ Raqam topildi\n📞 {format_uz_phone(phone)}"
        markup = _profile_button(data)
        if markup is not None:
            try:
                await message.answer(body, reply_markup=markup)
                return
            except Exception:
                # tg://user?id tugmasi maxfiylik sabab rad etilishi mumkin.
                logger.debug("[INLINE] profile button rejected", exc_info=True)
        await message.answer(body)


def normalize_uz_phone(raw: str) -> str:
    """Har qanday yozuvni +998XXXXXXXXX koʻrinishiga keltiradi."""
    digits = re.sub(r"\D", "", raw or "")
    if not digits.startswith("998"):
        digits = "998" + digits[-9:]
    return "+" + digits


def format_uz_phone(phone: str) -> str:
    """+998901234567 -> +998 90 123 45 67"""
    d = re.sub(r"\D", "", phone)
    if len(d) == 12 and d.startswith("998"):
        return f"+{d[:3]} {d[3:5]} {d[5:8]} {d[8:10]} {d[10:]}"
    return phone


def _profile_button(data: dict) -> Any:
    username = data.get("username")
    user_id = data.get("user_id")
    if username:
        label, url = f"💬 @{username}", f"https://t.me/{username}"
    elif user_id:
        label, url = "💬 Profilni ochish", f"tg://user?id={user_id}"
    else:
        return None
    try:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    except Exception:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=label, url=url)]]
    )
