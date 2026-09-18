"""
Custom fields extractor and mapper for Meta Lead Ads to AmoCRM.
Maps form answers to structured AmoCRM custom fields (A/B/C tier, LPR, business stage, etc.).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


# AmoCRM Field IDs
FIELD_LEAD_TIER = 1551693          # Lead toifasi (Sifati) [Select]
FIELD_LPR_STATUS = 1551695         # Qaror qabul qiluvchi (LPR) [Select]
FIELD_BUSINESS_STAGE = 1551697     # Tadbirkorlik holati [Select]
FIELD_TIMELINE = 1551699           # Boshlash muddati [Select]
FIELD_BRAND_NAME = 1551701         # Brend / Biznes nomi [Text]

# Existing System Field IDs
FIELD_LEAD_SOURCE = 1034663        # Lead manbasi [Select]
FIELD_MAIN_GOAL = 1034669          # Asosiy maqsad [Select]
FIELD_SERVICES = 1034671           # Tanlangan xizmatlar [Multi-Select]
FIELD_ACTIVITY_SECTOR = 1034673    # Faoliyat sohasi [Select]

# Enum IDs
ENUM_SOURCE_TARGET = 965711        # Target (Instagram / FB)

ENUM_TIER_A = 1377101              # 🟢 A - Issiq / VIP ($1000+, LPR, 1 oy)
ENUM_TIER_B = 1377103              # 🟡 B - Iliq ($300-$800, Rejada bor)
ENUM_TIER_C = 1377105              # 🔴 C - Sifatsiz (Byudjet yo'q / Noaniq)

ENUM_STAGE_PRODUCT_EXISTS = 1377115   # Mahsulotim bor, brend himoyalanmagan
ENUM_STAGE_NEW_BIZ = 1377117          # Yangi biznes boshlayapman
ENUM_STAGE_REBRAND = 1377119          # Brendim mavjud (rebrending)
ENUM_STAGE_SCALE = 1377121            # Brendimni rivojlantirmoqchiman

ENUM_SECTOR_TRADE = 965757            # Savdo
ENUM_SECTOR_PRODUCTION = 965755       # Ishlab chiqarish
ENUM_SECTOR_SERVICE = 965753          # Xizmat ko'rsatish
ENUM_SECTOR_EDUCATION = 965751        # Ta'lim
ENUM_SECTOR_IT = 965749               # IT va texnologiyalar
ENUM_SECTOR_MEDICINE = 965747         # Tibbiyot
ENUM_SECTOR_OTHER = 965745            # Boshqa

ENUM_GOAL_PROTECT = 1375123           # Himoya qilish / Patentlash
ENUM_GOAL_FAMOUS = 1375125            # Taniqli bo'lish
ENUM_GOAL_TRUST = 1375127             # Ishonch qozonish
ENUM_GOAL_OTHER = 1375129             # Boshqa


def _find_field_val(fields: Dict[str, str], keywords: List[str]) -> str:
    """Helper to find matching field by keyword prefixes or parts."""
    for key, val in fields.items():
        k_lower = key.lower()
        if any(kw in k_lower for kw in keywords):
            return str(val).strip()
    return ""


def extract_lead_custom_fields(fields: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Extracts structured AmoCRM custom fields from Meta Lead Ads question-answer dict.
    Returns list of custom field payload dictionaries compatible with AmoCRM API v4.
    """
    custom_fields: List[Dict[str, Any]] = []

    # 1. Lead manbasi: Always Target for Meta Lead Ads
    custom_fields.append({
        "field_id": FIELD_LEAD_SOURCE,
        "values": [{"enum_id": ENUM_SOURCE_TARGET}],
    })

    # 2. Brend / Biznes nomi
    brand_raw = _find_field_val(fields, ["brend", "biznes", "nomi", "kompaniya", "loyiha"])
    if brand_raw and brand_raw.lower() not in ["a", "yoq", "yo'q", "mavjud emas", "-"]:
        custom_fields.append({
            "field_id": FIELD_BRAND_NAME,
            "values": [{"value": brand_raw[:250]}],
        })

    # 3. Tadbirkorlik holati
    stage_raw = _find_field_val(fields, ["tadbirkorlik", "holat", "biznes_holati"]).lower()
    stage_enum: Optional[int] = None
    if "mahsulot" in stage_raw:
        stage_enum = ENUM_STAGE_PRODUCT_EXISTS
    elif "yangi" in stage_raw:
        stage_enum = ENUM_STAGE_NEW_BIZ
    elif "rebrend" in stage_raw:
        stage_enum = ENUM_STAGE_REBRAND
    elif "rivoj" in stage_raw:
        stage_enum = ENUM_STAGE_SCALE

    if stage_enum:
        custom_fields.append({
            "field_id": FIELD_BUSINESS_STAGE,
            "values": [{"enum_id": stage_enum}],
        })

    # 4. Faoliyat sohasi
    sector_raw = _find_field_val(fields, ["soha", "faoliyat"]).lower()
    sector_enum: Optional[int] = None
    if "savdo" in sector_raw or "magazin" in sector_raw:
        sector_enum = ENUM_SECTOR_TRADE
    elif "ishlab" in sector_raw or "zavod" in sector_raw or "fabrika" in sector_raw:
        sector_enum = ENUM_SECTOR_PRODUCTION
    elif "xizmat" in sector_raw or "servis" in sector_raw:
        sector_enum = ENUM_SECTOR_SERVICE
    elif "ta'lim" in sector_raw or "talim" in sector_raw or "maktab" in sector_raw or "kurs" in sector_raw:
        sector_enum = ENUM_SECTOR_EDUCATION
    elif "it" in sector_raw or "dastur" in sector_raw or "texnolog" in sector_raw:
        sector_enum = ENUM_SECTOR_IT
    elif "tibbiyot" in sector_raw or "klinika" in sector_raw or "apteka" in sector_raw:
        sector_enum = ENUM_SECTOR_MEDICINE
    elif sector_raw:
        sector_enum = ENUM_SECTOR_OTHER

    if sector_enum:
        custom_fields.append({
            "field_id": FIELD_ACTIVITY_SECTOR,
            "values": [{"enum_id": sector_enum}],
        })

    # 5. Asosiy maqsad
    goal_raw = _find_field_val(fields, ["maqsad", "patentlashdan_asosiy_maqsad"]).lower()
    goal_enum: Optional[int] = None
    if "himoya" in goal_raw or "patent" in goal_raw:
        goal_enum = ENUM_GOAL_PROTECT
    elif "taniqli" in goal_raw or "mashhur" in goal_raw:
        goal_enum = ENUM_GOAL_FAMOUS
    elif "ishonch" in goal_raw:
        goal_enum = ENUM_GOAL_TRUST
    elif goal_raw:
        goal_enum = ENUM_GOAL_OTHER

    if goal_enum:
        custom_fields.append({
            "field_id": FIELD_MAIN_GOAL,
            "values": [{"enum_id": goal_enum}],
        })

    # 6. Avtomatik Lead Toifasi (A/B tier initial qualification)
    # Agar mahsuloti tayyor bo'lsa va brend himoyasi kerak bo'lsa -> A toifa
    # Agar yangi biznes bo'lsa -> B toifa
    tier_enum = ENUM_TIER_B
    if stage_enum == ENUM_STAGE_PRODUCT_EXISTS:
        tier_enum = ENUM_TIER_A
    elif stage_enum == ENUM_STAGE_NEW_BIZ:
        tier_enum = ENUM_TIER_B

    custom_fields.append({
        "field_id": FIELD_LEAD_TIER,
        "values": [{"enum_id": tier_enum}],
    })

    return custom_fields
