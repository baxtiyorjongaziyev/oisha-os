"""Jon Branding rasmiy sotuv playbook'i — baholashning yagona manbasi.

Mezonlar rahbariyat bilan kelishilgan (2026-07-21). Ikkala baholovchi ham
shu yerdan o'qiydi:
  - `services.core.call_analyzer` — AmoCRM qo'ng'iroq notalari (6 bosqichli rubrik)
  - `services.ai.quality_analyzer` — menejer sifat ballari

Mezonni o'zgartirish kerak bo'lsa — FAQAT shu faylni o'zgartiring. Prompt
matnini analizatorlar ichida qayta yozmang, aks holda ikki xil rubrika
qaytadan paydo bo'ladi.
"""

from __future__ import annotations

# ─── Ball chegaralari (jahon amaliyoti: 90+ excellent, <40 critical) ───
SCORE_EXCELLENT = 90   # namunali qo'ng'iroq
SCORE_GOOD = 75        # yaxshi, kichik kamchiliklar
SCORE_AVERAGE = 60     # o'rtacha — o'sish zonasi
SCORE_RED = 40         # shundan past — qizil: darhol korrektsiya kerak

# ─── Bosqich og'irliklari ───
# "×2" degani: shu bosqich umumiy ballga boshqalardan 2 barobar kuchli
# ta'sir qiladi. E'tiroz va yakunlash — bitim taqdirini hal qiladigan
# bosqichlar, shuning uchun og'irroq.
STAGE_WEIGHTS = {
    "salomlashish": 1.0,
    "ehtiyojlar": 1.5,
    "qiymat": 1.5,
    "etirozlar": 2.0,
    "yakunlash": 2.0,
    "muloqot_sifati": 1.0,
}

# `quality_analyzer` bosqichlarni mayda metriklarga bo'lib baholaydi.
# Qaysi metrik qaysi bosqichga tegishli ekani ham SHU YERDA turadi — aks
# holda ikki baholovchi bir xil rubrikani turli og'irlik bilan hisoblab,
# bitta qo'ng'iroqqa ikki xil ball qo'yadi.
STAGE_METRICS = {
    "salomlashish": ("introduction",),
    "ehtiyojlar": ("need_identification", "question_quality"),
    "qiymat": ("value_proposition",),
    "etirozlar": ("objection_handling",),
    "yakunlash": ("closing", "follow_up"),
    "muloqot_sifati": ("tone", "active_listening", "talk_ratio"),
}


def metric_weights() -> dict[str, float]:
    """Metrik bo'yicha normallashtirilgan og'irliklar (yig'indisi 1.0).

    Bosqich og'irligi o'z metriklari orasida teng bo'linadi. Masalan
    `yakunlash` (2.0) ikkiga bo'linadi: closing va follow_up.
    """
    total = sum(STAGE_WEIGHTS.values())
    weights: dict[str, float] = {}
    for stage, metrics in STAGE_METRICS.items():
        share = STAGE_WEIGHTS[stage] / total / len(metrics)
        for metric in metrics:
            weights[metric] = share
    return weights

# ─── Qattiq qoidalar ───
MIN_CALL_SECONDS = 180          # 3 daqiqadan qisqa savdo suhbati — yomon belgi
IDEAL_CLIENT_TALK_PCT = 55      # mijoz kamida shuncha gapirishi kerak
PRIMARY_LANGUAGE = "o'zbek"     # asosiy muloqot tili

# Sukut shundan uzoq cho'zilsa — "keraksiz pauza" deb qayd etiladi.
# Ataylab saxiy: tabiiy suhbatda 1-3 soniyalik tanaffus normal, va pauza
# so'z sonidan BAHOLANADI (aniq o'lchov emas — `utils.transcript` ga qarang).
# Qisqa tanaffusni xato deb ko'rsatish sotuvchini asossiz ayblash bo'ladi.
MAX_ACCEPTABLE_PAUSE_SECONDS = 4.0

