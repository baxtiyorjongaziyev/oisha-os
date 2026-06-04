"""Sales scoring rubrics for General, Hunter and Closer call roles.

Three rubrics are defined:
- general: Any sales call (A1-F3, 18 criteria)
- hunter:  Cold outreach, qualification, first contact (H_A1-H_F3, 18 criteria)
- closer:  Proposal, negotiation, deal closing (C_A1-C_F3, 18 criteria)

Usage:
    from src.services.core.sales_rubric import get_rubric, compute_rubric_score, format_rubric_report

    report = format_rubric_report({"A1": 3, "A2": 2, ...}, role="general")
    result = compute_rubric_score(scores_dict, role="hunter")
"""

from typing import Dict, Any

# ─────────────────────────────────────────────────────────────────
# UMUMIY (General) rubrika — A1-F3
# Har qanday sotuv qo'ng'irog'i uchun
# ─────────────────────────────────────────────────────────────────
GENERAL_RUBRIC: Dict[str, Any] = {
    "name": "Umumiy Sotuv Qo'ng'irog'i",
    "description": "Har qanday sotuv qo'ng'iroqi uchun umumiy mezoni",
    "version": "2.0",
    "categories": [
        {
            "code": "A",
            "name": "Salomlashish",
            "weight": 0.12,
            "criteria": [
                {
                    "code": "A1",
                    "name": "O'zini tanishtirish",
                    "max_score": 3,
                    "levels": {
                        3: "Ismi, kompaniyasi va lavozimini aniq, qulay va do'stona tarzda aytadi; mijoz nomini ishlatadi",
                        2: "Ismi va kompaniyasini aytadi, lekin lavozim yoki mijoz nomi yo'q",
                        1: "Faqat ismi yoki kompaniyasini aytadi",
                        0: "O'zini tanishtirmaydi yoki noaniq",
                    },
                },
                {
                    "code": "A2",
                    "name": "Qo'ng'iroq maqsadini bildirish",
                    "max_score": 3,
                    "levels": {
                        3: "Qo'ng'iroq maqsadini aniq va foydali tarzda ifodalaydi; ruxsat so'raydi",
                        2: "Maqsadni aytadi, lekin ruxsat so'ramaydi yoki noaniq",
                        1: "Maqsad noaniq yoki chalg'ituvchi",
                        0: "Maqsad umuman aytilmaydi",
                    },
                },
                {
                    "code": "A3",
                    "name": "Boshlang'ich rapport",
                    "max_score": 3,
                    "levels": {
                        3: "Ismi/kompaniyasini oldindan biladi; shaxsiy element (avvalgi suhbat, kompaniya yangiligi) qo'shadi",
                        2: "Iliq munosabat, lekin shaxsiylashtirilgan element yo'q",
                        1: "Sovuq, skript kabi yoki sun'iy",
                        0: "Salomlashish yo'q yoki to'g'ridan-to'g'ri savdo bosimi",
                    },
                },
            ],
        },
        {
            "code": "B",
            "name": "Ehtiyojlar",
            "weight": 0.23,
            "criteria": [
                {
                    "code": "B1",
                    "name": "Ochiq savollar berish",
                    "max_score": 3,
                    "levels": {
                        3: "Strategik ochiq savollar beradi; javoblarni to'g'ri yo'naltiradi",
                        2: "Ochiq savollar bor, lekin yetarlicha chuqur emas",
                        1: "Ko'proq yopiq savollar; ehtiyoj yuzaki aniqlanadi",
                        0: "Savolsiz yoki to'g'ridan-to'g'ri taklif qiladi",
                    },
                },
                {
                    "code": "B2",
                    "name": "Og'riq nuqtasini topish",
                    "max_score": 3,
                    "levels": {
                        3: "Asosiy biznes muammosini aniqlab, uning ta'sirini tushuntiradi",
                        2: "Og'riq nuqtasini aniqlaydi, lekin ta'sirini chuqur o'rganmaydi",
                        1: "Sirtqi muammoni ko'radi, lekin asosiy sababni topa olmaydi",
                        0: "Og'riq nuqtasini aniqlamaydi",
                    },
                },
                {
                    "code": "B3",
                    "name": "Hozirgi holat va maqsad tushunish",
                    "max_score": 3,
                    "levels": {
                        3: "Hozirgi holat va maqsad o'rtasidagi farqni aniq tushunadi va tasdiqlaydi",
                        2: "Maqsadni so'raydi, lekin farqni aniq belgilamaydi",
                        1: "Faqat maqsad yoki faqat hozirgi holat so'raladi",
                        0: "Hech qaysi so'raladi",
                    },
                },
            ],
        },
        {
            "code": "C",
            "name": "Qiymat",
            "weight": 0.18,
            "criteria": [
                {
                    "code": "C1",
                    "name": "Yechimni muammoga bog'lash",
                    "max_score": 3,
                    "levels": {
                        3: "Yechimni aniq mijozning muammosiga bog'laydi; konkret foyda ko'rsatadi",
                        2: "Yechimni aytadi, lekin muammoga to'liq bog'lamaydi",
                        1: "Umumiy foyda gapiriladi, mijozning o'ziga moslashtirilmagan",
                        0: "Yechim umuman tushuntirilmaydi",
                    },
                },
                {
                    "code": "C2",
                    "name": "Social proof va dalillar",
                    "max_score": 3,
                    "levels": {
                        3: "Tegishli case study, raqam yoki testimonial keltiradi",
                        2: "Umumiy misol keltiradi, lekin raqam yoki konkret dalil yo'q",
                        1: "Faqat og'zaki ta'rif",
                        0: "Hech qanday dalil yo'q",
                    },
                },
                {
                    "code": "C3",
                    "name": "ROI va natija ko'rsatish",
                    "max_score": 3,
                    "levels": {
                        3: "Aniq ROI yoki o'lchanadigan natijani ko'rsatadi",
                        2: "Umumiy natijani aytadi, lekin o'lchanadigan emas",
                        1: "Faqat xususiyatlarni sanaydi",
                        0: "ROI yoki natija aytilmaydi",
                    },
                },
            ],
        },
        {
            "code": "D",
            "name": "E'tirozlar",
            "weight": 0.12,
            "criteria": [
                {
                    "code": "D1",
                    "name": "E'tirozni qabul qilish",
                    "max_score": 3,
                    "levels": {
                        3: "E'tirozni to'liq eshitadi, tan oladi va mijozni tushunganini bildiradi",
                        2: "Eshitadi, lekin to'liq tan olmaydi",
                        1: "E'tirozni o'chirishga harakat qiladi",
                        0: "E'tirozni e'tiborsiz qoldiradi yoki bahslashadi",
                    },
                },
                {
                    "code": "D2",
                    "name": "E'tirozni yengish",
                    "max_score": 3,
                    "levels": {
                        3: "E'tirozga aniq, dalillangan javob beradi; mijozni ishontiradi",
                        2: "Javob beradi, lekin to'liq ishontirmaydi",
                        1: "Umumiy javob beradi",
                        0: "E'tirozni yengolmaydi yoki bahslashadi",
                    },
                },
                {
                    "code": "D3",
                    "name": "E'tiroz asosini tushunish",
                    "max_score": 3,
                    "levels": {
                        3: "E'tirozning asosiy sababini aniqlaydi (narx, ishonchsizlik, vaqt, raqobatchi)",
                        2: "Sababni qisman aniqlaydi",
                        1: "E'tirozni sezadi lekin sababni aniqlamaydi",
                        0: "Hech qanday harakat yo'q",
                    },
                },
            ],
        },
        {
            "code": "E",
            "name": "Yakunlash",
            "weight": 0.20,
            "criteria": [
                {
                    "code": "E1",
                    "name": "Qaror so'rash",
                    "max_score": 3,
                    "levels": {
                        3: "Aniq va qat'iy yopish savoli beradi; tanlov texnikasini ishlatadi",
                        2: "Yopish savoli bor, lekin qat'iy emas",
                        1: "Yopish harakati noaniq yoki passiv",
                        0: "Yopish harakati yo'q",
                    },
                },
                {
                    "code": "E2",
                    "name": "Keyingi qadam belgilash",
                    "max_score": 3,
                    "levels": {
                        3: "Aniq keyingi qadam (sana, soat, mas'ul) kelishib olinadi",
                        2: "Keyingi qadam aytiladi, lekin aniq sana/vaqt yo'q",
                        1: "Noaniq keyingi qadam",
                        0: "Keyingi qadam yo'q",
                    },
                },
                {
                    "code": "E3",
                    "name": "Urgentlik yaratish",
                    "max_score": 3,
                    "levels": {
                        3: "Haqiqiy urgentlik (chegirma muddati, boshqa mijoz, narx o'zgarishi) yaratadi",
                        2: "Urgentlik mavjud, lekin sun'iy yoki zaif",
                        1: "Urgentlik urinishi bor, lekin kuchsiz",
                        0: "Urgentlik yaratilmaydi",
                    },
                },
            ],
        },
        {
            "code": "F",
            "name": "Muloqot sifati",
            "weight": 0.15,
            "criteria": [
                {
                    "code": "F1",
                    "name": "Tinglash va empatiya",
                    "max_score": 3,
                    "levels": {
                        3: "Faol tinglash ko'rsatadi; mijoz his-tuyg'ularini tan oladi",
                        2: "Tinglaydi, lekin empatiya kam",
                        1: "Gapni kesadi yoki o'z fikrini majburlaydi",
                        0: "Tinglashni ko'rsatmaydi",
                    },
                },
                {
                    "code": "F2",
                    "name": "Aniqlik va ishonch",
                    "max_score": 3,
                    "levels": {
                        3: "Aniq, ishonchli va professional gapiradi",
                        2: "Asosan aniq, lekin ba'zi noaniqliklar bor",
                        1: "Ko'p to'xtashlar, noaniqliklar, ishonchsiz ohang",
                        0: "Asosiy g'oya tushunarsiz",
                    },
                },
                {
                    "code": "F3",
                    "name": "Moslashuvchanlik",
                    "max_score": 3,
                    "levels": {
                        3: "Suhbat oqimiga ko'ra yondashuv o'zgartiradi; skriptdan chiqishi mumkin",
                        2: "Qisman moslashadi",
                        1: "Asosan skriptga amal qiladi",
                        0: "Robotik yoki moslashuvsiz",
                    },
                },
            ],
        },
    ],
}

