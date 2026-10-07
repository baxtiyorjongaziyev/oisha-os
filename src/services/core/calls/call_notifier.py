"""Telegram call intelligence proactive notification module."""

from __future__ import annotations

import logging
import os
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
        f"📞 <b>Telefon:</b> {caller_phone or 'N/A'}",
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


def is_problem_call(analysis: Dict[str, Any]) -> bool:
    """Qo'ng'iroqda muammo yoki hal qilinmagan e'tiroz bor-yo'qligini aniqlash."""
    score = analysis.get("sifat_bahosi") or analysis.get("overall_score")
    try:
        if score is not None and int(score) < 60:
            return True
    except (ValueError, TypeError):
        pass
    objections = analysis.get("etirozlar") or analysis.get("objections")
    if objections and isinstance(objections, list) and len(objections) > 0:
        return True
    mood = str(analysis.get("client_mood") or "").lower()
    if any(m in mood for m in ("salbiy", "negative", "e'tiroz", "jahl", "xafa", "norizo")):
        return True
    outcome = str(analysis.get("natija") or analysis.get("outcome") or "").lower()
    if any(o in outcome for o in ("yo'qotildi", "rad", "lost")):
        return True
    return False


def build_urgent_problem_alert(
    *,
    lead_id: int,
    call_id: str,
    summary: str,
    client_mood: str,
    duration_seconds: int,
    manager_name: str,
    caller_phone: str,
    analysis: Dict[str, Any],
    subdomain: str = "jonbranding",
) -> str:
    """Muammoli yoki e'tirozli qo'ng'iroqlar uchun shoshilinch SOS kartasi."""
    dur_m = int(duration_seconds or 0) // 60
    dur_s = int(duration_seconds or 0) % 60
    lead_url = f"https://{subdomain}.amocrm.ru/leads/detail/{lead_id}"

    score = analysis.get("sifat_bahosi") or analysis.get("overall_score") or "Noma'lum"
    objections = analysis.get("etirozlar") or analysis.get("objections") or []
    if isinstance(objections, list):
        objections = ", ".join(str(o) for o in objections if str(o).strip())

    lines = [
        "🚨 <b>DIQQAT: Qo'ng'iroqda muammo / E'tiroz aniqlandi!</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"👤 <b>Lid:</b> <a href=\"{lead_url}\">AmoCRM Lead #{lead_id}</a>",
        f"📞 <b>Telefon:</b> {caller_phone or 'N/A'}",
        f"🧑‍💼 <b>Menejer:</b> {manager_name or 'Aniqlanmadi'} · ⏱ {dur_m}m {dur_s}s",
        f"⭐️ <b>Sifat Bahosi:</b> {score}/100 🔴",
        f"🎭 <b>Kayfiyat:</b> {client_mood or 'Salbiy'}",
    ]
    if objections:
        lines.append(f"⚠️ <b>E'tiroz:</b> <i>{objections}</i>")
    lines.append(f"📝 <b>Muammo xulosasi:</b> {summary}")

    rec_str = _format_conversion_recommendations(analysis)
    if rec_str:
        lines.append(rec_str)
    else:
        lines.append("💡 <b>Tavsiya:</b> 15 daqiqa ichida qayta bog'lanish yoki ROP aralashuvi tavsiya etiladi.")
    return "\n".join(lines)


async def _dispatch_telegram_message(
    text: str,
    target_chat_id: Any,
    topic_id: Any = None,
) -> bool:
    """Telegram xabarini bot_client yoki Bot API orqali yuborish."""
    import os
    import requests
    from src.context import app_ctx

    bot_client = getattr(app_ctx, "bot_runtime", None) or getattr(app_ctx, "bot_client", None)
    kwargs: Dict[str, Any] = {"parse_mode": "HTML", "disable_web_page_preview": True}
    if topic_id:
        try:
            kwargs["message_thread_id"] = int(topic_id)
        except (ValueError, TypeError):
            pass

    if bot_client and hasattr(bot_client, "send_message"):
        try:
            await bot_client.send_message(chat_id=target_chat_id, text=text, **kwargs)
            return True
        except Exception as exc:
            logger.warning("[CALL] bot_client orqali yuborishda xatolik: %s", exc)

    # Fallback to direct Bot API HTTP request
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if bot_token and target_chat_id:
        payload = {"chat_id": target_chat_id, "text": text, **kwargs}
        try:
            res = requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json=payload, timeout=10)
            return res.status_code == 200
        except Exception as exc:
            logger.warning("[CALL] Bot API HTTP fallback xatolik: %s", exc)

    from src.services.core.instagram.leadgen_watchdog import send_admin_alert
    return send_admin_alert(text)


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
        from src.settings import settings

        target_chat_id = (
            getattr(settings, "CALL_ANALYSIS_GROUP_ID", None)
            or getattr(settings, "AMOCRM_ALERT_FORWARD_GROUP_ID", None)
            or getattr(settings, "CRM_GROUP_ID", None)
            or getattr(settings, "TARGET_LEADS_GROUP_ID", None)
            or os.getenv("TARGET_LEADS_GROUP_ID", "-1003854308552")
        )
        topic_id = (
            getattr(settings, "CALL_ANALYSIS_TOPIC_ID", None)
            or getattr(settings, "AMOCRM_ALERT_FORWARD_TOPIC_ID", None)
            or getattr(settings, "TARGET_LEADS_TOPIC_ID", None)
        )

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

        await _dispatch_telegram_message(msg_text, target_chat_id, topic_id)
        logger.info(
            "[CALL] Telegram alert sent for call %s -> chat %s topic %s",
            call_id,
            target_chat_id,
            topic_id,
        )

        # Agar qo'ng'iroqda muammo yoki e'tiroz bo'lsa, shoshilinch SOS alerti ham yuboriladi
        if is_problem_call(analysis):
            urgent_text = build_urgent_problem_alert(
                lead_id=lead_id,
                call_id=call_id,
                summary=summary,
                client_mood=client_mood,
                duration_seconds=duration_seconds,
                manager_name=manager_name,
                caller_phone=caller_phone,
                analysis=analysis,
                subdomain=subdomain,
            )
            await _dispatch_telegram_message(urgent_text, target_chat_id, topic_id)
            logger.info("[CALL] Urgent problem alert sent for call %s", call_id)

    except Exception as exc:
        logger.warning("[CALL] Failed to notify Telegram for call %s: %s", call_id, exc)
