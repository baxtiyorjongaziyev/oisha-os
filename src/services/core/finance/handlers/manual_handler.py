import logging
import re
import json
import html
from typing import Optional

from src.services.core.finance.hisobchi_engine import HisobchiEngine, _fmt_money
from src.services.utils.gemini_fallback import generate_content_with_fallback
from src.time_utils import get_local_now
from .utils import _reply_via_bot, resolve_finance_destination

logger = logging.getLogger(__name__)

_MAX_REPLY_LEN = 500
_MAX_CATEGORY_LEN = 100

async def parse_transaction_text_with_llm(client, model_name: str, text: str) -> Optional[dict]:
    system_prompt = """
    Foydalanuvchining o'zbek tilidagi ovozli xabar matnini (transkript) tahlil qiling va undan quyidagi ma'lumotlarni JSON formatida ajratib oling:
    - is_transaction (boolean): Matnda moliyaviy tranzaksiya (xarajat, kirim, to'lov, avans, ish haqi, tushum va hk) haqida gap ketganmi?
    - amount (integer): Tranzaksiya summasi (so'mda, faqat butun son). Agar aniq aytilmagan bo'lsa 0. (Masalan: "ellik ming" -> 50000, "bir yarim million" -> 1500000)
    - direction (string): 'out' (chiqim/xarajat/to'lov/avans bo'lsa) yoki 'in' (kirim/tushum/avans tushishi bo'lsa). Default: 'out'.
    - merchant (string): To'lov qilingan joy, do'kon, shaxs yoki xizmat nomi (masalan: "Korzinka", "Yandex Taxi", "Paynet", "Mijoz", "Ofis"). Maksimal 50 ta belgi. Agar aniq aytilmagan bo'lsa, xarajat yo'nalishiga qarab o'zingiz nom bering.
    - category (string): Xarajat/kirim toifasi (masalan: "Taksi", "Tushlik", "Ofis xarajati", "Marketing", "Dizayn xizmati", "Shaxsiy xarajat"). Maksimal 50 ta belgi.
    - ownership (string): 'business' (biznes/agentlik moliyasi bo'lsa) yoki 'personal' (shaxsiy/ro'zg'or moliyasi bo'lsa). Agar matnda "shaxsiy", "o'zimniki", "uyga", "ro'zg'orga", "shaxsiy xarajat", "shaxsiy ehtiyoj" kabi so'zlar bo'lsa yoki shaxsiy moliya ekani aniq aytilgan bo'lsa, 'personal' deb belgilang. Aks holda default: 'business'.
    - reason (string): Tranzaksiyaning batafsil sababi yoki izohi.

    Faqat va faqat JSON formatida javob bering, hech qanday markdown formatlashsiz (```json kabi taglarsiz), faqat toza JSON satri bo'lsin.
    """
    try:
        response, _ = await generate_content_with_fallback(
            client=client,
            primary_model=model_name,
            contents=[system_prompt, f"Tahlil qilinadigan matn:\n\"{text}\""],
            env_name="GEMINI_VOICE_FALLBACK_MODELS",
            log_prefix="[HISOBCHI-LLM]",
        )
        if response and response.text:
            cleaned_text = response.text.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_text)
    except Exception as exc:
        logger.error("Error occurred: %s", exc, exc_info=True)
    return None

async def handle_kirim_chiqim_text(event, engine: HisobchiEngine, text: str = "") -> bool:
    try:
        if not text:
            text = (event.message.message or "").strip()
        m = re.match(r"^/?(kirim|chiqim)\s+(\d[\d\s]*)\s+(.+)$", text, re.IGNORECASE)
        if not m:
            return False
        direction = "in" if m.group(1).lower() == "kirim" else "out"
        amount_str = re.sub(r"\s+", "", m.group(2))
        if not amount_str.isdigit():
            return False
        amount = int(amount_str)
        rest = m.group(3).strip()
        parts = rest.split("|", 1)
        merchant = parts[0].strip()[:50]
        reason = parts[1].strip() if len(parts) > 1 else ""
        ownership = "personal" if any(w in text.lower() for w in ["shaxsiy", "shaxsy"]) else "business"
        now = get_local_now()
        tx_time = now.strftime("%H:%M %d.%m.%Y")

        tx_id = await engine.save_transaction(
            source_bot="manual",
            direction=direction,
            amount=amount,
            merchant=merchant or "Noma'lum",
            card_suffix="",
            tx_time=tx_time,
            balance=None,
            raw_text=text,
            category="Boshqa",
            ownership=ownership,
            status="categorized",
            reason=reason,
        )
        icon = "➖ Chiqim" if direction == "out" else "➕ Kirim"
        own_label = "Biznes" if ownership == "business" else "Shaxsiy"
        await event.reply(
            f"✅ <b>#{tx_id} kiritildi</b>\n"
            f"{icon}: <b>{_fmt_money(amount)} UZS</b> ({own_label})\n"
            f"📍 {merchant}\n"
            f"{'📝 ' + reason if reason else ''}",
            parse_mode="html",
        )
        return True
    except Exception as exc:
        logger.error("Error occurred: %s", exc, exc_info=True)
        try:
            await event.reply(f"❌ Xatolik yuz berdi: {str(exc)}")
        except Exception:
            pass
        return True

