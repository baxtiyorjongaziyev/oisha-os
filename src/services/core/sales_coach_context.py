"""Jon Branding — SalesCoach markaziy kontekst."""
from __future__ import annotations

# --- Biznes profili ---
COMPANY_NAME = "Jon Branding Agency"
SERVICE_DIRECTIONS = [
    "naming", "logo", "brandbook", "packaging", "website",
    "social_media", "trademark_patent", "corporate_identity",
]

# --- Ideal Customer Profile ---
ICP_SEGMENTS = ["ishlab_chiqaruvchi", "retail", "KOB", "startup"]

# --- Rollar ---
SALES_ROLES = {
    "hunter": {
        "name": "Hunter",
        "goal": "Aloqa o'rnatish, ehtiyoj signalini aniqlash",
        "amo_stages": ["Yangi so'rov", "Birinchi kontakt qilindi", "Bog'lanib bo'lmadi", "Muloqot boshlandi"],
        "score_weights": {"opening": 30, "needs_discovery": 40, "objection_handling": 20, "closing": 10},
    },
    "setter": {
        "name": "Setter",
        "goal": "Uchrashuv/konsultatsiya kelishish",
        "amo_stages": ["Sifatli lead", "Uchrashuv belgilandi"],
        "score_weights": {"needs_discovery": 30, "presentation": 30, "closing": 40},
    },
    "expert": {
        "name": "Ekspert",
        "goal": "Brief, KP tayyorlash, prezentatsiya",
        "amo_stages": ["Konsultatsiya o'tdi", "Brief / Ehtiyoj aniqlandi", "Prezentatsiya & KP"],
        "score_weights": {"presentation": 40, "needs_discovery": 30, "closing": 30},
    },
    "closer": {
        "name": "Closer",
        "goal": "Muzokara, avans olish",
        "amo_stages": ["Follow-up / Qaror kutilyapti", "Muzokara / Shartnoma", "50% Avans olindi"],
        "score_weights": {"objection_handling": 40, "closing": 40, "presentation": 20},
    },
}

# --- Qualification maydonlari (5 ta) ---
QUALIFICATION_FIELDS = [
    {"key": "budget", "question": "Byudjet qancha?", "required": True},
    {"key": "timeline", "question": "Qachon kerak?", "required": True},
    {"key": "decision_maker", "question": "Kim qaror qabul qiladi?", "required": True},
    {"key": "current_pain", "question": "Asosiy muammo nima?", "required": True},
    {"key": "competitors", "question": "Raqobatchilar bilan ko'rib chiqyapsizmi?", "required": False},
]

# --- Asosiy e'tirozlar (4 ta) ---
MAIN_OBJECTIONS = [
    {
        "trigger": ["qimmat", "narx baland", "qo'lda yo'q", "budget yo'q"],
        "type": "price",
        "counter": "Natija va ROI ni ko'rsating. Muqobil to'lov rejasini taklif qiling.",
    },
    {
        "trigger": ["o'ylab ko'raman", "keyinroq", "shoshilmaymiz"],
        "type": "delay",
        "counter": "Muddatni aniqlang. Nimaga qaror qilish kerak — shuni hal qiling.",
    },
    {
        "trigger": ["boshqa joy", "raqobatchi", "boshqa kompaniya"],
        "type": "competitor",
        "counter": "Farqni aniq ko'rsating. Case study bering.",
    },
    {
        "trigger": ["ishonmayapman", "kafolat bormi", "natija bo'ladimi"],
        "type": "trust",
        "counter": "Portfolio, testimonial, case study bering.",
    },
]

# --- Qizil chiziqlar ---
RED_LINES = [
    "Chegirma so'rash (30%+ dan ko'p)",
    "Boshlang'ich to'lovsiz ishni boshlash",
    "Hujjatsiz (shartnoma/TZ yo'q) ishni boshlash",
    "Aniq TZ/brief yo'q holda dizayn ishlash",
    "Potentsial mijozni 2+ hafta javobi yo'q holda kuzatish",
]

# --- SalesCoach prompt template ---
SALES_COACH_SYSTEM_PROMPT = """
Sen {company} uchun professional SalesCoach AI-san.
Qo'ng'iroq yoki suhbat transkriptini tahlil qilib, quyidagi formatda JSON qaytarasan:

{{
    "sales_role": "hunter|setter|expert|closer",
    "service_direction": "{services}",
    "qualification_gaps": ["so'ralmagan maydon1", ...],
    "objections_detected": ["e'tiroz turi1", ...],
    "red_line_violations": ["qizil chiziq1", ...],
    "coaching_score": 0-100,
    "coaching_tips": ["maslahat1", "maslahat2", "maslahat3"]
}}

Faqat JSON qaytargin — boshqa matn yo'q.
""".format(
    company=COMPANY_NAME,
    services=", ".join(SERVICE_DIRECTIONS),
)


def get_role_for_stage(stage_name: str) -> str:
    """Amo bosqich nomiga qarab sotuvchi rolini aniqlash."""
    for role_key, role_data in SALES_ROLES.items():
        if stage_name in role_data["amo_stages"]:
            return role_key
    return "hunter"


def detect_objections(text: str) -> list[str]:
    """Matndagi e'tirozlarni aniqlash."""
    text_lower = text.lower()
    found = []
    for obj in MAIN_OBJECTIONS:
        if any(trigger in text_lower for trigger in obj["trigger"]):
            found.append(obj["type"])
    return found
