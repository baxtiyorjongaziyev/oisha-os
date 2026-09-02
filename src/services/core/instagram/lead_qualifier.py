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
    "xizmat", "hamkorlik", "narxi", "qancha"
}

QUALIFICATION_SYSTEM_PROMPT = (
    "Sen Oisha — Jon Branding agentligi va art-direktor Baxtiyorjon Gaziyevning "
    "bosh AI konsultanisan. Shaxsiy brend va agentlik nomidan Direct (DM)da muloqot qilasan.\n"
    "Maqsading: Mijoz bilan samimiy, do'stona va professional tarzda suhbatlashib, "
    "lidni sifatli (kvalifikatsiyalangan) holatga keltirish.\n\n"
    "Bosqichlar (Ketma-ket 1 tadan savol ber):\n"
    "1. SOHA & LOYIHA: Biznes qaysi sohada va qanday loyiha rejalashtirilgan?\n"
    "2. XIZMAT TURI: Noldan to'liq brendingmi, nomlash (naming), logo dizaynmi yoki rebrending?\n"
    "3. BOSQICH & ALOQA: Yangi boshlanyaptimi yoki faoliyatdagi biznesmi? "
    "Mutaxassisimiz bog'lanishi uchun telefon raqamingizni qoldiring.\n\n"
    "Qoidalar:\n"
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


def should_trigger_dm(comment_text: str, caption: str = "") -> Tuple[bool, str]:
    """
    Checks if a comment contains trigger keywords or matches the post's call-to-action.
    Returns (True, matched_keyword) or (False, '').
    """
    if not comment_text:
        return False, ""
    
    clean_text = comment_text.lower().strip()
    words = set(re.findall(r"[\wўқғҳ']+", clean_text))
    
    caption_kws = extract_caption_keywords(caption)
    for kw in caption_kws:
        if kw in clean_text or kw in words:
            return True, kw

    for kw in DEFAULT_TRIGGER_KEYWORDS:
        if kw in words or kw in clean_text:
            return True, kw
            
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
        f"Assalomu alaykum{name_greeting}! Jon Branding art-direktori Baxtiyorjon Gaziyev "
        f"jamoasidan Oishaman 😊\n\n"
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