# Muvaffaqiyatli qo'ng'iroq shulardan biri bilan tugashi shart:
VALID_OUTCOMES = (
    "uchrashuv sanasi belgilandi (offline yoki online)",
    "portfolio/keys yuborish kelishildi",
    "KP (tijorat taklifi) yuborish kelishildi",
    "to'lov kelishildi",
)

# ─── Natija taksonomiyasi (konversiya o'lchash uchun) ───
# `VALID_OUTCOMES` — odam o'qiydigan mezon; quyidagilari mashina o'qiydigan
# kalitlar. LLM shu kalitlardan BITTASINI qaytaradi, `metasell_conversion`
# esa shu asosda sotuvchi konversiyasini hisoblaydi. Ikkalasi bir xil
# haqiqatni ifodalaydi — mezon o'zgarsa, ikkalasi birga o'zgaradi.
OUTCOME_MEETING = "uchrashuv_kelishildi"
OUTCOME_MATERIALS = "material_yuborish"
OUTCOME_PROPOSAL = "kp_yuborish"
OUTCOME_PAYMENT = "tolov_kelishildi"
OUTCOME_FOLLOW_UP = "qayta_qongiroq"
OUTCOME_THINKING = "oylab_koradi"
OUTCOME_REFUSED = "rad_etdi"
OUTCOME_UNKNOWN = "aniqlanmadi"

# Konversiya sifatida hisoblanadigan natijalar — playbook'dagi
# `VALID_OUTCOMES` ning aynan mashina ko'rinishi.
CONVERTING_OUTCOMES = frozenset(
    {
        OUTCOME_MEETING,
        OUTCOME_MATERIALS,
        OUTCOME_PROPOSAL,
        OUTCOME_PAYMENT,
    }
)

ALL_OUTCOMES = (
    OUTCOME_MEETING,
    OUTCOME_MATERIALS,
    OUTCOME_PROPOSAL,
    OUTCOME_PAYMENT,
    OUTCOME_FOLLOW_UP,
    OUTCOME_THINKING,
    OUTCOME_REFUSED,
    OUTCOME_UNKNOWN,
)

OUTCOME_LABELS_UZ = {
    OUTCOME_MEETING: "Uchrashuv kelishildi",
    OUTCOME_MATERIALS: "Portfolio/keys yuborish kelishildi",
    OUTCOME_PROPOSAL: "KP yuborish kelishildi",
    OUTCOME_PAYMENT: "To'lov kelishildi",
    OUTCOME_FOLLOW_UP: "Qayta qo'ng'iroq belgilandi",
    OUTCOME_THINKING: "Mijoz o'ylab ko'radi (muddat yo'q)",
    OUTCOME_REFUSED: "Rad etdi",
    OUTCOME_UNKNOWN: "Aniqlanmadi",
}


# Eski (inglizcha) lug'atlar. Bitta `call_analyses.outcome` ustuniga bir
# nechta baholovchi yozadi va ularning lug'ati har xil:
#   - `services.ai.quality_analyzer` → sale|follow_up|lost|callback|not_sales
#   - `/api/sales-quality/ingest-analysis` → tashqi tizim yuborgan qiymat
#   - `services.core.deal_hygiene` → no_interest|wrong_number|spam|invalid
# Ular tarjima qilinmasa, Telegram yo'lidan kelgan "sale" qatori konversiya
# sifatida HISOBLANMAY qoladi va sotuvchi konversiyasi past ko'rsatiladi.
_LEGACY_OUTCOMES = {
    "sale": OUTCOME_PAYMENT,
    "won": OUTCOME_PAYMENT,
    "meeting": OUTCOME_MEETING,
    "proposal": OUTCOME_PROPOSAL,
    "follow_up": OUTCOME_FOLLOW_UP,
    "followup": OUTCOME_FOLLOW_UP,
    "callback": OUTCOME_FOLLOW_UP,
    "thinking": OUTCOME_THINKING,
    "lost": OUTCOME_REFUSED,
    "no_interest": OUTCOME_REFUSED,
    "not_interested": OUTCOME_REFUSED,
    "wrong_number": OUTCOME_REFUSED,
    "spam": OUTCOME_REFUSED,
    "invalid": OUTCOME_REFUSED,
    "not_sales": OUTCOME_UNKNOWN,
    "unknown": OUTCOME_UNKNOWN,
}


