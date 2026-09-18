"""Meta Lead Ads presentation, localization, and formatting helpers."""
from __future__ import annotations

import html
import re
from typing import Any, Dict, Optional

QUESTION_LABELS: Dict[str, tuple[str, str]] = {
    # Brand / Business name
    "brendingiz_yoki_bisnesingiz_nomi_nima": ("🏷", "Brend / Biznes nomi"),
    "brend_nomi": ("🏷", "Brend nomi"),
    "biznes_nomi": ("🏢", "Biznes nomi"),
    "kompaniya_nomi": ("🏢", "Kompaniya nomi"),
    # Goals / Objectives
    "brendni_patentlashdan_asosiy_maqsadingiz_nima": ("🎯", "Asosiy maqsad"),
    "patentlashdan_asosiy_maqsad": ("🎯", "Asosiy maqsad"),
    "patentlashdan_maqsad": ("🎯", "Asosiy maqsad"),
    "asosiy_maqsad": ("🎯", "Asosiy maqsad"),
    "maqsad": ("🎯", "Asosiy maqsad"),
    # Field / Industry
    "siz_qaysi_sohada_faoliyat_yuritasiz": ("💼", "Faoliyat sohasi"),
    "faoliyat_sohasi": ("💼", "Faoliyat sohasi"),
    "soha": ("💼", "Faoliyat sohasi"),
    "biznesingiz_faoliyat_turi": ("💼", "Biznes faoliyat turi"),
    "faoliyat_turi": ("💼", "Faoliyat turi"),
    # Business stage
    "tadbirkorlik_holatingiz_qanday": ("📊", "Tadbirkorlik holati"),
    "tadbirkorlik_holati": ("📊", "Tadbirkorlik holati"),
    "biznes_holati": ("📊", "Tadbirkorlik holati"),
    "biznes_bosqichi": ("📊", "Biznes bosqichi"),
    # Service / Offer
    "qaysi_xizmat_kerak": ("🛠", "Kerakli xizmat"),
    "xizmat_turi": ("🛠", "Kerakli xizmat"),
    "service": ("🛠", "Kerakli xizmat"),
    "services": ("🛠", "Kerakli xizmatlar"),
    "logotip_kerakmi": ("🎨", "Logotip kerakmi"),
    "sayt_kerakmi": ("🌐", "Veb-sayt kerakmi"),
    "reklama_kerakmi": ("🎯", "Target reklama"),
    "are_you_interested_in_our_products_or_services": ("❓", "Xizmatlarga qiziqish"),
    # Budget / Pricing
    "byudjet": ("💰", "Byudjet"),
    "budjet": ("💰", "Byudjet"),
    "budget": ("💰", "Byudjet"),
    "loyiha_budjeti": ("💰", "Loyiha byudjeti"),
    "narx": ("💰", "Narx toifasi"),
    # Location
    "shahar": ("📍", "Shahar"),
    "hudud": ("📍", "Hudud"),
    "viloyat": ("📍", "Viloyat"),
    "what_town_city_do_you_live_in": ("📍", "Yashash shahri"),
    "town_city": ("📍", "Shahar"),
    # Timeline
    "qachon_boshlaymiz": ("⏱", "Boshlash muddati"),
    "boshlash_vaqti": ("⏱", "Boshlash muddati"),
    "muddat": ("⏱", "Muddati"),
    # Contacts & Notes
    "izoh": ("💬", "Qoʻshimcha izoh"),
    "fikringiz": ("💬", "Fikringiz"),
    "qoshimcha_malumot": ("💬", "Qoʻshimcha maʼlumot"),
    "phone": ("📞", "Telefon"),
    "phone_number": ("📞", "Telefon"),
    "what_is_your_phone_number": ("📞", "Telefon"),
    "full_name": ("👤", "Mijoz ismi"),
    "name": ("👤", "Mijoz ismi"),
    "email": ("✉️", "Email"),
}

