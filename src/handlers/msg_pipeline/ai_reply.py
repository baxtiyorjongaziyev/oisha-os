from __future__ import annotations

import logging
from typing import Optional
from telethon import TelegramClient


logger = logging.getLogger("OishaAiReply")

def _pop_vision_context(chat_id: int) -> Optional[str]:
    """
    Shu chat uchun saqlangan rasm tahlilini olib, keshdan o'chirish.

    Bir marta ishlatiladi: aks holda bitta rasm keyingi barcha javoblarga
    ergashib, mavzu allaqachon o'zgargan bo'lsa ham kontekstni buzadi.
    """
    try:
        from src.context import app_ctx

        cache = getattr(app_ctx, "dm_vision_context", None)
        if not cache:
            return None
        entry = cache.pop(chat_id, None)
        if not entry:
            return None
        return entry.get("text") or None
    except Exception as exc:
        logger.debug("[DM-VISION] Kontekst o'qilmadi: %s", exc)
        return None


async def process_ai_reply(
    event,
    *,
    client: "TelegramClient",
    sender,
    chat_id: int,
    sender_name: str,
    message_text: str,
    msg_controller,
    auto_reply_gate,
    safe_responder,
    scouter,
    surgical_integration,
    action_parser,
    admin_bot,
) -> None:
    """Auto-reply gate orqali AI javobini generatsiya qilish va yuborish."""
    try:
        is_mentioned = False
        if event.message.text:
            me = await client.get_me()
            text_low = event.message.text.lower()
            me_username = (me.username or "").lower()
            is_mentioned = bool(me_username and f"@{me_username}" in text_low)

        decision = await auto_reply_gate.evaluate(
            msg_controller.db,
            is_mentioned=is_mentioned,
            lead_score=0,
            message_text=event.message.text or "",
        )
        logger.info(
            "[AUTO_GATE] chat=%s action=%s reason=%s "
            "mode=%s kill=%s",
            chat_id,
            decision.action,
            decision.reason,
            decision.effective_mode,
            decision.kill_switch_on,
        )

        if decision.action == "skip":
            return
        if decision.action == "escalate":
            if admin_bot:
                try:
                    await admin_bot.notify_lead(
                        f"🚨 **REVIEW kerak** chat=`{chat_id}` sender={sender_name}\n"
                        f"Sabab: `{decision.reason}`\n"
                        f"Matn: {(event.message.text or '')[:500]}"
                    )
                except Exception as notify_ex:
                    logger.warning("[AUTO_GATE] escalate notify failed: %s", notify_ex)
            return

        dosye = await scouter.get_user_dosye(sender.id)

        # Shu chatda yaqinda yuborilgan rasm tahlili (process_media yozadi).
        # Faqat prompt kontekstini boyitadi — gate qarori yuqorida chiqarilgan
        # va bu yerda o'zgarmaydi, shuning uchun shadow rejimi shadow qoladi.
        vision_context = _pop_vision_context(chat_id)

        await safe_responder.prepare_to_reply(event, client)

        ai_raw_response = None
        
        async with event.client.action(chat_id, 'typing'):
            if surgical_integration and surgical_integration.should_use_surgical(
                str(sender.id), message_text or ""
            ):
                try:
                    surgical_context = {
                        "user_info": {
                            "first_name": getattr(sender, "first_name", ""),
                            "last_name": getattr(sender, "last_name", ""),
                            "username": getattr(sender, "username", ""),
                        },
                        "chat_id": chat_id,
                        "source": "telegram",
                    }
                    if vision_context:
                        surgical_context["image_context"] = vision_context
                    surgical_result = await surgical_integration.process_message(
                        user_id=str(sender.id),
                        message=message_text or "",
                        context=surgical_context,
                    )
                    if surgical_result.get("mode") == "surgical":
                        ai_raw_response = surgical_result.get("response")
                        logger.info(
                            "[SURGICAL] Autonomous response uid=%s "
                            "stage=%s prob=%s",
                            sender.id,
                            surgical_result.get("deal_info", {}).get("stage"),
                            f"{surgical_result.get('deal_info', {}).get('probability', 0):.0%}",
                        )
                        if surgical_result.get("deal_info", {}).get("probability", 1) < 0.2:
                            ai_raw_response = None
                except Exception as surg_ex:
                    logger.warning("[SURGICAL] Fallback to legacy: %s", surg_ex)

            if not ai_raw_response:
                legacy_context = {
                    "chat_id": chat_id,
                    "is_group": not event.is_private,
                    "dosye": dosye,
                }
                if vision_context:
                    legacy_context["image_context"] = vision_context
                ai_raw_response = await msg_controller.get_response(
                    user_id=sender.id,
                    user_name=sender_name,
                    message=message_text,
                    context=legacy_context,
                )

            if ai_raw_response:
                final_text = await action_parser.parse_and_execute(
                    reply_text=ai_raw_response,
                    sender_id=sender.id,
                    sender_name=sender_name,
                    username=getattr(sender, "username", "yoq"),
                    saved_phone=None,
                    context=None,
                    is_business=False,
                )

        if ai_raw_response and final_text:
                if decision.action == "shadow":
                    if admin_bot:
                        try:
                            await admin_bot.notify_lead(
                                f"👁 **SHADOW PREVIEW** chat=`{chat_id}` sender={sender_name}\n"
                                f"Rejim: `{decision.effective_mode}` ({decision.reason})\n"
                                f"📥 User: {(event.message.text or '')[:300]}\n"
                                f"🤖 Bot draft: {final_text[:500]}"
                            )
                        except Exception as notify_ex:
                            logger.warning(
                                "[AUTO_GATE] shadow notify failed: %s", notify_ex
                            )
                    try:
                        await msg_controller.db.log_message(
                            sender.id, final_text, is_ai=True
                        )
                    except Exception as log_ex:
                        logger.error(
                            "[USERBOT] Failed to log AI reply (shadow): %s", log_ex
                        )
                    logger.info("[USERBOT] Shadow preview queued for chat %s", chat_id)
                else:
                    # STRICT OWNER POLICY: Never send outbound AI replies from personal userbot account (@baxtiyorjon_gaziyev)
                    logger.info(
                        "[USERBOT] Outbound AI reply from userbot account is strictly disabled for chat %s (%s)",
                        chat_id,
                        sender_name,
                    )
                    try:
                        await msg_controller.db.log_message(
                            sender.id, final_text, is_ai=True
                        )
                    except Exception as log_ex:
                        logger.error("[USERBOT] Failed to log AI reply: %s", log_ex)

    except Exception as exc:
        logger.error("[USERBOT] Error while handling message: %s", exc)