def normalise_outcome(value: object) -> str:
    """Erkin matnni rasmiy natija kalitiga keltiradi."""
    text = str(value or "").strip().lower()
    if not text:
        return OUTCOME_UNKNOWN
    if text in ALL_OUTCOMES:
        return text
    # Eski lug'atni aniq moslik bo'yicha tarjima qilamiz — substring
    # qidiruvidan OLDIN, aks holda "lost" hech bir kalitga tushmaydi.
    legacy = _LEGACY_OUTCOMES.get(text.replace("-", "_").replace(" ", "_"))
    if legacy:
        return legacy
    # LLM ba'zan kalit o'rniga tavsif qaytaradi — kalit so'z bo'yicha topamiz.
    aliases = (
        (OUTCOME_PAYMENT, ("to'lov", "tolov", "payment", "shartnoma")),
        (OUTCOME_PROPOSAL, ("kp", "tijorat taklif", "proposal", "smeta")),
        (OUTCOME_MEETING, ("uchrashuv", "meeting", "uchrashish")),
        (OUTCOME_MATERIALS, ("portfolio", "keys", "material", "namuna")),
        (OUTCOME_REFUSED, ("rad", "yo'q dedi", "refus", "qiziqmadi")),
        (OUTCOME_THINKING, ("o'ylab", "oylab", "think")),
        (OUTCOME_FOLLOW_UP, ("qayta", "follow", "keyinroq")),
    )
    for key, needles in aliases:
        if any(needle in text for needle in needles):
            return key
    return OUTCOME_UNKNOWN


def outcome_converted(outcome: object) -> bool:
    """Natija playbook bo'yicha konversiya hisoblanadimi?"""
    return normalise_outcome(outcome) in CONVERTING_OUTCOMES


def outcome_prompt_uz() -> str:
    """Natijani aniqlash uchun LLM promptiga qo'yiladigan matn."""
    lines = [
        "QO'NG'IROQ NATIJASI — quyidagi kalitlardan AYNAN BITTASINI tanlang:",
    ]
    for key in ALL_OUTCOMES:
        mark = " ← konversiya" if key in CONVERTING_OUTCOMES else ""
        lines.append(f"   {key} — {OUTCOME_LABELS_UZ[key]}{mark}")
    lines.append(
        "Natija FAQAT suhbatda ANIQ kelishilgan bo'lsa yoziladi. Menejer "
        "taklif qilgan, lekin mijoz rozi bo'lmagan bo'lsa — konversiya EMAS."
    )
    return "\n".join(lines) + "\n"

FORBIDDEN = (
    "Raqobatchilarni yomonlash",
    "Sotuv o'sishiga va'da berish ('sotuvingiz 2x oshadi' kabi)",
    "Savdo ustiga savdo qurish (mijoz rozı bo'lmagan qo'shimcha xizmatni tiqishtirish)",
    "Narxni bitta aniq raqam qilib aytish — narx faqat vilka (dan-gacha oraliq) usulida",
)


