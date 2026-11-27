"""
Lead Filter Guard — Rolni aniqlash (Entity Resolution) va saralash himoyasi.

Kontaktlarni toʻgʻri toifalarga ajratadi:
1. TEAM_MEMBER (Jamoa aʼzosi) — Mumtozmaxal, Shahnoza, Rayxona, Baxtiyorjon va h.k.
2. SERVICE_PROVIDER (Xizmat provayderi) — Uztelecom, Ucell, Beeline, botlar.
3. DUMMY_RECORD (Log/Qoʻngʻiroq yozuvi) — "Не дозвонился", "Пропущен".
4. CLIENT (Mijoz) — Haqiqiy xarid niyatiga ega potensial xaridor.

Nol-galutsinatsiya (Zero Hallucination) va Zero Fabrication talablarini toʻliq taʼminlaydi.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, Optional, Tuple


class EntityRole(str, Enum):
    """Kontakt va foydalanuvchilarning operatsion rollari."""
    TEAM_MEMBER = "team_member"          # Jon Branding ichki jamoasi (oʻzimizning xodimlar)
    SERVICE_PROVIDER = "service_provider" # Aloqa operatorlari, tizim botlari
    DUMMY_RECORD = "dummy_record"        # Qoʻngʻiroq logi, "Не дозвонился"
    CLIENT = "client"                    # Haqiqiy mijoz (buying intent bilan)


# 1. Jon Branding ichki jamoa aʼzolari va kalit soʻzlari (Team Members)
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
    re.compile(r"\bвчера\s+(?:вы|мы|говорили)\b", re.I),
]


def resolve_entity_role(
    name: Optional[str] = None,
    phone: Optional[str] = None,
    username: Optional[str] = None,
    notes: Optional[str] = None,
) -> Tuple[EntityRole, str]:
    """
    Kontaktning kimligini (rolini) aniqlash.
    
    Qaytaradi:
        (EntityRole.TEAM_MEMBER, sabab) — agar Jon Branding xodimi boʻlsa.
        (EntityRole.SERVICE_PROVIDER, sabab) — aloqa operatori yoki provayder boʻlsa.
        (EntityRole.DUMMY_RECORD, sabab) — avtomatlashtirilgan log yozuvi boʻlsa.
        (EntityRole.CLIENT, "mijoz") — haqiqiy mijoz boʻlsa.
    """
    name_clean = (name or "").strip().lower()
    username_clean = (username or "").strip().lower().lstrip("@")

    # A) Ichki jamoa tekshiruvi (Team Member)
    for kw in INTERNAL_TEAM_KEYWORDS:
        if kw in name_clean or kw in username_clean:
            return EntityRole.TEAM_MEMBER, f"jamoa_azosi:{kw}"

    # B) Servis provayderlar va botlar (Service Provider)
    for kw in SERVICE_PROVIDER_KEYWORDS:
        if kw in name_clean or kw in username_clean:
            if kw in ("menejer", "menejeri", "manager") and (
                "menejer" in name_clean or "menejeri" in name_clean or "manager" in name_clean
            ):
                return EntityRole.SERVICE_PROVIDER, "service_provider:menejer_title"
            if kw not in ("menejer", "menejeri", "manager"):
                return EntityRole.SERVICE_PROVIDER, f"service_provider:{kw}"

    # C) Yaroqsiz / log sdelkalar (Dummy Record)
    for pat in DUMMY_LEAD_PATTERNS:
        if pat.search(name_clean):
            return EntityRole.DUMMY_RECORD, f"dummy_deal_marker:{pat.pattern}"

    return EntityRole.CLIENT, "mijoz"


def is_team_member(
    name: Optional[str] = None,
    phone: Optional[str] = None,
    username: Optional[str] = None,
) -> bool:
    """Kontakt Jon Branding jamoa aʼzosi (Team Member) ekanini tekshirish."""
    role, _ = resolve_entity_role(name=name, phone=phone, username=username)
    return role == EntityRole.TEAM_MEMBER


def is_excluded_contact(
    name: Optional[str] = None,
    phone: Optional[str] = None,
    username: Optional[str] = None,
    notes: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Mijozlar voronkasiga aralashmasligi kerak boʻlgan shaxslarni tekshirish.
    Jamoa aʼzolari va provayderlarni sotuv roʻyxatiga tiqmaslik uchun xizmat qiladi.
    """
    role, detail = resolve_entity_role(name=name, phone=phone, username=username, notes=notes)
    if role != EntityRole.CLIENT:
        return True, f"{role.value}:{detail}"
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
    evidence_text = re.sub(r"['\u2018\u2019\u02bb\u02bc`]", "ʻ", (evidence or "").strip().lower())

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
