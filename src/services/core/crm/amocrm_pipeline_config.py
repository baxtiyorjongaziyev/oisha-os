from __future__ import annotations

from dataclasses import dataclass


SALES_PIPELINE_ID = 10117998
LEGACY_CLOSER_PIPELINE_ID = 10123314
FARMER_PIPELINE_ID = 10123318
REACTIVATION_PIPELINE_ID = 10947042
QC_PIPELINE_ID = 10427390
HR_PIPELINE_ID = 10963570
PARTNERSHIP_PIPELINE_ID = 10947046

ACTIVE_PIPELINE_IDS = [SALES_PIPELINE_ID, FARMER_PIPELINE_ID, REACTIVATION_PIPELINE_ID]

REACTIVATION_DAILY_LIMIT = 10

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
    DesiredStatus("Konsultatsiya o'tdi", 80, "#99ccff", 86306474),
    DesiredStatus("Brief / Ehtiyoj aniqlandi", 90, "#fffeb2", 86306482),
    DesiredStatus("Prezentatsiya & KP", 100, "#ffff99", 86306486),
    DesiredStatus("Follow-up / Qaror kutilyapti", 110, "#fffeb2", 86306490),
    DesiredStatus("Muzokara / Shartnoma", 120, "#99ccff", 86306492),
    DesiredStatus(SALES_ADVANCE_STATUS_NAME, 130, "#99ccff", 86306494),
)

FARMER_STATUSES: tuple[DesiredStatus, ...] = (
    DesiredStatus(FARMER_START_STATUS_NAME, 20, "#99ccff", 80215334),
    DesiredStatus("Ish jarayonida", 30, "#ffff99", 80215338),
    DesiredStatus("Taqdimot & Pravkalar", 40, "#ffcc66", 80215342),
    DesiredStatus("Topshirishga tayyor", 50, "#99ccff", 80215438),
    DesiredStatus(FARMER_FINAL_PAYMENT_PENDING_STATUS_NAME, 60, "#fffeb2", 86306514),
    DesiredStatus(FARMER_FINAL_PAYMENT_RECEIVED_STATUS_NAME, 70, "#99ccff"),
    DesiredStatus(FARMER_REVIEW_STATUS_NAME, 80, "#fffeb2", 86076834),
)

CLOSER_TO_SALES_STATUS_NAME = {
    "Konsultatsiya o'tdi": "Konsultatsiya o'tdi",
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

REACTIVATION_SCENARIO_TEXT = (
    "🎯 ESKI MIJOZLARNI QAYTA UYG'OTISH SENARIYSI\n\n"
    "1. SALOMLASHISH:\n"
    "Assalomu alaykum, [Ism] aka, yaxshimisiz?\n"
    "Biz avval siz bilan biznesingiz bo‘yicha gaplashgan edik. Shuning uchun yana bir holatingizni bilib qo‘yay deb qo‘ng‘iroq qildim.\n"
    "Hozir ishlar qanday ketyapti?\n\n"
    "2. BIZNESINI GAPIRTIRISH:\n"
    "- Hozir savdo yaxshimi?\n"
    "- Mijozlar ko‘paydimi?\n"
    "- O‘sha paytdagi rejalaringizdan qaysilarini qildingiz?\n"
    "- Hozir biznesda sizni eng ko‘p qiynayotgan narsa nima?\n\n"
    "3. BRANDINGNI SODDA TUSHUNTIRISH:\n"
    "Masalan, odam bozorda 10 ta bir xil do‘konni ko‘rsa, bittasini tanlashi kerak bo‘ladi. U nimaga qaraydi?\n"
    "Nomiga, ko‘rinishiga, ishonchiga, boshqalardan farqiga.\n"
    "Odam sizni ko‘rib: “Ha, mana shu joy jiddiy ishlaydi” deb o‘ylashi kerak.\n"
    "Bizning ishimiz ham shuni tartibga solish:\n"
    "- nima sotasiz;\n"
    "- nima uchun sizni tanlash kerak;\n"
    "- sizga ishonsa bo‘ladimi;\n"
    "- siz boshqalardan nimangiz bilan yaxshisiz — shuni tez tushunishi kerak.\n\n"
    "4. MUAMMONI OCHISH:\n"
    "Sizda hozir shunaqa holat bormi:\n"
    "- Odamlar mahsulotingizni yaxshi bilmaydi?\n"
    "- Ko‘p savdolashadimi?\n"
    "- Raqobatchilar bilan sizni bir xil ko‘radimi?\n"
    "- Yaxshi ishlaysiz, lekin tashqaridan bu bilinmayaptimi?\n\n"
    "5. ODDIY MISOL:\n"
    "Masalan, ikkita ustani olaylik. Ikkalasi ham bir xil yaxshi ishlaydi.\n"
    "Bittasining nomi bor, ko‘rinishi chiroyli, ishlari tartibli ko‘rsatilgan, mijozlarning fikri bor.\n"
    "Ikkinchisi esa shunchaki telefon raqami bilan ishlaydi.\n"
    "Odam ko‘pincha birinchisiga ko‘proq ishonadi. Hatto narxi qimmatroq bo‘lsa ham.\n"
    "Biznesda tashqi ko‘rinish ham shunaqa ishlaydi.\n\n"
    "6. UCHRASHUVGA OLIB KELISH (CLOSING):\n"
    "Menimcha, telefonda uzoq gaplashgandan ko‘ra, bir marta uchrashib biznesingizni ko‘rib chiqganimiz yaxshi.\n"
    "Siz nima qilasiz, mijozlaringiz kim, hozir qayerda qiynalyapsiz — shuni ko‘ramiz.\n"
    "Keyin sizga sodda qilib:\n"
    "“Mana bu joyni o‘zgartirish kerak”\n"
    "“Mana bu joy yaxshi”\n"
    "“Mana bu narsaga pul sarflash shart emas” — deb aytamiz.\n"
    "Sizga seshanba qulaymi yoki chorshanba?"
)

