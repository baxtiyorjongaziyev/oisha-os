"""
Situational Morning Mindset Boost Builder for Oisha-OS.

Generates dynamic, non-repetitive daily psychological coaching messages
based on live operational indicators (AmoCRM leads/tasks, Airtable/DB project
deadlines, call quality analytics, and weekday cadence).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


WEEKDAY_CADENCE: Dict[int, Tuple[str, str]] = {
    0: ("Dushanba — Haftalik Sprint Starti", "Haftani birinchi qo'ng'iroqdan qo'rqmasdan, yuqori temp bilan boshlash"),
    1: ("Seshanba — Chuqur Diagnostika Kuni", "Mijoz og'rig'ini aniqlash va 3+ daqiqalik sifatli muloqot qurish"),
    2: ("Chorshanba — Hafta Ekvatori va Tozalash", "Qotib qolgan bitimlarni uyg'otish va voronkani harakatga keltirish"),
    3: ("Payshanba — E'tirozlarni Sindirish Kuni", "Narx va muddat bo'yicha ikkilanayotgan mijozlarga 10x qiymat ko'rsatish"),
    4: ("Juma — Haftalik Closing va Marra", "Ochiq muzokaralarni aniq qaror, shartnoma va to'lov bilan yakunlash"),
    5: ("Shanba — Qoldiq Zaxira va Tahlil", "Hafta davomida ulgurilmagan mijozlar bilan bog'lanish va keyingi haftaga zamin"),
    6: ("Yakshanba — Strategik Fokus", "Yangi haftaning eng muhim 3 ta bitimini oldindan nishonga olish"),
}


@dataclass(frozen=True)
class MindsetTheme:
    code: str
    title: str
    golden_rules: Tuple[Tuple[str, str], ...]
    default_tasks: Tuple[Tuple[str, str, str], ...]
    closings: Tuple[str, ...]


THEMES: Dict[str, MindsetTheme] = {
    "stagnation_breaker": MindsetTheme(
        code="stagnation_breaker",
        title="Qo'ng'iroq Kechiktirishni Sindirish (Call Reluctance Breaker)",
        golden_rules=(
            (
                "Eng yomon qaror — qo'ng'iroq qilmaslik va kechiktirishdir. Noaniqlik energiyani yeydi, harakat esa qo'rquvni yo'qotadi!",
                "Mijozning 'Yo'q' yoki 'Hozir emas' degan javobi — mag'lubiyat emas, vaqtingizni tejaydigan aniqlikdir!",
            ),
            (
                "24 soatdan ortiq jim qolgan lid har soatda sovib boradi — birinchi bo'lib aloqaga chiqqan g'olib bo'ladi.",
                "Ideal paytni kutmang: 60 soniyalik samimiy qo'ng'iroq 3 kunlik sukutdan 10 barobar kuchli!",
            ),
            (
                "Telefon qilishdan oldingi hayajon faqat birinchi 'Alo' deyilguncha davom etadi — raqamni tering!",
                "Sotishga urinmang, mijozning bugungi holatini aniqlashtirish uchun bog'laning.",
            ),
        ),
        default_tasks=(
            (
                "24 soatdan ortiq harakatsiz yotgan eng yirik lidingizni oching va soat 10:30 gacha raqamini tering.",
                "Uzoq javob bermayotgan mijozga yozish o'rniga to'g'ridan-to'g'ri qo'ng'iroq qilib: 'Loyihani davom ettiramizmi yoki to'xtatamizmi?' deb so'rang.",
                "Har bir suhbat yakunida keyingi aloqa vaqtini CRM vazifasiga aniq soat bilan muhrlang.",
            ),
            (
                "Kecha ko'tarmagan mijozlarga ertalabki yangi energiya bilan qayta qo'ng'iroq qiling.",
                "Eng ko'p tortinayotgan 1 ta 'og'ir' mijozingiz bilan 3 daqiqalik ochiq suhbat o'tkazing.",
                "Voronkada javobsiz osilib turgan bitimlarni 'keyingi qadam' yoki 'yopilgan' statusiga aniqlashtiring.",
            ),
        ),
        closings=(
            "Bugun sukutni sindiramiz — har bir terilgan raqam yangi imkoniyat! Olg'a!",
            "Birinchi 30 daqiqada eng qiyin qo'ng'iroqni bajaring, qolgan kun yengil o'tadi!",
        ),
    ),
    "deadline_shield": MindsetTheme(
        code="deadline_shield",
        title="Proaktiv Mas'uliyat va Muddat Himoyasi (PM & SLA Shield)",
        golden_rules=(
            (
                "Kechikishni yashirish — soatli bomba qo'yish demakdir. Proaktivlik esa professionalizmning eng yuqori belgisidir!",
                "Mijoz g'azabi shaxsingizga emas, mavhumlikka qaratilgan — unga aniq reja va muddat bering.",
            ),
            (
                "Muammoni hech qachon yechimsiz aytmang: mijozga 'kechikdik' emas, 'sifat uchun A va B yechim bor' deb chiqing.",
                "Qo'shimcha ish (scope creep) uchun chegara qo'yish mijozni uzoqlashtirmaydi, balki ekspert sifatida hurmat uyg'otadi.",
            ),
        ),
        default_tasks=(
            (
                "Muddati yaqinlashgan yoki kechikayotgan loyiha mijoziga 12:00 gacha o'zingiz birinchi bo'lib status va yechim yuboring.",
                "Muddati o'tgan CRM vazifalarni birma-bir yopib, har bir mijozga aniq javob qaytaring.",
                "Qo'shimcha talab chiqqan loyihalarda darhol yangi muddat va byudjet chegarasini diplomatik kelishib oling.",
            ),
            (
                "Bugun topshirilishi kerak bo'lgan ishlarni ertalabdan jamoa bilan tekshirib, xavfli nuqtalarni oldindan yoping.",
                "Norozilik bildirgan yoki kutib qolgan mijoz bilan yozishma emas, ovozli muloqot orqali ishonchni tiklang.",
                "Har bir aktiv loyiha bo'yicha mijozga qisqa 'oraliq natija' yuborib, xotirjamlik bering.",
            ),
        ),
        closings=(
            "Intizom va ochiq muloqot — Jon Branding ishonchining poydevori! Kuchli bo'ling!",
            "Muammodan qochmaymiz, uni yechim bilan boshqaramiz! Bugun tartib va aniqlik kuni!",
        ),
    ),
    "call_quality_focus": MindsetTheme(
        code="call_quality_focus",
        title="Chuqur Diagnostika va Sifatli Muloqot (3+ Daqiqa Standarti)",
        golden_rules=(
            (
                "30 soniyalik 'salom-alik' sotuv emas! Mijozning haqiqiy biznes og'rig'i faqat 3-daqiqadan keyin ochiladi.",
                "Mijozga narx aytishdan oldin uning muammosini o'zidan yaxshiroq tushunib oling — shunda narx ikkinchi darajaga tushadi.",
            ),
            (
                "Kim savol bersa — suhbatni o'sha boshqaradi. Monolog o'qimang, mijozni gapirtiradigan ochiq savollar bering!",
                "Har bir rad javobi ortida aytilmagan shubha yotadi — shu shubhani topgan sotuvchi bitimni yopadi.",
            ),
        ),
        default_tasks=(
            (
                "Bugun har bir mijoz bilan suhbatda kamida 3 ta ochiq diagnostika savolini bering (Hozir sotuv qanday? Asosiy to'siq nima?).",
                "Suhbat davomiyligini 3+ daqiqaga yetkazib, mijozning asl maqsadini aniqlamasdan narxga o'tmang.",
                "Kunlik 50+ sifatli suhbat marrasini bajarish uchun ertalab 10:00 dan ritmga kiring.",
            ),
            (
                "Mijoz 'O'ylab ko'raman' desa, darhol: 'Qaror qabul qilishda sizni eng ko'p nima ikkilantiryapti?' deb aniqlashtiring.",
                "Har bir suhbatda Jon Branding keys va natijalaridan aniq 1 ta misol keltiring.",
                "Qisqa uzilib qolgan qo'ng'iroqlarni tahlil qilib, kirish jumlangizni yanada qiziqarli qiling.",
            ),
        ),
        closings=(
            "Bugun son bilan birga sifatda ham rekord qo'yamiz! Har bir suhbat — san'at asari bo'lsin!",
            "Mijozni chin dildan eshitgan mutaxassisga mijozning o'zi sotib olishni xohlaydi! Olg'a!",
        ),
    ),
    "closing_confidence": MindsetTheme(
        code="closing_confidence",
        title="Qiymatga Ishonch va Dadil Closing (Price & Deal Mastery)",
        golden_rules=(
            (
                "Narx aytishdan uyalmang — siz xarajat emas, mijoz biznesini 10x o'stiradigan strategik aktiv sotyapsiz!",
                "Mijoz 'Qimmat' desa, bu rad javobi emas — bu 'Menga shu narxga arziydigan qiymatni isbotlab ber' degan so'rovdir.",
            ),
            (
                "Narxni aytgandan keyin birinchi bo'lib gapirgan odam yutqazadi: summani dadil ayting va sokinlik bilan mijoz javobini kuting.",
                "Chegirma berishga shoshilmang — qiymatni himoya qilish brendimiz va mehnatingiz qadrini belgilaydi.",
            ),
        ),
        default_tasks=(
            (
                "KP yuborilgan va qaror kutayotgan 3 ta issiq mijozga bog'lanib, shartnoma sanasini aniq belgilang.",
                "Narx aytayotganda ovozingizdagi ikkilanishni yo'qoting: paket qiymatini biznes foydasi bilan bog'lab tushuntiring.",
                "Bugun kamida 1 ta osilib turgan muzokarani aniq to'lov yoki uchrashuv kelishuvi bilan yakunlang.",
            ),
            (
                "Katta chekli mijozlarga qo'ng'iroq qilishni kechga qoldirmang — eng yuqori energiyangizni eng yirik bitimlarga bering.",
                "Mijoz e'tiroz bildirganda himoyalanmang, 'Tushunaman, keling hisoblab ko'ramiz...' deb ROI tilida gaplashing.",
                "Yopilgan bitimlardan darhol tavsiya (referral) yoki keyingi bosqich (upsell) imkoniyatini so'rang.",
            ),
        ),
        closings=(
            "Keling, bugun natijalar va yopilgan bitimlar rekordini yangilaymiz! Olg'a!",
            "O'z qiymatiga ishongan jamoani hech qanday e'tiroz to'xtata olmaydi! Zafar sizniki!",
        ),
    ),
}


def _format_money(amount: float) -> str:
    val = float(amount or 0)
    if val <= 0:
        return ""
    if val >= 1_000_000:
        return f"{val:,.0f} so'm".replace(",", " ")
    return f"${val:,.0f}"


def select_situational_theme(
    ctx: Dict[str, Any], now: datetime
) -> Tuple[MindsetTheme, str]:
    """Metrics va hafta kuniga qarab eng dolzarb psixologik mavzuni tanlash."""
    stagnated = int(ctx.get("stagnated_count") or 0)
    overdue_proj = int(ctx.get("overdue_projects_count") or 0)
    overdue_tasks = int(ctx.get("overdue_tasks_count") or 0)
    recent_calls = int(ctx.get("recent_calls_count") or 0)
    avg_score = float(ctx.get("avg_call_score") or 0.0)
    solid_calls = int(ctx.get("solid_calls_count") or 0)
    active_leads = int(ctx.get("active_leads_count") or 0)
    won_recent = int(ctx.get("won_recent_count") or 0)

    if overdue_proj > 0 or overdue_tasks >= 5:
        reason = (
            f"Muddati xavf ostidagi loyihalar ({overdue_proj} ta) va kechikkan vazifalarni "
            "proaktiv yechim bilan yopish rejimi."
        )
        return THEMES["deadline_shield"], reason

    if stagnated >= 3 or (stagnated > 0 and active_leads == 0):
        reason = (
            f"CRM da {stagnated} ta lid 24+ soatdan beri harakatsiz — "
            "qo'ng'iroqdan ikkilanishni sindirish va mijozlarni uyg'otish rejimi."
        )
        return THEMES["stagnation_breaker"], reason

    if recent_calls > 0 and (avg_score > 0 and avg_score < 65 or solid_calls < 5):
        reason = (
            f"So'nggi suhbatlar tahlili (sifat: {avg_score:.0f}/100, 3+ daq suhbat: {solid_calls} ta) — "
            "chuqur diagnostika va sifatli muloqotga o'tish rejimi."
        )
        return THEMES["call_quality_focus"], reason

    if won_recent > 0 or active_leads >= 10 or now.weekday() in (3, 4):
        reason = (
            "Voronkadagi aktiv bitimlarni dadil narx aytish va aniq qaror bilan "
            "shartnomaga aylantirish (Closing) rejimi."
        )
        return THEMES["closing_confidence"], reason

    ordered_keys = [
        "stagnation_breaker",
        "call_quality_focus",
        "closing_confidence",
        "deadline_shield",
    ]
    theme_key = ordered_keys[now.toordinal() % len(ordered_keys)]
    _, weekday_desc = WEEKDAY_CADENCE.get(now.weekday(), WEEKDAY_CADENCE[0])
    return THEMES[theme_key], f"{weekday_desc}."


def build_metrics_lines(ctx: Dict[str, Any]) -> List[str]:
    """Faqat real tekshirilgan ko'rsatkichlar mavjud bo'lganda vaziyat blokini tuzish."""
    lines: List[str] = []

    if "stagnated_count" in ctx and ctx["stagnated_count"] is not None:
        stag_count = int(ctx["stagnated_count"])
        top_lead = ctx.get("top_stagnated_lead")
        top_val = ctx.get("top_stagnated_value")
        detail = f" (fokus: *{top_lead}*" + (f", {top_val})" if top_val else ")") if top_lead else ""
        lines.append(f"• ⏳ 24s+ harakatsiz lidlar: **{stag_count} ta**{detail}")

    if "active_leads_count" in ctx and ctx["active_leads_count"] is not None:
        act_count = int(ctx["active_leads_count"])
        pipe_str = _format_money(float(ctx.get("pipeline_value") or 0))
        pipe_part = f" (qiymati: **{pipe_str}**)" if pipe_str else ""
        lines.append(f"• 💼 Aktiv bitimlar (Pipeline): **{act_count} ta**{pipe_part}")

    if int(ctx.get("won_recent_count") or 0) > 0:
        lines.append(f"• 🏆 Yangi yopilgan bitimlar (Won): **{int(ctx['won_recent_count'])} ta**")

    if int(ctx.get("overdue_tasks_count") or 0) > 0:
        lines.append(f"• 📌 Muddati o'tgan CRM vazifalar: **{int(ctx['overdue_tasks_count'])} ta**")

    if "overdue_projects_count" in ctx and ctx["overdue_projects_count"] is not None:
        ov_proj = int(ctx["overdue_projects_count"])
        if ov_proj > 0:
            top_proj = ctx.get("top_overdue_project")
            proj_detail = f" (*{top_proj}*)" if top_proj else ""
            lines.append(f"• 🛡 Muddati xavf ostidagi loyihalar: **{ov_proj} ta**{proj_detail}")
        elif int(ctx.get("active_projects_count") or 0) > 0:
            lines.append(f"• 🏗 Jarayondagi aktiv loyihalar: **{int(ctx['active_projects_count'])} ta** (kechikishsiz)")

    if int(ctx.get("recent_calls_count") or 0) > 0:
        calls = int(ctx["recent_calls_count"])
        solid = int(ctx.get("solid_calls_count") or 0)
        score = float(ctx.get("avg_call_score") or 0.0)
        score_part = f" | O'rtacha ball: **{score:.0f}/100**" if score > 0 else ""
        lines.append(
            f"• 📞 So'nggi qo'ng'iroqlar: **{calls} ta** (3+ daq sifatli: **{solid} ta**{score_part})"
        )

    return lines


def build_situational_tasks(
    theme: MindsetTheme, ctx: Dict[str, Any], seed: int
) -> List[str]:
    """Vaziyat ko'rsatkichlariga moslashtirilgan 3 ta aniq kunlik vazifa."""
    base_triplet = list(theme.default_tasks[seed % len(theme.default_tasks)])

    stagnated = int(ctx.get("stagnated_count") or 0)
    top_lead = ctx.get("top_stagnated_lead")
    overdue_proj = int(ctx.get("overdue_projects_count") or 0)
    top_proj = ctx.get("top_overdue_project")
    overdue_tasks = int(ctx.get("overdue_tasks_count") or 0)
    recent_calls = int(ctx.get("recent_calls_count") or 0)
    solid_calls = int(ctx.get("solid_calls_count") or 0)
    active_leads = int(ctx.get("active_leads_count") or 0)

    if stagnated > 0:
        lead_ref = f"*{top_lead}* boshchiligidagi " if top_lead else ""
        base_triplet[0] = (
            f"CRM dagi {lead_ref}**{stagnated} ta** harakatsiz lidga 11:00 gacha "
            "qo'ng'iroq qilib, aniq qaror ('davom ettiramizmi yoki yopamizmi?') oling."
        )

    if overdue_proj > 0:
        proj_ref = f" (*{top_proj}*)" if top_proj else ""
        base_triplet[1] = (
            f"Muddati kechikayotgan **{overdue_proj} ta** loyiha{proj_ref} bo'yicha "
            "mijoz kutmasidan oldin yechim va yangilangan reja bilan aloqaga chiqing."
        )
    elif overdue_tasks > 0:
        base_triplet[1] = (
            f"CRM da muddati o'tgan **{overdue_tasks} ta** vazifani tushlikkacha "
            "to'liq yopib, har bir bitimga yangi keyingi qadam belgilang."
        )

    if recent_calls > 0 and solid_calls < 20:
        target_solid = max(solid_calls + 10, 25)
        base_triplet[2] = (
            f"Bugun kamida **{target_solid} ta** 3+ daqiqalik chuqur suhbat o'tkazing — "
            "mijoz og'rig'ini ochmasdan narx aytishga shoshilmang!"
        )
    elif active_leads > 0:
        base_triplet[2] = (
            f"Aktiv voronkadagi **{active_leads} ta** bitim ichidan eng issiq 3 tasiga "
            "bugun dadil narx va shartnoma muddatini taklif qiling — 10x qiymat beryapsiz!"
        )

    return base_triplet


