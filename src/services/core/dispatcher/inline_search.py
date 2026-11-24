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

PHONE_RE = (
    r"(?<!\d)(\+?998|8)?[\s\-\(\)]*\d{2}[\s\-\)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}(?!\d)"
)
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

    from src.services.core.dispatcher.phone_contact_card import make_phone_search

    dp.message(F.text.regexp(PHONE_RE))(
        make_phone_search(is_admin=is_admin, perform_global_lookup=perform_global_lookup)
    )
