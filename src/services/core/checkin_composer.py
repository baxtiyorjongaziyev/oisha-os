"""Soatlik check-in matnini AI bilan, odamga o'xshab yozish.

Har soat bir xil qolip zerikarli: AI oxirgi check-in va sotuvchining oxirgi javobini ko'radi,
gapni takrorlamaydi, oldingi va'dalarni so'raydi ("Shaxboz aka bilan gaplashdingizmi?").
AI ishlamasa ``None`` qaytadi va chaqiruvchi qolip matnga qaytadi.
"""
from __future__ import annotations

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

_LEAK_MARKERS = (
    "system prompt",
    "developer prompt",
    "user prompt",
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
    "savol:",
    "javob:",
    "menejer:",
    "<think",
    "</think",
    "<|channel|>",
    "<|message|>",
    "<|start|>",
)
_ENGLISH_META_WORDS = frozenset({
    "the", "is", "are", "was", "but", "wait", "only", "last", "hour",
    "low", "script", "context", "prefix", "prompt", "developer",
    "emoji", "should", "must", "dial", "dials", "latin", "blame", "convert", "help",
})
_TERMINAL_CHARS = frozenset(".!?…")
_CLOSING_WRAPPERS = frozenset("\"'»”’)")
_DANGLING_ENDINGS = (",", ";", ":", "-", "—", "(", "[", "{", "}", "\\")

COMPOSE_SYSTEM = """Sen Oishasan — Jon Branding sotuv boʻlimining samimiy, doʻstona hamkasbisan.
Onlayn ishlayotgan sotuv menejeriga soatlik qisqa xabar yozasan. Maqsad: nazorat qilish emas,
yonida turib yordam berish va ruhlantirish.

Qanday yozish kerak:
- Odamdek, jonli gapir. Har safar boshqacha boshla: salomni har soat takrorlama
  (kun davomida bir marta salom yetadi), shablon iboralardan qoch.
- Avvalgi xabaring va menejerning oxirgi javobi berilsa, oʻshandan davom et: aytgan
  mijozlarini, vaʼdalarini ismi bilan eslat (masalan: "Mijoz bilan qayta gaplasha oldingizmi?").
- Qoʻngʻiroq raqamlarini faqat mazmunli boʻlsa qisqa eslat; hamma raqamni roʻyxat qilma.
- Faqat bitta, aniq savol ber. Kerak boʻlsa bitta foydali maslahat yoki tayyor gap qoʻsh.
- Yaxshi natijani maqta, qiyin soatda ruhlantir. Hech qachon ayblama.
- 2–4 qisqa gap. Oʻzbek lotin. 0–1 emoji. Markdown, HTML, sarlavha ishlatma.
- Maqsad — konversiyani oshirish: kerak boʻlsa bitimni yopishga, toʻlovni tezlashtirishga yoki
  eʼtirozga javob berishga yordam taklif qil. Javob soʻrasang, "shu xabarga reply qilib" deb qoʻsh.
- Suhbatlar mazmuni berilsa, shunga tayanib aniq maslahat ber (qaysi eʼtiroz, keyingi qadam).
  Mijoz raqamini va shaxsiy gaplarini yozma.
- CRMʼga vazifa qoʻyaman dema: vazifalarni qoʻngʻiroq tahlili oʻzi qoʻyadi.
Faqat xabar matnini qaytar, menejer ismini oʻzing qoʻshma (boshiga qoʻshiladi)."""


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _ends_cleanly(text: str) -> bool:
    stripped = text.rstrip()
    if not stripped:
        return False
    if ord(stripped[-1]) >= 0x2600 or stripped[-1] in {"\ufe0f", "\u200d"}:
        return True
    inner = stripped.rstrip("".join(_CLOSING_WRAPPERS))
    return bool(inner and (inner[-1] in _TERMINAL_CHARS or ord(inner[-1]) >= 0x2600))


