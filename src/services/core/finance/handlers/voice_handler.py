import logging
import os
import html
from src.services.core.finance.hisobchi_engine import HisobchiEngine
from src.time_utils import get_local_now
from .manual_handler import parse_transaction_text_with_llm
from .utils import resolve_finance_destination

logger = logging.getLogger(__name__)

async def process_finance_voice_message(
    event, client, engine: HisobchiEngine, voice_processor
) -> bool:
    msg = event.message
    if not getattr(msg, "voice", None):
        return False

    temp_path = f"temp_hisobchi_voice_{event.id}.ogg"
    try:
        await client.download_media(msg, file=temp_path)

        transcript = await voice_processor.transcribe(temp_path, mode="voice")
        if not transcript:
            logger.warning("[HISOBCHI-VOICE] Transcription returned empty result")
            return False

        text_to_parse = transcript
        if "Matn:" in transcript:
            parts = transcript.split("|")
            for part in parts:
                if "Matn:" in part:
                    text_to_parse = part.replace("Matn:", "").strip()
                    break

        logger.info("[HISOBCHI-VOICE] Transcribed: %s", text_to_parse)

        parsed = await parse_transaction_text_with_llm(
            client=voice_processor.client,
            model_name=voice_processor.model_name,
            text=text_to_parse,
        )
        if not parsed:
            logger.warning("[HISOBCHI-VOICE] LLM failed to parse transcript: %s", text_to_parse)
            return False

        if not parsed.get("is_transaction"):
            logger.info("[HISOBCHI-VOICE] Not a transaction voice message: %s", text_to_parse)
            return False

        amount = parsed.get("amount", 0)
        direction = parsed.get("direction", "out")
        merchant = parsed.get("merchant", "Noma'lum")
        category = parsed.get("category", "Boshqa")
        ownership = parsed.get("ownership", "business")
        reason = parsed.get("reason", "")
        confidence = parsed.get("confidence")

        _LOW_CONFIDENCE = 0.6
        low_confidence = isinstance(confidence, (int, float)) and confidence < _LOW_CONFIDENCE
        if low_confidence:
            await engine.log_ai_gap(
                kind="low_confidence",
                reason=f"LLM ishonch darajasi past ({confidence}) — amount/direction noaniq bo'lishi mumkin",
                source="voice",
                raw_text=text_to_parse,
                confidence=float(confidence),
                chat_id=event.chat_id,
            )

        reply_to = getattr(msg, "reply_to", None)
        replied_msg_id = getattr(reply_to, "reply_to_msg_id", None) if reply_to else None

        tx = None
        finance_group_id, _, _ = await resolve_finance_destination(client)
        if replied_msg_id and finance_group_id:
            tx = await engine.get_pending_by_finance_msg(
                finance_chat_id=finance_group_id,
                finance_msg_id=replied_msg_id,
            )

        if tx:
            tx_id = tx["id"]
            merchant = tx["merchant"]

            await engine.categorize(tx_id, category, ownership, reason=reason)
            await engine.learn_rule(
                merchant=merchant,
                card_suffix=tx.get("card_suffix", ""),
                direction=tx["direction"],
                amount=int(tx["amount"]),
                category=category,
                ownership=ownership,
            )

            amount_str = f"{tx['amount']:,}".replace(",", " ")
            direction_icon = "➖" if tx["direction"] == "out" else "➕"
            own_label = "Biznes" if ownership == "business" else "Shaxsiy"

            await event.reply(
                f"🎙️ <b>Ovozli javob qabul qilindi!</b>\n"
                f"{direction_icon} {amount_str} UZS — <b>{html.escape(category)} ({own_label})</b>\n"
                f"📍 {html.escape(merchant)}\n"
                f"🧠 Keyingi safar avtomatik toifalanadi.",
                parse_mode="html",
            )
            logger.info("[HISOBCHI-VOICE] tx #%s categorized as '%s' (%s) from voice reply", tx_id, category, ownership)
            return True
        else:
            if amount <= 0:
                await event.reply("⚠️ Ovozli xabardan tranzaksiya summasini aniqlab bo'lmadi. Iltimos, summani aniqroq ayting.")
                return True

            tx_time_str = get_local_now().strftime("%H:%M %d.%m.%Y")

            tx_id = await engine.save_transaction(
                source_bot="voice",
                direction=direction,
                amount=amount,
                merchant=merchant,
                card_suffix="",
                tx_time=tx_time_str,
                balance=None,
                raw_text=text_to_parse,
                category=category,
                ownership=ownership,
                status="categorized",
                reason=reason,
            )

            amount_str = f"{amount:,}".replace(",", " ")
            direction_icon = "➖ Chiqim" if direction == "out" else "➕ Kirim"
            own_label = "Biznes" if ownership == "business" else "Shaxsiy"
            reason_line = f"\n📝 Izoh: {reason}" if reason else ""
            confidence_warning = (
                "\n\n⚠️ Ishonchim past — summani/yo'nalishni tekshirib qo'ying." if low_confidence else ""
            )

            await event.reply(
                f"🎙️ <b>Ovozli to'lov #{tx_id} kiritildi!</b>\n\n"
                f"{direction_icon}: <b>{amount_str} UZS</b> ({own_label})\n"
                f"📍 {html.escape(merchant)}\n"
                f"🗂 Toifa: <b>{html.escape(category)}</b>"
                f"{html.escape(reason_line)}"
                f"{confidence_warning}",
                parse_mode="html",
            )
            logger.info("[HISOBCHI-VOICE] Manual tx #%s saved as '%s' (%s) from standalone voice", tx_id, category, ownership)
            return True

    except Exception as exc:
        logger.error("Error occurred: %s", exc, exc_info=True)
        try:
            await event.reply(f"❌ Xatolik yuz berdi: {str(exc)}")
        except Exception:
            pass
    finally:
        if os.path.exists(temp_path):
            try:
                await voice_processor.cleanup(temp_path)
            except Exception as exc:
                logger.error("Error occurred: %s", exc, exc_info=True)

    return False
