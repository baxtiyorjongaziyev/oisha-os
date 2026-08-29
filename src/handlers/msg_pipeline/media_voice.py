"""
Voice transcription and image/document vision analysis pipeline handler.
"""
import asyncio
import logging
import os
import tempfile
from typing import Any, Dict, Optional

from src.settings import settings
from src.context import app_ctx

logger = logging.getLogger("OishaMediaVoice")

_vision_cache: Dict[str, Any] = {}

async def process_voice(
    event,
    *,
    client: "TelegramClient",
    sender,
    sender_name: str,
    msg_controller,
    voice_processor,
    admin_bot,
    surgical_integration,
    auto_reply_gate,
) -> None:
    """Ovozli xabarlarni Gemini STT orqali qayta ishlash."""
    logger.info("🎙️ [VOICE] New voice from %s...", sender_name)
    try:
        temp_path = f"temp_voice_{event.id}.ogg"
        await client.download_media(event.message, file=temp_path)

        try:
            from src.agents.negotiation_engine import transcribe_and_assess_audio

            with open(temp_path, "rb") as f:
                audio_bytes = f.read()
            crm_status = ""
            if hasattr(msg_controller, "crm"):
                try:
                    user_info = await msg_controller.db.get_user_info(
                        event.sender_id
                    )
                    phone = user_info.get("phone") if user_info else None
                    if phone:
                        crm_status = await msg_controller.crm.get_user_context(
                            phone
                        )
                except Exception as exc:
                    logger.debug("[VOICE] CRM context lookup failed: %s", exc)

            async with client.action(event.chat_id, 'typing'):
                stt_result = await transcribe_and_assess_audio(
                    audio_bytes, mime_type="audio/ogg", crm_status=crm_status
                )
            transcript = stt_result.get("transcript", "")
            assessment = stt_result.get("assessment")

            if transcript:
                admin_note = f"🎙️ **Ovozli xabar ({sender_name}):**\n\n{transcript}"
                if assessment:
                    admin_note += (
                        f"\n\n🔍 **Assessment:** stage={assessment.stage} "
                        f"| intent={assessment.intent} "
                        f"| prob={assessment.close_probability:.0%}"
                    )
                if admin_bot:
                    await admin_bot.notify_lead(admin_note)

                if (
                    surgical_integration
                    and surgical_integration.should_use_surgical(
                        str(event.sender_id), transcript
                    )
                ):
                    surgical_result = await surgical_integration.process_message(
                        str(event.sender_id),
                        transcript,
                        context={"source": "voice", "user_info": {}},
                    )
                    if surgical_result.get("mode") == "surgical":
                        voice_reply = surgical_result.get("response", "")
                        if voice_reply:
                            _voice_decision = await auto_reply_gate.evaluate(
                                msg_controller.db,
                                is_mentioned=False,
                                lead_score=0,
                                message_text=transcript or "",
                            )
                            if _voice_decision.action == "send":
                                await event.reply(voice_reply)
                                logger.info(
                                    "[VOICE→SURGICAL] Auto-replied to %s",
                                    sender_name,
                                )
                            else:
                                logger.info(
                                    "[VOICE→SURGICAL] Skipped reply (gate=%s)",
                                    _voice_decision.action,
                                )

        except Exception as stt_err:
            logger.warning("[VOICE] Gemini STT failed, fallback: %s", stt_err)
            result = await voice_processor.transcribe(temp_path)
            if result and admin_bot:
                await admin_bot.notify_lead(
                    f"🎙️ **Ovozli xabar ({sender_name}):**\n\n{result}"
                )

        asyncio.create_task(voice_processor.cleanup(temp_path))
    except Exception as exc:
        logger.error("[VOICE] Integration error: %s", exc)


# ---------------------------------------------------------------------------
# 6. Media/Document — Google Drive upload
# ---------------------------------------------------------------------------

def _resolve_gemini_client(voice_processor) -> Any:
    """Vision uchun Gemini client topish — avval voice_processor, keyin yangi client."""
    client = getattr(voice_processor, "client", None)
    if client is not None:
        return client

    try:
        from src.settings import settings as _s
        from src.services.utils.voice_processor import VoiceProcessor

        gemini_key = getattr(_s, "GEMINI_API_KEY", None)
        if not gemini_key:
            return None
        key_val = (
            gemini_key.get_secret_value()
            if hasattr(gemini_key, "get_secret_value")
            else str(gemini_key)
        )
        if not key_val:
            return None
        return VoiceProcessor(api_key=key_val).client
    except Exception as exc:
        logger.debug("[DM-VISION] Gemini client olinmadi: %s", exc)
        return None


