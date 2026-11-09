"""
Lead Filter Guard — Ichki jamoa, aloqa provayderlari va soxta bitimlarni filtrlash.

Nol-galutsinatsiya (Zero Hallucination) va Zero Fabrication talablarini taʼminlaydi.
Oʻz xodimlarimiz, Uztelecom kabi operatorlar yoki 'Menejer' deb saqlangan
kontaktlarning 'mijoz' sifatida tahlil qilinishi va ularga xabar generatsiya
qilinishini 100% bloklaydi.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

# 1. Jon Branding ichki jamoa aʼzolari va kalit soʻzlari
INTERNAL_TEAM_KEYWORDS = {
    "jon branding",
    "jonbranding",
    "mumtozmaxal",
    "normurodova",
    "shahnoza",
    "abdijabborova",
    "rayxon",
    "rayxona",
    "baxtiyorjon",
    "gaziyev",
    "dilbar",
    "dilorom",
    "farangiz",
    "amina",
    "oisha",
}

# 2. Servis provayderlar, aloqa operatorlari va tizim botlari
SERVICE_PROVIDER_KEYWORDS = {
    "uztelecom",
    "uzmobile",
    "ucell",
    "beeline",
    "mobiuz",
    "ums",
    "perfectum",
    "amobot",
    "telegram",
    "bot",
    "support",
    "operator",
    "admin",
    "moderator",
    "menejer",
    "menejeri",
    "manager",
}

# 3. Yaroqsiz, qoʻngʻiroq logi yoki test sdelkalar
DUMMY_LEAD_PATTERNS = [
    re.compile(r"не\s+дозвонился", re.I),
    re.compile(r"пропущен", re.I),
    re.compile(r"звонок\s+(?:на|от)", re.I),
    re.compile(r"^test\b", re.I),
    re.compile(r"^тест\b", re.I),
]

# 4. Asossiz / toʻqima iboralar (hallucinated claims)
HALLUCINATED_CLAIM_PATTERNS = [
    re.compile(r"\bkecha\s+aytgan\b", re.I),
    re.compile(r"\bkecha\s+gaplashgan\b", re.I),
    re.compile(r"\bvчера\s+(?:вы|мы|говорили)\b", re.I),
]


def is_excluded_contact(
    name: Optional[str] = None,
    phone: Optional[str] = None,
    username: Optional[str] = None,
    notes: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Kontakt yoki bitim ichki xodim, provayder yoki yaroqsiz kontakt ekanini aniqlash.
    
    Qaytaradi:
        (True, sabab) — agar chiqarib tashlanishi shart boʻlsa.
        (False, "") — agar haqiqiy mijoz boʻlishi mumkin boʻlsa.
    """
    name_clean = (name or "").strip().lower()
    username_clean = (username or "").strip().lower().lstrip("@")
    notes_clean = (notes or "").strip().lower()

    # A) Ichki jamoa tekshiruvi
    for kw in INTERNAL_TEAM_KEYWORDS:
        if kw in name_clean or kw in username_clean:
            return True, f"internal_team_member:{kw}"

    # B) Servis provayderlar va botlar
    for kw in SERVICE_PROVIDER_KEYWORDS:
        if kw in name_clean or kw in username_clean:
            # Masalan, 'Dilnoza Uztelecom' yoki 'Ifora Menejer'
            if kw == "menejer" and ("menejer" in name_clean or "menejeri" in name_clean):
                return True, "service_provider:menejer_title"
            if kw != "menejer" and kw in name_clean:
                return True, f"service_provider:{kw}"

    # C) Yaroqsiz / log sdelkalar
    for pat in DUMMY_LEAD_PATTERNS:
        if pat.search(name_clean):
            return True, f"dummy_deal_marker:{pat.pattern}"

    return False, ""


def validate_lead_qualification(
    raw_industry: Optional[str] = None,
    raw_role: Optional[str] = None,
    raw_budget: Optional[str] = None,
    evidence: Optional[str] = None,
) -> Dict[str, str]:
    """
    Zero Hallucination qoidasiga koʻra soha, lavozim va byudjetni tekshirish.
    Dalilsiz shablon ('Tadbirkorlik / Ishlab chiqarish', 'LPR') yopishtirishni taqiqlaydi.
    """
    evidence_text = (evidence or "").strip().lower()
    
    # 1. Soha (Industry)
    industry = "Nomaʼlum"
    if raw_industry and raw_industry != "Tadbirkorlik / Ishlab chiqarish":
        industry = raw_industry
    elif evidence_text:
        if any(w in evidence_text for w in ["mebel", "qadoq", "upakovka", "ishlab chiqarish"]):
            industry = "Ishlab chiqarish"
        elif any(w in evidence_text for w in ["qurilish", "bino", "remont", "ventilyatsiya"]):
            industry = "Qurilish"
        elif any(w in evidence_text for w in ["restoran", "kafe", "shirinlik", "oziq-ovqat"]):
            industry = "HoReCa / Oziq-ovqat"
        elif any(w in evidence_text for w in ["savdo", "magazin", "doʻkon", "optom"]):
            industry = "Savdo"
        elif any(w in evidence_text for w in ["klinika", "dorixona", "tibbiyot"]):
            industry = "Tibbiyot"

    # 2. Lavozim / Qaror qabul qiluvchi
    role = "Tekshirilmagan"
    if raw_role and raw_role not in ["Qaror qabul qiluvchi (LPR)", "LPR"]:
        role = raw_role
    elif evidence_text:
        if any(w in evidence_text for w in ["asoschi", "direktor", "ceo", "rahbar", "ega"]):
            role = "Rahbar / Asoschi"
        elif any(w in evidence_text for w in ["boshliq", "menejer", "marketing"]):
            role = "Boʻlim rahbari"

    # 3. Toʻlov qobiliyati / Byudjet
    budget = "Tekshirilmagan"
    norm_budget = (raw_budget or "").replace("'", "ʻ")
    if raw_budget and norm_budget not in ["Oʻrtacha (Business)", "Business"]:
        budget = raw_budget

    return {
        "industry": industry,
        "role": role,
        "budget": budget,
    }


def sanitize_outreach_message(
    message_text: str,
    contact_name: str,
    has_recent_conversation: bool = False,
) -> str:
    """
    Xabardagi soxta / galutsinatsiyalangan iboralarni ('Kecha aytgan loyihangiz...') tozalaydi.
    Agar kecha gaplashilgani haqida dalil boʻlmasa, insoniy va hurmatli salomlashishga almashtiradi.
    """
    if not message_text:
        return ""

    text = message_text
    has_hallucinated_claim = any(pat.search(text) for pat in HALLUCINATED_CLAIM_PATTERNS)

    if has_hallucinated_claim and not has_recent_conversation:
        # Galutsinatsiyalangan "Kecha aytgan..." oʻrniga haqiqiy, samimiy salomlashish
        cleaned = (
            f"Assalomu alaykum, {contact_name}! Jon Branding agentligidan bezovta qilyapmiz. "
            f"Avvalgi loyihangiz yuzasidan yangiliklarni bilish va sohangiz boʻyicha yangi "
            f"keyslarimizni ulashish maqsadida bogʻlandik. Qisqa tanishib chiqish uchun qulaymi? 🤝"
        )
        return cleaned

    return text