# ─────────────────────────────────────────────────────────────────
# HUNTER rubrika — Birinchi kontakt va BANT kvalifikatsiya
# Sovuq qo'ng'iroq, lead topish, uchrashuv booking
# ─────────────────────────────────────────────────────────────────
HUNTER_RUBRIC: Dict[str, Any] = {
    "name": "Hunter — Birinchi Kontakt va Kvalifikatsiya",
    "description": "Sovuq qo'ng'iroq, lead topish, birinchi kontakt va BANT kvalifikatsiya",
    "version": "2.0",
    "categories": [
        {
            "code": "H_A",
            "name": "Birinchi Kontakt",
            "weight": 0.15,
            "criteria": [
                {
                    "code": "H_A1",
                    "name": "Hook — diqqat tortish",
                    "max_score": 3,
                    "levels": {
                        3: "Darhol diqqat tortadigan, mijozga tegishli hook bilan boshlaydi (muammo, foyda, statistika)",
                        2: "Qiziqarli boshlash bor, lekin kuchsiz yoki umumiy",
                        1: "Standart tanishtirish, hook yo'q",
                        0: "To'g'ridan-to'g'ri savdo yoki hook umuman yo'q",
                    },
                },
                {
                    "code": "H_A2",
                    "name": "Tadqiqot ko'rsatkichlari",
                    "max_score": 3,
                    "levels": {
                        3: "Mijozning kompaniyasi, sohasi yoki muammosi haqida oldindan biladi va ishlatadi",
                        2: "Ba'zi bilim bor, lekin yuzaki",
                        1: "Umumiy, shaxsiylashtirilmagan yondashuv",
                        0: "Hech qanday oldindan tayyorlik ko'rinmaydi",
                    },
                },
                {
                    "code": "H_A3",
                    "name": "Ruxsat va vaqt boshqaruvi",
                    "max_score": 3,
                    "levels": {
                        3: "Vaqt mavjudligini so'raydi; maqsadni aniq bildiradi; qulay bo'lmasa qayta qo'ng'iroq kelishadi",
                        2: "Ruxsat so'raydi, lekin maqsad noaniq",
                        1: "Ruxsat so'ramaydi, lekin qisqa aytadi",
                        0: "Ruxsatsiz to'g'ridan-to'g'ri savdoga o'tadi",
                    },
                },
            ],
        },
        {
            "code": "H_B",
            "name": "BANT Kvalifikatsiya",
            "weight": 0.25,
            "criteria": [
                {
                    "code": "H_B1",
                    "name": "Budget — byudjet aniqlash",
                    "max_score": 3,
                    "levels": {
                        3: "Byudjet mavjudligini va hajmini mohirona so'raydi; doirani aniqlaydi",
                        2: "Byudjet haqida so'raydi, lekin aniq doira aniqlanmaydi",
                        1: "Byudjet mavzu ko'tariladi, lekin aniqlanmaydi",
                        0: "Byudjet haqida umuman so'ralmagsa",
                    },
                },
                {
                    "code": "H_B2",
                    "name": "Authority — qaror qabul qiluvchi",
                    "max_score": 3,
                    "levels": {
                        3: "Qaror qabul qiluvchi kim ekanligini aniqlab, to'g'ridan-to'g'ri u bilan gaplashadi yoki yo'l topadi",
                        2: "Qaror qabul qiluvchini aniqlaydi, lekin unga yetmaydi",
                        1: "Lavozimni so'raydi, lekin qaror jarayonini tushunmaydi",
                        0: "Qaror qabul qiluvchi haqida so'rash yo'q",
                    },
                },
                {
                    "code": "H_B3",
                    "name": "Need + Timeline — ehtiyoj va muddat",
                    "max_score": 3,
                    "levels": {
                        3: "Haqiqiy ehtiyoj va aniq muddat/urgentlikni aniqlaydi",
                        2: "Ehtiyoj yoki muddatdan birini aniqlaydi",
                        1: "Ehtiyoj umumiy, muddat aniq emas",
                        0: "Ne ehtiyoj, ne muddat aniqlanmaydi",
                    },
                },
            ],
        },
        {
            "code": "H_C",
            "name": "Og'riq Nuqtasi Kashfiyoti",
            "weight": 0.20,
            "criteria": [
                {
                    "code": "H_C1",
                    "name": "Asosiy muammo aniqlash",
                    "max_score": 3,
                    "levels": {
                        3: "3-5 ta kuchli ochiq savol bilan haqiqiy biznes muammosini topadi",
                        2: "Muammoni aniqlaydi, lekin chuqurlashtirmaydi",
                        1: "Faqat sirtqi muammoni ko'radi",
                        0: "Muammo aniqlanmaydi",
                    },
                },
                {
                    "code": "H_C2",
                    "name": "Ta'sir va xarajat aniqlash",
                    "max_score": 3,
                    "levels": {
                        3: "Muammoning biznesga ta'siri (yo'qotilgan pul, vaqt, imkoniyat) aniqlanadi",
                        2: "Ta'sir seziladi, lekin o'lchanadigan emas",
                        1: "Muammo aytiladi, ta'sir so'ralmaydi",
                        0: "Ta'sir haqida so'rash yo'q",
                    },
                },
                {
                    "code": "H_C3",
                    "name": "Hozirgi yechim baholash",
                    "max_score": 3,
                    "levels": {
                        3: "Hozir qanday yechim ishlatayotganini va nima yetishmayotganini aniqlaydi",
                        2: "Hozirgi yechimni so'raydi, lekin kamchiliklarni aniqlamaydi",
                        1: "Faqat muammo bor/yo'q so'raladi",
                        0: "Hozirgi yechim haqida so'rash yo'q",
                    },
                },
            ],
        },
        {
            "code": "H_D",
            "name": "Qiziqtirish va Qiymat Teaser",
            "weight": 0.15,
            "criteria": [
                {
                    "code": "H_D1",
                    "name": "Qiziqish uyg'otish",
                    "max_score": 3,
                    "levels": {
                        3: "Mijozning muammosiga bevosita bog'liq foydani teaser sifatida beradi; demo/uchrashuv istagini uyg'otadi",
                        2: "Qiziqtiradi, lekin muammoga to'g'ridan-to'g'ri bog'lamaydi",
                        1: "Umumiy qiziqtirish, shaxsiylashtirilmagan",
                        0: "Qiziqtirish harakati yo'q",
                    },
                },
                {
                    "code": "H_D2",
                    "name": "Raqobatchidan farqlash",
                    "max_score": 3,
                    "levels": {
                        3: "Aniq va o'lchanadigan UVP (unique value proposition) bilan raqobatchidan farqlanadi",
                        2: "Farq aytiladi, lekin aniq emas yoki isbotlanmagan",
                        1: "Umumiy farq talaqlari",
                        0: "Hech qanday farq ko'rsatilmaydi",
                    },
                },
                {
                    "code": "H_D3",
                    "name": "Social proof ishlating",
                    "max_score": 3,
                    "levels": {
                        3: "Sohaga tegishli case study yoki raqam keltiradi (suhbat bosqichiga mos)",
                        2: "Umumiy misol, raqam yo'q",
                        1: "Faqat og'zaki ta'rif",
                        0: "Social proof yo'q",
                    },
                },
            ],
        },
        {
            "code": "H_E",
            "name": "Keyingi Qadam Booking",
            "weight": 0.20,
            "criteria": [
                {
                    "code": "H_E1",
                    "name": "Uchrashuv yoki demo booking",
                    "max_score": 3,
                    "levels": {
                        3: "Aniq sana va vaqt bilan uchrashuv/demo kelishadi; kalendarni tekshiradi",
                        2: "Uchrashuv taklif qiladi, lekin aniq sana/vaqt yo'q",
                        1: "Noaniq 'keyinroq uchrashamiz' deyiladi",
                        0: "Keyingi qadam belgilanmaydi",
                    },
                },
                {
                    "code": "H_E2",
                    "name": "Tasdiqlash va follow-up",
                    "max_score": 3,
                    "levels": {
                        3: "Kelishuvni tasdiqlab, qisqa xabar/email jo'natishga va'da beradi",
                        2: "Tasdiqlab, lekin follow-up haqida noaniq",
                        1: "Faqat og'zaki va'da",
                        0: "Hech qanday tasdiqlash yo'q",
                    },
                },
                {
                    "code": "H_E3",
                    "name": "Gatekeeper o'tish",
                    "max_score": 3,
                    "levels": {
                        3: "Gatekeeper bilan professional ishlaydi; qaror qabul qiluvchiga yetish uchun yo'l topadi",
                        2: "Gatekeeperga murojaat qiladi, lekin qaror qabul qiluvchiga yetmaydi",
                        1: "Gatekeeperga bir marta urinadi",
                        0: "Gatekeeperda qoladi yoki tashlab ketadi",
                    },
                },
            ],
        },
        {
            "code": "H_F",
            "name": "Muloqot va Qat'iyat",
            "weight": 0.05,
            "criteria": [
                {
                    "code": "H_F1",
                    "name": "Rad etishga chidamlilik",
                    "max_score": 3,
                    "levels": {
                        3: "Rad etishni professional qabul qiladi; sababni so'rab qayta bog'lanish imkonini saqlaydi",
                        2: "Rad etishga bardosh beradi, lekin qayta imkon yaratmaydi",
                        1: "Rad etishda befarq yoki takrorlaydi",
                        0: "Rad etishda darhol taslim yoki bahslashadi",
                    },
                },
                {
                    "code": "H_F2",
                    "name": "Ton va energiya",
                    "max_score": 3,
                    "levels": {
                        3: "Yuqori energiya, ishonchli, do'stona va qiziqarli ovoz toni",
                        2: "Yaxshi ton, lekin ba'zi hollarda pasayadi",
                        1: "Past energiya yoki monoton",
                        0: "Juda past yoki noqulay ton",
                    },
                },
                {
                    "code": "H_F3",
                    "name": "Vaqt boshqaruvi",
                    "max_score": 3,
                    "levels": {
                        3: "3-7 daqiqa ichida asosiy maqsadga erishadi; suhbatni nazorat qiladi",
                        2: "Asosiy maqsadga erishadi, lekin vaqtdan ko'p foydalanadi",
                        1: "Vaqtni boshqara olmaydi; suhbat cho'ziladi",
                        0: "Vaqt nazorati yo'q",
                    },
                },
            ],
        },
    ],
}

