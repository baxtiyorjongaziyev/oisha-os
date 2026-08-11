import logging
import os
from typing import Optional
from src.services.core.finance.hisobchi_engine import HisobchiEngine, _fmt_money
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)

async def handle_receipt_photo(
    event, engine: HisobchiEngine, client=None, voice_processor=None, direction: Optional[str] = None
) -> bool:
    msg = event.message
    photo = getattr(msg, "photo", None)
    if not photo:
        return False

    temp_path = None
    try:
        await event.reply("⏳ Chek o'qilmoqda...")
        temp_path = f"temp_hisobchi_photo_{event.id}.jpg"
        dl_client = client or event.client
        await dl_client.download_media(msg, file=temp_path)

        from src.services.core.hisobchi_vision import process_receipt_photo

        gemini_client = voice_processor.client if voice_processor else None
        if not gemini_client:
            from src.services.utils.voice_processor import VoiceProcessor
            from src.settings import settings as _s
            gemini_key = getattr(_s, "GEMINI_API_KEY", None)
            if gemini_key:
                try:
                    gemini_key_val = gemini_key.get_secret_value() if hasattr(gemini_key, "get_secret_value") else str(gemini_key)
                    vp = VoiceProcessor(api_key=gemini_key_val)
                    gemini_client = vp.client
                except Exception as exc:
                    logger.error("Error occurred: %s", exc, exc_info=True)
        if not gemini_client:
            await event.reply("⚠️ Gemini client yoqilmagan.")
            return True
        parsed = await process_receipt_photo(gemini_client, temp_path)
        if not parsed:
            await event.reply("⚠️ Rasmda chek/chek ma'lumotlari topilmadi.")
            return True

        amount = parsed["amount"]
        merchant = parsed["merchant"]
        category = parsed.get("category", "Boshqa")
        notes = parsed.get("notes", "")
        now = get_local_now()
        tx_time = now.strftime("%H:%M %d.%m.%Y")

        dir_val = direction or "out"

        tx_id = await engine.save_transaction(
            source_bot="photo",
            direction=dir_val,
            amount=amount,
            merchant=merchant,
            card_suffix="",
            tx_time=tx_time,
            balance=None,
            raw_text=f"[Chek] {merchant}: {amount} UZS",
            category=category,
            ownership="business",
            status="categorized",
            reason=notes,
        )
        icon = "➖ Chiqim" if dir_val == "out" else "➕ Kirim"
        reply = (
            f"📸 <b>Chek #{tx_id} — qabul qilindi!</b>\n"
            f"{icon}: <b>{_fmt_money(amount)} UZS</b>\n"
            f"📍 {merchant}\n"
            f"🗂 {category}"
        )
        if notes:
            reply += f"\n📝 {notes}"
        await event.reply(reply, parse_mode="html")
        return True

    except Exception as exc:
        logger.error("Error occurred: %s", exc, exc_info=True)
        try:
            await event.reply(f"❌ Xatolik yuz berdi: {str(exc)}")
        except Exception:
            pass
        return True
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as exc:
                logger.error("Error occurred: %s", exc, exc_info=True)
