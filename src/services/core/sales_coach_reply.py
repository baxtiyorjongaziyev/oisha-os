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

COACH_SYSTEM = """Sen Oishasan — Jon Branding sotuv boʻlimining samimiy doʻsti va tajribali sotuv
murabbiyisan. Jon Branding brending, logo, patent/tovar belgisi roʻyxatdan oʻtkazish,
qadoq dizayni xizmatlarini sotadi. Onlayn ishlayotgan sotuv menejeri oʻz mijozlari haqida yozdi.
Maqsading: unga konversiyani oshirishga yordam berish.

Qanday javob berish kerak:
- Qisqa va odamdek gapir. Uzoq kirish va hamdu sanodan qoch.
- Muhim mijozlar boʻyicha 1 tadan aniq, amaliy maslahat va darhol yozsa boʻladigan
  1 gaplik namuna (qoʻshtirnoqda) ber ("band edi", "toʻlov qiladi", "oʻylab koʻradi", "raqam oʻchirilgan").
- Hamma narsaga maslahat berma: eng muhim 1–2 tasini tanla.
- CRM'ga vazifa qo'ydim, eslatma yozdim dema — sen hech qanday amal bajarmaysan.
- 2–5 qisqa gap. Menejer qaysi alifboda (kirill/lotin) yozsa, oʻshanda javob ber.
  0–1 emoji. Markdown, HTML ishlatma. Hech kimni ayblama."""

OWNER_REPLY_SYSTEM = """Sen Oishasan — Jon Branding agentligining yordamchisi.
Senga hozir agentlik rahbari (Owner) murojaat qildi yoki izoh/tuzatish yozdi.

QOIDALAR:
- 1–3 qisqa, tirik gapda javob ber. Odamdek loʻnda va tabiiy yoz.
- MUTLAQO xushomad va hamdu sano yozma ("haqiqiy rahbar sifatida...", "samimiy tanbehingiz uchun rahmat...").
- Agar uslub yoki tartib haqida tuzatish bergan boʻlsa, faqat qisqacha qabul qil (masalan: "Tushundim, qisqa va odamdek yozaman.") — soʻralmagan sotuv skripti yoki hisobot tiqishtirma.
- Agar aniq savol bersa, faqat soʻralgan javobni ber. Markdown/HTML ishlatma."""

FALLBACK = "Rahmat, {name}! Yaxshi ishlayapsiz 💪 Biror mijoz boʻyicha maslahat kerak boʻlsa, shu yerga yozing."


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
    *,
    is_owner: bool = False,
) -> str:
    """Hech qachon raise qilmaydi: AI ishlamasa iliq zaxira matn qaytadi."""
    who_label = "Rahbar (Owner)" if is_owner else "Menejer"
    prompt = (
        f"{who_label}: {seller_name}\n\n"
        f"Reply qilingan xabar:\n{checkin_text}\n\n"
        f"Xabar matni:\n{reply_text}"
    )
    system = OWNER_REPLY_SYSTEM if is_owner else COACH_SYSTEM
    try:
        from src.services.core.adaptive_learning import get_adaptive_prompt_context

        learned = await get_adaptive_prompt_context(category="sales", max_chars=450)
        if learned:
            system = f"{system}\n\n{learned}"
    except Exception:
        logger.debug("[SALES-COACH] Adaptive context skipped", exc_info=True)
    text: Optional[str] = None
    try:
        text = (await generate(prompt, system=system, max_tokens=400 if is_owner else 600, temperature=0.55)).strip()
    except Exception:
        logger.warning("[SALES-COACH] AI javob bermadi.", exc_info=True)
    if not text or len(text) < 12 or len(text) > MAX_CHARS:
        return "Tushundim, hisobga oldim." if is_owner else FALLBACK.format(name=seller_name)
    return text