def is_valid_reply(text: str, *, min_chars: int = 20, max_chars: int = MAX_CHARS) -> bool:
    """AI javobi kesilmagan, prompt/fikr sizmagan va butun gap ekanini tekshiradi."""
    cleaned = (text or "").strip()
    if len(cleaned) < min_chars or len(cleaned) > max_chars:
        return False
    lowered = cleaned.lower()
    if any(marker in lowered for marker in _LEAK_MARKERS):
        return False
    if cleaned.endswith(_DANGLING_ENDINGS) or "{" in cleaned or "}" in cleaned:
        return False
    if cleaned.count('"') % 2 != 0 or cleaned.count("(") > cleaned.count(")"):
        return False
    if re.search(r"(?:^|\n)\s*\*\s+", cleaned):
        return False
    if re.search(r"\((?:blame|thinking|note|optional|hint|example)\)", lowered):
        return False
    if re.search(r"\b(\w+)(?:\s+\1){3,}\b", lowered):
        return False
    lines = [ln.strip().lower() for ln in cleaned.splitlines() if len(ln.strip()) >= 6]
    if len(lines) != len(set(lines)):
        return False
    ascii_words = [w.lower() for w in re.findall(r"[A-Za-z]+", cleaned)]
    if sum(1 for w in ascii_words if w in _ENGLISH_META_WORDS) >= 2:
        return False
    return _ends_cleanly(cleaned)


async def router_generate_complete(
    prompt: str,
    *,
    system: str,
    max_tokens: int,
    temperature: float,
    log_tag: str = "[CHECKIN]",
) -> str:
    from src.services.utils.free_ai_router import get_free_ai_router

    result = await get_free_ai_router().generate_text(
        prompt, system=system, max_tokens=max_tokens, temperature=temperature
    )
    if getattr(result, "finish_reason", "") == "length":
        logger.warning("%s AI javobi kesildi (finish_reason=length), zaxira ishlatiladi.", log_tag)
        return ""
    return (getattr(result, "text", "") or "").strip()


async def _router_generate(prompt: str, *, system: str, max_tokens: int, temperature: float) -> str:
    return await router_generate_complete(
        prompt, system=system, max_tokens=max_tokens, temperature=temperature, log_tag="[CHECKIN]"
    )


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


async def compose_checkin(
    seller_name: str,
    now: datetime,
    activity: Optional[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None,
    generate: Optional[Generate] = None,
) -> Optional[str]:
    gen = generate or _router_generate
    ctx = context if context is not None else load_context()
    same_day = str(ctx.get("date") or "") == f"{now:%Y-%m-%d}"
    prompt_parts = [
        f"Hozir: {now:%H:%M}. Menejer: {seller_name}.",
        f"Bugun allaqachon salomlashganmiz: {'ha' if same_day else 'yo`q'}.",
        _describe_activity(activity),
    ]
    if same_day and ctx.get("last_checkin"):
        prev = _strip_html(str(ctx["last_checkin"]))
        if seller_name:
            prev = re.sub(
                rf"^{re.escape(seller_name)}(?:\s*\([^)]*\))?\s*,\s*", "", prev, flags=re.IGNORECASE
            ).strip()
        if is_valid_reply(prev, max_chars=MAX_CHARS + 200):
            prompt_parts.append(f"Sening oldingi xabaring:\n{prev}")
    if same_day and ctx.get("last_reply"):
        prompt_parts.append(f"Menejerning oxirgi javobi:\n{ctx['last_reply']}")
    system = COMPOSE_SYSTEM
    try:
        from src.services.core.adaptive_learning import get_adaptive_prompt_context

        learned = await get_adaptive_prompt_context(category="sales", max_chars=350)
        if learned:
            system = f"{system}\n\n{learned}"
    except Exception:
        logger.debug("[CHECKIN] Adaptive context skipped", exc_info=True)
    try:
        text = await gen(
            "\n\n".join(prompt_parts), system=system, max_tokens=500, temperature=0.6
        )
    except Exception:
        logger.warning("[CHECKIN] AI matn yozmadi, qolipga qaytiladi.", exc_info=True)
        return None
    text = (text or "").strip().strip('"')
    prefix = re.match(rf"^{re.escape(seller_name)}\s*[,:\-—]+\s*", text, flags=re.IGNORECASE)
    if prefix:
        text = text[prefix.end() :].strip()
    if not is_valid_reply(text, max_chars=MAX_CHARS):
        return None
    return text
