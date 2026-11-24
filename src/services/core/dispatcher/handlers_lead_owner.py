"""Admin-bot: "bu kimning lidi?" savoliga javob.

Ishlatish (admin shaxsiy chatda yoki sotuv guruhida):
- ``/kimning_lidi 998901234567`` (yoki ``/lid_egasi``) — ID, amoCRM link, telefon yoki ism
- ``998901234567 kimning lidi?`` — tabiiy savol
"""
from __future__ import annotations

import logging
import re
from typing import Any, Callable, Optional

logger = logging.getLogger("LeadOwnerHandler")

COMMAND_RE = r"(?i)^/(kimning_lidi|lid_egasi)(@\w+)?(\s|$)"
QUESTION_RE = r"(?i)^(.+?)\s+kim(ning|ni|niki)\s+lid(i|imi)?\s*\??$"


def extract_query(text: str) -> str:
    text = (text or "").strip()
    m = re.match(COMMAND_RE, text)
    if m:
        return text[m.end():].strip()
    m = re.match(QUESTION_RE, text)
    return m.group(1).strip() if m else ""


def _allowed_chat_ids() -> set[int]:
    try:
        from src.settings import settings

        ids = {
            getattr(settings, "CRM_SALES_REPORT_GROUP_ID", None),
            getattr(settings, "TARGET_LEADS_GROUP_ID", None),
        }
        return {int(i) for i in ids if i}
    except Exception:
        return set()


async def handle_lead_owner(
    message: Any,
    *,
    is_admin: Callable[[int], bool],
    get_amocrm_client: Optional[Callable[[], Any]],
    db: Any,
) -> None:
    sender_id = int(getattr(getattr(message, "from_user", None), "id", 0) or 0)
    chat_id = int(getattr(getattr(message, "chat", None), "id", 0) or 0)
    if not (is_admin(sender_id) or chat_id in _allowed_chat_ids()):
        return

    query = extract_query(getattr(message, "text", "") or "")
    if not query:
        await message.answer(
            "Foydalanish: <code>/kimning_lidi &lt;lid ID | amoCRM link | telefon | ism&gt;</code>",
            parse_mode="HTML",
        )
        return
    amocrm = get_amocrm_client() if get_amocrm_client else None
    if amocrm is None:
        await message.answer("❌ amoCRM ulanmagan.")
        return
    try:
        from src.services.core.crm.lead_owner_resolver import who_owns

        text = await who_owns(amocrm, db, query, getattr(amocrm, "subdomain", "") or "")
        await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as exc:
        logger.error("[LEAD OWNER] %r: %s", query, exc, exc_info=True)
        await message.answer("❌ Lid egasini aniqlashda xato.")


def register_lead_owner_handlers(
    dp: Any,
    *,
    is_admin: Callable[[int], bool],
    get_amocrm_client: Optional[Callable[[], Any]],
    db: Any,
) -> None:
    from aiogram import F

    async def _handler(message: Any) -> None:
        await handle_lead_owner(
            message, is_admin=is_admin, get_amocrm_client=get_amocrm_client, db=db
        )

    dp.message(F.text.regexp(COMMAND_RE))(_handler)
    dp.message(F.text.regexp(QUESTION_RE))(_handler)