VALUE_TRANSLATIONS: Dict[str, str] = {
    # Patenting & Protection
    "brendimni_boshqalardan_himoya_qilish": "Brendimni boshqalardan himoya qilish",
    "brend_nomini_qonuniy_himoyalash": "Brend nomini qonuniy himoyalash",
    "biznesni_kengaytirish": "Biznesni kengaytirish",
    "hozircha_ma'lumot_olyapman": "Hozircha maʼlumot olyapman",
    "hozircha_malumot_olyapman": "Hozircha maʼlumot olyapman",
    # Entrepreneurial state
    "yangi_biznes_boshlayapman": "Yangi biznes boshlayapman",
    "brendim_allaqachon_majvud": "Brendim allaqachon mavjud",
    "brendim_allaqachon_mavjud": "Brendim allaqachon mavjud",
    "mahsulotim_bor,_lekin_brendni_himoyalamaganman": "Mahsulotim bor, lekin brendni himoyalamaganman",
    "brendimni_rivojlantirmoqchiman": "Brendimni rivojlantirmoqchiman",
    # Industry
    "ishlab_chiqarish": "Ishlab chiqarish",
    "xizmat_korsatish": "Xizmat koʻrsatish",
    "xizmat_ko'rsatish": "Xizmat koʻrsatish",
    "savdo": "Savdo",
    "talim": "Taʼlim",
    "ta'lim": "Taʼlim",
    "boshqa": "Boshqa",
    # Yes / No options
    "yes": "Ha",
    "ha": "Ha",
    "no": "Yoʻq",
    "yoq": "Yoʻq",
    "not_now": "Hozir emas",
    "not now": "Hozir emas",
}


def clean_form_key(value: str) -> str:
    """Normalize raw form question or field key."""
    return re.sub(r"[^a-z0-9_]+", "_", value.strip().lower()).strip("_")


def humanize_question(key: str) -> tuple[str, str]:
    """Return (emoji, human_label) for ANY form question key."""
    cleaned = clean_form_key(key)
    if cleaned in QUESTION_LABELS:
        return QUESTION_LABELS[cleaned]

    # Semantic keyword matches:
    if any(w in cleaned for w in ("brend", "biznes_nom", "nomi", "brand")):
        return ("🏷", "Brend / Biznes nomi")
    if any(w in cleaned for w in ("maqsad", "patent", "goal")):
        return ("🎯", "Asosiy maqsad")
    if any(w in cleaned for w in ("soha", "faoliyat", "industry", "sector")):
        return ("💼", "Faoliyat sohasi")
    if any(w in cleaned for w in ("holat", "tadbirkor", "status", "bosqich")):
        return ("📊", "Tadbirkorlik holati")
    if any(w in cleaned for w in ("xizmat", "service", "mahsulot", "product", "logo", "sayt")):
        return ("🛠", "Kerakli xizmat")
    if any(w in cleaned for w in ("budjet", "byudjet", "narx", "pul", "budget", "price")):
        return ("💰", "Byudjet")
    if any(w in cleaned for w in ("shahar", "town", "city", "manzil", "joylashuv", "viloyat", "region")):
        return ("📍", "Hudud / Yashash joyi")
    if any(w in cleaned for w in ("vaqt", "muddat", "qachon", "time", "date", "reja")):
        return ("⏱", "Boshlash muddati")
    if any(w in cleaned for w in ("qiziqish", "interest", "interested")):
        return ("❓", "Xizmatlarga qiziqish")
    if any(w in cleaned for w in ("izoh", "fikr", "comment", "note", "malumot", "message")):
        return ("💬", "Qoʻshimcha maʼlumot")

    # Generic clean title case formatting:
    clean_title = re.sub(r"_(nima|qanday|qaysi|yozing|kiriting|qiling|bormi)$", "", cleaned)
    words = clean_title.replace("_", " ").strip().split()
    label = " ".join(w.capitalize() for w in words) if words else "Savol"
    return ("•", label)


def humanize_answer(val: str) -> str:
    """Format and prettify ANY raw form answer value."""
    if not val:
        return ""
    cleaned_key = clean_form_key(val)
    if cleaned_key in VALUE_TRANSLATIONS:
        return VALUE_TRANSLATIONS[cleaned_key]

    text = val.replace("_", " ")

    # Fix common Uzbek typos and apostrophes:
    text = text.replace("majvud", "mavjud")
    text = re.sub(r"\bta['ʻʼ]lim\b", "Taʼlim", text, flags=re.IGNORECASE)
    text = re.sub(r"\bma['ʻʼ]lumot\b", "maʼlumot", text, flags=re.IGNORECASE)
    text = re.sub(r"\bko['ʻʼ]rsatish\b", "koʻrsatish", text, flags=re.IGNORECASE)

    # Clean punctuation and multiple whitespace:
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"\s*([.?!;:])\s*", r"\1 ", text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    if not text:
        return ""

    lower = text.lower()
    if lower == "yes":
        return "Ha"
    if lower == "no":
        return "Yoʻq"
    if lower in ("not now", "not_now"):
        return "Hozir emas"

    # Capitalize the first letter if lowercase, keeping brand capitalization:
    return text[0].upper() + text[1:]


