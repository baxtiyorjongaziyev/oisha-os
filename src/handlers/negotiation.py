"""Negotiation agent handler for autonomous sales conversations."""
from __future__ import annotations

import logging
import os
import time
import asyncio

from src.context import app_ctx
from src.settings import settings

logger = logging.getLogger(__name__)


def _negotiation_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _should_block_private_userbot_reply(event) -> bool:
    return bool(getattr(event, "is_private", False)) and not bool(
        getattr(event, "out", False)
    )


async def _is_personal_folder_sender(sender) -> bool:
    return False


async def negotiation_agent_handler(event):
    """Safe autonomous negotiation for allowed Telegram messages."""
    if not _env_enabled("ENABLE_AI_NEGOTIATION"):
        return
    if _should_block_private_userbot_reply(event):
        logger.info(
            "[NEGOTIATION] Personal DM ignored by policy chat=%s", event.chat_id
        )
        return
    if event.out or not event.is_private or not getattr(event.message, "text", None):
        return

    message_date = getattr(event.message, "date", None)
    max_age = _negotiation_int("NEGOTIATION_MAX_MESSAGE_AGE_SECS", 600)
    if message_date and time.time() - message_date.timestamp() > max_age:
        return

    sender = await event.get_sender()
    if getattr(sender, "bot", False):
        return
    if app_ctx.safe_responder and await app_ctx.safe_responder.is_team_member(
        event.sender_id, getattr(sender, "username", None)
    ):
        return
    if await _is_personal_folder_sender(sender):
        logger.info(f"[NEGOTIATION] Personal/family folder skip chat={event.chat_id}")
        return

    text = (event.message.text or "").strip()
    if not text or text.startswith("/"):
        return
    from src.services.core.auto_lead_agent import detect_non_customer_context
    non_customer_reason = detect_non_customer_context(text)
    if non_customer_reason:
        logger.info(
            f"[NEGOTIATION] Non-customer context skip chat={event.chat_id} reason={non_customer_reason}"
        )
        return

    chat_id = event.chat_id
    db = app_ctx.msg_controller.db
    last_msg_key = f"negotiation:last_msg:{chat_id}"
    if str(await db.get_state(last_msg_key, "")) == str(event.id):
        return
    await db.set_state(last_msg_key, event.id)

    reply_delay = _negotiation_int("NEGOTIATION_REPLY_DELAY_SECS", 8)
    if reply_delay > 0:
        await asyncio.sleep(reply_delay)
        latest = await app_ctx.client.get_messages(chat_id, limit=1)
        if latest and latest[0].id != event.id:
            return

    now = time.time()
    cooldown = _negotiation_int("NEGOTIATION_COOLDOWN_SECS", 120)
    last_reply_key = f"negotiation:last_reply_at:{chat_id}"
    try:
        last_reply_at = float(await db.get_state(last_reply_key, "0") or 0)
    except (TypeError, ValueError):
        last_reply_at = 0.0
    if now - last_reply_at < cooldown:
        logger.info(f"[NEGOTIATION] Cooldown skip chat={chat_id}")
        return

    day = time.strftime("%Y-%m-%d", time.localtime(now))
    daily_key = f"negotiation:daily_count:{chat_id}:{day}"
    try:
        daily_count = int(await db.get_state(daily_key, "0") or 0)
    except (TypeError, ValueError):
        daily_count = 0
    daily_limit = _negotiation_int("NEGOTIATION_DAILY_LIMIT", 25)
    if daily_count >= daily_limit:
        logger.info(f"[NEGOTIATION] Daily limit skip chat={chat_id}")
        return

    sender_name = getattr(sender, "first_name", "Mijoz")
    username = getattr(sender, "username", None)

    sender_profile = {"id": sender.id, "first_name": sender_name, "username": username}
    try:
        known_customer = await db.is_crm_synced(sender.id)
    except Exception:
        known_customer = False

    lead_data = None
    try:
        lead_data = await app_ctx.auto_lead_agent.extract_lead_info(text, sender_profile)
    except Exception as exc:
        logger.warning(
            f"[NEGOTIATION] Lead classification failed chat={chat_id}: {type(exc).__name__}"
        )

    if not known_customer and not (lead_data and lead_data.get("is_lead")):
        intent = (lead_data or {}).get("intent_category", "NO_SIGNAL")
        logger.info(
            f"[NEGOTIATION] Non-customer/no-lead skip chat={chat_id} intent={intent}"
        )
        return

    try:
        await db.log_message(sender.id, text, is_ai=False)
    except Exception as exc:
        logger.debug(f"[NEGOTIATION] Incoming log skipped: {exc}")

    try:
        if (
            lead_data
            and lead_data.get("is_lead")
            and not await db.is_crm_synced(sender.id)
        ):
            phone = (
                lead_data.get("phone") or getattr(sender, "phone", None) or "Raqam yo'q"
            )
            await app_ctx.msg_controller.crm.sync_lead(
                user_id=sender.id,
                name=f"DM Lead: {sender_name}",
                phone=phone,
                note=f"AI negotiation intake\nIntent: {lead_data.get('intent_category')}\nEhtiyoj: {lead_data.get('needs')}\nTelegram: @{username or 'yoq'}",
            )
            await db.set_crm_synced(sender.id)
    except Exception as exc:
        logger.warning(
            f"[NEGOTIATION] CRM intake skipped chat={chat_id}: {type(exc).__name__}"
        )

    high_risk_terms = ("shikoyat", "qaytarish", "advokat", "sud", "aldadi", "firibgar")
    if any(term in text.lower() for term in high_risk_terms):
        final_text = (
            "Xabaringizni qabul qildim. Bu masalani e'tibor bilan ko'rib chiqish kerak, "
            "shuning uchun Baxtiyor akaga yetkazaman va sizga aniq javob bilan qaytamiz."
        )
    else:
        try:
            final_text = await app_ctx.msg_controller.get_response(
                user_id=sender.id,
                user_name=sender_name,
                message=text,
                context={
                    "source": "autonomous_negotiation",
                    "policy": "Be concise, warm, professional. Ask one clear next-step question. Do not overpromise discounts, deadlines, or legal guarantees.",
                    "telegram_username": username,
                },
            )
        except Exception as exc:
            logger.warning(
                f"[NEGOTIATION] AI response fallback chat={chat_id}: {type(exc).__name__}"
            )
            final_text = (
                "Assalomu alaykum! Xabaringizni oldim. Loyihangiz bo'yicha to'g'ri yo'naltirishim uchun "
                "faoliyatingiz, asosiy maqsadingiz va sizga qulay bog'lanish vaqtini yozib yuboring."
            )

    final_text = (final_text or "").strip()
    if not final_text:
        return
    if len(final_text) > 1200:
        final_text = final_text[:1190].rstrip() + "..."

    async with app_ctx.client.action(chat_id, "typing"):
        await asyncio.sleep(1)
    sent = await event.respond(final_text)
    await db.set_state(last_reply_key, int(now))
    await db.set_state(daily_key, daily_count + 1)
    await db.set_state(f"negotiation:last_sent_msg:{chat_id}", getattr(sent, "id", ""))
    try:
        await db.log_message(sender.id, final_text, is_ai=True)
    except Exception as exc:
        logger.debug(f"[NEGOTIATION] Outgoing log skipped: {exc}")
    logger.info(f"[NEGOTIATION] Replied chat={chat_id} msg={event.id}")
