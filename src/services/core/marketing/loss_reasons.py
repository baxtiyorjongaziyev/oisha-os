"""AmoCRM rad etish sabablarini ikki toifaga ajratish: reklama masalasi yoki sotuv masalasi.

"Reklama" — lid o'zi noto'g'ri auditoriya (targetolog javobgar).
"Sotuv"   — lid to'g'ri edi, lekin sotuv jarayonida yo'qotildi (sotuv bo'limi javobgar).
Standart xarita AmoCRM'dagi sabablar ro'yxatiga (2026-10-12) asoslangan; `META_LOSS_AD_REASON_IDS`
env (vergul bilan ID'lar) bilan "reklama" ro'yxatini to'liq almashtirish mumkin.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

AD, SALES, UNKNOWN = "reklama", "sotuv", "noma'lum"

REASON_NAMES: Dict[int, str] = {
    21860098: "Qimmat / Byudjet yetmadi",
    21860102: "Javob bermadi / Yo'qolib qoldi",
    21860106: "Raqobatchini tanladi",
    21860110: "Rejasi o'zgardi / Hozir kerak emas",
    23521002: "Bizning soha emas / Xizmat mos kelmadi",
    23521290: "Muddat / Shartlar to'g'ri kelmadi",
    24237406: "Spam / Adashgan lid",
    24424670: "Qaror qiluvchi emas",
    24424674: "Qiymatni tushunmadi",
    24466610: "Hozir ehtiyoj yo'q",
    24466614: "Narx mos emas",
    24466618: "Keyinroq",
    24466622: "Aloqa qilib bo'lmadi",
    24466626: "Sifatsiz murojaat",
}

DEFAULT_AD_REASON_IDS = frozenset({
    21860098,  # byudjeti yo'q auditoriya
    23521002,  # bizning soha emas
    24237406,  # spam / adashgan
    24424670,  # qaror qiluvchi emas
    24466610,  # ehtiyoj yo'q
    24466626,  # sifatsiz murojaat
})


def _ad_reason_ids() -> frozenset:
    raw = os.getenv("META_LOSS_AD_REASON_IDS", "").strip()
    if not raw:
        return DEFAULT_AD_REASON_IDS
    return frozenset(int(x) for x in raw.split(",") if x.strip().isdigit())


def classify(reason_id: Optional[Any]) -> str:
    try:
        rid = int(reason_id)
    except (TypeError, ValueError):
        return UNKNOWN
    if rid <= 0:
        return UNKNOWN
    return AD if rid in _ad_reason_ids() else SALES


def reason_name(reason_id: Optional[Any]) -> str:
    try:
        return REASON_NAMES.get(int(reason_id), f"#{reason_id}")
    except (TypeError, ValueError):
        return "Sabab ko'rsatilmagan"
