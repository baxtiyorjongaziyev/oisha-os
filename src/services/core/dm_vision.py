"""DM Vision — Analyze any image a client sends in a Telegram DM via Gemini Vision.

Farqi `hisobchi_vision` dan: u faqat chek/kvitansiya qidiradi va moliya guruhida
ishlaydi. Bu modul mijoz DM'ida kelgan **istalgan** rasmni tahlil qiladi —
referens dizayn, raqobatchi ishi, brif skrinshoti, vizitka, mahsulot fotosi.

Natija ikki joyga ketadi:
  1. AmoCRM lead notesi — sotuvchi CRM'da rasmni ochmasdan mazmunini ko'radi
  2. AI javob konteksti — draft yozuvchi rasmni "ko'rgan" holda javob tayyorlaydi
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from src.settings import settings
from src.services.utils.gemini_fallback import generate_content_with_fallback

logger = logging.getLogger(__name__)

# Gemini javobini cheklash — nota ham, prompt konteksti ham qisqa bo'lishi kerak.
MAX_SUMMARY_CHARS = 600
MAX_TEXT_CHARS = 800

_PROMPT = (
    "Sen Jon Branding agentligining vizual tahlilchisisan. Mijoz Telegram'da "
    "rasm yubordi. Rasmni ko'rib, quyidagi JSON'ni qaytar. Faqat JSON, "
    "boshqa matn yoki markdown belgilari yo'q.\n\n"
    "{\n"
    '  "summary": "Rasmda nima borligi, 1-2 gap, o\'zbek tilida",\n'
    '  "category": "reference_design | competitor_work | brief | business_card | '
    'product_photo | receipt | screenshot | document | personal | other",\n'
    '  "extracted_text": "Rasmdagi barcha o\'qiladigan matn, bo\'lmasa bo\'sh satr",\n'
    '  "contact": {"name": "", "phone": "", "company": ""},\n'
    '  "is_business_relevant": true/false,\n'
    '  "sales_hint": "Sotuvchi uchun bir gaplik maslahat, kerak bo\'lmasa bo\'sh"\n'
    "}\n\n"
    "Qoidalar:\n"
    "- contact maydonini faqat rasmda aniq ko'rinsa to'ldir (vizitka, imzo, "
    "reklama banneri). Taxmin qilma, ko'rinmasa bo'sh qoldir.\n"
    "- is_business_relevant: rasm ish/loyiha/xarid bilan bog'liq bo'lsa true. "
    "Shaxsiy foto, mem, tabrik rasmi bo'lsa false.\n"
    "- Odamlarning tashqi ko'rinishi, irqi, yoshi yoki sog'lig'i haqida "
    "xulosa chiqarma va yozma."
)


def _clip(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _normalize(data: dict) -> dict:
    """Model javobini kutilgan shaklga keltirish — yetishmagan kalitlar to'ldiriladi."""
    raw_contact = data.get("contact")
    contact_src = raw_contact if isinstance(raw_contact, dict) else {}
    contact = {
        "name": _clip(contact_src.get("name"), 100),
        "phone": _clip(contact_src.get("phone"), 40),
        "company": _clip(contact_src.get("company"), 100),
    }
    return {
        "summary": _clip(data.get("summary"), MAX_SUMMARY_CHARS),
        "category": _clip(data.get("category"), 40) or "other",
        "extracted_text": _clip(data.get("extracted_text"), MAX_TEXT_CHARS),
        "contact": contact if any(contact.values()) else {},
        "is_business_relevant": bool(data.get("is_business_relevant", False)),
        "sales_hint": _clip(data.get("sales_hint"), 200),
    }


async def analyze_dm_image(client: Any, image_path: str) -> Optional[dict]:
    """
    DM'da kelgan rasmni Gemini Vision orqali tahlil qilish.

    Qaytaradi normalizatsiya qilingan dict, yoki None — tahlil bo'lmasa.
    Hech qachon exception ko'tarmaydi: rasm tahlili qo'shimcha imkoniyat,
    u ishlamasa ham asosiy media oqimi (Drive upload) davom etishi kerak.
    """
    if not client or not image_path:
        return None

    try:
        upload = client.files.upload(path=image_path)
    except Exception as exc:
        logger.warning("[DM-VISION] Rasm yuklanmadi: %s", exc)
        return None

    try:
        response, model = await generate_content_with_fallback(
            client=client,
            primary_model=(
                getattr(settings, "GEMINI_VISION_MODEL", None)
                or settings.GEMINI_CALL_MODEL
            ),
            contents=[_PROMPT, upload],
            env_name="GEMINI_VISION_FALLBACK_MODELS",
            log_prefix="[DM-VISION]",
        )
    except Exception as exc:
        logger.warning("[DM-VISION] Vision chaqiruvi muvaffaqiyatsiz: %s", exc)
        return None

    text = getattr(response, "text", None)
    if not text or not isinstance(text, str):
        logger.debug("[DM-VISION] Matnli javob qaytmadi (model=%s)", model)
        return None

    cleaned = text.strip().replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        # Matnli fallback provayder rasmni ko'rmaydi va erkin matn qaytaradi —
        # bunday javob JSON bo'lmaydi, uni sukut bilan tashlab yuboramiz.
        logger.info("[DM-VISION] JSON emas, tashlab yuborildi (model=%s): %s", model, exc)
        return None

    if not isinstance(data, dict):
        return None

    result = _normalize(data)
    if not result["summary"]:
        return None

    logger.info(
        "[DM-VISION] Tahlil tayyor model=%s category=%s relevant=%s",
        model,
        result["category"],
        result["is_business_relevant"],
    )
    return result


def format_for_crm_note(result: dict, sender_name: str = "") -> str:
    """Vision natijasini AmoCRM notesi uchun o'qiladigan matnga aylantirish."""
    lines = ["🖼 Mijoz rasm yubordi — avtomatik tahlil"]
    if sender_name:
        lines.append(f"Kimdan: {sender_name}")
    lines.append(f"Turi: {result.get('category', 'other')}")
    lines.append(f"Mazmuni: {result.get('summary', '')}")

    contact = result.get("contact") or {}
    if contact:
        parts = [
            f"{label}: {contact[key]}"
            for key, label in (("name", "Ism"), ("phone", "Tel"), ("company", "Kompaniya"))
            if contact.get(key)
        ]
        if parts:
            lines.append("Rasmdan topilgan kontakt — " + ", ".join(parts))

    if result.get("extracted_text"):
        lines.append(f"Rasmdagi matn: {result['extracted_text']}")
    if result.get("sales_hint"):
        lines.append(f"Maslahat: {result['sales_hint']}")

    return "\n".join(lines)


def format_for_ai_context(result: dict) -> str:
    """Vision natijasini javob yozuvchi AI uchun qisqa kontekstga aylantirish."""
    parts = [f"[Mijoz rasm yubordi] {result.get('summary', '')}"]
    if result.get("extracted_text"):
        parts.append(f"Rasmdagi matn: {result['extracted_text']}")
    if result.get("sales_hint"):
        parts.append(f"Eslatma: {result['sales_hint']}")
    return " | ".join(p for p in parts if p)
