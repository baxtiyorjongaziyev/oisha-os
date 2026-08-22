"""
Psychological Coach & Mindset Barrier Breaker for Sales Reps and Project Managers.

Metodologiya:
1. Kognitiv-Xulq-atvor Terapiyasi (CBT) — Kognitiv xatoliklar va katastrofizatsiyani yo'qotish.
2. Stoitsizm (Premeditatio Malorum / Fear Setting) — Eng yomon stsenariyni dekonstruksiya qilish.
3. Inaction Cost — Qilmaslikning og'ir oqibatlarini ochib berish.
4. Micro-Scripts & Sparring — Bosimsiz, 1-2 jumlali aniq ochilish gapi.
5. Micro-Action & Accountability — 3 daqiqalik harakat va natija hisobdorligi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class PsychologicalRole(str, Enum):
    SALES = "sales"
    PM = "pm"
    GENERAL = "general"


class FearCategory(str, Enum):
    # Sales fears
    CALL_RELUCTANCE = "call_reluctance"            # Telefon qilishdan qo'rqish
    REJECTION_FEAR = "rejection_fear"              # "Yo'q" degan javobdan qo'rqish
    PRICE_ANXIETY = "price_anxiety"                # Narx aytishdan uyalish/qo'rqish
    FOLLOWUP_SHAME = "followup_shame"              # Kechikkan/sovugan lidga qayta chiqishdan iymanish
    OBJECTION_FREEZE = "objection_freeze"          # E'tirozlardan qo'rqish / dovdirash
    
    # PM fears
    BAD_NEWS_DELAY = "bad_news_delay"              # Kechikish yoki xatoni aytishdan qo'rqish
    SCOPE_CREEP_BILLING = "scope_creep_billing"    # Bepul ishga "yo'q" deb qo'shimcha to'lov so'rash
    ANGRY_CLIENT_AVOIDANCE = "angry_client_avoidance" # Asabiy mijoz bilan to'qnashuvdan qochish
    FINAL_PAYMENT_DEMAND = "final_payment_demand"  # Qoldiq pulni so'rashdan tortinish
    BURNOUT_OVERWHELM = "burnout_overwhelm"        # Bosim ostida qotib qolish (freeze)


@dataclass(frozen=True)
class PsychologicalBreakthrough:
    role: PsychologicalRole
    category: FearCategory
    fear_label: str
    worst_case_analysis: str
    inaction_cost: str
    mindset_shift: str
    micro_script: str
    action_challenge: str


class PsychologicalCoach:
    """Oisha-OS Psixologik Kouchi va Ruhiy To'siqlarni Yechuvchi Yordamchi."""

    # Kalit so'zlar va kategoriyalarga xaritalash
    FEAR_PATTERNS = [
        # PM patterns (aniqroq bo'lgani uchun oldinroq keladi)
        (r"kechik|ulgurmay|kechikish|vaqtida bitma|topshira olmay|kech qol", FearCategory.BAD_NEWS_DELAY, PsychologicalRole.PM),
        (r"qo'shimcha ish|bepul|scope creep|yana narsa qo'sh|tekinga|qo'shimcha pul|qo'shimcha to'lov", FearCategory.SCOPE_CREEP_BILLING, PsychologicalRole.PM),
        (r"asabiy|jahli chiqqan|baqir|urish|norozi mijoz|shikoyat|janjal", FearCategory.ANGRY_CLIENT_AVOIDANCE, PsychologicalRole.PM),
        (r"qoldiq|oxirgi to'lov|pulni so'ra|akt|yakuniy to'lov|hisobni yop", FearCategory.FINAL_PAYMENT_DEMAND, PsychologicalRole.PM),
        (r"charchadim|ulgurmayapman|boshim qotdi|nima qilishni bilmay|hamma narsa tiqil", FearCategory.BURNOUT_OVERWHELM, PsychologicalRole.PM),

        # Specific Sales patterns (specific reasons first)
        (r"rad et|yo'q de|rad javob|otkaz|yo'q desa|rad qilish", FearCategory.REJECTION_FEAR, PsychologicalRole.SALES),
        (r"narx ayt|qimmat|summa|3000|5000|narxni aytish|chegirma", FearCategory.PRICE_ANXIETY, PsychologicalRole.SALES),
        (r"ancha bo'ldi|esdan chiq|2 hafta|1 oy|qayta yoz|uyalyapman|bezovta qil", FearCategory.FOLLOWUP_SHAME, PsychologicalRole.SALES),
        (r"e'tiroz|o'ylab ko'ramiz|boshqa agentlik|nima deyman", FearCategory.OBJECTION_FREEZE, PsychologicalRole.SALES),
        (r"telefon qil|qo'ng'iroq qil|qilsam nima bo'ladi|qilolmayapman|qo'ng'iroqdan qo'rq|telefon ko'tar|call reluctance", FearCategory.CALL_RELUCTANCE, PsychologicalRole.SALES),
    ]

    @classmethod
    def detect_category(cls, text: str, default_role: str = "sales") -> tuple[FearCategory, PsychologicalRole]:
        lowered = (text or "").lower()
        for pattern, category, role in cls.FEAR_PATTERNS:
            if re.search(pattern, lowered):
                return category, role
        
        # Default fallback
        if default_role.lower() == "pm":
            return FearCategory.BURNOUT_OVERWHELM, PsychologicalRole.PM
        return FearCategory.CALL_RELUCTANCE, PsychologicalRole.SALES

    @classmethod
    def deconstruct_fear(
        cls,
        text: str,
        role: Optional[str] = None,
        client_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> PsychologicalBreakthrough:
        """Qo'rquvni tahlil qilib, 5 bosqichli amaliy psixologik yechim yaratadi."""
        context = context or {}
        client = client_name or context.get("client_name") or "[Mijoz ismi]"
        deal_value = context.get("deal_value") or "$2,000 - $5,000"
        
        explicit_role = PsychologicalRole.PM if role == "pm" else (PsychologicalRole.SALES if role == "sales" else None)
        category, detected_role = cls.detect_category(text, default_role=role or "sales")
        final_role = explicit_role or detected_role

        if category == FearCategory.CALL_RELUCTANCE:
            return PsychologicalBreakthrough(
                role=final_role,
                category=category,
                fear_label="Qo'ng'iroq qilishdan oldingi ikkilanish (Call Reluctance)",
                worst_case_analysis=(
                    f"Hozir {client}ga telefon qilsang eng yomon holatda nima bo'ladi?\n"
                    "1. 'Hozir bandman, keyinroq qiling' deydi.\n"
                    "2. 'Bizga hozir kerak emas' deydi.\n"
                    "3. Go'shakni ko'tarmasligi mumkin.\n"
                    "👉 Shulardan birortasi sen uchun o'limmi yoki agentlik yopiladimi? Yo'q! "
                    "Sen shunchaki 1 daqiqa ichida vaziyatga 100% oydinlik kiritasan va noaniqlik yukidan qutulasan."
                ),
                inaction_cost=(
                    "Agar hozir telefon qilmasang nima bo'ladi?\n"
                    f"• {client} raqobatchiga ketadi yoki muammosi sovuydi.\n"
                    f"• Kutilayotgan {deal_value} daromad yo'qotiladi.\n"
                    "• Sen esa butun kun 'qilsammikan yo qilmasammikan' deb o'zingni ruhiy charchatib yurasan."
                ),
                mindset_shift=(
                    "🎯 **Fokusni o'zgartir:** Senga hozir nimadir 'sotish' yoki majburlash shart emas. "
                    "Sening maqsading — do'stona tarzda ularning rejasini bilish va yordam berishga tayyorligingni bildirish."
                ),
                micro_script=(
                    f"📞 **Telefonni olib aytadigan 1-jumlang:**\n"
                    f"💬 *'Assalomu alaykum, {client}! Jon Branding'dan bog'lanyapman. Sizni ko'p vaqtingizni olmayman, "
                    "faqat bitta qisqa savol: loyihani hozir davom ettiramizmi yoki keyinroqqa qoldiramizmi? Shunga qarab rejamizni to'g'rilab olmoqchi edik.'*"
                ),
                action_challenge=(
                    "⏱ **3 DAQIQALIK CHALLENGE:**\n"
                    f"Hozir chuqur nafas ol, raqamni ter va tugmani bos! Qo'ng'iroqdan keyin menga **'Qildim'** deb yoz. Qani, ketdik!"
                ),
            )

        elif category == FearCategory.REJECTION_FEAR:
            return PsychologicalBreakthrough(
                role=final_role,
                category=category,
                fear_label="Rad etilishdan qo'rqish (Fear of Rejection / 'Yo'q' deyilishi)",
                worst_case_analysis=(
                    f"Mijoz 'Yo'q, biz boshlamaymiz' desa nima bo'ladi?\n"
                    "Bu sening shaxsingga emas, mijozning ayni damdagi holatiga berilgan javob. "
                    "'Yo'q' javobi — bu ham aniqlik! Sen vaqtingni bo'sh umidlarga sarflamay, real xaridorga o'tasan."
                ),
                inaction_cost=(
                    "Rad javobidan qo'rqib jim o'tirsang: soxta umid bilan kun o'tadi, pipeline tiqilib qoladi, yangi lidlarga kuch qolmaydi."
                ),
                mindset_shift=(
                    "💡 *'Har bir 'Yo'q' javobi — seni keyingi 'Ha' ga bitta qadam yaqinlashtiradi.'* "
                    "Top sotuvchilar eng ko'p 'Yo'q' eshitadiganlardir."
                ),
                micro_script=(
                    f"💬 *'Tushundim, {client}. Ochiq aytganingiz uchun rahmat! Agar kelgusida brending yoki dizayn kerak bo'lsa, "
                    "biz har doim aloqadamiz. Ishlaringizga omad!'*"
                ),
                action_challenge=(
                    "🚀 Hozir qo'ng'iroq qil. Agar 'Yo'q' desa ham — o'zingga 'Bitta xavotirdan qutuldim!' deb baho ber!"
                ),
            )

        elif category == FearCategory.PRICE_ANXIETY:
            return PsychologicalBreakthrough(
                role=final_role,
                category=category,
                fear_label="Narx aytishdan uyalish va qo'rqish (Price Anxiety)",
                worst_case_analysis=(
                    f"Narxni aytganingda ({deal_value}) 'Qimmat-ku!' desa nima bo'ladi?\n"
                    "Bu norozilik emas — bu tabiiy savdo signali! Mijoz shunchaki 'Nimaga bu narxga arziydi?' deb so'ramoqda."
                ),
                inaction_cost=(
                    "Narxni past aytsang yoki qo'rqib avtomat chegirma bersang: jamoa kam foyda oladi, "
                    "mijoz esa arzon xizmatni qadrlamaydi."
                ),
                mindset_shift=(
                    "💎 Biz rasm chizmaymiz — biz mijozning biznesiga yuz minglab dollar olib keladigan qiyofa va tizim yaratamiz. "
                    "Sening narxing uning foydasi oldida arzimas."
                ),
                micro_script=(
                    f"💬 *'Loyiha narxi {deal_value}. Bunga to'liq pozitsiyalash, brend strategiya va natija kafolati kiradi. "
                    "Biz arzon qilib yarim yo'lda tashlab ketmaymiz, to'liq ishlaydigan tizim topshiramiz. Qaysi to'lov grafigi sizga qulay?'*"
                ),
                action_challenge=(
                    "🔥 Narxni dadil, ovozingni pasaytirmay ayt va jim tur! Birinchi gapirgan odam yutqazadi."
                ),
            )

        elif category == FearCategory.FOLLOWUP_SHAME:
            return PsychologicalBreakthrough(
                role=final_role,
                category=category,
                fear_label="Kechikkan lidga qayta chiqishdan iymanish (Follow-up Shame)",
                worst_case_analysis=(
                    f"2-3 hafta oldingi lidga hozir yozsang yoki telefon qilsang nima deydi?\n"
                    "'Nimaga buncha kech qildingiz?' deydimi? Aksincha, 'Yaxshi ham eslatdingiz, o'zim ham ulgurmay turgandim' deydi 80% holatda!"
                ),
                inaction_cost=(
                    "Uyalib yozmasang: mijoz 'bularga qiziq emas ekan' deb boshqa agentlikka buyurtma berib yuboradi."
                ),
                mindset_shift=(
                    "🤝 Bu bezovta qilish emas — bu mijozga g'amxo'rlik qilish va professionallik."
                ),
                micro_script=(
                    f"💬 *'Assalomu alaykum, {client}! O'tgan safar rejangizni muhokama qilgandik. Ishlar ko'pligi sababli oraga biroz vaqt tushdi. "
                    "Hozir loyiha bo'yicha qaysi bosqichdasiz? Qisqa yangilab olsak bo'ladimi?'*"
                ),
                action_challenge=(
                    "⚡️ Hozir darhol ushbu xabarni yubor yoki telefon qil. 2 daqiqa kifoya!"
                ),
            )

        elif category == FearCategory.BAD_NEWS_DELAY:
            return PsychologicalBreakthrough(
                role=final_role,
                category=category,
                fear_label="PM: Muddat kechikishi yoki xatoni aytishdan qo'rqish (Delay Anxiety)",
                worst_case_analysis=(
                    f"Kechikishni hozir aytmasang va oxirgi kuni aytsang nima bo'ladi?\n"
                    "Mijozning g'azabi 10 barobar kuchli bo'ladi va ishonch butunlay yo'qoladi!\n"
                    "Agar HOZIR aytsang: 'Kechikish bor, lekin sababi sifatni kuchaytirish va mana yechim' desang, mijoz seni professional sifatida hurmat qiladi."
                ),
                inaction_cost=(
                    "Jim o'tirish — halokatli bomba taymerini yoqish bilan barobar. Kechikish baribir fosh bo'ladi!"
                ),
                mindset_shift=(
                    "🛡 **Proaktivlik — eng yuqori professionalizm.** Xabarni kechiktirish emas, yechim bilan birga oldindan borish kerak."
                ),
                micro_script=(
                    f"💬 *'Assalomu alaykum, {client}! Loyihangiz bo'yicha oraliq tahlil qildik. Sifatni maksimal darajaga yetkazish uchun "
                    "bizga qo'shimcha 2 kun kerak bo'lmoqda. Buning evaziga sizga to'liq tekshirilgan va mukammal natija topshiramiz. "
                    "Yangi topshirish sanasi: [Sana]. Buni qulay vaqtda tasdiqlab bersangiz.'*"
                ),
                action_challenge=(
                    "🚨 Hozir yoz yoki qo'ng'iroq qil. Yechim bilan borgan PM hech qachon yutqazmaydi!"
                ),
            )

        elif category == FearCategory.SCOPE_CREEP_BILLING:
            return PsychologicalBreakthrough(
                role=final_role,
                category=category,
                fear_label="PM: Qo'shimcha talablarga pul so'rashdan tortinish (Scope Creep)",
                worst_case_analysis=(
                    "Mijozga 'Bu qo'shimcha ish, shuning uchun qo'shimcha to'lov bo'ladi' desang xafa bo'ladimi?\n"
                    "Yo'q! Biznesmenlar hamma narsa resurs va xarajat ekanini juda yaxshi tushunadi. "
                    "Agar bepul qilib bersang — keyin yana 20 ta tekin talab qo'yadi va loyiha zarariga ishlaydi."
                ),
                inaction_cost=(
                    "Dizaynerlar tekinga ishlab charchaydi, loyiha vaqti cho'ziladi, agentlik foydasi nolga tushadi."
                ),
                mindset_shift=(
                    "⚖️ **Chegara qo'yish — hurmat garovi.** Asosiy shartnomani himoya qilish PMning birinchi vazifasidir."
                ),
                micro_script=(
                    f"💬 *'{client}, bu ajoyib g'oya! Lekin bu bizning asosiy shartnomamiz doirasidan tashqarida. "
                    "Buni alohida mini-vazifa sifatida qo'shishimiz mumkin, bahosi: [Summa], muddati: [Kun]. "
                    "Buni alohida qilamizmi yoki asosiy ishni tugatib keyin o'tamizmi?'*"
                ),
                action_challenge=(
                    "💪 Chegarani muloyim, lekin qat'iy qilib belgilab qo'y!"
                ),
            )

        elif category == FearCategory.ANGRY_CLIENT_AVOIDANCE:
            return PsychologicalBreakthrough(
                role=final_role,
                category=category,
                fear_label="PM/Sales: Asabiy yoki jahli chiqqan mijoz bilan to'qnashuv",
                worst_case_analysis=(
                    f"Jahli chiqqan {client}ga qo'ng'iroq qilsang nima bo'ladi?\n"
                    "Avval biroz his-tuyg'usini chiqaradi. Agar sen xotirjam tinglab, 'Sizni tushundim, keling hozir buni tuzatamiz' desang, "
                    "u 3 daqiqada tinchlanadi va senga eng sadoqatli mijozga aylanadi!"
                ),
                inaction_cost=(
                    "Chatda qochib yursang — mijoz o'zini mensilmagandek his qiladi va shartnomani bekor qilishgacha boradi."
                ),
                mindset_shift=(
                    "🧯 Olovni o'chirish uchun o't o'chiruvchi bo'l. Mijozning jahlini shaxsiy deb bilma — u o'z loyihasidan xavotirda."
                ),
                micro_script=(
                    f"💬 *'Assalomu alaykum, {client}. Vaziyatdan to'liq xabardorman va sizning xavotiringizni 100% tushunib turibman. "
                    "Men shaxsan buni nazoratga oldim. Keling, 5 daqiqa ichida buni qanday to'g'irlashimizni kelishib olamiz.'*"
                ),
                action_challenge=(
                    "🎯 Go'shakni ol, xotirjam chuqur nafas ol va faqat tingla, bahslashma. Yechim ber!"
                ),
            )

        elif category == FearCategory.FINAL_PAYMENT_DEMAND:
            return PsychologicalBreakthrough(
                role=final_role,
                category=category,
                fear_label="PM/Sales: Yakuniy to'lov va hisobni yopishni so'rashdan tortinish",
                worst_case_analysis=(
                    "Ish bitgandan keyin 'Qoldiq to'lovni o'tkazib bersangiz' desang nima deb o'ylaydi?\n"
                    "Hech narsa yomon o'ylamaydi! Siz halol mehnatingiz haqini so'rayapsiz. Bu dunyodagi eng normal biznes jarayoni."
                ),
                inaction_cost=(
                    "To'lovni o'z vaqtida so'ramasang — kassa bo'shab qoladi, xodimlar oyligi kechikadi."
                ),
                mindset_shift=(
                    "💰 Xizmat ko'rsatildimi — to'lov olinishi shart. Bu biznes odobi."
                ),
                micro_script=(
                    f"💬 *'{client}, barcha ishlarni muvaffaqiyatli yakunladik va materiallarni topshirdik! "
                    "Shartnoma bo'yicha yakuniy hisob-fakturani yuboryapman. Qoldiq to'lovni bugun tasdiqlab bersangiz, "
                    "yakuniy manba fayllarni to'liq sizga ochib beramiz. Hamkorlik uchun rahmat!'*"
                ),
                action_challenge=(
                    "📑 Fakturani yubor va to'lovni talab qil!"
                ),
            )

        else: # BURNOUT_OVERWHELM or fallback
            return PsychologicalBreakthrough(
                role=final_role,
                category=category,
                fear_label="Ortiqcha yuklama va bosim ostida qotib qolish (Burnout & Freeze)",
                worst_case_analysis=(
                    "Hamma ishlar birdaniga yig'ilib qolganda vahimaga tushsang nima bo'ladi?\n"
                    "Miyang bloklanadi va hech qaysi ish bitmaydi. "
                    "Lekin hozir hammasini emas, faqat BITTA eng muhim ishni (Frog) tanlab qilsang — 30 daqiqada nazorat qaytadi!"
                ),
                inaction_cost=(
                    "Vahimada qolsang kun boy beriladi va ertaga yuk 2 barobar ko'payadi."
                ),
                mindset_shift=(
                    "🧘 **Filni bo'laklab yeyish kerak.** Hozir 10 ta ishni o'ylama. Faqat keyingi 15 daqiqadagi bitta qadamga e'tibor qarat."
                ),
                micro_script=(
                    "📋 *'Hozir qog'oz ol va faqat eng muhim 1 ta ishni yoz. Qolganlarini bir chetga sur.'*"
                ),
                action_challenge=(
                    "⏳ Taymerni 15 daqiqaga qo'y va faqat shu 1 ta vazifani bajar!"
                ),
            )

    @classmethod
    def format_telegram_breakthrough(cls, breakthrough: PsychologicalBreakthrough) -> str:
        """Telegram uchun chiroyli, emotsional va professional formatlangan javob matni."""
        return (
            f"🧠 **OISHA PSIXOLOGIK KOUCHING & MINDSET**\n"
            f"🎯 **Holat:** `{breakthrough.fear_label}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔍 **1. ENG YOMON STSENARIY TAHLILI (Hozir qilsang nima bo'ladi?):**\n"
            f"{breakthrough.worst_case_analysis}\n\n"
            f"⏳ **2. QILMASLIKNING HAQIQIY NARXI (Qilmasang nima bo'ladi?):**\n"
            f"{breakthrough.inaction_cost}\n\n"
            f"{breakthrough.mindset_shift}\n\n"
            f"{breakthrough.micro_script}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{breakthrough.action_challenge}"
        )

    @classmethod
    def roleplay_sparring(
        cls,
        role: str,
        scenario: str,
        user_reply: Optional[str] = None,
    ) -> str:
        """Tezkor e'tiroz yoki asabiy mijoz simulyatsiyasi (Sparring)."""
        role_label = "Project Manager" if role.lower() == "pm" else "Sotuvchi"
        
        if not user_reply:
            # Stsenariyni boshlash
            return (
                f"🥊 **OISHA SPARRING PARTNER [{role_label}]**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎭 **Stsenariy:** *{scenario or 'Qimmat / Vaqtim yoʻq eʼtirozi'}*\n\n"
                "Men — qattiqqo'l mijozman. Mana mening e'tirozim:\n"
                "🗣 *'Eshitdim taklifingizni. Lekin narxingiz juda qimmat, bozorda boshqalar 2 barobar arzonga qilib beryapti. Nimaga sizdan olishim kerak?'*\n\n"
                "👉 **Sening navbating:** Bunga nima deb javob berasan? Javobingni yoz, men xatolaringni to'g'rilab beraman!"
            )
        
        # Javobni tahlil qilish
        return (
            f"🥊 **SPARRING TAHLILI VA FEEDBACK**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 **Sening javobing:** *\"{user_reply}\"*\n\n"
            "✅ **Kuchli tomoni:** Suhbatni to'xtatmay, dialogda qolding.\n"
            "⚠️ **Kouching maslahati:** Narxni himoya qilishga shoshilma, avval mijozning qiymat va sifat mezonini ochib ol:\n"
            "💡 *\"To'g'ri, bozorda arzonroq variantlar bor. Lekin siz uchun faqat narx muhimmi yoki natija beradigan, xatosiz ishlaydigan brending kerakmi?\"*\n\n"
            "🔥 Endi haqiqiy mijozga qo'ng'iroq qilishga tayyorsan! Raqamni ter!"
        )
