"""Telegram call intelligence proactive notification module."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("CallNotifier")


def _format_conversion_recommendations(analysis: Dict[str, Any]) -> str:
    """Format conversion recommendations into concise bullet points."""
    tavsiyalar = (
        analysis.get("konversiya_tavsiyalari")
        or analysis.get("tavsiyalar")
        or []
    )
    if isinstance(tavsiyalar, str):
        tavsiyalar = [tavsiyalar]
    clean = [str(t).strip() for t in tavsiyalar if str(t).strip()]
    if not clean:
        return ""
    lines = ["💡 <b>Konversiya Tavsiyalari:</b>"]
    for t in clean[:2]:
        lines.append(f"  • {t}")
    return "\n".join(lines)


def _format_agreed_time(analysis: Dict[str, Any]) -> str:
    """Format agreed date and time if present in analysis."""
    agreed_dt = analysis.get("kelishilgan_vaqt")
    if agreed_dt and hasattr(agreed_dt, "strftime"):
        return f"⏰ <b>Kelishilgan vaqt:</b> {agreed_dt.strftime('%d.%m.%Y %H:%M')}\n"
    return ""


def build_call_alert_message(
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
) -> str:
    """Construct HTML formatted message for Telegram call intelligence alerts."""
    dur_m = int(duration_seconds or 0) // 60
    dur_s = int(duration_seconds or 0) % 60
    lead_url = f"https://{subdomain}.amocrm.ru/leads/detail/{lead_id}"

    outcome = analysis.get("natija") or analysis.get("outcome") or ""
    score = analysis.get("sifat_bahosi") or analysis.get("overall_score") or ""
    objections = analysis.get("etirozlar") or analysis.get("objections") or []
    if isinstance(objections, list):
        objections = ", ".join(str(o) for o in objections if str(o).strip())

    msg_lines = [
        "🎙 <b>AI Qo'ng'iroq Tahlili (Call Intelligence)</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"👤 <b>Lid:</b> <a href=\"{lead_url}\">AmoCRM Lead #{lead_id}</a>",
        f"📞 <b>Telefon:</b> <code>{caller_phone or 'N/A'}</code>",
        f"🧑‍💼 <b>Menejer:</b> {manager_name or 'Aniqlanmadi'}",
        f"⏱ <b>Davomiyligi:</b> {dur_m}m {dur_s}s",
        f"🎭 <b>Kayfiyat:</b> {client_mood} | <b>Toifa:</b> {category}",
    ]
    if score:
        msg_lines.append(f"⭐️ <b>Sifat Bahosi:</b> {score}/100")
    if outcome:
        msg_lines.append(f"📊 <b>Natija:</b> {outcome}")
    if objections:
        msg_lines.append(f"⚠️ <b>E'tirozlar:</b> {objections}")

    msg_lines.append(f"📝 <b>Xulosa:</b> {summary}")

    agreed_time_str = _format_agreed_time(analysis)
    if agreed_time_str:
        msg_lines.append(agreed_time_str.strip())

    msg_lines.append(f"🎯 <b>Keyingi qadam:</b> {next_steps}")

    rec_str = _format_conversion_recommendations(analysis)
    if rec_str:
        msg_lines.append(rec_str)

    if task_id:
        msg_lines.append(f"✅ <b>AmoCRM Vazifasi:</b> Biriktirildi (Task #{task_id})")

    return "\n".join(msg_lines)


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

        msg_text = build_call_alert_message(
            lead_id=lead_id,
            call_id=call_id,
            category=category,
            summary=summary,
            client_mood=client_mood,
            next_steps=next_steps,
            duration_seconds=duration_seconds,
            manager_name=manager_name,
            caller_phone=caller_phone,
            analysis=analysis,
            task_id=task_id,
            subdomain=subdomain,
        )

        kwargs: Dict[str, Any] = {"parse_mode": "HTML", "disable_web_page_preview": True}
        if topic_id:
            kwargs["reply_to_message_id"] = topic_id

        if hasattr(bot_client, "send_message"):
            await bot_client.send_message(chat_id=target_chat_id, text=msg_text, **kwargs)
    except Exception as exc:
        logger.warning("[CALL] Failed to notify Telegram for call %s: %s", call_id, exc)