def render_morning_boost(
    context: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> str:
    """Yakuniy Telegram Markdown xabarini yig'ish."""
    ctx = dict(context or {})
    current_dt = now or datetime.now()
    metric_fingerprint = (
        int(ctx.get("stagnated_count") or 0) * 3
        + int(ctx.get("overdue_projects_count") or 0) * 5
        + int(ctx.get("overdue_tasks_count") or 0) * 7
        + int(ctx.get("active_leads_count") or 0)
    )
    seed = current_dt.toordinal() + metric_fingerprint

    weekday_label, _ = WEEKDAY_CADENCE.get(current_dt.weekday(), WEEKDAY_CADENCE[0])
    theme, focus_reason = select_situational_theme(ctx, current_dt)
    rules_pair = theme.golden_rules[seed % len(theme.golden_rules)]
    tasks = build_situational_tasks(theme, ctx, seed)
    closing = theme.closings[seed % len(theme.closings)]
    metrics_lines = build_metrics_lines(ctx)

    parts: List[str] = [
        "🔥 **OISHA KUNLIK PSIXOLOGIK IMPULS (MINDSET BOOST)**",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"Assalomu alaykum, Jon Branding jamoasi! 🚀 ({current_dt.strftime('%d.%m.%Y')} | {weekday_label})",
        "",
    ]

    if metrics_lines:
        parts.append("📊 **Bugungi vaziyat va ko'rsatkichlar:**")
        parts.extend(metrics_lines)
        parts.append("")

    parts.extend(
        [
            f"🧭 **Bugungi fokus — {theme.title}:**",
            f"_{focus_reason}_",
            "",
            "💡 **Bugungi oltin qoida:**",
            f"• *'{rules_pair[0]}'*",
            f"• *'{rules_pair[1]}'*",
            "",
            "🎯 **Bugungi 3 ta vazifangiz:**",
            f"1. {tasks[0]}",
            f"2. {tasks[1]}",
            f"3. {tasks[2]}",
            "",
            f"⚡️ **{closing}**",
        ]
    )
    return "\n".join(parts)
