"""Agent sozlamalaridan javob yozuvchi uchun instruksiya matni.

Cheklovlar (GUARDRAILS) sozlamalardan qat'i nazar har doim qo'shiladi —
docs/reveo-clone-spec.md 2-bo'lim.
"""
from __future__ import annotations

from typing import Any, Dict

GUARDRAILS = (
    "Katalogda yoki bilimlar bazasida yo'q narxni aytma — menejerga ber.",
    "Ish vaqti, mavjudlik, muddat yoki kafolatni o'ylab topma.",
    "\"Men botman\" deb o'zingdan gapirma, lekin so'rashsa yashirma.",
    "Mijoz ma'lumotini hech kimga berma.",
    "Shikoyat yoki bahs bo'lsa darhol menejerga ber.",
)
_LANGUAGES = {"uz": "o'zbek", "ru": "rus", "en": "ingliz"}
_AGENT_TYPES = {
    "balanced": "muvozanatli: yordam beradi va yumshoq sotadi",
    "sales": "faol sotuvchi: har javobda keyingi qadamni taklif qiladi",
    "support": "maslahatchi: avval savolga to'liq javob beradi",
}


def build_instructions(settings: Dict[str, Any]) -> str:
    language = _LANGUAGES.get(settings.get("language"), "o'zbek")
    lines = [
        f"Asosiy til: {language}; mijoz boshqa tilda yozsa, o'sha tilda javob ber.",
        f"Agent turi: {_AGENT_TYPES.get(settings.get('agent_type'), _AGENT_TYPES['balanced'])}.",
        f"Informativlik {settings.get('informativeness', 3)}/5 "
        "(1 — faqat savolga javob, 5 — faol tafsilot beradi).",
        f"Javob uzunligi {settings.get('reply_length', 3)}/5 "
        "(1 — juda qisqa, 5 — batafsil).",
        f"Ton: {settings.get('tone', '')}",
        f"Sotuv maqsadi: {settings.get('sales_goal', '')}",
        f"Narx va offer qoidalari: {settings.get('offer_rules', '')}",
        f"Malakalash: {settings.get('qualification', '')}",
        f"Menejerga berish: {settings.get('handoff', '')}",
        "Qat'iy cheklovlar:",
        *(f"- {rule}" for rule in GUARDRAILS),
    ]
    return "\n".join(lines)
