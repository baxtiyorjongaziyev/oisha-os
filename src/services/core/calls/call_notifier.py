"""Telegram call intelligence proactive notification module."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("CallNotifier")


async def send_call_analysis_telegram_alert(
    *,
    lead_id: int,
    call_id: str,
    category: str,
    summary: str,
    client_mood: str,
    next_steps: str,
    duration_seconds: int,
    manager_name: str,
    caller_phone: str,
    analysis: Dict[str, Any],
    task_id: Optional[str] = None,
    subdomain: str = "jonbranding",
) -> None:
    """Send formatted Call Intelligence alert card to the Sales/CRM topic via @jonairobot."""
    try:
        from src.context import app_ctx
        from src.settings import settings

        bot_client = getattr(app_ctx, "bot_runtime", None) or getattr(app_ctx, "bot_client", None)
        if not bot_client:
            return

        target_chat_id = (
            getattr(settings, "AMOCRM_ALERT_FORWARD_GROUP_ID", None)
            or getattr(settings, "CRM_GROUP_ID", None)
        )
        topic_id = getattr(settings, "AMOCRM_ALERT_FORWARD_TOPIC_ID", None)
        if not target_chat_id:
            return

        dur_m = int(duration_seconds or 0) // 60
        dur_s = int(duration_seconds or 0) % 60
        lead_url = f"https://{subdomain}.amocrm.ru/leads/detail/{lead_id}"

        outcome = analysis.get("natija") or analysis.get("outcome") or ""
        score = analysis.get("sifat_bahosi") or analysis.get("overall_score") or ""
        objections = analysis.get("etirozlar") or analysis.get("objections") or []
        if isinstance(objections, list):
            objections = ", ".join(str(o) for o in objections if str(o).strip())

        msg_text = (
            f"🎙 <b>AI Qo'ng'iroq Tahlili (Call Intelligence)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Lid:</b> <a href=\"{lead_url}\">AmoCRM Lead #{lead_id}</a>\n"
            f"📞 <b>Telefon:</b> <code>{caller_phone or 'N/A'}</code>\n"
            f"🧑‍💼 <b>Menejer:</b> {manager_name or 'Aniqlanmadi'}\n"
            f"⏱ <b>Davomiyligi:</b> {dur_m}m {dur_s}s\n"
            f"🎭 <b>Kayfiyat:</b> {client_mood} | <b>Toifa:</b> {category}\n"
        )
        if score:
            msg_text += f"⭐️ <b>Sifat Bahosi:</b> {score}/100\n"
        if outcome:
            msg_text += f"📊 <b>Natija:</b> {outcome}\n"
        if objections:
            msg_text += f"💡 <b>E'tirozlar:</b> {objections}\n"
        msg_text += (
            f"📝 <b>Xulosa:</b> {summary}\n"
            f"🎯 <b>Keyingi qadam:</b> {next_steps}\n"
        )
        if task_id:
            msg_text += f"✅ <b>AmoCRM Vazifasi:</b> Biriktirildi (Task #{task_id})\n"

        kwargs: Dict[str, Any] = {"parse_mode": "HTML", "disable_web_page_preview": True}
        if topic_id:
            kwargs["reply_to_message_id"] = topic_id

        if hasattr(bot_client, "send_message"):
            await bot_client.send_message(chat_id=target_chat_id, text=msg_text, **kwargs)
    except Exception as exc:
        logger.warning("[CALL] Failed to notify Telegram for call %s: %s", call_id, exc)