async def handle_topic_plain_text(event, engine: HisobchiEngine, text: str, direction: str) -> bool:
    try:
        text = text.strip()
        m = re.match(r"^/?(\d[\d\s]*)\s*(?:uzs|so['\"]m)?\s*(.+)$", text, re.IGNORECASE)
        if not m:
            return False
        amount_str = re.sub(r"\s+", "", m.group(1))
        if not amount_str.isdigit():
            return False
        amount = int(amount_str)
        rest = m.group(2).strip()
        parts = rest.split("|", 1)
        merchant = parts[0].strip()[:50]
        reason = parts[1].strip() if len(parts) > 1 else ""
        ownership = "personal" if any(w in text.lower() for w in ["shaxsiy", "shaxsy"]) else "business"
        now = get_local_now()
        tx_time = now.strftime("%H:%M %d.%m.%Y")

        tx_id = await engine.save_transaction(
            source_bot="manual",
            direction=direction,
            amount=amount,
            merchant=merchant or "Noma'lum",
            card_suffix="",
            tx_time=tx_time,
            balance=None,
            raw_text=text,
            category="Boshqa",
            ownership=ownership,
            status="categorized",
            reason=reason,
        )
        icon = "➖ Chiqim" if direction == "out" else "➕ Kirim"
        own_label = "Biznes" if ownership == "business" else "Shaxsiy"
        await event.reply(
            f"✅ <b>#{tx_id} kiritildi</b>\n"
            f"{icon}: <b>{_fmt_money(amount)} UZS</b> ({own_label})\n"
            f"📍 {merchant}\n"
            f"{'📝 ' + reason if reason else ''}",
            parse_mode="html",
        )
        return True
    except Exception as exc:
        logger.error("Error occurred: %s", exc, exc_info=True)
        try:
            await event.reply(f"❌ Xatolik yuz berdi: {str(exc)}")
        except Exception:
            pass
        return True

async def handle_finance_group_reply(event, client, engine: HisobchiEngine, bot_client=None) -> bool:
    try:
        finance_group_id, _, _ = await resolve_finance_destination(client)
        if not finance_group_id:
            return False

        if event.chat_id != finance_group_id:
            return False

        sender = await event.get_sender()
        if getattr(sender, "bot", False):
            return False

        msg = event.message
        reply_to = getattr(msg, "reply_to", None)
        if not reply_to:
            return False

        replied_msg_id = getattr(reply_to, "reply_to_msg_id", None)
        if not replied_msg_id:
            return False

        tx = await engine.get_pending_by_finance_msg(
            finance_chat_id=finance_group_id,
            finance_msg_id=replied_msg_id,
        )
        if not tx:
            return False

        text = (msg.message or "").strip()

        lower_full_text = text.casefold()
        if any(
            marker in lower_full_text
            for marker in ("yangi to'lov", "yangi kirim", "yangi chiqim", "javob bering yoki", "bu to'lov nima uchun", "bu pul nima uchun")
        ):
            return False

        # Reject replies that look like their own transaction post (amount + currency),
        # not a category/reason comment — prevents misattributing a foreign bot's
        # payment notification to this pending tx's amount.
        if re.search(r"\b\d[\d\s]*\s*(usd|uzs|so['\"]m|\$)\b", lower_full_text):
            await _reply_via_bot(
                event, bot_client,
                "⚠️ Bu xabar alohida to'lov/tranzaksiya ko'rinishida — kategoriya sifatida qabul qilinmadi. "
                "Iltimos faqat toifa/sabab yozing (masalan: \"Dizayn xizmati\").",
            )
            return True

        if text.lower().startswith("/skip"):
            await engine.skip(tx["id"])
            await _reply_via_bot(event, bot_client, "⏭ O'tkazib yuborildi.")
            return True

        if not text or text.startswith("/"):
            return False

        if len(text) > _MAX_REPLY_LEN:
            await _reply_via_bot(event, bot_client, f"⚠️ Izoh juda uzun (maksimal {_MAX_REPLY_LEN} belgi). Iltimos, qisqaroq yozing.")
            return True

        reason = text
        ownership = "business"
        lower_text = text.casefold()
        if any(w in lower_text for w in ["shaxsiy", "personal", "shaxsy"]):
            ownership = "personal"

        category = re.split(r"\s*\|\s*|\r?\n", text, maxsplit=1)[0].strip()
        category = re.sub(r"\s*,?\s*(shaxsiy|personal|shaxsy)\s*$", "", category, flags=re.IGNORECASE).strip()
        if not category:
            await _reply_via_bot(event, bot_client, "⚠️ Toifa yoki sabab matnini yozing.")
            return True
        if len(category) > _MAX_CATEGORY_LEN:
            category = category[:_MAX_CATEGORY_LEN].rstrip()

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
        await _reply_via_bot(
            event, bot_client,
            f"✅ <b>Qabul qilindi!</b>\n"
            f"{direction_icon} {amount_str} UZS — <b>{html.escape(category)} ({own_label})</b>\n"
            f"📍 {html.escape(merchant)}\n"
            f"🧠 Keyingi safar avtomatik kategoriyalanadi.",
            parse_mode="html",
        )
        return True
    except Exception as exc:
        logger.error("Error occurred: %s", exc, exc_info=True)
        try:
            await event.reply(f"❌ Xatolik yuz berdi: {str(exc)}")
        except Exception:
            pass
        return True
