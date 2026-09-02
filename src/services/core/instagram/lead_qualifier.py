"""
Instagram Lead Qualification and Trigger Service.
Handles keyword triggers, caption-keyword extraction, unique name generation,
and 3-step DM qualification funnel.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple
import structlog

from src.settings import settings

logger = structlog.get_logger("InstagramLeadQualifier")

DEFAULT_TRIGGER_KEYWORDS = {
    "nom", "brand", "brend", "logo", "branding", "rebrending",
    "narx", "keys", "dizayn", "start", "loyiha", "konsultatsiya",
    "xizmat", "hamkorlik", "narxi", "qancha", "naming", "nomlash",
    "identika", "buklet", "upakovka", "packaging", "kontent",
}

# Uzbek Cyrillic -> Latin so a comment like "Ном" matches the "nom" keyword.
_CYRILLIC_MAP = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "x", "ц": "s", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "",
    "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "ў": "o", "қ": "q", "ғ": "g", "ҳ": "h",
})


def _to_latin(text: str) -> str:
    # Fold the various apostrophe glyphs (ʻ ʼ ‘ ’ `) to a plain one first.
    for ch in ("ʻ", "ʼ", "‘", "’", "`"):
        text = text.replace(ch, "'")
    return text.translate(_CYRILLIC_MAP)


# A comment that asks a question is also a lead: reach out in the DM.
QUESTION_MARKERS = {
    "qanday", "qanaqa", "qanaqasiga", "qachon", "necha", "nechta",
    "bormi", "boʻladimi", "bo'ladimi", "boladimi", "mumkinmi",
    "kerakmi", "qilasizmi", "qilasizlarmi", "beresizmi", "ishlaysizmi",
    "kim", "qayer", "qayerda", "nima", "nimaga", "chi",
}

QUALIFICATION_SYSTEM_PROMPT = (
    "Sen Oisha — Baxtiyor Gaziyevning menejerisan. Baxtiyor Gaziyevning "
    "shaxsiy brendi va jamoasi nomidan Direct (DM)da muloqot qilasan.\n"
    "MUHIM QOIDA: Shaxsiy DMda 'Jon Branding' nomini MUTLAQO ISHLATMA! O'zingni doimo "
    "'Baxtiyor Gaziyevning menejerlari Oishaman' deb tanishtirasan.\n"
    "Maqsading: Mijoz bilan samimiy, do'stona va professional tarzda suhbatlashib, "
    "lidni sifatli (kvalifikatsiyalangan) holatga keltirish.\n\n"
    "Bosqichlar (Ketma-ket 1 tadan savol ber):\n"
    "1. SOHA & LOYIHA: Biznes qaysi sohada va qanday loyiha rejalashtirilgan?\n"
    "2. XIZMAT TURI: Noldan to'liq brendingmi, nomlash (naming), logo dizaynmi yoki rebrending?\n"
    "3. BOSQICH & ALOQA: Yangi boshlanyaptimi yoki faoliyatdagi biznesmi? "
    "Baxtiyor Gaziyev yoki jamoamiz siz bilan bog'lanishi uchun telefon raqamingizni qoldiring.\n\n"
    "Qoidalar:\n"
    "- 'Jon Branding' deb yozma, faqat 'Baxtiyor Gaziyev' yoki 'Baxtiyor Gaziyev jamoasi' deb gapir.\n"
    "- HECH QACHON bir xil nomlarni hammaga takrorlama! Agar nom so'ralsa, loyihaga mos "
    "kamida 2-3 ta mutlaqo yangi, jarangdor va zamonaviy nom variantlarini ber.\n"
    "- O'zbek tilida, iliq, samimiy va ishonchli ohangda yoz.\n"
    "- Xabarlar qisqa (2-4 gap) bo'lsin, bir vaqtning o'zida savollarga ko'mib tashlama.\n"
    "- Agar mijoz telefon raqamini bersa yoki aniq niyat bildirsa, javobing oxiriga "
    "[LEAD_REPORT: QUALITY=sifatli] tegini qo'sh."
)


def extract_caption_keywords(caption: str) -> List[str]:
    """Extracts trigger keywords requested in the post caption."""
    if not caption:
        return []
    keywords = set()
    patterns = [
        r"(?:izoh|komment|comment)(?:da|larda|ga)?\s+['\"«]?([a-zA-Zа-яА-ЯёЁўқғҳЎҚҒҲ0-9_\-]+)['\"»]?\s+(?:deb|deb\s+yozing|qoldiring|yozing)",
        r"(?:yozing|qoldiring)\s*:\s*['\"«]?([a-zA-Zа-яА-ЯёЁўқғҳЎҚҒҲ0-9_\-]+)['\"»]?",
        r"['\"«]([a-zA-Zа-яА-ЯёЁўқғҳЎҚҒҲ0-9_\-]{2,20})['\"»]\s+(?:deb\s+yozing|deb\s+qoldiring)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, caption, flags=re.IGNORECASE):
            word = match.group(1).strip().lower()
            if len(word) >= 2:
                keywords.add(word)
    return list(keywords)


# Reactions that are not a lead: emoji-only, a bare "+", a lone praise word.
_NON_LEAD_WORDS = {
    "zor", "zo'r", "ajoyib", "top", "super", "klass", "class", "love",
    "cool", "nice", "wow", "voy", "mashaa", "mashaallah", "mashallah",
    "omad", "barakalla", "yaxshi",
}


def _has_meaningful_text(comment_text: str) -> bool:
    """True unless the comment is only emoji / punctuation / a lone praise word."""
    letters = re.findall(r"[^\W\d_]", comment_text, flags=re.UNICODE)
    if len(letters) < 2:
        return False  # emoji, "+", "!!!", single letter
    words = set(re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)*", _to_latin(comment_text.lower())))
    words = {w for w in words if len(w) >= 2}
    if not words:
        return False
    # Only a short burst of praise words, nothing else -> not a lead.
    if words <= _NON_LEAD_WORDS and len(words) <= 2:
        return False
    return True


def should_trigger_dm(comment_text: str, caption: str = "") -> Tuple[bool, str]:
    """
    Decide whether a commenter should get an outreach DM.

    Policy: DM everyone who wrote a real message. Only pure emoji / punctuation /
    a lone praise word is skipped. Keyword and question matches still report the
    specific keyword so the opening DM can be tailored.
    Returns (True, matched_keyword) or (False, '').
    """
    if not comment_text:
        return False, ""

    clean_text = _to_latin(comment_text.lower().strip())
    words = set(re.findall(r"[\wўқғҳ']+", clean_text))

    caption_kws = extract_caption_keywords(caption)
    for kw in caption_kws:
        if kw in clean_text or kw in words:
            return True, kw

    for kw in DEFAULT_TRIGGER_KEYWORDS:
        if kw in words or kw in clean_text:
            return True, kw

    if "?" in comment_text or (words & QUESTION_MARKERS):
        return True, "savol"

    # No specific keyword, but a real message -> still reach out.
    if _has_meaningful_text(comment_text):
        return True, "aloqa"

    return False, ""


def generate_initial_dm_message(commenter_name: str, keyword: str = "", caption: str = "") -> str:
    """Generates the warm, initial qualifying DM outreach message."""
    name_greeting = f", {commenter_name}" if commenter_name and commenter_name != "Foydalanuvchi" else ""
    
    kw_lower = keyword.lower()
    if kw_lower in {"nom", "naming", "nomlash"}:
        topic = "nomlash (naming) va brending"
    elif kw_lower in {"logo", "dizayn", "identika"}:
        topic = "logo va vizual identifikatsiya"
    elif kw_lower in {"rebrending"}:
        topic = "rebrending loyihangiz"
    elif kw_lower in {"narx", "narxi", "qancha"}:
        topic = "xizmat narxlari va loyihangiz"
    elif kw_lower == "savol":
        topic = "savolingiz va loyihangiz"
    elif kw_lower == "aloqa":
        topic = "brending yoki dizayn"
    else:
        topic = "brending va loyihangiz"

    return (
        f"Assalomu alaykum{name_greeting}! Baxtiyor Gaziyevning "
        f"menejerlari Oishaman 😊\n\n"
        f"Izohingizni ko'rib, siz bilan bevosita bog'lanmoqchi bo'ldim. "
        f"Sizga aynan qaysi yo'nalishda {topic} bo'yicha yechim kerak edi? "
        f"Biznesingiz qanday sohada?"
    )


async def generate_qualifying_dm_response(
    user_message: str,
    history: Optional[List[Dict[str, str]]] = None,
    commenter_name: str = "",
) -> str:
    """Generates the next step in the qualification funnel using Free AI Router."""
    history = history or []
    history_lines = []
    for h in history[-6:]:
        role = "Mijoz" if h.get("role") == "user" else "Oisha"
        history_lines.append(f"{role}: {h.get('content', '')}")
    
    history_block = "\n".join(history_lines)
    prompt = (
        f"Muloqot tarixi:\n{history_block}\n\n"
        f"Mijoz ({commenter_name}): {user_message}\n\n"
        f"Oisha javobi:"
    )

    try:
        from src.services.utils.free_ai_router import get_free_ai_router
        result = await get_free_ai_router().generate_text(
            prompt,
            system=QUALIFICATION_SYSTEM_PROMPT,
            max_tokens=250,
            temperature=0.7,
        )
        text = (result.text or "").strip()
        if text:
            return text
    except Exception as exc:
        logger.warning("[QUALIFIER] generate_qualifying_dm_response fallback: %s", exc)
        
    return (
        "Qiziqishingiz uchun rahmat! Biznesingiz haqida qisqacha ma'lumot bersangiz, "
        "sizga eng mos taklif va namunalarni taqdim etamiz 😊"
    )


def sync_lead_to_amocrm(
    name: str,
    phone: str = "",
    lead_name: str = "",
    details: str = "",
    source: str = "Instagram",
) -> Optional[int]:
    """Creates or updates a contact and deal in AmoCRM for qualified Instagram leads."""
    try:
        from src.services.core.crm.amocrm.sync import AmoCRMSync

        amocrm = AmoCRMSync(
            subdomain=settings.AMOCRM_SUBDOMAIN,
            client_id=settings.AMOCRM_CLIENT_ID.get_secret_value() if settings.AMOCRM_CLIENT_ID else "",
            client_secret=settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.AMOCRM_CLIENT_SECRET else "",
            redirect_uri=settings.AMOCRM_REDIRECT_URI,
            refresh_token=settings.AMOCRM_REFRESH_TOKEN.get_secret_value() if settings.AMOCRM_REFRESH_TOKEN else "",
        )
        contact_name = name or "Instagram Mijoz"
        contact_id = amocrm.create_contact(
            name=contact_name,
            phone=phone,
            custom_fields=None,
        )
        if contact_id:
            deal_title = lead_name or f"Instagram: {contact_name}"
            lead_id = amocrm.create_lead_for_contact(
                contact_id=contact_id,
                lead_name=deal_title,
            )
            if lead_id and details:
                amocrm.add_note_to_lead(
                    lead_id=lead_id,
                    text=f"📥 Instagram Lead Tafsilotlari:\n{details}",
                )
            logger.info(
                "[AMOCRM] Lead synced successfully from Instagram",
                lead_id=lead_id,
                contact_id=contact_id,
            )
            return lead_id
    except Exception as exc:
        logger.warning("[AMOCRM] sync_lead_to_amocrm error: %s", exc)
    return None

