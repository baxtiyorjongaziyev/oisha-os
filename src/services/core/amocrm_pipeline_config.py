from __future__ import annotations

from dataclasses import dataclass


SALES_PIPELINE_ID = 10117998
LEGACY_CLOSER_PIPELINE_ID = 10123314
FARMER_PIPELINE_ID = 10123318

STATUS_WON = 142
STATUS_LOST = 143

SALES_ADVANCE_STATUS_NAME = "50% Avans olindi"
FARMER_START_STATUS_NAME = "Loyiha va Brief"
FARMER_FINAL_PAYMENT_PENDING_STATUS_NAME = "Yakuniy 50% to'lov kutilmoqda"
FARMER_FINAL_PAYMENT_RECEIVED_STATUS_NAME = "Yakuniy to'lov olindi"
FARMER_REVIEW_STATUS_NAME = "Loyiha yopildi / Review"


@dataclass(frozen=True)
class DesiredStatus:
    name: str
    sort: int
    color: str
    existing_id: int | None = None


SALES_STATUSES: tuple[DesiredStatus, ...] = (
    DesiredStatus("Yangi so'rov", 20, "#fffeb2", 80178230),
    DesiredStatus("Birinchi kontakt qilindi", 30, "#fffeb2", 86076798),
    DesiredStatus("Bog'lanib bo'lmadi", 40, "#fffeb2", 80178226),
    DesiredStatus("Muloqot boshlandi", 50, "#fffeb2", 80178222),
    DesiredStatus("Sifatli lead", 60, "#fffeb2", 86076802),
    DesiredStatus("Uchrashuv belgilandi", 70, "#fffeb2", 80178218),
    DesiredStatus("Konsultatsiya o'tdi", 80, "#99ccff"),
    DesiredStatus("Brief / Ehtiyoj aniqlandi", 90, "#fffeb2"),
    DesiredStatus("Prezentatsiya & KP", 100, "#ffff99"),
    DesiredStatus("Follow-up / Qaror kutilyapti", 110, "#fffeb2"),
    DesiredStatus("Muzokara / Shartnoma", 120, "#99ccff"),
    DesiredStatus(SALES_ADVANCE_STATUS_NAME, 130, "#99ccff"),
)

FARMER_STATUSES: tuple[DesiredStatus, ...] = (
    DesiredStatus(FARMER_START_STATUS_NAME, 20, "#99ccff", 80215334),
    DesiredStatus("Ish jarayonida", 30, "#ffff99", 80215338),
    DesiredStatus("Taqdimot & Pravkalar", 40, "#ffcc66", 80215342),
    DesiredStatus("Topshirishga tayyor", 50, "#99ccff", 80215438),
    DesiredStatus(FARMER_FINAL_PAYMENT_PENDING_STATUS_NAME, 60, "#fffeb2"),
    DesiredStatus(FARMER_FINAL_PAYMENT_RECEIVED_STATUS_NAME, 70, "#99ccff"),
    DesiredStatus(FARMER_REVIEW_STATUS_NAME, 80, "#fffeb2", 86076834),
)

CLOSER_TO_SALES_STATUS_NAME = {
    "Konsultatsiya o'tdi": "Konsultatsiya o'tdi",
    "Konsultatsiya o‘tdi": "Konsultatsiya o'tdi",
    "Brief / Ehtiyoj aniqlandi": "Brief / Ehtiyoj aniqlandi",
    "Prezentatsiya & KP": "Prezentatsiya & KP",
    "Follow-up / Qaror kutilyapti": "Follow-up / Qaror kutilyapti",
    "Muzokara / Shartnoma": "Muzokara / Shartnoma",
    SALES_ADVANCE_STATUS_NAME: SALES_ADVANCE_STATUS_NAME,
    "Неразобранное": "Yangi so'rov",
}

FINAL_PAYMENT_TASK_TEXT = (
    "Oisha: loyiha topshirishga tayyor. Yakuniy fayllar va topshirish xulosasini "
    "tayyorlang, mijozga yuboring va qolgan 50% to'lovni undiring."
)
