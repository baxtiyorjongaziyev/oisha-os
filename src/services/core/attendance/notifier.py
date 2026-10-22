"""Shubhali davomat haqida owner'ga xabar.

Owner qarori (2026-10-22): GPS+QR o'tsa — avtomatik tasdiq; faqat shubhali holat
Telegram orqali ``OWNER_ID`` ga yuboriladi. Bot ulanmagan bo'lsa xabar log qilinadi,
yuborildi deb ko'rsatilmaydi.
"""
from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class ReviewNotifier(Protocol):
    async def notify_review(self, text: str) -> bool: ...


class NullNotifier:
    async def notify_review(self, text: str) -> bool:
        logger.warning("[ATTENDANCE] review notification not sent (no bot): %s", text)
        return False


class TelegramOwnerNotifier:
    """Bot API ga to'g'ridan-to'g'ri HTTP — API jarayoni bot jarayonidan alohida ishlaydi."""

    def __init__(self, bot_token: str, owner_id: int, timeout_s: float = 10.0):
        self.bot_token, self.owner_id, self.timeout_s = bot_token, owner_id, timeout_s

    async def notify_review(self, text: str) -> bool:
        if not self.bot_token or not self.owner_id:
            return await NullNotifier().notify_review(text)
        import httpx

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.post(url, json={"chat_id": self.owner_id, "text": text})
            ok = resp.status_code == 200 and resp.json().get("ok") is True
            if not ok:
                logger.error("[ATTENDANCE] owner notification rejected: HTTP %s", resp.status_code)
            return ok
        except Exception:
            logger.exception("[ATTENDANCE] owner notification failed")
            return False


def default_notifier() -> ReviewNotifier:
    try:
        from src.settings import settings

        token = settings.BOT_TOKEN.get_secret_value() if settings.BOT_TOKEN else ""
        return TelegramOwnerNotifier(token, int(settings.OWNER_ID or 0))
    except Exception:
        logger.exception("[ATTENDANCE] notifier config unavailable")
        return NullNotifier()


def format_review(name: str, kind: str, local_time: str, reasons: list[str]) -> str:
    label = "keldi" if kind == "check_in" else "ketdi"
    why = ", ".join(reasons) or "noma'lum"
    return f"⚠️ Davomat tekshiruvi: {name} {local_time} da {label}.\nSabab: {why}\nHolat: PENDING_REVIEW"
