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
    "Sen — Baxtiyor Gaziyevning O'ZISAN. Branding bo'yicha ekspert va art-direktor, "
    "shaxsiy Instagram sahifangdan kelgan izohlarga javoban Direct (DM)da "
    "mijozlar bilan 1-shaxsda, o'z nomingdan muloqot qilasan.\n"
    "MUHIM QOIDA: O'zingni menejer yoki 'Oisha' deb tanishtirma. Doimo 'men', "
    "'o'zim' deb, Baxtiyor Gaziyev sifatida gapir. 'Jon Branding' nomini SHAXSIY "
    "DMda MUTLAQO ISHLATMA.\n"
    "Maqsading: Mijoz bilan samimiy, do'stona va professional tarzda suhbatlashib, "
    "lidni sifatli (kvalifikatsiyalangan) holatga keltirish.\n\n"
    "Bosqichlar (Ketma-ket 1 tadan savol ber):\n"
    "1. SOHA & LOYIHA: Biznes qaysi sohada va qanday loyiha rejalashtirilgan?\n"
    "2. XIZMAT TURI: Noldan to'liq brendingmi, nomlash (naming), logo dizaynmi yoki rebrending?\n"
    "3. BOSQICH & ALOQA: Yangi boshlanyaptimi yoki faoliyatdagi biznesmi? "
    "Bog'lanishim uchun telefon raqamingizni qoldiring.\n\n"
    "Qoidalar:\n"
    "- 'Jon Branding' deb yozma. O'zingni 'Baxtiyor Gaziyev' deb, 1-shaxsda gapir.\n"
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
            return True, kw_lat

    for kw in DEFAULT_TRIGGER_KEYWORDS:
        kw_lat = _to_latin(kw)
        if kw_lat in words or kw_lat in clean_text:
            return True, kw_lat

    for qm in QUESTION_MARKERS:
        qm_lat = _to_latin(qm)
        if qm_lat in words or qm_lat in clean_text:
            return True, "savol"

    if len(word_tokens) >= 2 and clean_text not in _DISQUALIFIED_REACTIONS:
        return True, "aloqa"

    return False, ""


def generate_initial_dm_message(commenter_name: str, keyword: str = "", caption: str = "") -> str:
    """Static fallback opener (used when the AI router is unavailable)."""
    name_greeting = f" {commenter_name}" if commenter_name and commenter_name != "Foydalanuvchi" else ""
    kw_lower = keyword.lower()
    if kw_lower in {"nom", "naming", "nomlash"}:
        topic = "nomlash bo'yicha"
    elif kw_lower in {"logo", "dizayn", "identika"}:
        topic = "logo yoki vizual uslub bo'yicha"
    elif kw_lower in {"rebrending"}:
        topic = "rebrending bo'yicha"
    elif kw_lower in {"narx", "narxi", "qancha"}:
        topic = "narxlar bo'yicha"
    else:
        topic = "brending bo'yicha"
    return (
        f"Salom{name_greeting}! Bu Baxtiyor 🙂 Izohingizni ko'rib qoldim, "
        f"o'zim yozay dedim. {topic} nima rejalashtiryapsiz, qaysi sohada ish qilasiz?"
    )


_DM_OPENER_SYSTEM = (
    "Sen — Baxtiyor Gaziyevning O'ZISAN. Branding eksperti va art-direktor. "
    "Instagram sahifangga izoh yozgan odamga Direct (DM)da BIRINCHI xabarni "
    "yozyapsan.\n"
    "Yozish uslubi:\n"
    "- TIRIK ODAM kabi yoz. Robot, shablon, rasmiy 'murojaat' ohangi TAQIQLANADI.\n"
    "- Do'stona, iliq, tabiiy. Xuddi tanish odamга yozayotgandek.\n"
    "- 1-shaxs: 'men', 'o'zim yozdim'. O'zingni 'menejer' yoki 'Oisha' dema.\n"
    "- Qisqa: 1-2 gap, 25 so'zdan kam. Salomlashув + izohига ishora + bittа "
    "ochiq savol (qaysi soha / qanday loyiha).\n"
    "- Emoji 0-1 ta, tabiiy joyда.\n"
    "- 'Jon Branding' so'zini ishlatма.\n"
    "- Har odamга boshqаcha yoz, shablon takrorlama."
)


async def generate_initial_dm_message_ai(
    commenter_name: str, comment_text: str, keyword: str = "", caption: str = ""
) -> str:
    """Human-sounding first DM, tailored to what the person actually commented."""
    name = commenter_name if commenter_name and commenter_name != "Foydalanuvchi" else ""
    cap = f'\nPost mavzusi: "{caption[:200]}"' if caption else ""
    prompt = (
        f"{cap}\n"
        f'{name or "Bir odam"} sahifangга shu izohni yozdi: "{comment_text}"\n\n'
        f"Shu odamга Direct'да yozadigan birinchi, samimiy xabaringni yoz:"
    )
    try:
        from src.services.utils.free_ai_router import get_free_ai_router
        result = await get_free_ai_router().generate_text(
            prompt, system=_DM_OPENER_SYSTEM, max_tokens=120, temperature=0.85
        )
        text = (result.text or "").strip().strip('"')
        if text:
            return text
    except Exception as exc:  # noqa: BLE001
        logger.warning("[META] DM opener AI fallback: %s", exc)
    return generate_initial_dm_message(commenter_name, keyword, caption)


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
