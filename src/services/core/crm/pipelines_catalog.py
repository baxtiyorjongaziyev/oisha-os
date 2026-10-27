"""Jon CRM — 9 Voronka, Bosqichlar, Custom Maydonlar va Teglar Katalogi.

amoCRM ning 1:1 strukturasi (9 ta voronka, 75 ta status, 21 ta BANT/SPIN custom field)
hamda Twenty CRM (`crm.jonbranding.uz`) bilan sinxron mapping konfiguratsiyasi.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# 1. Mas'ul xodimlar katalogi
CRM_SELLERS: List[Dict[str, Any]] = [
    {"id": 8128012, "slug": "baxtiyorjon", "name": "Baxtiyorjon Gaziyev", "role": "Asoschi / Art-direktor"},
    {"id": 13021974, "slug": "shahnoza", "name": "Shahnoza Abdijabborova", "role": "Sotuv menejeri"},
    {"id": 13838466, "slug": "oydin", "name": "Oydin Ermuhammadova", "role": "Sotuv menejeri"},
    {"id": 9000001, "slug": "rayxona", "name": "Rayxona", "role": "Sotuv menejeri"},
    {"id": 9000002, "slug": "mumtozmaxal", "name": "Mumtozmaxal", "role": "Sotuvchi"},
]

SELLER_ID_TO_NAME: Dict[int, str] = {s["id"]: s["name"] for s in CRM_SELLERS}
SELLER_ID_TO_NAME[13841510] = "Oydin Ermuhammadova"

# 2. Barcha 9 ta voronka va ularning haqiqiy bosqichlari (Sof o'zbekcha amoCRM 1:1)
PIPELINES_CATALOG: List[Dict[str, Any]] = [
    {
        "id": 11162698,
        "name": "Sotuv bo'limi",
        "badge": "Asosiy",
        "is_archive": False,
        "statuses": [
            {"id": 87609510, "slug": "nerazobrannoe", "title": "Saralanmagan", "color": "#94a3b8", "twenty": "NEW"},
            {"id": 89067962, "slug": "yangi", "title": "Yangi murojaatlar", "color": "#3b82f6", "twenty": "NEW"},
            {"id": 87609518, "slug": "qayta_aloqa", "title": "Qayta aloqa", "color": "#f59e0b", "twenty": "SCREENING"},
            {"id": 87609522, "slug": "oylamoqda", "title": "Saralash (Kvalifikatsiya)", "color": "#ea580c", "twenty": "SCREENING"},
            {"id": 87609526, "slug": "uchrashuv", "title": "Uchrashuv belgilandi", "color": "#8b5cf6", "twenty": "MEETING"},
            {"id": 89380154, "slug": "uchrashuvga_keldi", "title": "Uchrashuv bo'lib o'tdi", "color": "#6366f1", "twenty": "MEETING"},
            {"id": 88871066, "slug": "jarayonda", "title": "Shartnoma va to'lov", "color": "#14b8a6", "twenty": "PROPOSAL"},
            {"id": 142, "slug": "sotuv", "title": "Muvaffaqiyatli sotuv", "color": "#22c55e", "twenty": "CUSTOMER"},
            {"id": 143, "slug": "qiziqmadi", "title": "Yopildi va amalga oshmadi", "color": "#ef4444", "twenty": "PROPOSAL"},
        ],
    },
    {
        "id": 10123318,
        "name": "Mijozlar bilan ishlash (Farmer)",
        "badge": "Ishlab chiqarish",
        "is_archive": False,
        "statuses": [
            {"id": 80215330, "slug": "farmer_unsorted", "title": "Saralanmagan", "color": "#94a3b8", "twenty": "NEW"},
            {"id": 80215334, "slug": "loyiha_brief", "title": "Loyiha va brif", "color": "#3b82f6", "twenty": "NEW"},
            {"id": 80215338, "slug": "ish_jarayonida", "title": "Ish jarayonida", "color": "#f59e0b", "twenty": "SCREENING"},
            {"id": 80215342, "slug": "taqdimot_pravka", "title": "Taqdimot va tuzatishlar", "color": "#8b5cf6", "twenty": "MEETING"},
            {"id": 80215438, "slug": "topshirishga_tayyor", "title": "Topshirishga tayyor", "color": "#14b8a6", "twenty": "PROPOSAL"},
            {"id": 86306514, "slug": "yakuniy_tolov_kutilmoqda", "title": "Yakuniy 50% to'lov kutilmoqda", "color": "#ea580c", "twenty": "PROPOSAL"},
            {"id": 86076834, "slug": "loyiha_review", "title": "Loyiha topshirildi / Fikr", "color": "#6366f1", "twenty": "CUSTOMER"},
            {"id": 86306518, "slug": "yakuniy_tolov_olindi", "title": "Yakuniy to'lov olindi", "color": "#10b981", "twenty": "CUSTOMER"},
            {"id": 142, "slug": "sotuv", "title": "Muvaffaqiyatli yakunlandi", "color": "#22c55e", "twenty": "CUSTOMER"},
            {"id": 143, "slug": "qiziqmadi", "title": "Yopildi va amalga oshmadi", "color": "#ef4444", "twenty": "PROPOSAL"},
        ],
    },
    {
        "id": 10947042,
        "name": "Qayta faollashtirish (Reaktivatsiya)",
        "badge": "Qayta uyg'otish",
        "is_archive": False,
        "statuses": [
            {"id": 86076842, "slug": "react_unsorted", "title": "Saralanmagan", "color": "#94a3b8", "twenty": "NEW"},
            {"id": 86076846, "slug": "sovuq_baza", "title": "Sovuq baza", "color": "#64748b", "twenty": "NEW"},
            {"id": 86076850, "slug": "react_aloqa", "title": "Qayta aloqa qilindi", "color": "#3b82f6", "twenty": "SCREENING"},
            {"id": 86076854, "slug": "qiziqish_qaytdi", "title": "Qiziqish uyg'ondi", "color": "#f59e0b", "twenty": "SCREENING"},
            {"id": 86076858, "slug": "react_uchrashuv", "title": "Uchrashuv / Tijoriy taklif", "color": "#8b5cf6", "twenty": "MEETING"},
            {"id": 86076862, "slug": "closerga_qaytarildi", "title": "Sotuvga o'tkazildi", "color": "#14b8a6", "twenty": "PROPOSAL"},
            {"id": 142, "slug": "sotuv", "title": "Muvaffaqiyatli sotuv", "color": "#22c55e", "twenty": "CUSTOMER"},
            {"id": 143, "slug": "qiziqmadi", "title": "Yopildi va amalga oshmadi", "color": "#ef4444", "twenty": "PROPOSAL"},
        ],
    },
    {
        "id": 10947046,
        "name": "Hamkorlik (Partnership)",
        "badge": "Hamkorlar",
        "is_archive": False,
        "statuses": [
            {"id": 86076866, "slug": "part_unsorted", "title": "Saralanmagan", "color": "#94a3b8", "twenty": "NEW"},
            {"id": 86076870, "slug": "yangi_hamkor", "title": "Yangi hamkor", "color": "#3b82f6", "twenty": "NEW"},
            {"id": 86076874, "slug": "part_kontakt", "title": "Aloqa o'rnatildi", "color": "#f59e0b", "twenty": "SCREENING"},
            {"id": 86076878, "slug": "shartlar_kelishildi", "title": "Shartlar kelishildi", "color": "#8b5cf6", "twenty": "MEETING"},
            {"id": 142, "slug": "sotuv", "title": "Hamkorlik imzolandi", "color": "#22c55e", "twenty": "CUSTOMER"},
            {"id": 143, "slug": "qiziqmadi", "title": "Yopildi va amalga oshmadi", "color": "#ef4444", "twenty": "PROPOSAL"},
        ],
    },
    {
        "id": 10427390,
        "name": "Sifat nazorati (NPS va LTV)",
        "badge": "Sodiqlik",
        "is_archive": False,
        "statuses": [
            {"id": 82391142, "slug": "qc_unsorted", "title": "Saralanmagan", "color": "#94a3b8", "twenty": "NEW"},
            {"id": 82391146, "slug": "nps_fikr", "title": "Mijoz fikrini olish (NPS)", "color": "#3b82f6", "twenty": "SCREENING"},
            {"id": 86076838, "slug": "case_review", "title": "Keys va video-fikr olish", "color": "#8b5cf6", "twenty": "MEETING"},
            {"id": 82391150, "slug": "cross_sell", "title": "Qo'shimcha xizmat taklifi", "color": "#f59e0b", "twenty": "PROPOSAL"},
            {"id": 82391154, "slug": "ltv_doimiy", "title": "Doimiy mijoz (LTV)", "color": "#14b8a6", "twenty": "CUSTOMER"},
            {"id": 142, "slug": "sotuv", "title": "Qayta sotuv amalga oshdi", "color": "#22c55e", "twenty": "CUSTOMER"},
            {"id": 143, "slug": "qiziqmadi", "title": "Yopildi va amalga oshmadi", "color": "#ef4444", "twenty": "PROPOSAL"},
        ],
    },
    {
        "id": 10963570,
        "name": "Ishga qabul (HR Vakansiya)",
        "badge": "Kadrlar",
        "is_archive": False,
        "statuses": [
            {"id": 86197546, "slug": "hr_unsorted", "title": "Saralanmagan", "color": "#94a3b8", "twenty": "NEW"},
            {"id": 86197550, "slug": "yangi_ariza", "title": "Yangi rezyume (CV)", "color": "#3b82f6", "twenty": "NEW"},
            {"id": 86197554, "slug": "hr_saralash", "title": "Dastlabki saralash", "color": "#f59e0b", "twenty": "SCREENING"},
            {"id": 86197558, "slug": "hr_suhbat", "title": "Birlamchi suhbat", "color": "#8b5cf6", "twenty": "MEETING"},
            {"id": 86197562, "slug": "hr_test", "title": "Sinov topshirig'i", "color": "#ea580c", "twenty": "MEETING"},
            {"id": 86197566, "slug": "hr_final", "title": "Rahbar bilan suhbat", "color": "#6366f1", "twenty": "PROPOSAL"},
            {"id": 86197570, "slug": "hr_offer", "title": "Ish taklifi yuborildi", "color": "#14b8a6", "twenty": "PROPOSAL"},
            {"id": 142, "slug": "sotuv", "title": "Ishga qabul qilindi", "color": "#22c55e", "twenty": "CUSTOMER"},
            {"id": 143, "slug": "qiziqmadi", "title": "Rad etildi", "color": "#ef4444", "twenty": "PROPOSAL"},
        ],
    },
    {
        "id": 11322658,
        "name": "Koll-markaz (UTC)",
        "badge": "Qo'ng'iroqlar",
        "is_archive": False,
        "statuses": [
            {"id": 88756942, "slug": "utc_unsorted", "title": "Saralanmagan", "color": "#94a3b8", "twenty": "NEW"},
            {"id": 88756946, "slug": "utc_yangi", "title": "Yangi murojaat", "color": "#3b82f6", "twenty": "NEW"},
            {"id": 88756950, "slug": "utc_aloqa", "title": "Aloqa qilindi", "color": "#f59e0b", "twenty": "SCREENING"},
            {"id": 88756954, "slug": "utc_ehtiyoj", "title": "Ehtiyoj aniqlandi", "color": "#ea580c", "twenty": "SCREENING"},
            {"id": 88756958, "slug": "utc_uchrashuv", "title": "Uchrashuv belgilandi", "color": "#8b5cf6", "twenty": "MEETING"},
            {"id": 88756962, "slug": "utc_taklif", "title": "Tijoriy taklif berildi", "color": "#6366f1", "twenty": "PROPOSAL"},
            {"id": 88756966, "slug": "utc_qaror", "title": "Qaror kutilmoqda", "color": "#14b8a6", "twenty": "PROPOSAL"},
            {"id": 142, "slug": "sotuv", "title": "Muvaffaqiyatli sotuv", "color": "#22c55e", "twenty": "CUSTOMER"},
            {"id": 143, "slug": "qiziqmadi", "title": "Yopildi va amalga oshmadi", "color": "#ef4444", "twenty": "PROPOSAL"},
        ],
    },
    {
        "id": 11162702,
        "name": "[Arxiv] Ekspert sotuvi (Closer)",
        "badge": "Arxiv",
        "is_archive": True,
        "statuses": [
            {"id": 87609530, "slug": "cl_unsorted", "title": "Saralanmagan", "color": "#94a3b8", "twenty": "NEW"},
            {"id": 87609534, "slug": "cl_uchrashuv", "title": "Uchrashuv o'tdi", "color": "#3b82f6", "twenty": "MEETING"},
            {"id": 87609538, "slug": "cl_kp", "title": "Tijoriy taklif (KP)", "color": "#f59e0b", "twenty": "PROPOSAL"},
            {"id": 87609542, "slug": "cl_muzokara", "title": "Muzokara", "color": "#8b5cf6", "twenty": "PROPOSAL"},
            {"id": 87609546, "slug": "cl_shartnoma", "title": "Shartnoma tayyorlanmoqda", "color": "#14b8a6", "twenty": "PROPOSAL"},
            {"id": 87609550, "slug": "cl_avans", "title": "Avans kutilmoqda", "color": "#ea580c", "twenty": "PROPOSAL"},
            {"id": 142, "slug": "sotuv", "title": "Muvaffaqiyatli sotuv", "color": "#22c55e", "twenty": "CUSTOMER"},
            {"id": 143, "slug": "qiziqmadi", "title": "Yopildi va amalga oshmadi", "color": "#ef4444", "twenty": "PROPOSAL"},
        ],
    },
    {
        "id": 11295630,
        "name": "[Arxiv] Target murojaatlari",
        "badge": "Arxiv",
        "is_archive": True,
        "statuses": [
            {"id": 88564634, "slug": "tg_unsorted", "title": "Saralanmagan", "color": "#94a3b8", "twenty": "NEW"},
            {"id": 88696194, "slug": "tg_yangi", "title": "Yangi murojaat", "color": "#3b82f6", "twenty": "NEW"},
            {"id": 88564638, "slug": "tg_aloqa", "title": "Aloqa qilindi", "color": "#f59e0b", "twenty": "SCREENING"},
            {"id": 88564642, "slug": "tg_ehtiyoj", "title": "Ehtiyoj aniqlandi", "color": "#ea580c", "twenty": "SCREENING"},
            {"id": 88564646, "slug": "tg_uchrashuv", "title": "Uchrashuv belgilandi", "color": "#8b5cf6", "twenty": "MEETING"},
            {"id": 88564682, "slug": "tg_taklif", "title": "Taklif berildi", "color": "#6366f1", "twenty": "PROPOSAL"},
            {"id": 88564686, "slug": "tg_qaror", "title": "Qaror kutilmoqda", "color": "#14b8a6", "twenty": "PROPOSAL"},
            {"id": 142, "slug": "sotuv", "title": "To'lov qabul qilindi", "color": "#22c55e", "twenty": "CUSTOMER"},
            {"id": 143, "slug": "qiziqmadi", "title": "Yopildi va amalga oshmadi", "color": "#ef4444", "twenty": "PROPOSAL"},
        ],
    },
]

# 3. 21 ta BANT/SPIN/Sotuv Custom Maydonlari Katalogi
DEAL_CUSTOM_FIELDS_SCHEMA: List[Dict[str, Any]] = [
    {"key": "brand_name", "amo_id": 1551701, "label": "Brend / Biznes nomi", "type": "text", "group": "bant"},
    {"key": "industry", "amo_id": 1034673, "label": "Faoliyat sohasi", "type": "select", "group": "bant", "options": [
        "Oziq-ovqat", "Restoran / HoReCa", "Chakana savdo", "Qurilish / Ko'chmas mulk", "Ta'lim",
        "Tibbiyot", "IT", "Ishlab chiqarish", "Moliya", "Go'zallik", "Logistika", "Tekstil / Kiyim", "Boshqa"
    ]},
    {"key": "business_stage", "amo_id": 1551697, "label": "Tadbirkorlik holati", "type": "select", "group": "bant", "options": [
        "Yangi biznes (Startap)", "Faol biznes (1-3 yil)", "Yirik korxona (3+ yil)", "Rebrending bosqichida"
    ]},
    {"key": "service_type", "amo_id": 1552241, "label": "Kerakli xizmatlar", "type": "multiselect", "group": "bant", "options": [
        "Brend strategiya", "Neyming", "Patentlash", "Logotip", "Brendbuk", "Firma uslubi", "Qadoq dizayni", "Rebrending", "Veb-sayt", "SMM"
    ]},
    {"key": "main_goal", "amo_id": 1034669, "label": "Asosiy maqsad", "type": "select", "group": "bant", "options": [
        "Sotuvni oshirish", "Yangi mahsulot chiqarish", "Premium segmentga o'tish", "Huquqiy himoya (Patent)", "Eksportga chiqish"
    ]},
    {"key": "pain_point", "amo_id": 1552243, "label": "Mijoz nimani hal qilmoqchi? (SPIN)", "type": "textarea", "group": "spin"},
    {"key": "ai_need_summary", "amo_id": 1427493, "label": "Mijozning ehtiyoji (AI xulosasi)", "type": "textarea", "group": "spin"},
    {"key": "decision_role", "amo_id": 1552249, "label": "Qaror qiluvchi (Authority)", "type": "select", "group": "bant", "options": [
        "O'zi qaror qiladi (Founder)", "Hamkorlar bilan maslahatlashadi", "Boshqaruvchi / Marketolog", "Noma'lum"
    ]},
    {"key": "budget_fit", "amo_id": 1552251, "label": "Narxga moslik (Budget)", "type": "select", "group": "bant", "options": [
        "5 mln gacha", "5 - 15 mln", "15 - 50 mln", "50 - 150 mln", "150 mln+", "Narx aytilmadi"
    ]},
    {"key": "start_timeline", "amo_id": 1552245, "label": "Boshlash vaqti (Timeline)", "type": "select", "group": "bant", "options": [
        "Darhol / Shu hafta", "Shu oy ichida", "1-3 oydan keyin", "Faqat narx o'rganmoqda"
    ]},
    {"key": "meeting_format", "amo_id": 1427499, "label": "Uchrashuv formati", "type": "select", "group": "process", "options": [
        "Ofisda yuzma-yuz", "Zoom / Google Meet", "Telegram orqali", "Telefon orqali"
    ]},
    {"key": "next_step", "amo_id": 1552255, "label": "Keyingi aniq qadam", "type": "text", "group": "process"},
    {"key": "callback_date", "amo_id": 1552247, "label": "Qayta aloqa sanasi", "type": "date", "group": "process"},
    {"key": "callback_status", "amo_id": 1034667, "label": "Qayta bog'lanish statusi", "type": "select", "group": "process", "options": [
        "Ko'tarmadi (1-marta)", "Ko'tarmadi (2+ marta)", "Vaqti yo'q edi", "KP ko'rib chiqmoqda", "Shartnoma kutilyapti"
    ]},
    {"key": "advance_amount", "amo_id": 1545969, "label": "Avans summasi (UZS)", "type": "number", "group": "finance"},
    {"key": "remaining_payment_date", "amo_id": 1545967, "label": "Qoldiq to'lov sanasi", "type": "date", "group": "finance"},
    {"key": "payment_method", "amo_id": 1034683, "label": "To'lov usuli", "type": "select", "group": "finance", "options": [
        "Pul o'tkazish (Perechisleniye)", "Naqd", "Karta (P2P)", "Bo'lib to'lash"
    ]},
    {"key": "lead_source", "amo_id": 1034663, "label": "Lid manbasi", "type": "select", "group": "marketing", "options": [
        "Target (Meta Ads)", "Instagram Organik", "Telegram", "Sayt (jonbranding.uz)", "Networking (PCG / Metasell)", "Tavsiya (Sarafan)", "Qayta mijoz"
    ]},
    {"key": "telegram_username", "amo_id": 1037937, "label": "Telegram @username", "type": "text", "group": "marketing"},
    {"key": "meta_lead_id", "amo_id": 1554007, "label": "Meta Lead ID", "type": "text", "group": "marketing"},
]

AMO_CF_ID_TO_KEY: Dict[int, str] = {cf["amo_id"]: cf["key"] for cf in DEAL_CUSTOM_FIELDS_SCHEMA}


def get_pipeline_by_id(pipeline_id: int) -> Dict[str, Any]:
    """Return pipeline config by ID, defaulting to Sotuv Bo'limi."""
    for p in PIPELINES_CATALOG:
        if p["id"] == pipeline_id:
            return p
    return PIPELINES_CATALOG[0]


def resolve_status_info(pipeline_id: int, status_id: Optional[int] = None, status_slug: Optional[str] = None) -> Dict[str, Any]:
    """Resolve status dictionary (id, slug, title, color, twenty) for a pipeline."""
    pipeline = get_pipeline_by_id(pipeline_id)
    statuses = pipeline["statuses"]
    if status_id is not None:
        for st in statuses:
            if st["id"] == status_id:
                return st
    if status_slug:
        for st in statuses:
            if st["slug"] == status_slug:
                return st
        # Legacy dialer slug mapping for Sotuv Bo'limi
        if status_slug == "kotarmadi":
            for st in statuses:
                if st["slug"] in ("qayta_aloqa", "utc_aloqa", "react_aloqa", "tg_aloqa"):
                    return st
    return statuses[1] if len(statuses) > 1 else statuses[0]