def rubric_prompt_uz() -> str:
    """6 bosqichli rasmiy rubrik — LLM promptiga qo'yiladigan matn."""
    return (
        "JON BRANDING RASMIY SOTUV RUBRIKASI (har bosqich 0-100 ball):\n\n"
        "1. Salomlashish:\n"
        "   - Menejer O'Z ISMINI va 'Jon Branding' kompaniyasini tanishtirdimi? (majburiy)\n"
        "   - Qo'ng'iroq maqsadini boshida aytdimi? (majburiy)\n"
        "   - 'Bizni qayerdan topdingiz?' — faqat BIRINCHI qo'ng'iroqda va lead manbasi\n"
        "     noma'lum bo'lsa majburiy; keyingi qo'ng'iroqlarda talab qilinmaydi.\n\n"
        "2. Ehtiyojlar (og'irlik 1.5x):\n"
        "   - Biznes turini so'radimi?\n"
        "   - Mijoz maqsadini aniqladimi?\n"
        "   - Muddatni so'radimi?\n"
        "   - Qaror qabul qiluvchi kimligini aniqladimi?\n"
        "   - Qaysi xizmat (brending/dizayn/SMM/sayt) mosligini aniqladimi? (majburiy)\n"
        "   - Byudjet: so'ragan bo'lsa plus, lekin birinchi qo'ng'iroqda so'ramagani\n"
        "     uchun ball KAMAYTIRILMAYDI.\n\n"
        "3. Qiymat taqdimoti (og'irlik 1.5x):\n"
        "   - Taklifni mijoz ehtiyojiga bog'ladimi?\n"
        "   - Narx aytilgan bo'lsa — FAQAT vilka usulida (masalan '20 mln dan 50 mln gacha')\n"
        "     aytilishi shart. Bitta qat'iy raqam aytsa — ball kamaytiriladi.\n"
        "   - Portfolio/keys: uchrashuvda ko'rsatish yoki Telegram orqali yuborishni\n"
        "     taklif qildimi?\n"
        "   - Sotuv o'sishiga va'da berdimi? Bergan bo'lsa — JIDDIY XATO, ball keskin past.\n\n"
        "4. E'tirozlar (og'irlik 2x):\n"
        "   - Tipik e'tirozlar: 'qimmat', 'o'ylab ko'raman'.\n"
        "   - 'Qimmat' — narx tarkibini va qiymatni tushuntirdimi?\n"
        "   - 'O'ylab ko'raman' — aniq MUDDAT belgilab, qayta qo'ng'iroq KELISHDIMI?\n"
        "     (majburiy; kelishmasa ball past)\n"
        "   - E'tiroz bo'lmagan qo'ng'iroqda: e'tiroz chiqmasligi menejer aybi emas,\n"
        "     o'rtacha-yuqori ball qo'ying.\n\n"
        "5. Yakunlash (og'irlik 2x):\n"
        "   - Qo'ng'iroq quyidagilardan KAMIDA BITTASI bilan tugadimi:\n"
        "     uchrashuv sanasi / portfolio-keys yuborish / KP yuborish / to'lov?\n"
        "   - Ideal natija: OFFLINE yoki ONLINE UCHRASHUV kelishuvi.\n"
        "   - Keyingi qadam + aniq muddat kelishilmagan bo'lsa — ball PAST bo'lishi shart.\n\n"
        "6. Muloqot sifati:\n"
        "   - Professional ohang, hurmat.\n"
        "   - Mijozni bo'lmasdan tingladimi?\n"
        "   - Asosan o'zbek tilida so'zladimi?\n"
        "   - Gapirish nisbati: mijoz ko'proq gapirgani yaxshi "
        f"(ideal: mijoz ≥{IDEAL_CLIENT_TALK_PCT}%).\n"
        f"   - Keraksiz pauza: {MAX_ACCEPTABLE_PAUSE_SECONDS:g} soniyadan uzun sukut "
        "mijozni sovutadi. Menejer javobni kutib qotib qolganmi yoki "
        "suhbatni boshqarganmi?\n\n"
        "TAQIQLAR (har biri uchun ball keskin kamaytiriladi va weaknesses'ga yoziladi):\n"
        + "".join(f"   - {rule}\n" for rule in FORBIDDEN)
        + "\n"
        f"QO'SHIMCHA: {MIN_CALL_SECONDS // 60} daqiqadan qisqa savdo suhbati — "
        "chuqur ehtiyoj aniqlash bo'lmagani belgisi; buni weaknesses'da qayd eting.\n"
    )


def category_for_score(score: int) -> str:
    """Umumiy ball bo'yicha rasmiy toifa."""
    if score >= SCORE_EXCELLENT:
        return "excellent"
    if score >= SCORE_GOOD:
        return "good"
    if score >= SCORE_AVERAGE:
        return "average"
    if score >= SCORE_RED:
        return "poor"
    return "critical"