# ─────────────────────────────────────────────────────────────────
# CLOSER rubrika — Taklif, muzokara va shartnoma yopish
# Kvalifitsiyalangan leadni shartnomaga olib kelish
# ─────────────────────────────────────────────────────────────────
CLOSER_RUBRIC: Dict[str, Any] = {
    "name": "Closer — Taklif, Muzokara va Yopish",
    "description": "Kvalifitsiyalangan leadni shartnomaga olib kelish",
    "version": "2.0",
    "categories": [
        {
            "code": "CL_A",
            "name": "Qayta Bog'lanish va Asoslash",
            "weight": 0.10,
            "criteria": [
                {
                    "code": "CL_A1",
                    "name": "Avvalgi suhbatni eslash",
                    "max_score": 3,
                    "levels": {
                        3: "Avvalgi suhbatdan aniq tafsilotlarni (muammo, maqsad, kelishuv) eslaydi va tasdiqlaydi",
                        2: "Umumiy eslatma bor, lekin detallar yo'q",
                        1: "Avvalgi suhbatga ishora qiladi, detallar noaniq",
                        0: "Avvalgi suhbat umuman eslatilmaydi",
                    },
                },
                {
                    "code": "CL_A2",
                    "name": "Agenda belgilash",
                    "max_score": 3,
                    "levels": {
                        3: "Suhbat maqsadini aniq belgilaydi; agendani kelishadi; mijoz kutishini boshqaradi",
                        2: "Maqsad aytiladi, lekin agenda yo'q",
                        1: "Noaniq boshlash",
                        0: "Bevosita taklif/narxga o'tadi",
                    },
                },
                {
                    "code": "CL_A3",
                    "name": "Ehtiyoj tasdiqlash",
                    "max_score": 3,
                    "levels": {
                        3: "Avvalgi ehtiyojlarni tasdiqlaydi va yangi o'zgarishlar bor-yo'qligini so'raydi",
                        2: "Ehtiyojni tasdiqlaydi, yangi o'zgarish so'rash yo'q",
                        1: "Faqat avvalgi ehtiyojni takrorlaydi",
                        0: "Ehtiyoj umuman tasdiqlanmaydi",
                    },
                },
            ],
        },
        {
            "code": "CL_B",
            "name": "Taklif Taqdimoti",
            "weight": 0.25,
            "criteria": [
                {
                    "code": "CL_B1",
                    "name": "Shaxsiylashtirilgan taklif",
                    "max_score": 3,
                    "levels": {
                        3: "Taklif aniq mijozning muammosi va maqsadiga moslashtirilgan; umumiy emas",
                        2: "Taklif asosan moslab berilgan, lekin ba'zi umumiy qismlar bor",
                        1: "Standart taklif, kam moslashtirilgan",
                        0: "Umumiy yoki standart taklif",
                    },
                },
                {
                    "code": "CL_B2",
                    "name": "Qiymat narxdan oldin",
                    "max_score": 3,
                    "levels": {
                        3: "Narxdan oldin aniq ROI va qiymatni tushuntiradi; mijoz o'zi narx so'ragunicha kutadi",
                        2: "Qiymat bor, lekin narx bilan birga aytiladi",
                        1: "Narx birinchi aytiladi, keyin qiymat",
                        0: "Faqat narx aytiladi, qiymat yo'q",
                    },
                },
                {
                    "code": "CL_B3",
                    "name": "Paketlar va variantlar",
                    "max_score": 3,
                    "levels": {
                        3: "2-3 ta paket taklif qiladi; har birining qiymat va narxi aniq; 'yuqori' paket birinchi aytiladi",
                        2: "2 ta variant bor, lekin taqqoslash aniq emas",
                        1: "Faqat 1 ta variant",
                        0: "Variant yo'q; tanlov yo'q",
                    },
                },
            ],
        },
        {
            "code": "CL_C",
            "name": "E'tirozlarni Yengish",
            "weight": 0.20,
            "criteria": [
                {
                    "code": "CL_C1",
                    "name": "Narx e'tirozini yengish",
                    "max_score": 3,
                    "levels": {
                        3: "Narx e'tirozini ROI, muqobil taqqoslash yoki to'lov rejasi bilan professional yengadi",
                        2: "E'tirozga javob beradi, lekin to'liq ishontirmaydi",
                        1: "Chegirma taklif qiladi (qiymatni tushuntirmasdan)",
                        0: "E'tirozni e'tiborsiz qoldiradi yoki darhol chegirma beradi",
                    },
                },
                {
                    "code": "CL_C2",
                    "name": "Vaqt/kechiktirish e'tirozini yengish",
                    "max_score": 3,
                    "levels": {
                        3: "Kechiktirish xarajatini ko'rsatadi; urgentlik yaratadi; erta qaror qilishga undaydi",
                        2: "Urgentlik yaratishga urinadi, lekin kuchsiz",
                        1: "Oddiy 'tez qaror qiling' deyiladi",
                        0: "Kechiktirishga rozi bo'ladi yoki javob yo'q",
                    },
                },
                {
                    "code": "CL_C3",
                    "name": "Raqobatchi e'tirozini yengish",
                    "max_score": 3,
                    "levels": {
                        3: "Raqobatchi bilan taqqoslashni professional boshqaradi; UVPni kuchaytiradi; raqobatchini mensimasdan",
                        2: "Farqni aytadi, lekin puxta emas",
                        1: "Raqobatchini kamsitadi yoki himoyalanadi",
                        0: "Raqobatchi mavzusini boshqara olmaydi",
                    },
                },
            ],
        },
        {
            "code": "CL_D",
            "name": "Muzokara va Kelishuv",
            "weight": 0.15,
            "criteria": [
                {
                    "code": "CL_D1",
                    "name": "Chegirma/imtiyoz boshqarish",
                    "max_score": 3,
                    "levels": {
                        3: "Chegirmani faqat evaziga (ko'p xizmat, avans, referral) beradi; qiymatni saqlab qoladi",
                        2: "Chegirmani shartli beradi, lekin shart aniq emas",
                        1: "So'ralsa chegirma beradi, shartsiz",
                        0: "Darhol katta chegirma beradi yoki narxdan bosh tortadi",
                    },
                },
                {
                    "code": "CL_D2",
                    "name": "Anchoring texnikasi",
                    "max_score": 3,
                    "levels": {
                        3: "Yuqori narxdan boshlaydi (anchor); o'rta paket 'optimal' ko'rinadi",
                        2: "Anchoring bor, lekin kuchsiz yoki aniq emas",
                        1: "To'g'ridan-to'g'ri target narxdan boshlaydi",
                        0: "Pastdan boshlaydi yoki anchoring yo'q",
                    },
                },
                {
                    "code": "CL_D3",
                    "name": "Win-win kelishuv",
                    "max_score": 3,
                    "levels": {
                        3: "Ikkala tomon foydalanadigan kelishuvga keladi; mijoz ham g'olib his qiladi",
                        2: "Kelishuv bor, lekin bir tomonga ko'proq",
                        1: "Faqat kompaniya foydasi ko'zlanadi",
                        0: "Kelishuv bo'lmaydi yoki bahslashib ajraladi",
                    },
                },
            ],
        },
        {
            "code": "CL_E",
            "name": "Shartnoma Yopish",
            "weight": 0.20,
            "criteria": [
                {
                    "code": "CL_E1",
                    "name": "Trial close — sinov yopish",
                    "max_score": 3,
                    "levels": {
                        3: "Asosiy yopishdan oldin 2-3 marta trial close ishlatadi; mijoz tayyor emasligini erta aniqlaydi",
                        2: "1-2 marta sinov savoli bor",
                        1: "Faqat asosiy yopish savoli",
                        0: "Yopish harakati yo'q",
                    },
                },
                {
                    "code": "CL_E2",
                    "name": "Qat'iy yopish",
                    "max_score": 3,
                    "levels": {
                        3: "Aniq, qat'iy va tanlovli yopish savoli beradi; 'ha' ni farazlaydi (assumptive close)",
                        2: "Yopish savoli bor, lekin noaniq yoki zaif",
                        1: "Passiv yopish ('agar xohlasangiz...')",
                        0: "Yopish harakati yo'q; mijoz o'zi qaror qilishi kutiladi",
                    },
                },
                {
                    "code": "CL_E3",
                    "name": "Shartnoma va to'lov qadam",
                    "max_score": 3,
                    "levels": {
                        3: "Shartnoma va birinchi to'lov uchun aniq qadamlar, muddat va mas'ul belgiladi",
                        2: "Shartnoma haqida aytiladi, lekin qadamlar noaniq",
                        1: "Faqat 'shartnoma jo'natamiz' deyiladi",
                        0: "Shartnoma yoki to'lov haqida hech narsa yo'q",
                    },
                },
            ],
        },
        {
            "code": "CL_F",
            "name": "Upsell va Munosabat Mustahkamlash",
            "weight": 0.10,
            "criteria": [
                {
                    "code": "CL_F1",
                    "name": "Qo'shimcha xizmat taklifi",
                    "max_score": 3,
                    "levels": {
                        3: "Asosiy xizmatdan keyin mos qo'shimcha xizmat mohirona taklif qiladi",
                        2: "Upsell urinishi bor, lekin kuchsiz yoki erta",
                        1: "Faqat so'rasa qo'shimcha haqida aytadi",
                        0: "Upsell harakati yo'q",
                    },
                },
                {
                    "code": "CL_F2",
                    "name": "Referral so'rash",
                    "max_score": 3,
                    "levels": {
                        3: "Shartnoma imzolangandan so'ng professional referral so'raydi va motivatsiya keltiradi",
                        2: "Referral so'raydi, lekin noaniq",
                        1: "Umumiy 'do'stlaringizga aytib qo'ying' deyiladi",
                        0: "Referral haqida so'rash yo'q",
                    },
                },
                {
                    "code": "CL_F3",
                    "name": "Munosabatni mustahkamlash",
                    "max_score": 3,
                    "levels": {
                        3: "Mijozni qaror qilgani uchun tabriklab, ishonch mustahkamlaydi; onboarding jarayonini tushuntiradi",
                        2: "Tabrik bor, lekin onboarding noaniq",
                        1: "Faqat 'rahmat' deyiladi",
                        0: "Yakunlash yo'q yoki sovuq tugatish",
                    },
                },
            ],
        },
    ],
}

