"""Xabarlarni odamga oʻxshab tuzadi va javobni tushunadi.

AI ishlamasa ham tizim toʻxtamaydi: har bir funksiyada iliq zaxira matn bor.
"""
from __future__ import annotations

import logging
import random
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional

from src.services.core.daily_priority.state import (
    STATUS_ACCEPTED,
    STATUS_CHANGED,
    STATUS_DECLINED,
    STATUS_DONE,
)

logger = logging.getLogger("DailyPriority")

Generate = Callable[..., Awaitable[str]]
MAX_CHARS = 600

PERSONA = (
    "Sen Oisha — Jon Branding agentligining operatsion rahbari. Jamoa aʼzosiga "
    "Telegramʼda shaxsan yozyapsan. Tiling: oʻzbekcha, samimiy, qisqa, tirik odamdek; "
    "rasmiyatchilik va shablonsiz. 2-4 gap. Ism bilan murojaat qil. Markdown, roʻyxat, "
    "qoʻshtirnoq ishlatma. Faqat berilgan faktlarga tayan, raqam yoki ism toʻqima."
)


async def _router_generate(prompt: str, *, system: str, max_tokens: int, temperature: float) -> str:
    from src.services.core.checkin_composer import router_generate_complete

    return await router_generate_complete(
        prompt, system=system, max_tokens=max_tokens, temperature=temperature, log_tag="[DAILY]"
    )


def _valid(text: Optional[str]) -> bool:
    from src.services.core.checkin_composer import is_valid_reply

    return bool(text) and is_valid_reply(text, max_chars=MAX_CHARS)


async def _ai(prompt: str, generate: Optional[Generate], temperature: float = 0.8) -> Optional[str]:
    gen = generate or _router_generate
    try:
        text = (await gen(prompt, system=PERSONA, max_tokens=500, temperature=temperature)).strip()
    except Exception:
        logger.warning("[DAILY] AI javob bermadi.", exc_info=True)
        return None
    return text if _valid(text) else None


