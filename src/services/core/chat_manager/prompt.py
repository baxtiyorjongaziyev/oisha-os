"""Agent sozlamalari va bilimlar bazasidan javob yozuvchi uchun instruksiya.

Cheklovlar (GUARDRAILS) sozlamalardan qat'i nazar har doim qo'shiladi —
docs/reveo-clone-spec.md 2-bo'lim. Agent faqat bilimlar bazasidagi faktlarga
tayanadi; u yerda yo'q narsani menejerga beradi.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

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
_KNOWLEDGE_CHARS = 12000


def build_instructions(settings: Dict[str, Any],
                       knowledge: Optional[Iterable[Dict[str, Any]]] = None) -> str:
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
    entries = list(knowledge or [])
    if entries:
        lines.append("Bilimlar bazasi (faqat shu faktlarga tayan):")
        used = 0
        for entry in entries:
            block = f"## {entry['title']}\n{entry['body']}"
            if used + len(block) > _KNOWLEDGE_CHARS:
                break
            lines.append(block)
            used += len(block)
    else:
        lines.append("Bilimlar bazasi bo'sh: narx va shartlar bo'yicha har doim menejerga ber.")
    return "\n".join(lines)