def question_sort_key(item: tuple[str, str]) -> tuple[int, str]:
    """Sort questions in executive order: Brand -> Goal -> Sphere -> State -> Other."""
    key = clean_form_key(item[0])
    if any(w in key for w in ("brend", "biznes_nom", "nomi", "brand")):
        return (1, key)
    if any(w in key for w in ("maqsad", "patent", "goal")):
        return (2, key)
    if any(w in key for w in ("soha", "faoliyat", "industry", "sector")):
        return (3, key)
    if any(w in key for w in ("holat", "tadbirkor", "status", "bosqich")):
        return (4, key)
    if any(w in key for w in ("xizmat", "service", "mahsulot", "product", "logo", "sayt")):
        return (5, key)
    if any(w in key for w in ("budjet", "byudjet", "narx", "budget", "price")):
        return (6, key)
    if any(w in key for w in ("vaqt", "muddat", "qachon", "time", "date")):
        return (7, key)
    if any(w in key for w in ("shahar", "town", "city", "manzil", "joylashuv", "viloyat")):
        return (8, key)
    if any(w in key for w in ("qiziqish", "interest")):
        return (9, key)
    if any(w in key for w in ("izoh", "fikr", "comment", "note", "malumot")):
        return (10, key)
    return (20, key)


def build_leadgen_note(
    leadgen_id: str,
    payload: Dict[str, Any],
    fields: Dict[str, str],
    exclude_keys: Optional[set[str]] = None,
    ad_name: Optional[str] = None,
) -> str:
    """Build a detailed, human-readable AmoCRM lead note."""
    lines = [
        "Facebook Lead Ads orqali avtomatik tushdi.",
        f"Leadgen ID: {leadgen_id}",
    ]
    if ad_name:
        lines.append(f"Reklama/Aksiya: {ad_name}")
    for key in ("form_id", "ad_id", "adgroup_id", "campaign_id", "created_time"):
        if payload.get(key):
            lines.append(f"{key}: {payload[key]}")

    ignored = exclude_keys or set()
    extras = [(k, v) for k, v in fields.items() if k not in ignored]
    if not extras and fields:
        extras = list(fields.items())
    if extras:
        sorted_extras = sorted(extras, key=question_sort_key)
        lines.append("")
        lines.append("Forma savol-javoblari:")
        for k, v in sorted_extras:
            _, label = humanize_question(k)
            ans = humanize_answer(v)
            lines.append(f"• {label}: {ans}")
    return "\n".join(lines)


def build_telegram_message(
    leadgen_id: str,
    lead_id: Optional[int],
    name: str,
    phone: str,
    email: str,
    fields: Dict[str, str],
    exclude_keys: Optional[set[str]] = None,
    cost_per_lead: Optional[float] = None,
    ad_name: Optional[str] = None,
) -> str:
    """Format a clean, executive CRM group notification for a Facebook lead."""
    lead_link = (
        f'<a href="https://jonbranding.amocrm.ru/leads/detail/{lead_id}">#{lead_id}</a>'
        if lead_id
        else "yaratilmadi"
    )
    lines = [
        "🔥 <b>YANGI FACEBOOK LEAD ADS LEAD</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"👤 <b>Mijoz:</b> {html.escape(name or 'Nomaʼlum')}",
        f"📞 <b>Telefon:</b> {html.escape(phone or 'yoʼq')}",
    ]
    if email:
        lines.append(f"✉️ <b>Email:</b> {html.escape(email)}")
    lines.extend(
        [
            f"🧾 <b>AmoCRM:</b> {lead_link}",
            "🎯 <b>Voronka:</b> Target LEADs",
            f"🆔 <b>Meta lead:</b> <code>{html.escape(leadgen_id)}</code>",
        ]
    )
    if ad_name:
        lines.append(f"🎬 <b>Reklama/Aksiya:</b> {html.escape(ad_name)}")
    if cost_per_lead:
        formatted = f"{round(cost_per_lead):,}".replace(",", " ")
        lines.append(f"💵 <b>Taxminiy lid narxi:</b> ~{formatted} so'm (30 kunlik oʻrtacha)")

    ignored = exclude_keys or set()
    extras = [(k, v) for k, v in fields.items() if k not in ignored]
    if extras:
        sorted_extras = sorted(extras, key=question_sort_key)
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("📋 <b>Soʻrovnoma javoblari:</b>")
        for k, v in sorted_extras:
            emoji, label = humanize_question(k)
            ans = humanize_answer(v)
            lines.append(f"{emoji} <b>{html.escape(label)}:</b> {html.escape(ans)}")

    return "\n".join(lines)