# ─────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────
RUBRICS: Dict[str, Dict[str, Any]] = {
    "general": GENERAL_RUBRIC,
    "hunter": HUNTER_RUBRIC,
    "closer": CLOSER_RUBRIC,
}

GRADE_THRESHOLDS = [
    (90, "A+"),
    (80, "A"),
    (70, "B"),
    (60, "C"),
    (50, "D"),
    (0,  "F"),
]


def get_rubric(role: str) -> Dict[str, Any]:
    """Role ('general'|'hunter'|'closer') bo'yicha rubrikani qaytarish."""
    return RUBRICS.get((role or "general").lower(), GENERAL_RUBRIC)


def compute_rubric_score(scores: Dict[str, int], role: str = "general") -> Dict[str, Any]:
    """
    Criterion code → 0-3 score dict dan umumiy ball va breakdown hisoblash.

    Args:
        scores: {"A1": 3, "B2": 2, ...}  criterion kodi → ball
        role:   "general" | "hunter" | "closer"

    Returns:
        {
            "overall": 0-100 int,
            "grade":   "A+"|"A"|"B"|"C"|"D"|"F",
            "category_scores": {cat_name: {"earned", "max", "pct", "weight"}},
            "rubric_name": str,
        }
    """
    rubric = get_rubric(role)
    category_scores: Dict[str, Any] = {}
    total_weighted = 0.0
    total_weight = 0.0

    for cat in rubric["categories"]:
        cat_earned = 0
        cat_max = 0
        for criterion in cat["criteria"]:
            code = criterion["code"]
            earned = max(0, min(int(scores.get(code, 0)), criterion["max_score"]))
            cat_earned += earned
            cat_max += criterion["max_score"]

        pct = round(cat_earned * 100 / cat_max) if cat_max else 0
        weight = cat["weight"]
        category_scores[cat["name"]] = {
            "earned": cat_earned,
            "max": cat_max,
            "pct": pct,
            "weight": weight,
        }
        total_weighted += pct * weight
        total_weight += weight

    overall = round(total_weighted / total_weight) if total_weight else 0

    grade = "F"
    for threshold, g in GRADE_THRESHOLDS:
        if overall >= threshold:
            grade = g
            break

    return {
        "overall": overall,
        "grade": grade,
        "category_scores": category_scores,
        "rubric_name": rubric["name"],
    }


