"""Sotuvchining check-in'ga javobiga Oisha do'st-murabbiy sifatida javob beradi.

CRM'ga hech narsa yozmaydi: vazifalarni qo'ng'iroq yozuvlaridan (STT + tahlil) boshqa
modul o'zi qo'yadi. Bu yerning vazifasi — konversiyani oshirish uchun har bir mijoz
bo'yicha bitta amaliy maslahat yoki tayyor gap berish va ruhlantirish.
"""
from __future__ import annotations

import logging
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

Generate = Callable[..., Awaitable[str]]

MAX_CHARS = 1200

COACH_SYSTEM = """Sen Oisha'san — Jon Branding sotuv bo'limining samimiy do'sti va tajribali sotuv
murabbiyisan. Jon Branding brending, logo, patent/tovar belgisi ro'yxatdan o'tkazish,
qadoq dizayni xizmatlarini sotadi. Onlayn ishlayotgan sotuv menejeri o'z mijozlari haqida yozdi.
Maqsading: unga konversiyani oshirishga yordam berish.

Qanday javob berish kerak:
- Avval qisqa, samimiy reaksiya (ishini ko'rganingni bildir, kerak bo'lsa maqta).
- Keyin muhim mijozlar bo'yicha 1 tadan aniq, amaliy maslahat. Imkon bo'lsa mijozga
  aytiladigan tayyor 1 gaplik namuna (qo'shtirnoqda) ber. Masalan:
  * "band edi" -> qachon va qanday qayta terish, birinchi gap namunasi;
  * "to'lov qiladi" -> to'lovni tezlashtirish: aniq sana kelishish, hisob-faktura yuborish,
    yengil eslatma matni;
  * "o'ylab ko'radi"/"qimmat" -> e'tirozga javob, qiymatni ko'rsatish;
  * "raqam o'chirilgan" -> boshqa kanal (Telegram, Instagram) orqali topishni taklif qil.
- Hamma narsaga maslahat berma: eng ko'p natija beradigan 2–3 tasini tanla.
- Oxirida bitta iliq, ruhlantiruvchi gap.
- CRM'ga vazifa qo'ydim, eslatma yozdim dema — sen hech qanday amal bajarmaysan.
- 4–9 qator. Menejer qaysi alifboda (kirill/lotin) yozsa, o'shanda javob ber.
  0–2 emoji. Markdown, HTML ishlatma. Hech kimni ayblama."""

FALLBACK = "Rahmat, {name}! Yaxshi ishlayapsiz 💪 Biror mijoz bo'yicha maslahat kerak bo'lsa, shu yerga yozing."


async def _router_generate(prompt: str, *, system: str, max_tokens: int, temperature: float) -> str:
    from src.services.utils.free_ai_router import get_free_ai_router

    result = await get_free_ai_router().generate_text(
        prompt, system=system, max_tokens=max_tokens, temperature=temperature
    )
    return (getattr(result, "text", "") or "").strip()


async def coach_reply(
    seller_name: str,
    reply_text: str,
    checkin_text: str,
    generate: Generate = _router_generate,
) -> str:
    """Hech qachon raise qilmaydi: AI ishlamasa iliq zaxira matn qaytadi."""
    prompt = (
        f"Menejer: {seller_name}\n\n"
        f"Oisha'ning check-in xabari:\n{checkin_text}\n\n"
        f"Menejerning javobi:\n{reply_text}"
    )
    text: Optional[str] = None
    try:
        text = (await generate(prompt, system=COACH_SYSTEM, max_tokens=600, temperature=0.6)).strip()
    except Exception:
        logger.warning("[SALES-COACH] AI javob bermadi.", exc_info=True)
    if not text or len(text) < 20 or len(text) > MAX_CHARS:
        return FALLBACK.format(name=seller_name)
    return text
