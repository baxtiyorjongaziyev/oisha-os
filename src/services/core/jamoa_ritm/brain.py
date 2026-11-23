"""Hamroh AI javoblari: mentionʼga javob, haftalik retro va egaga oʻz-oʻzini tahlil.

LLM chaqiruvlari ``free_ai_router`` orqali oʻtadi (provayder ishlamasa boshqasiga oʻtadi).
AI javob bermasa, har bir funksiya xavfsiz zaxira matnini qaytaradi.
"""
from __future__ import annotations

import logging
from datetime import datetime, tzinfo
from typing import Awaitable, Callable, Optional

from src.services.core.jamoa_ritm.store import ROLE_HAMROH, ROLE_MEMBER, ROLE_RITM
from src.services.core.jamoa_ritm.texts import (
    HAMROH_SYSTEM,
    RETRO_FALLBACK,
    RETRO_TASK,
    TAHLIL_TASK,
    load_oisha_soul,
)

logger = logging.getLogger(__name__)

Generate = Callable[..., Awaitable[str]]

TELEGRAM_LIMIT = 3500
ANSWER_FALLBACK = "Hozir javob tayyorlay olmadim. Birozdan keyin qayta soʻrab koʻring."


async def _router_generate(prompt: str, *, system: str, max_tokens: int, temperature: float) -> str:
    from src.services.utils.free_ai_router import get_free_ai_router

    result = await get_free_ai_router().generate_text(
        prompt, system=system, max_tokens=max_tokens, temperature=temperature
    )
    return (getattr(result, "text", "") or "").strip()


def _clip(text: str, limit: int = TELEGRAM_LIMIT) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def format_transcript(messages: list[dict], max_chars: int = 12000, tz: Optional[tzinfo] = None) -> str:
    """Xabarlarni ``HH:MM Ism: matn`` qatorlariga aylantiradi; sigʻmasa eng yangilari qoladi."""
    if tz is None:
        from src.time_utils import get_local_timezone

        tz = get_local_timezone()
    lines: list[str] = []
    used = 0
    for item in reversed(messages):
        stamp = datetime.fromtimestamp(int(item.get("created_at") or 0), tz).strftime("%a %H:%M")
        role = item.get("role")
        if role == ROLE_HAMROH:
            name = "Hamroh"
        elif role == ROLE_RITM:
            name = "Oisha (ritm)"
        else:
            name = item.get("user_name") or "Aʼzo"
        line = f"{stamp} {name}: {' '.join(str(item.get('text') or '').split())}"
        if used + len(line) + 1 > max_chars:
            break
        lines.append(line)
        used += len(line) + 1
    lines.reverse()
    return "\n".join(lines)


class HamrohBrain:
    def __init__(self, generate: Optional[Generate] = None, tz: Optional[tzinfo] = None):
        self._generate = generate or _router_generate
        self._tz = tz

    async def _ask(self, prompt: str, *, max_tokens: int, temperature: float) -> str:
        soul = load_oisha_soul()
        system = f"[OISHA YADRO]\n{soul}\n\n{HAMROH_SYSTEM}" if soul else HAMROH_SYSTEM
        try:
            from src.services.core.adaptive_learning import get_adaptive_prompt_context

            learned = await get_adaptive_prompt_context(max_chars=350)
            if learned:
                system = f"{system}\n\n{learned}"
        except Exception:
            logger.debug("[HAMROH] Adaptive context skipped", exc_info=True)
        try:
            text = await self._generate(
                prompt, system=system, max_tokens=max_tokens, temperature=temperature
            )
        except Exception as exc:
            logger.error("[HAMROH] AI javob bermadi: %s", exc)
            return ""
        return _clip(text)

    async def answer(self, question: str, context: list[dict], asker: str = "") -> str:
        transcript = format_transcript(context, max_chars=6000, tz=self._tz) or "(suhbat yoʻq)"
        who = asker or "Jamoa aʼzosi"

        asker_context = ""
        try:
            from src.services.core.onboarding import get_self_onboarding

            member = get_self_onboarding().lookup_member(asker)
            if member:
                asker_context = f"\n(Murojaat qiluvchi: {member.name}, vazifasi/roli: {member.role})\n"
        except Exception:
            logger.debug("onboarding_lookup_failed", exc_info=True)

        prompt = (
            f"Guruhdagi oxirgi suhbat:\n{transcript}\n\n---\n"
            f"{who}{asker_context} senga murojaat qildi:\n{question.strip()}"
        )
        return await self._ask(prompt, max_tokens=600, temperature=0.3) or ANSWER_FALLBACK

    async def weekly_retro(self, messages: list[dict]) -> str:
        members = [m for m in messages if m.get("role", ROLE_MEMBER) == ROLE_MEMBER]
        if not members:
            return RETRO_FALLBACK
        prompt = (
            f"{RETRO_TASK}\nSuhbat (haftaning oxirgi {len(members)} ta xabari, toʻliq boʻlmasligi mumkin):\n"
            f"{format_transcript(members, tz=self._tz)}"
        )
        return await self._ask(prompt, max_tokens=700, temperature=0.4) or RETRO_FALLBACK

    async def self_review(self, messages: list[dict], counts: Optional[dict[str, int]] = None) -> str:
        """``counts`` — butun hafta boʻyicha ``{role: soni}``. Berilmasa, raqamlar faqat
        namunadan hisoblanadi va bu matnda ochiq aytiladi (toʻliq hisob deb koʻrsatilmaydi)."""
        if counts is not None:
            stats = (
                "Statistika (butun hafta): kuzatilgan xabarlar — "
                f"{counts.get(ROLE_MEMBER, 0)}, Hamroh javoblari — {counts.get(ROLE_HAMROH, 0)}."
            )
        else:
            answered = sum(1 for m in messages if m.get("role") == ROLE_HAMROH)
            observed = sum(1 for m in messages if m.get("role", ROLE_MEMBER) == ROLE_MEMBER)
            stats = (
                f"Statistika (faqat oxirgi {len(messages)} ta yozuv boʻyicha, butun hafta emas): "
                f"kuzatilgan xabarlar — {observed}, Hamroh javoblari — {answered}."
            )
        fallback = (
            "Hamroh: haftalik oʻz-oʻzini tahlil\n"
            f"{stats}\n"
            "AI tahlil hozir tayyorlanmadi; batafsil hisobot keyingi haftada."
        )
        if not messages:
            return fallback
        prompt = (
            f"{TAHLIL_TASK}\n{stats}\n\n"
            f"Suhbat (haftaning oxirgi {len(messages)} ta yozuvi, toʻliq boʻlmasligi mumkin):\n"
            f"{format_transcript(messages, tz=self._tz)}"
        )
        text = await self._ask(prompt, max_tokens=900, temperature=0.3)
        return f"Hamroh: haftalik oʻz-oʻzini tahlil\n{text}" if text else fallback
