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


def _secret_text(value) -> str:
    """Return a Pydantic secret or plain setting without leaking it."""
    getter = getattr(value, "get_secret_value", None)
    return str(getter() if callable(getter) else value or "")

DEFAULT_TRIGGER_KEYWORDS = {
    "nom", "ном", "brand", "brend", "бренд", "logo", "лого",
    "branding", "бrenдинг", "брендинг", "rebrending", "ребрендинг",
    "narx", "нарх", "narxi", "нархи", "keys", "кейс", "кейслар",
    "dizayn", "дизайн", "start", "старт", "loyiha", "лойиха",
    "konsultatsiya", "консультация", "xizmat", "хизмат",
    "hamkorlik", "хамкорлик", "qancha", "канча", "food", "fastfood"
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


_DISQUALIFIED_REACTIONS = {
    "zo'r", "zor", "gap yo'q", "gap yoq", "raxmat", "rahmat", "super",
    "klass", "alo", "a'lo", "omad", "molodets", "malades", "tasanno",
    "ofarin", "salom", "assalomu alaykum", "va alaykum assalom"
}

_CYRILLIC_MAP = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "x", "ц": "s", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "",
    "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "ў": "o", "қ": "q", "ғ": "g", "ҳ": "h",
})


def _to_latin(text: str) -> str:
    for ch in ("ʻ", "ʼ", "‘", "’", "`"):
        text = text.replace(ch, "'")
    return text.translate(_CYRILLIC_MAP)


QUESTION_MARKERS = {
    "qanday", "qanaqa", "qanaqasiga", "qachon", "necha", "nechta",
    "bormi", "bo'ladimi", "boladimi", "mumkinmi", "kerakmi", "qilasizmi",
    "qilasizlarmi", "beresizmi", "ishlaysizmi", "kim", "qayer", "qayerda",
    "nima", "nimaga", "chi", "narxi", "qancha"
}


def should_trigger_dm(comment_text: str, caption: str = "") -> Tuple[bool, str]:
    """
    Checks if a comment contains trigger keywords, question markers, or represents
    a meaningful communicative lead message rather than pure praise/emoji.
    """
    if not comment_text:
        return False, ""
    
    clean_text = _to_latin(comment_text.lower().strip())
    word_tokens = re.findall(r"[\w']+", clean_text)
    words = set(word_tokens)
    
    if not word_tokens:
        return False, ""
        
    if len(word_tokens) == 1 and (clean_text in _DISQUALIFIED_REACTIONS or word_tokens[0] in _DISQUALIFIED_REACTIONS):
        return False, ""
        
    caption_kws = extract_caption_keywords(caption)
    for kw in caption_kws:
        kw_lat = _to_latin(kw)
        if kw_lat in clean_text or kw_lat in words:
            return True, kw

    for kw in DEFAULT_TRIGGER_KEYWORDS:
        kw_lat = _to_latin(kw)
        if kw_lat in words or kw_lat in clean_text:
            return True, kw

    for qm in QUESTION_MARKERS:
        if qm in words or qm in clean_text:
            return True, qm

    if len(word_tokens) >= 2 and clean_text not in _DISQUALIFIED_REACTIONS:
        return True, word_tokens[0]

    return False, ""


def generate_initial_dm_message(commenter_name: str, keyword: str = "", caption: str = "") -> str:
    """Generates the warm, initial qualifying DM outreach message."""
    name_greeting = f", {commenter_name}" if commenter_name and commenter_name != "Foydalanuvchi" else ""
    
    kw_lower = keyword.lower()
    if kw_lower in {"nom", "naming"}:
        topic = "nomlash (naming) va brending"
    elif kw_lower in {"logo", "dizayn"}:
        topic = "logo va vizual identifikatsiya"
    elif kw_lower in {"rebrending"}:
        topic = "rebrending loyihangiz"
    else:
        topic = "brending va loyihangiz"

    return (
        f"Assalomu alaykum{name_greeting}! Baxtiyor Gaziyevning "
        f"menejerlari Oishaman 😊\n\n"
        f"Izohingizni ko'rib, sizga yordam berish uchun yozdim. Sizga aynan qaysi yo'nalishda {topic} "
        f"bo'yicha yechim kerak edi? Biznesingiz qanday sohada?"
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
    if not phone.strip():
        logger.info("[AMOCRM] Qualified Instagram lead has no phone yet; sync deferred")
        return None
    try:
        from src.services.core.crm.amocrm.sync import AmoCRMSync

        amocrm = AmoCRMSync(
            subdomain=settings.AMOCRM_SUBDOMAIN,
            client_id=_secret_text(settings.AMOCRM_CLIENT_ID),
            client_secret=_secret_text(settings.AMOCRM_CLIENT_SECRET),
            redirect_url=settings.AMOCRM_REDIRECT_URL,
        )
        contact_name = name or "Instagram Mijoz"
        contact_id = amocrm.create_contact(
            name=contact_name,
            phone=phone,
        )
        if contact_id:
            deal_title = lead_name or f"Instagram: {contact_name}"
            lead_id = amocrm.create_lead_for_contact(
                contact_id=contact_id,
                lead_name=deal_title,
            )
            if lead_id and details:
                amocrm.add_lead_note(lead_id, f"📥 Instagram Lead Tafsilotlari:\n{details}")
            logger.info(
                "[AMOCRM] Lead synced successfully from Instagram",
                lead_id=lead_id,
                contact_id=contact_id,
            )
            return lead_id
    except Exception as exc:
        logger.warning("[AMOCRM] sync_lead_to_amocrm error: %s", exc)
    return None
