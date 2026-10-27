"""Soatlik check-in matnini AI bilan, odamga o'xshab yozish.

Har soat bir xil qolip zerikarli: AI oxirgi check-in va sotuvchining oxirgi javobini ko'radi,
gapni takrorlamaydi, oldingi va'dalarni so'raydi ("Shaxboz aka bilan gaplashdingizmi?").
AI ishlamasa ``None`` qaytadi va chaqiruvchi qolip matnga qaytadi.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional

logger = logging.getLogger(__name__)

Generate = Callable[..., Awaitable[str]]

CONTEXT_FILE = "data/checkin_context.json"
MAX_CHARS = 700

COMPOSE_SYSTEM = """Sen Oisha'san — Jon Branding sotuv bo'limining samimiy, do'stona hamkasbisan.
Onlayn ishlayotgan sotuv menejeriga soatlik qisqa xabar yozasan. Maqsad: nazorat qilish emas,
yonida turib yordam berish va ruhlantirish.

Qanday yozish kerak:
- Odamdek, jonli gapir. Har safar boshqacha boshla: salomni har soat takrorlama
  (kun davomida bir marta salom yetadi), shablon iboralardan qoch.
- Avvalgi xabaring va menejerning oxirgi javobi berilsa, o'shandan davom et: aytgan
  mijozlarini, va'dalarini ismi bilan eslat ("Shaxboz aka bilan qayta gaplasha oldingizmi?").
- Qo'ng'iroq raqamlarini faqat mazmunli bo'lsa qisqa eslat; hamma raqamni ro'yxat qilma.
- Faqat bitta, aniq savol ber. Kerak bo'lsa bitta foydali maslahat yoki tayyor gap qo'sh.
- Yaxshi natijani maqta, qiyin soatda ruhlantir. Hech qachon ayblama.
- 2–4 qisqa gap. O'zbek lotin. 0–1 emoji. Markdown, HTML, sarlavha ishlatma.
- Javob berishni so'rasang, "shu xabarga reply qilib" deb qo'sh — javobdan amoCRM'ga vazifa qo'yiladi.
Faqat xabar matnini qaytar, menejer ismini o'zing qo'shma (boshiga qo'shiladi)."""


async def _router_generate(prompt: str, *, system: str, max_tokens: int, temperature: float) -> str:
    from src.services.utils.free_ai_router import get_free_ai_router

    result = await get_free_ai_router().generate_text(
        prompt, system=system, max_tokens=max_tokens, temperature=temperature
    )
    return (getattr(result, "text", "") or "").strip()


def load_context(path: str = CONTEXT_FILE) -> Dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_context(update: Dict[str, Any], path: str = CONTEXT_FILE) -> None:
    data = load_context(path)
    data.update(update)
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
    except OSError:
        logger.warning("[CHECKIN] Kontekst saqlanmadi.", exc_info=True)


def _describe_activity(activity: Optional[Dict[str, Any]]) -> str:
    if not activity or not activity.get("total"):
        return "Oxirgi soatda telefoniyada qo'ng'iroq yo'q."
    clients = "; ".join(
        f"{c.get('name') or c.get('number')} — {int(c.get('duration') or 0)} soniya"
        for c in (activity.get("answered_clients") or [])[:5]
    )
    return (
        f"Oxirgi soatda {activity['total']} ta raqam terilgan, {activity.get('answered', 0)} tasi ko'targan, "
        f"3 daqiqadan uzun suhbat: {activity.get('solid', 0)} ta. Ko'targanlar: {clients or 'yo`q'}."
    )


async def compose_checkin(
    seller_name: str,
    now: datetime,
    activity: Optional[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None,
    generate: Generate = _router_generate,
) -> Optional[str]:
    ctx = context if context is not None else load_context()
    same_day = str(ctx.get("date") or "") == f"{now:%Y-%m-%d}"
    prompt_parts = [
        f"Hozir: {now:%H:%M}. Menejer: {seller_name}.",
        f"Bugun allaqachon salomlashganmiz: {'ha' if same_day else 'yo`q'}.",
        _describe_activity(activity),
    ]
    if same_day and ctx.get("last_checkin"):
        prompt_parts.append(f"Sening oldingi xabaring:\n{ctx['last_checkin']}")
    if same_day and ctx.get("last_reply"):
        prompt_parts.append(f"Menejerning oxirgi javobi:\n{ctx['last_reply']}")
    try:
        text = await generate(
            "\n\n".join(prompt_parts), system=COMPOSE_SYSTEM, max_tokens=300, temperature=0.8
        )
    except Exception:
        logger.warning("[CHECKIN] AI matn yozmadi, qolipga qaytiladi.", exc_info=True)
        return None
    text = (text or "").strip().strip('"')
    if len(text) < 20 or len(text) > MAX_CHARS:
        return None
    return text