async def _analyze_dm_photo(
    media_path: str,
    *,
    event,
    sender_name: str,
    msg_controller,
    voice_processor,
) -> Optional[dict]:
    """
    DM rasmini tahlil qilib, natijani CRM notesiga va reply kontekstiga yozish.

    Tahlil qo'shimcha imkoniyat — bu yerdagi hech qanday xato Drive yuklash
    oqimini to'xtatmasligi kerak, shuning uchun hammasi yutib yuboriladi.
    """
    from src.settings import settings as _settings

    if not getattr(_settings, "DM_VISION_ENABLED", True):
        return None

    gemini_client = _resolve_gemini_client(voice_processor)
    if not gemini_client:
        logger.debug("[DM-VISION] Gemini client yo'q — tahlil o'tkazib yuborildi")
        return None

    from src.services.core.dm_vision import (
        analyze_dm_image,
        format_for_ai_context,
        format_for_crm_note,
    )

    result = await analyze_dm_image(gemini_client, media_path)
    if not result:
        return None

    # 1. AI javob konteksti — process_ai_reply shu yerdan o'qiydi.
    #    Faqat xotirada saqlanadi; auto_reply_gate hukmiga ta'sir qilmaydi.
    try:
        from src.context import app_ctx

        cache = getattr(app_ctx, "dm_vision_context", None)
        if cache is None:
            cache = {}
            app_ctx.dm_vision_context = cache
        cache[event.chat_id] = {
            "text": format_for_ai_context(result),
            "message_id": getattr(event.message, "id", None),
        }
    except Exception as exc:
        logger.debug("[DM-VISION] Kontekst saqlanmadi: %s", exc)

    # 2. AmoCRM notesi — faqat biznesga aloqador rasmlar uchun, aks holda
    #    shaxsiy fotolar bilan sdelka tarixi ifloslanadi.
    if result.get("is_business_relevant"):
        try:
            note = format_for_crm_note(result, sender_name)
            phone = None
            user_info = await msg_controller.db.get_user_info(event.sender_id)
            if user_info:
                phone = user_info.get("phone")
            contact_phone = (result.get("contact") or {}).get("phone")
            await msg_controller.crm.sync_lead(
                user_id=event.sender_id,
                name=f"DM Lead: {sender_name}",
                phone=phone or contact_phone or "Raqam yo'q",
                note=note,
            )
        except Exception as exc:
            logger.warning("[DM-VISION] CRM notesi yozilmadi: %s", exc)

    return result


async def process_media(
    event,
    *,
    client: "TelegramClient",
    sender_name: str,
    msg_controller,
    admin_bot,
    voice_processor=None,
) -> None:
    """Media/hujjatlarni tahlil qilish va Google Drive ga yuklash."""
    logger.info("📁 [MEDIA] New media from %s...", sender_name)
    media_path = None
    try:
        media_path = await client.download_media(event.message)
        if media_path:
            vision_result = None
            if event.message.photo:
                try:
                    vision_result = await _analyze_dm_photo(
                        media_path,
                        event=event,
                        sender_name=sender_name,
                        msg_controller=msg_controller,
                        voice_processor=voice_processor,
                    )
                except Exception as exc:
                    logger.warning("[DM-VISION] Tahlil xatosi: %s", exc)

            def upload_drive():
                return msg_controller.google.drive.upload_file(media_path)

            drive_link = await asyncio.to_thread(upload_drive)

            if drive_link:
                if admin_bot:
                    type_str = "Rasm" if event.message.photo else "Hujjat"
                    notify_lines = [
                        f"📁 **Yangi {type_str} ({sender_name}):**",
                        f"🔗 [Google Drive Link]({drive_link})",
                    ]
                    if vision_result:
                        notify_lines.append(
                            f"🖼 **Tahlil:** {vision_result.get('summary', '')}"
                        )
                        contact = vision_result.get("contact") or {}
                        if contact.get("phone"):
                            notify_lines.append(
                                f"📞 **Rasmdan raqam:** {contact['phone']}"
                            )
                    await admin_bot.notify_lead("\n".join(notify_lines))

    except Exception as exc:
        logger.error("[MEDIA] Integration error: %s", exc)
    finally:
        if media_path and os.path.exists(media_path):
            try:
                os.remove(media_path)
            except OSError as exc:
                logger.debug("[MEDIA] Temp fayl o'chmadi: %s", exc)
