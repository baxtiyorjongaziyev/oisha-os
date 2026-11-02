"""Telegram bot handlers for Oisha-OS seamless web authentication."""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from src.api.web_auth_store import approve_tg_login_state, issue_tg_otp_code

logger = logging.getLogger(__name__)

_UNAUTHORIZED_MSG = (
    "⛔ Kechirasiz, siz Oisha-OS xodimlari roʻyxatida mavjud emassiz. "
    "Kirish faqat tasdiqlangan xodimlar uchun."
)
_STATE_EXPIRED_MSG = (
    "⚠️ Kirish havolasining muddati oʻtgan yoki yaroqsiz. "
    "Iltimos, saytdan qayta urinib koʻring."
)
_APPROVED_MSG = (
    "✅ Oisha-OS tizimiga kirish muvaffaqiyatli tasdiqlandi!\n\n"
    "Brauzeringizga qaytishingiz mumkin — sahifa avtomatik ochiladi."
)


def _get_authorized_role(user_id: int, db: Any = None) -> Optional[str]:
    """Return the authorized system role for a Telegram user ID, or None if unauthorized."""
    try:
        from src.settings import settings

        owner_id = int(getattr(settings, "OWNER_ID", 0) or 0)
        if owner_id and int(user_id) == owner_id:
            return "owner"
        whitelist = [
            int(x)
            for x in (getattr(settings, "WHITELIST_IDS", []) or [])
            if str(x).isdigit()
        ]
        if int(user_id) in whitelist:
            return "admin"
    except Exception as exc:
        logger.warning("[WEB-AUTH] Settings tekshiruvida xatolik: %s", exc)

    return None


async def handle_start_weblogin(message: Any, state_token: str, db: Any = None) -> None:
    """Handle /start login_<state> deep-link authorization."""
    user = getattr(message, "from_user", None)
    if not user:
        return

    user_id = int(user.id)
    role = _get_authorized_role(user_id, db=db)
    if not role:
        logger.warning("[WEB-AUTH] Ruxsatsiz kirish urinishi: user_id=%s, username=%s", user_id, user.username)
        await message.answer(_UNAUTHORIZED_MSG)
        return

    clean_state = str(state_token or "").strip()
    approved_url = approve_tg_login_state(
        clean_state,
        user_id=user_id,
        username=getattr(user, "username", None),
        first_name=getattr(user, "first_name", None),
        role=role,
    )
    if not approved_url and (clean_state.startswith("login_") or clean_state.startswith("weblogin_")):
        stripped = clean_state.removeprefix("weblogin_").removeprefix("login_")
        approved_url = approve_tg_login_state(
            stripped,
            user_id=user_id,
            username=getattr(user, "username", None),
            first_name=getattr(user, "first_name", None),
            role=role,
        )

    if approved_url:
        logger.info("[WEB-AUTH] Muvaffaqiyatli tasdiqlandi: user_id=%s role=%s state=%s", user_id, role, clean_state)
        await message.answer(_APPROVED_MSG)
    else:
        logger.warning("[WEB-AUTH] Notoʻgʻri yoki eskirgan state: user_id=%s state=%s", user_id, clean_state)
        await message.answer(_STATE_EXPIRED_MSG)


async def handle_login_otp(message: Any, db: Any = None) -> None:
    """Generate and send a 6-digit one-time password (OTP) for web login."""
    user = getattr(message, "from_user", None)
    if not user:
        return

    user_id = int(user.id)
    role = _get_authorized_role(user_id, db=db)
    if not role:
        logger.warning("[WEB-AUTH] Ruxsatsiz OTP soʻrovi: user_id=%s, username=%s", user_id, user.username)
        await message.answer(_UNAUTHORIZED_MSG)
        return

    code = issue_tg_otp_code(
        user_id=user_id,
        username=getattr(user, "username", None),
        first_name=getattr(user, "first_name", None),
        role=role,
    )
    logger.info("[WEB-AUTH] OTP yaratildi: user_id=%s role=%s", user_id, role)
    text = (
        "🔑 <b>Oisha-OS tizimiga bir martalik kirish kodingiz:</b>\n\n"
        f"<code>{code}</code>\n\n"
        "Ushbu kod 10 daqiqa davomida amal qiladi. Kodni hech kimga bermang."
    )
    await message.answer(text, parse_mode="HTML")


def register_web_auth_handlers(dp: Any, db: Any = None, is_admin: Any = None) -> None:
    """Register deep-link and OTP web auth handlers on an aiogram Dispatcher."""
    from aiogram import F

    @dp.message(F.text.regexp(r"(?i)^/start\s+(weblogin_|login_)([a-zA-Z0-9_-]+)"))
    async def _deep_link(message: Any) -> None:
        match = re.match(r"(?i)^/start\s+((?:weblogin_|login_)[a-zA-Z0-9_-]+)", message.text or "")
        token = match.group(1) if match else ""
        await handle_start_weblogin(message, state_token=token, db=db)

    @dp.message(F.text.regexp(r"(?i)^/(login|kirish|web_auth|kod)$"))
    async def _otp_cmd(message: Any) -> None:
        await handle_login_otp(message, db=db)
