"""Transkripsiyadan so'zlovchilar nisbatini hisoblash — umumiy yordamchi.

`call_analyzer` (AmoCRM qo'ng'iroq notalari) va `quality_analyzer` (menejer
reytinglari) bir xil transkripsiyalarni o'qiydi, shuning uchun mantiq shu
yerda bitta joyda turadi. Ilgari ikkala fayl o'z nusxasini saqlagan va
ikkalasi ham rolsiz yorliqlarda 0% qaytarib, sotuvchini asossiz jazolagan.
"""

from __future__ import annotations

import re
from typing import Dict, List

_CLIENT_LABELS = re.compile(r"^(mijoz|xaridor|client)\s*:", re.IGNORECASE)
_AGENT_LABELS = re.compile(
    r"^(sotuvchi|menejer|manager|agent|xodim|oisha)\s*:", re.IGNORECASE
)
# Diarizatsiya ko'pincha rolsiz yorliq beradi: "A:", "B:", "Speaker 1:", "1:".
# Bunda kim sotuvchi ekani transkripsiyadan bilinmaydi.
_GENERIC_LABELS = re.compile(r"^(?:speaker\s*)?([ab]|[12])$", re.IGNORECASE)


def speaker_split(transcript: str) -> tuple[int, int, bool]:
    """Return (client_pct, agent_pct, attributed).

    `attributed` is False when speakers carry role-less labels (A/B, 1/2) —
    the two percentages are then a raw first/second-speaker split, not a
    client/agent split. Callers must not present them as roles, and must not
    score the agent on them.
    """
    client_chars = 0
    agent_chars = 0
    generic_chars: Dict[str, int] = {}
    generic_order: List[str] = []

    for line in (transcript or "").splitlines():
        line = line.strip()
        if not line:
            continue
        colon_pos = line.find(":")
        if colon_pos < 1:
            continue
        label = line[:colon_pos].strip()
        text = line[colon_pos + 1:].strip()
        if _CLIENT_LABELS.match(label + ":"):
            client_chars += len(text)
        elif _AGENT_LABELS.match(label + ":"):
            agent_chars += len(text)
        elif _GENERIC_LABELS.match(label):
            key = label.upper()
            if key not in generic_chars:
                generic_chars[key] = 0
                generic_order.append(key)
            generic_chars[key] += len(text)

    total = client_chars + agent_chars
    if total > 0:
        return (
            round(client_chars * 100 / total),
            round(agent_chars * 100 / total),
            True,
        )

    # Rolsiz yorliqlar: aynan 2 ta so'zlovchi bo'lsagina nisbat mazmunli.
    if len(generic_order) == 2:
        first, second = (generic_chars[k] for k in generic_order)
        gen_total = first + second
        if gen_total > 0:
            return (
                round(first * 100 / gen_total),
                round(second * 100 / gen_total),
                False,
            )

    return 0, 0, False


def talk_ratio_verdict(client_pct: int, attributed: bool = True) -> str:
    """Human-readable verdict for the talk ratio.

    Ma'lumot yo'qligi (0%) sotuvchining aybi emas — bunday holatda hukm
    chiqarmaymiz. Rolsiz yorliqlarda ham kim ko'p gapirgani noma'lum.
    """
    if not attributed or client_pct <= 0:
        return "ℹ️ Gapirish nisbati aniqlanmadi — transkripsiyada rollar belgilanmagan"
    if client_pct >= 55:
        return f"✅ Yaxshi — mijoz {client_pct}% gapirdi (ideal: ≥55%)"
    if client_pct >= 40:
        return f"⚠️ O'rtacha — mijoz {client_pct}% gapirdi (ideal: ≥55%)"
    return f"🔴 Zaif — sotuvchi haddan ko'p gapirdi, mijoz faqat {client_pct}% gapirdi"