def fmt_money(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " soʻm" if amount else ""


def describe_task(task: Dict[str, Any]) -> str:
    parts = [task["name"], f"bosqich: {task['stage']}"]
    if task.get("price"):
        parts.append(f"summa: {fmt_money(task['price'])}")
    if task.get("idle_days"):
        parts.append(f"oxirgi harakatdan beri {task['idle_days']} kun")
    return ", ".join(parts)


def task_action(task: Dict[str, Any], role: str) -> str:
    if role == "finance":
        return f"{task['name']} boʻyicha kutilayotgan toʻlovni undirish"
    if "Shartnoma" in task["stage"]:
        return f"{task['name']} bilan shartnomani imzolatib, avansni olish"
    return f"{task['name']} bilan kelishuvni yopib, toʻlovga olib chiqish"


# ---------------------------------------------------------------- ertalab

_MORNING_FALLBACKS = [
    "Xayrli tong, {name}! Bugun eng muhim ishingiz menimcha shu: {action}{money}. "
    "Shunga rozimisiz yoki bugun pulni boshqa joydan olamizmi?",
    "{name}, salom! Bugungi asosiy pul — {action}{money}. "
    "Shu ishni bugun yopamizmi?",
    "Assalomu alaykum, {name}! Bugun birinchi navbatda: {action}{money}. "
    "Shu sizning eng muhim ishingizmi?",
]
_OPEN_FALLBACK = (
    "Xayrli tong, {name}! Bugun pul keltiradigan eng muhim ishingiz nima? "
    "Bir gap bilan yozing, kun davomida yoningizda boʻlaman."
)


async def compose_morning(
    member: Dict[str, Any],
    tasks: List[Dict[str, Any]],
    yesterday: Optional[Dict[str, Any]] = None,
    generate: Optional[Generate] = None,
) -> str:
    name = member["name"]
    role = member.get("role", "sales")
    if not tasks:
        return _OPEN_FALLBACK.format(name=name)

    top = tasks[0]
    facts = [f"Asosiy taklif: {task_action(top, role)} ({describe_task(top)})."]
    for extra in tasks[1:]:
        facts.append(f"Zaxira variant: {describe_task(extra)}.")
    if yesterday and yesterday.get("task"):
        status = yesterday.get("status")
        facts.append(
            f"Kecha ({yesterday.get('day')}) vaʼda qilingan ish: {yesterday['task']}; holati: {status}."
        )
    prompt = (
        f"Jamoa aʼzosi: {name} (rol: {'moliya' if role == 'finance' else 'sotuv'}).\n"
        + "\n".join(facts)
        + "\n\nErtalabki xabar yoz: agar kechagi ish bajarilmagan boʻlsa qisqa eslat; "
        "keyin bugungi asosiy ishni aniq taklif qil va oxirida shu ish rostdan eng "
        "muhimmi deb soʻra."
    )
    text = await _ai(prompt, generate)
    if text:
        return text
    money = f" ({fmt_money(top['price'])})" if top.get("price") else ""
    return random.choice(_MORNING_FALLBACKS).format(name=name, action=task_action(top, role), money=money)


# ---------------------------------------------------------------- javobni tushunish

# Apostrof turlari: ʻ ʼ ` va ASCII (\x27) — foydalanuvchi qaysi birini yozsa ham mos keladi.
_AP = r"[ʻʼ`\x27]?"
_DONE = re.compile(
    rf"\b(bajardim|bajarildi|qildim|tugadi|to{_AP}ladi|tuladi|oldim|imzoladi|yopdim|yopildi)\b", re.I
)
_YES = re.compile(
    rf"^\s*(ha|xa|xo{_AP}p|hop|ok|okey|roziman|mayli|albatta|to{_AP}g{_AP}ri|tugri|shu)\b", re.I
)
_NO = re.compile(rf"^\s*(yo{_AP}q|yuq|boshqa|emas)\b", re.I)


def classify_reply(text: str) -> str:
    """accepted | done | changed | declined — oddiy qoidalar bilan, AIʼsiz."""
    cleaned = (text or "").strip()
    if not cleaned:
        return STATUS_DECLINED
    if _DONE.search(cleaned):
        return STATUS_DONE
    if _YES.search(cleaned):
        return STATUS_ACCEPTED
    if _NO.search(cleaned):
        # "Yoʻq, bugun X qilaman" — oʻz ishini aytgan.
        return STATUS_CHANGED if len(cleaned.split()) > 3 else STATUS_DECLINED
    # Uzun erkin javob — odatda oʻz ishini aytadi.
    return STATUS_CHANGED if len(cleaned.split()) >= 3 else STATUS_ACCEPTED


_REPLY_FALLBACKS = {
    STATUS_ACCEPTED: "Zoʻr, {name}! Kelishdik. Kun oʻrtasida natijani bir soʻrab qoʻyaman 🙂",
    STATUS_DONE: "Barakalla, {name}! Ajoyib natija 👏 Shu temp bilan davom etamiz.",
    STATUS_CHANGED: "Tushundim, {name}. Unda bugungi asosiy ish — siz aytgani. Omad, kechroq qanday boʻlganini soʻrayman.",
    STATUS_DECLINED: "Mayli, {name}. Unda bugun qaysi ish pul keltiradi? Bir gap bilan yozing, birga rejalaymiz.",
}


async def compose_reply(
    member: Dict[str, Any],
    status: str,
    their_text: str,
    proposed_task: str,
    generate: Optional[Generate] = None,
) -> str:
    name = member["name"]
    prompt = (
        f"Jamoa aʼzosi: {name}.\nErtalab taklif qilingan ish: {proposed_task or 'aniq ish taklif qilinmagan'}.\n"
        f"Uning javobi: {their_text}\nJavobni tushunish natijasi: {status}.\n\n"
        "Qisqa (1-2 gap) tabiiy javob yoz. accepted boʻlsa — qoʻllab-quvvatla va kechroq "
        "soʻrashingni ayt; done — chin dildan maqta; changed — uning rejasini qabul qil; "
        "declined — bugun qaysi ish pul keltirishini muloyim soʻra."
    )
    text = await _ai(prompt, generate, temperature=0.7)
    return text or _REPLY_FALLBACKS.get(status, _REPLY_FALLBACKS[STATUS_ACCEPTED]).format(name=name)


# ---------------------------------------------------------------- eslatmalar

async def compose_nudge(member: Dict[str, Any], task: str, generate: Optional[Generate] = None) -> str:
    name = member["name"]
    text = await _ai(
        f"{name} ertalabki xabaringga hali javob bermadi. Taklif qilingan ish: {task}. "
        "Bosim qilmasdan, doʻstona qisqa eslatma yoz (1-2 gap).",
        generate,
    )
    return text or f"{name}, ertalabki xabarimni koʻrdingizmi? Bugungi asosiy ish boʻyicha bir ogʻiz yozib qoʻying 🙂"


async def compose_followup(member: Dict[str, Any], task: str, generate: Optional[Generate] = None) -> str:
    name = member["name"]
    text = await _ai(
        f"{name} bugun shu ishni qilishga kelishgan edi: {task}. Hozir kun oʻrtasi. "
        "Qanday ketayotganini tabiiy, qisqa soʻra; yordam kerakmi deb ham qoʻsh.",
        generate,
    )
    return text or f"{name}, {task} — qanday ketyapti? Biror joyda yordam kerak boʻlsa ayting."


# ---------------------------------------------------------------- egasiga xulosa

_STATUS_LABEL = {
    "proposed": "javob bermadi",
    STATUS_ACCEPTED: "kelishildi",
    STATUS_CHANGED: "oʻz ishini tanladi",
    STATUS_DONE: "bajardi ✅",
    STATUS_DECLINED: "rad etdi",
}


def compose_owner_summary(day: str, team: List[Dict[str, Any]], entries: Dict[str, Any]) -> str:
    lines = [f"📋 Kunlik pul ishlari — {day}", ""]
    done = 0
    silent = []
    for member in team:
        entry = entries.get(member["key"])
        if not entry:
            lines.append(f"• {member['name']}: bugun soʻrov yuborilmadi")
            continue
        status = entry.get("status", "proposed")
        done += status == STATUS_DONE
        if status == "proposed":
            silent.append(member["name"])
        line = f"• {member['name']}: {entry.get('task') or '—'} — {_STATUS_LABEL.get(status, status)}"
        if entry.get("reply"):
            line += f"\n   Javobi: {entry['reply'][:160]}"
        if entry.get("followup_reply"):
            line += f"\n   Kunduzgi javobi: {entry['followup_reply'][:160]}"
        lines.append(line)
    lines += ["", f"Bajarildi: {done}/{len(team)}"]
    if silent:
        lines.append(f"⚠️ Javob bermaganlar: {', '.join(silent)}")
    return "\n".join(lines)
