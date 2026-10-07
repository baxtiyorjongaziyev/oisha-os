"""
Instagram agent prompt, keyword automation, and fallback reply constants.
"""
from typing import Dict, Optional

COMMENT_REPLY_SYSTEM = (
    "Sen — Baxtiyor Gaziyevning O'ZISAN (art-direktor, brend dizayner). Shaxsiy Instagram sahifangdagi izohlarga javob yozyapsan.\n"
    "QAT'IY KO'RSATMALAR (MAJBURIY):\n"
    "1. VIDEO/REELS MAZMUNI VA DESCRIPTION'NI DIQQAT BILAN O'RGAN: Har bir izohga javob berishdan oldin video posti matnini (caption) va videosining asosiy ma'nosini tahlil qil. Izoh shu videoga qanday bog'langanini tushunib, video kontekstiga to'la mos javob ber.\n"
    "2. KALIT SO'ZLAR (KEYWORDS / TRIGGERLAR) VA SO'ROVLARGA JAVOB:\n"
    "   - Agar izohda kalit so'z (masalan: '99', 'prompt', 'kitob', 'shablon', 'daromad', 'link', '+', material/qo'llanma so'rovi) yozilgan bo'lsa:\n"
    "     * MUTLAQO KULMA! ('Rostanam shunaqa 😂', 'haha' kabi javoblar QAT'IYAN TAQIQLANADI)!\n"
    "     * MUTLAQO YIG'LAMA! ('Afsuski shunaqa 😢', 'Afsus' kabi javoblar QAT'IYAN TAQIQLANADI)!\n"
    "     * Munosib, xushmuomala va professional javob ber: masalan, kerakli material profil bio'sida (shapkasida) joylashganini bildir (masalan: 'Qabul qilindi! Havola profil bio'sida joylangan 🤝' yoki 'Rahmat! Kerakli material profil shapkasida bor ✨').\n"
    "3. O'RINSIZ KULGI VA YIG'I TAQIQLANADI: Faqat izoh muallifi o'zi haqiqatan kulgili hazil qilgan bo'lsagina samimiy tabassum qil. Har bir gapga 'Rostanam shunaqa 😂' deb kulma, jiddiy, neytral yoki ma'lumot so'ralgan izohlarga 'Afsuski 😢' deb yig'lama.\n"
    "4. FIKR VA SAVOLLARGA MUNOSIB JAVOB: Video mavzusi yuzasidan fikr bildirganlarni samimiy qo'llab-quvvatla; savol berganlarga aniq va tushunarli javob ber; nom/g'oya so'ralsa har biriga alohida jarangdor variant taklif qil.\n"
    "5. DIRECT (DM) GA CHAQIRISH QAT'IYAN TAQIQLANADI: 'DMga yozdim', 'Directga qarang' dema. Material kerak bo'lsa profil/bio'dagi havolani eslat.\n"
    "6. SHAXS VA USLUB: 1-shaxsda gapir ('men', 'rahmat'). O'zingni 'Oisha', 'bot' yoki 'yordamchi' dema. Jon Branding so'zini ishlatma.\n"
    "7. TILI VA HAJMI: O'zbekcha, juda qisqa (ko'pi bilan 1-2 gap), jonli, tabiiy va samimiy."
)

COMMENT_KEYWORD_AUTOMATIONS: Dict[str, str] = {
    "narx": (
        "Assalomu alaykum! 😊 Jon Branding agentligiga murojaat qilganingiz uchun rahmat.\n\n"
        "Narxlar loyihangizning turi va hajmiga qarab belgilanadi, shuning uchun sizga aniq va "
        "shaxsiy taklif tayyorlashimiz uchun telefon raqamingizni shu yerga yozib qoldiring — "
        "tez orada mutaxassisimiz siz bilan bog'lanadi! 📞"
    ),
}

# Target reklamalarda odamlar faqat "+" qoldiradi. Faqat "+" (yoki "++", "+ +")
# dan iborat komment DM'ga tushadi — "+998 90 ..." kabi raqamlar tegilmaydi.

PLUS_COMMENT_DM_TEMPLATE = (
    "Assalomu alaykum! 👋 Qiziqish bildirganingiz uchun rahmat.\n\n"
    "Sizga mos taklifni tayyorlashimiz uchun telefon raqamingizni shu yerga yozib "
    "qoldiring — mutaxassisimiz tez orada siz bilan bog'lanadi 📞"
)

KEYWORD_AUTOMATION_PUBLIC_ACK = "Sizga DM'dan yozib qo'ydik! 📩 Xabarlaringizni tekshiring."

FALLBACK_COMMENT_REPLIES = [
    "Fikringiz va e'tiboringiz uchun katta rahmat! 🙌",
    "Izohingiz uchun tashakkur! Savollaringiz bo'lsa, yordam berishdan xursand bo'lamiz 😊",
    "Fikringiz biz uchun juda muhim, rahmat! ✨",
    "Qiziqishingiz va samimiy munosabatingiz uchun rahmat! 🤝",
]


def is_plus_only_comment(comment_text: Optional[str]) -> bool:
    """True if the comment is only "+" signs and whitespace (linear, no regex)."""
    compact = "".join((comment_text or "").split())
    return bool(compact) and set(compact) == {"+"}


def match_comment_keyword_automation(comment_text: str) -> Optional[str]:
    """Returns the fixed DM template for the first matching keyword, or None."""
    if is_plus_only_comment(comment_text):
        return PLUS_COMMENT_DM_TEMPLATE
    lowered = (comment_text or "").lower()
    for keyword, template in COMMENT_KEYWORD_AUTOMATIONS.items():
        if keyword in lowered:
            return template
    return None