def format_rubric_report(scores: Dict[str, int], role: str = "general") -> str:
    """Odam o'qiy oladigan tekstli hisobot."""
    result = compute_rubric_score(scores, role)
    rubric = get_rubric(role)

    lines = [
        f"📊 {result['rubric_name']}",
        f"Umumiy ball: {result['overall']}/100  |  Daraja: {result['grade']}",
        "",
    ]

    for cat in rubric["categories"]:
        cat_data = result["category_scores"].get(cat["name"], {})
        pct = cat_data.get("pct", 0)
        earned = cat_data.get("earned", 0)
        max_s = cat_data.get("max", 0)
        w = int(cat_data.get("weight", 0) * 100)
        emoji = "✅" if pct >= 70 else ("⚠️" if pct >= 50 else "🔴")
        lines.append(f"{emoji} {cat['name']} ({w}%): {earned}/{max_s} ({pct}%)")

    return "\n".join(lines)


def build_ai_scoring_prompt(transcript: str, role: str = "general") -> str:
    """Gemini/Claude uchun rubrika-asosli scoring prompt."""
    rubric = get_rubric(role)
    criteria_lines = []
    all_codes = []

    for cat in rubric["categories"]:
        criteria_lines.append(f"\n### {cat['name']} (og'irlik: {int(cat['weight']*100)}%)")
        for c in cat["criteria"]:
            all_codes.append(c["code"])
            levels_text = " | ".join(f"{k}:{v[:60]}..." for k, v in sorted(c["levels"].items(), reverse=True))
            criteria_lines.append(f"  {c['code']} — {c['name']}: {levels_text}")

    codes_json = "{" + ", ".join(f'"{code}": <0-3>' for code in all_codes) + "}"

    return (
        f"Siz Jon Branding sotuv trener botisiz.\n"
        f"Quyidagi telefon suhbati transkripsiyasini '{rubric['name']}' mezonlari bo'yicha baholang.\n\n"
        f"MEZONLAR:\n{''.join(criteria_lines)}\n\n"
        f"Har bir mezon uchun 0-3 ball bering.\n"
        f"Faqat JSON qaytaring:\n"
        f'{{"scores": {codes_json},\n'
        f' "summary": "2-3 gapda O\'zbekcha xulosa",\n'
        f' "strengths": ["...", "..."],\n'
        f' "weaknesses": ["...", "..."],\n'
        f' "coaching_tip": "Eng muhim 1 ta tavsiya"\n}}\n\n'
        f"Transkripsiya:\n{transcript}"
    )
