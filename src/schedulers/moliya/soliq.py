"""Oylik soliq eslatmasi — egasiga (OWNER_ID) shaxsiy xabar, 09:00.

Jadval (soliq-ops skill, owner standarti 2026-10-14):
- 1-sana: JShDS + Ijtimoiy soliq (11101_20), INPS (101), KLS tekshiruvi
- 5-sana: Aylanma soliq (10104_36)
- 12-sana: nazorat — muddatga 3 kun qoldi
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

SOLIQ_KUNLARI = (1, 5, 12)


def build_soliq_eslatma(now: datetime) -> str | None:
    if now.day == 1:
        return (
            "🧾 <b>Soliq vaqti (1-sana)</b>\n\n"
            "• JShDS + Ijtimoiy soliq (<code>11101_20</code>) — 15-sanagacha\n"
            "• INPS (<code>101</code>) — 15-sanagacha\n"
            "• KLS tekshiruvi\n\n"
            "Xodimlar oyligi qatʼiy — hozir topshiring."
        )
    if now.day == 5:
        return (
            "🧾 <b>Soliq vaqti (5-sana)</b>\n\n"
            "• Aylanmadan olinadigan soliq (<code>10104_36</code>) — 16-sanagacha\n\n"
            "Aylanma auditini tekshirib, yuboring."
        )
    if now.day == 12:
        return (
            "⏰ <b>Soliq nazorati (12-sana)</b>\n\n"
            "Muddatga 3 kun qoldi. Topshirildimi?\n"
            "• JShDS (<code>11101_20</code>) — 15-sana\n"
            "• INPS (<code>101</code>) — 15-sana\n"
            "• Aylanma (<code>10104_36</code>) — 16-sana"
        )
    return None


async def run_soliq_eslatma(now: datetime) -> bool:
    from src.settings import settings

    text = build_soliq_eslatma(now)
    if text is None:
        return False
    owner_id = getattr(settings, "OWNER_ID", None)
    bot_token = os.environ.get("BOT_TOKEN") or getattr(settings, "BOT_TOKEN", None)
    if hasattr(bot_token, "get_secret_value"):
        bot_token = bot_token.get_secret_value()
    if not owner_id or not bot_token:
        logger.warning("[SOLIQ] OWNER_ID yoki BOT_TOKEN yoʼq — eslatma yuborilmadi")
        return False
    try:
        from telegram import Bot

        await Bot(token=bot_token).send_message(
            chat_id=owner_id, text=text, parse_mode="HTML"
        )
        logger.info("[SOLIQ] Eslatma yuborildi (kun=%s)", now.day)
        return True
    except Exception:
        logger.error("[SOLIQ] Eslatma yuborishda xato", exc_info=True)
        return False
