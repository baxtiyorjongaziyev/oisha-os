"""
Psychological Coach & Mindset Barrier Breaker for Sales Reps and Project Managers.
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
    CALL_RELUCTANCE = "call_reluctance"
    REJECTION_FEAR = "rejection_fear"
    PRICE_ANXIETY = "price_anxiety"
    FOLLOWUP_SHAME = "followup_shame"
    OBJECTION_FREEZE = "objection_freeze"
    BAD_NEWS_DELAY = "bad_news_delay"
    SCOPE_CREEP_BILLING = "scope_creep_billing"
    ANGRY_CLIENT_AVOIDANCE = "angry_client_avoidance"
    FINAL_PAYMENT_DEMAND = "final_payment_demand"
    BURNOUT_OVERWHELM = "burnout_overwhelm"


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


def _build_sales_call_reluctance(role: PsychologicalRole, client: str, deal_value: str) -> PsychologicalBreakthrough:
    return PsychologicalBreakthrough(
        role=role, category=FearCategory.CALL_RELUCTANCE,
        fear_label="Qo'ng'iroq qilishdan oldingi ikkilanish (Call Reluctance)",
        worst_case_analysis=f"Hozir {client}ga telefon qilsang eng yomon holatda 'bandman' deydi yoki ko'tarmaydi. Bu o'lim emas!",
        inaction_cost=f"Qilmasang: {client} raqobatchiga ketadi, {deal_value} yo'qotiladi.",
        mindset_shift="Fokusni sotishdan do'stona hol-ahvol so'rashga o'zgartir.",
        micro_script=f"Assalomu alaykum, {client}! Loyihani hozir davom ettiramizmi yoki keyinroqqa qoldiramizmi?",
        action_challenge="3 DAQIQALIK CHALLENGE: Raqamni ter va natijasini yoz!",
    )


def _build_sales_rejection_and_price(cat: FearCategory, role: PsychologicalRole, client: str, deal_value: str) -> PsychologicalBreakthrough:
    if cat == FearCategory.PRICE_ANXIETY:
        return PsychologicalBreakthrough(
            role=role, category=cat, fear_label="Narx aytishdan uyalish/qo'rqish (Price Anxiety)",
            worst_case_analysis=f"Hozir {client} 'Qimmat' desa bu savdolashish boshlanishi demakdir.",
            inaction_cost=f"Arzon sotsang agentlik zarar ko'radi, {deal_value} yo'qotiladi.",
            mindset_shift="Biz natija va qiymat sotamiz.",
            micro_script=f"Loyihaning to'liq paketi {deal_value}. Bu sizga qulaymi?",
            action_challenge="Narxni dadil ayt va sukut saqla!",
        )
    return PsychologicalBreakthrough(
        role=role, category=cat, fear_label="Rad etilishdan qo'rqish (Rejection Fear)",
        worst_case_analysis=f"Hozir {client} 'Yo'q' desa — bu ham aniqlik! Vaqting tejaladi.",
        inaction_cost="Soxta umid bilan kun o'tib ketadi.",
        mindset_shift="Rad javobi shaxsingga emas, ayni damdagi vaziyatga berilgan.",
        micro_script=f"Agar hozir vaqti bo'lmasa, qaysi oyda qayta bog'lansak qulay bo'ladi?",
        action_challenge="Rad javobini yengish uchun darhol keyingi lidga o't!",
    )


def _build_pm_fear(cat: FearCategory, role: PsychologicalRole, client: str) -> PsychologicalBreakthrough:
    if cat == FearCategory.BAD_NEWS_DELAY:
        return PsychologicalBreakthrough(
            role=role, category=cat, fear_label="Muddat kechikishi va kechikishni aytishdan qo'rqish (Bad News Delay)",
            worst_case_analysis=f"Hozir {client}ga oxirgi daqiqada aytgandan ko'ra hozir aytish 10x yaxshi.",
            inaction_cost="Mijoz ishonchi mutlaqo yo'qoladi.",
            mindset_shift="Muammoni yechim bilan birga olib bor.",
            micro_script=f"Hurmatli {client}, sifatni kafolatlash uchun bizga yana 1 kun kerak bo'lmoqda.",
            action_challenge="Mijozga darhol yangilangan muddatni xabar qil!",
        )
    return PsychologicalBreakthrough(
        role=role, category=cat, fear_label="Mijoz bilan ziddiyat (Client Friction)",
        worst_case_analysis=f"Hozir {client}ning e'tirozini professional eshitib yechim berish mumkin.",
        inaction_cost="Katta janjal va loyiha buzilishiga olib keladi.",
        mindset_shift="Mijoz g'azabi brendga emas, vaziyatga qaratilgan.",
        micro_script="Sizni tushunib turibman, keling birgalikda yechim topamiz.",
        action_challenge="Mijoz bilan sovuqqonlik bilan bog'lan va dalillarni taqdim et.",
    )


class PsychologicalCoach:
    """Oisha-OS Psixologik Kouchi."""

    FEAR_PATTERNS = [
        (r"qo.shimcha pul|yangi narsa.*qo.sh|scope creep|qo.shimcha to.lov", FearCategory.SCOPE_CREEP_BILLING, PsychologicalRole.PM),
        (r"asabiy|jahli chiqqan|janjal|baqirdi|urishdi|angry", FearCategory.ANGRY_CLIENT_AVOIDANCE, PsychologicalRole.PM),
        (r"kechik|ulgurmay|kechikish|vaqtida bitma|topshira olmay|kech qol", FearCategory.BAD_NEWS_DELAY, PsychologicalRole.PM),
        (r"narx aytish|qimmat desa|3000\$|narx.*qo.rq|chegirma so.ra", FearCategory.PRICE_ANXIETY, PsychologicalRole.SALES),
        (r"rad et|yo.q de|yoqmasa|rad javob|otkaz", FearCategory.REJECTION_FEAR, PsychologicalRole.SALES),
        (r"telefon|qilolmay|qidir|terolmay|tortin|ikillan|uyal|qo.ng.iroq", FearCategory.CALL_RELUCTANCE, PsychologicalRole.SALES),
    ]

    @classmethod
    def detect_category(cls, text: str, default_role: str = "sales") -> tuple[FearCategory, PsychologicalRole]:
        text_lower = text.lower()
        for pattern, cat, role in cls.FEAR_PATTERNS:
            if re.search(pattern, text_lower):
                return cat, role
        return FearCategory.CALL_RELUCTANCE, (PsychologicalRole.PM if default_role == "pm" else PsychologicalRole.SALES)

    @classmethod
    def deconstruct_fear(
        cls, text: str, role: Optional[str] = None, client_name: Optional[str] = None, context: Optional[Dict[str, Any]] = None
    ) -> PsychologicalBreakthrough:
        context = context or {}
        client = client_name or context.get("client_name") or "[Mijoz ismi]"
        deal_value = context.get("deal_value") or "$2,000 - $5,000"

        category, detected_role = cls.detect_category(text, default_role=role or "sales")
        final_role = PsychologicalRole.PM if role == "pm" else (PsychologicalRole.SALES if role == "sales" else detected_role)

        if category == FearCategory.CALL_RELUCTANCE:
            return _build_sales_call_reluctance(final_role, client, deal_value)
        if category in (FearCategory.REJECTION_FEAR, FearCategory.PRICE_ANXIETY):
            return _build_sales_rejection_and_price(category, final_role, client, deal_value)
        return _build_pm_fear(category, final_role, client)

    @classmethod
    def format_telegram_breakthrough(cls, b: PsychologicalBreakthrough) -> str:
        return (
            f"🧠 **OISHA PSIXOLOGIK KOUCHING** 🛡️\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 **Muammo:** {b.fear_label}\n\n"
            f"☠️ **ENG YOMON STSENARIY:**\n{b.worst_case_analysis}\n\n"
            f"💸 **QILMASLIKNING HAQIQIY NARXI:**\n{b.inaction_cost}\n\n"
            f"💡 **TAFAKKUR BURILISHI (MINDSET SHIFT):**\n{b.mindset_shift}\n\n"
            f"🎯 **MIKRO-SKRIPT:**\n`{b.micro_script}`\n\n"
            f"⚡️ **CHALLENGE:**\n{b.action_challenge}"
        )

    @classmethod
    def roleplay_sparring(cls, role: str = "sales", scenario: str = "", user_reply: Optional[str] = None) -> str:
        if not user_reply:
            return (
                f"🥊 **OISHA SPARRING PARTNER** 🛡️\n"
                f"Siz bilan rolli sparring mashqi boshlandi!\n\n"
                f"Mijoz e'tirozi: 'Sizning taklifingiz va narxingiz juda qimmat, boshqalar arzonroq qilib beradi.'\n"
                f"Mijozga qanday javob berasiz? Javobingizni yozing."
            )
        return (
            f"🥊 **SPARRING TAHLILI VA FEEDBACK** 🛡️\n"
            f"Sizning javobingiz: '{user_reply}'\n\n"
            f"✅ **Kuchli tomoni:** E'tirozni qabul qilib, qiymatga urg'u berdingiz.\n"
            f"🎯 **Tavsiya:** Savol bilan yakunlang: 'Qaysi jihat siz uchun muhimroq: narxmi yoki natija?'"
        )
