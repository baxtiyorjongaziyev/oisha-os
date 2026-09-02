"""
Constants, SQL queries, and Uzbek localization labels for MetaSell.
"""

# bo'lsa — bitta omadli/omadsiz qo'ng'iroq butun tavsiyani buzadi.
MIN_CALLS_FOR_DIAGNOSIS = 6
MIN_CALLS_PER_GROUP = 2

# Bosqich ballari orasidagi farq shundan kichik bo'lsa — shovqin deb
# qaraladi, o'sish nuqtasi sifatida ko'rsatilmaydi.
MIN_MEANINGFUL_GAP = 5.0

# Trend ko'rsatish uchun HAR IKKI davrda shuncha qo'ng'iroq bo'lishi kerak.
# 2 ta qo'ng'iroqdan "+50%" chiqarish — chalg'ituvchi raqam.
MIN_CALLS_FOR_TREND = 5

# Javob berish foizi shundan past bo'lsa — alohida ogohlantiriladi.
# Ko'tarilmagan qo'ng'iroq hech qanday ball olmaydi, shuning uchun u
# sifat statistikasida ko'rinmaydi; buni alohida aytish kerak.
MIN_ACCEPTABLE_ANSWER_RATE = 80.0

STAGE_LABELS_UZ = {
    "salomlashish": "Salomlashish va tanishtirish",
    "ehtiyojlar": "Ehtiyojni aniqlash",
    "qiymat": "Qiymat taqdimoti",
    "etirozlar": "E'tirozlar bilan ishlash",
    "yakunlash": "Yakunlash va keyingi qadam",
    "muloqot_sifati": "Muloqot sifati",
}

# Har bosqich uchun aniq, bajarib bo'ladigan mashq. Umumiy "yaxshiroq
# ishlang" maslahati konversiyani oshirmaydi — aniq harakat oshiradi.
STAGE_DRILLS_UZ = {
    "salomlashish": (
        "Har qo'ng'iroqni bir xil boshlang: ism + 'Jon Branding' + qo'ng'iroq "
        "maqsadi. Shu uch elementni 10 ta qo'ng'iroqda og'zaki mashq qiling."
    ),
    "ehtiyojlar": (
        "Taklif aytishdan OLDIN kamida 4 ta ochiq savol bering: biznes turi, "
        "maqsad, muddat, qaror qabul qiluvchi. Savol bermay narx aytmang."
    ),
    "qiymat": (
        "Taklifni mijoz aytgan og'riqqa bog'lab ayting: 'Siz ... dedingiz — "
        "shuning uchun biz ...'. Narxni faqat vilka usulida ayting."
    ),
    "etirozlar": (
        "'Qimmat' va 'o'ylab ko'raman' uchun tayyor javobni yodlang. "
        "'O'ylab ko'raman' javobidan keyin ALBATTA aniq sana belgilang."
    ),
    "yakunlash": (
        "Hech bir qo'ng'iroqni keyingi qadamsiz tugatmang. Yakunda aniq "
        "taklif qiling: 'Kelasi seshanba soat 15:00 da uchrashamizmi?'"
    ),
    "muloqot_sifati": (
        "Mijozni bo'lmang. Har javobidan keyin 2 soniya kuting. Maqsad — "
        "mijoz suhbatning yarmidan ko'pini gapirsin."
    ),
}


# So'rovlar to'liq literal — ustun ro'yxati f-string bilan qurilsa,
# bandit B608 (SQL injection) ogohlantiradi va gate qizil bo'ladi.
_ANALYSIS_COLUMNS = (
    "manager_name, overall_score, scores, outcome, converted, "
    "weaknesses, strengths, objections, category, call_id, lead_id, "
    "duration_seconds, created_at, lead_price, lead_won, "
    "breakdown_at, breakdown_reason, longest_pause_seconds"
)

_SELECT_RECENT_SQL = (
    "SELECT manager_name, overall_score, scores, outcome, converted, "
    "weaknesses, strengths, objections, category, call_id, lead_id, "
    "duration_seconds, created_at, lead_price, lead_won, "
    "breakdown_at, breakdown_reason, longest_pause_seconds "
    "FROM call_analyses "
    "WHERE overall_score > 0 AND created_at >= datetime('now', ?) "
    "ORDER BY created_at DESC"
)

_SELECT_WINDOW_SQL = (
    "SELECT manager_name, overall_score, scores, outcome, converted, "
    "weaknesses, strengths, objections, category, call_id, lead_id, "
    "duration_seconds, created_at, lead_price, lead_won, "
    "breakdown_at, breakdown_reason, longest_pause_seconds "
    "FROM call_analyses "
    "WHERE overall_score > 0 "
    "AND created_at >= datetime('now', ?) "
    "AND created_at < datetime('now', ?) "
    "ORDER BY created_at DESC"
)

