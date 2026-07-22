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

# Muvaffaqiyatli qo'ng'iroq shulardan biri bilan tugashi shart:
VALID_OUTCOMES = (
    "uchrashuv sanasi belgilandi (offline yoki online)",
    "portfolio/keys yuborish kelishildi",
    "KP (tijorat taklifi) yuborish kelishildi",
    "to'lov kelishildi",
)

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
        f"(ideal: mijoz ≥{IDEAL_CLIENT_TALK_PCT}%).\n\n"
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
