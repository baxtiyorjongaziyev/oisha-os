"""Soatlik check-in matnini AI bilan, odamga o'xshab yozish.

Har soat bir xil qolip zerikarli: AI oxirgi check-in va sotuvchining oxirgi javobini ko'radi,
gapni takrorlamaydi, oldingi va'dalarni so'raydi ("Shaxboz aka bilan gaplashdingizmi?").
AI ishlamasa ``None`` qaytadi va chaqiruvchi qolip matnga qaytadi.
"""
from __future__ import annotations

import html
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional

logger = logging.getLogger(__name__)

Generate = Callable[..., Awaitable[str]]

CONTEXT_FILE = "data/checkin_context.json"
MAX_CHARS = 700
_TERMINAL_CHARS = frozenset(".!?…")
_CLOSING_WRAPPERS = frozenset("\"'»”’)")
_LEAK_MARKERS = (
    "developer prompt",
    "system prompt",
    "prefix context",
    "uzbek latin",
    "last_checkin",
    "compose_system",
    "chain of thought",
    "dial in the last",
    "in the last hour",
    "activity is low",
    "no dials",
    "instruction says",
    "prompt says",
    "shaxsiy gaplarim:",
    "raqamlar:",
    "savol:",
    "maslahat:",
    "javob:",
    "menejer:",
)
_ENGLISH_META_WORDS = frozenset({
    "the", "is", "are", "was", "but", "wait", "only", "last", "hour",
    "low", "script", "context", "prefix", "prompt", "developer",
    "emoji", "should", "must", "dial", "dials", "latin",
    "blame", "help", "convert", "thinking", "reasoning", "instruction", "draft",
})

COMPOSE_SYSTEM = """Sen Oisha'san — Jon Branding sotuv bo'limining samimiy, do'stona hamkasbisan.
Onlayn ishlayotgan sotuv menejeriga soatlik qisqa xabar yozasan. Maqsad: nazorat qilish emas,
yonida turib yordam berish va ruhlantirish.

Qanday yozish kerak:
- Odamdek, jonli gapir. Har safar boshqacha boshla: salomni har soat takrorlama
  (kun davomida bir marta salom yetadi), shablon iboralardan qoch.
- Avvalgi xabaring va menejerning oxirgi javobi berilsa, o'shandan davom et: aytgan
  mijozlarini, vaʼdalarini ismi bilan eslat (masalan: "Mijoz bilan qayta gaplasha oldingizmi?").
- Qo'ng'iroq raqamlarini faqat mazmunli bo'lsa qisqa eslat; hamma raqamni ro'yxat qilma.
- Faqat bitta, aniq savol ber. Kerak bo'lsa bitta foydali maslahat yoki tayyor gap qo'sh.
- Yaxshi natijani maqta, qiyin soatda ruhlantir. Hech qachon ayblama.
- 2–4 qisqa gap. O'zbek lotin. 0–1 emoji. Markdown, HTML, sarlavha ishlatma.
- Maqsad — konversiyani oshirish: kerak bo'lsa bitimni yopishga, to'lovni tezlashtirishga yoki
  e'tirozga javob berishga yordam taklif qil. Javob so'rasang, "shu xabarga reply qilib" deb qo'sh.
- Suhbatlar mazmuni berilsa, shunga tayanib aniq maslahat ber (qaysi e'tiroz, keyingi qadam).
  Mijoz raqamini va shaxsiy gaplarini yozma.
- CRM'ga vazifa qo'yaman dema: vazifalarni qo'ng'iroq tahlili o'zi qo'yadi.
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
    text = (
        f"Oxirgi soatda {activity['total']} ta raqam terilgan, {activity.get('answered', 0)} tasi ko'targan, "
        f"3 daqiqadan uzun suhbat: {activity.get('solid', 0)} ta. Ko'targanlar: {clients or 'yo`q'}."
    )
    summaries = [s for s in (activity.get("summaries") or []) if s]
    if summaries:
        text += "\nSuhbatlar mazmuni (amoCRM'dagi AI tahlil):\n" + "\n".join(f"- {s}" for s in summaries)
    return text


def _is_emoji_char(ch: str) -> bool:
    return ord(ch) >= 0x2600 or ch in {"\ufe0f", "\u200d"}


def _ends_cleanly(text: str) -> bool:
    stripped = text.rstrip()
    if not stripped:
        return False
    if _is_emoji_char(stripped[-1]):
        return True
    inner = stripped.rstrip("".join(_CLOSING_WRAPPERS))
    return bool(inner and (inner[-1] in _TERMINAL_CHARS or _is_emoji_char(inner[-1])))


def _looks_like_reasoning_leak(text: str) -> bool:
    lowered = text.lower()
    if "<think>" in lowered or "</think>" in lowered:
        return True
    if re.search(r"(?:^|\n)\s*\*\s+", text):
        return True
    if any(marker in lowered for marker in _LEAK_MARKERS):
        return True
    if re.search(r"\((?:blame|thinking|note|optional|hint|example)\)", lowered):
        return True
    if re.search(r"\b(\w+)(?:\s+\1){3,}\b", lowered):
        return True
    lines = [ln.strip().lower() for ln in text.splitlines() if len(ln.strip()) >= 6]
    if len(lines) != len(set(lines)):
        return True
    ascii_words = [w.lower() for w in re.findall(r"[A-Za-z]+", text)]
    return sum(1 for w in ascii_words if w in _ENGLISH_META_WORDS) >= 2


def _is_valid_checkin_text(text: str) -> bool:
    if len(text) < 20 or len(text) > MAX_CHARS:
        return False
    if _looks_like_reasoning_leak(text):
        return False
    return _ends_cleanly(text)


def _sanitize_previous_checkin(raw: Any, seller_name: str) -> str:
    cleaned = html.unescape(re.sub(r"<[^>]+>", "", str(raw or ""))).strip()
    if seller_name:
        pattern = rf"^{re.escape(seller_name)}(?:\s*\([^)]*\))?\s*,\s*"
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned if _is_valid_checkin_text(cleaned) else ""


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
    prev_checkin = _sanitize_previous_checkin(ctx.get("last_checkin"), seller_name) if same_day else ""
    if prev_checkin:
        prompt_parts.append(f"Sening oldingi xabaring:\n{prev_checkin}")
    if same_day and ctx.get("last_reply"):
        prompt_parts.append(f"Menejerning oxirgi javobi:\n{ctx['last_reply']}")
    try:
        text = await generate(
            "\n\n".join(prompt_parts), system=COMPOSE_SYSTEM, max_tokens=600, temperature=0.6
        )
    except Exception:
        logger.warning("[CHECKIN] AI matn yozmadi, qolipga qaytiladi.", exc_info=True)
        return None
    text = (text or "").strip().strip('"')
    if not _is_valid_checkin_text(text):
        logger.warning("[CHECKIN] AI chiqishi notoʻliq yoki xizmat matni chiqdi, qolipga qaytiladi.")
        return None
    return text
