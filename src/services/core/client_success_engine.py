"""Client Success, Retention, and Financial Risk Automation Engine for JonBranding.
Covers:
1. Automated Client Onboarding & Roadmap generator
2. NPS (1-10) & Client Feedback collection
3. Automated Upsell & LTV triggers (7 days post completion)
4. Weekly Budget & Financial Overrun Telegram Alerts
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Optional
import httpx

from src.services.core.airtable_config import (
    airtable_records_page,
    airtable_request_headers,
)
from src.settings import settings
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)

AIRTABLE_API_BASE = "https://api.airtable.com/v0"
DEFAULT_BASE_ID = "app8xoyx1XCumYFXV"
LOYIHALAR_TABLE_ID = "tblJbUobSlygSwYAI"
BUDJET_TABLE_ID = "tblSm2Jx5mTE4tEQ7"
TRX_TABLE_ID = "tblrqxqIzyrvg7XpQ"

FINANCE_GROUP_ID = -1003967389019
TOPIC_EXPENSES = 4
TOPIC_INCOME = 2


def _get_headers() -> dict[str, str]:
    return airtable_request_headers()


def generate_onboarding_message(project_name: str, client_name: str, service: str, pm_name: str, start_date: str, end_date: str) -> str:
    """Generate professional VIP client onboarding message for Telegram/WhatsApp."""
    return (
        f"🎉 <b>Assalomu alaykum, {client_name}!</b>\n"
        f"JonBranding jamoasi nomidan to‘lovingiz qabul qilinganini mamnuniyat bilan tasdiqlaymiz!\n\n"
        f"📋 <b>Loyiha:</b> <i>{project_name}</i>\n"
        f"🎨 <b>Xizmat turi:</b> {service}\n"
        f"👤 <b>Sizning shaxsiy Project Menejeringiz (PM):</b> {pm_name}\n"
        f"📅 <b>Ishlash muddati:</b> {start_date} — {end_date}\n\n"
        f"📌 <b>Loyiha tartibi va bosqichlari:</b>\n"
        f"1️⃣ <b>Brief & Strategik tahlil:</b> Maqsadli auditoriya va yo‘nalishni aniqlash;\n"
        f"2️⃣ <b>Dizayn & Konseptsiya:</b> Eksklyuziv variantlar ishlab chiqish;\n"
        f"3️⃣ <b>Pravkalar & Sayqallash:</b> 2 bosqichli bepul tuzatish imkoniyati;\n"
        f"4️⃣ <b>Final topshirish:</b> Ishlab chiqarishga tayyor barcha manba fayllarni yetkazish.\n\n"
        f"Savollar yoki takliflar bo‘yicha PM {pm_name} siz bilan doimiy aloqada bo‘ladi. Birgalikda ajoyib natija yaratamiz! 🚀"
    )


def generate_nps_survey_message(project_name: str, client_name: str) -> str:
    """Generate NPS & Feedback request message upon project completion."""
    return (
        f"🤝 <b>Hurmatli {client_name}!</b>\n\n"
        f"<b>{project_name}</b> loyihamiz muvaffaqiyatli yakunlandi va barcha materiallar sizga topshirildi.\n\n"
        f"Biz har doim xizmat sifatini eng yuqori darajada ushlab turishga intilamiz. "
        f"JonBranding jamoasi bilan ishlash tajribangizni <b>1 dan 10 gacha</b> baholay olasizmi?\n\n"
        f"⭐ <b>1</b> — Qoniqarsiz | ⭐ <b>10</b> — A'lo darajada\n\n"
        f"<i>Shuningdek, xizmatimiz haqidagi samimiy fikringiz yoki takliflaringiz biz uchun bebahodir!</i>"
    )


def get_upsell_recommendation(completed_service: str) -> tuple[str, str]:
    """Determine the next logical service and pitch template based on completed service."""
    srv_lower = completed_service.lower()
    if "naming" in srv_lower:
        rec_service = "🎨 Brandbook & Identika"
        pitch = (
            "Siz bilan yangi brend nomini yaratdik! Keyingi eng muhim qadam — ushbu nomni "
            "mijozlar ko‘zida jozibali qiluvchi professional Logotip, Vizual Identika va Brandbook yaratishdir. "
            "Mavjud mijozimiz sifatida sizga ushbu xizmatga maxsus 10% hamkorlik bonusi ajratilgan!"
        )
    elif "logo" in srv_lower or "identika" in srv_lower:
        rec_service = "📦 Qadoq & Etiketka dizayni"
        pitch = (
            "Logotip va brending tayyor bo‘ldi! Endi mahsulotingiz peshtaxtalarda birinchi bo‘lib ko‘zga tashlanishi uchun "
            "premium Qadoq (Packaging) yoki Brandbook qoidalarini to‘liq joriy qilishni taklif etamiz."
        )
    elif "branding" in srv_lower:
        rec_service = "🌐 Web-sayt & Landing"
        pitch = (
            "Brendingiz to‘liq shakllandi! Uni internet orqali savdoga aylantirish uchun "
            "yuqori konversiyali rasmiy Web-sayt yoki Landing page ishlab chiqish vaqt keldi."
        )
    else:
        rec_service = "⚖️ Patent va Savdo Belgisi"
        pitch = (
            "Yaratilgan brendingizni raqobatchilardan 100% himoya qilish uchun "
            "Davlat patent idorasida Savdo Belgisi (Trademark) sifatida rasmiylashtirishni tavsiya qilamiz."
        )
    return rec_service, pitch


async def generate_weekly_budget_report() -> str:
    """Analyze monthly budget vs actual transactions and return executive Telegram summary."""
    base_id = getattr(settings, "AIRTABLE_BASE_ID", None) or DEFAULT_BASE_ID
    headers = _get_headers()

    current_month_str = get_local_now().strftime("%Y-%m")
    current_month_name = get_local_now().strftime("%B %Y")

    async with httpx.AsyncClient(timeout=20.0) as client:
        # 0. Fetch categories lookup
        cat_resp = await client.get(f"{AIRTABLE_API_BASE}/{base_id}/tblRt6aiU6Vy2yLCD?pageSize=50", headers=headers)
        cats, _ = airtable_records_page(cat_resp, resource="budget categories")
        cat_names = {c["id"]: c["fields"].get("Kategoriya", "Kategoriya") for c in cats}

        # 1. Fetch budget table
        b_resp = await client.get(f"{AIRTABLE_API_BASE}/{base_id}/{BUDJET_TABLE_ID}?pageSize=50", headers=headers)
        budgets, _ = airtable_records_page(b_resp, resource="budgets")

        # 2. Fetch P&L
        pnl_resp = await client.get(f"{AIRTABLE_API_BASE}/{base_id}/tblAgVaGlVory2yAW?pageSize=50", headers=headers)
        pnl_records, _ = airtable_records_page(pnl_resp, resource="weekly P&L")
        current_pnl = next((r["fields"] for r in pnl_records if r["fields"].get("Oy nomi", "").startswith(current_month_str)), {})

    kirim = current_pnl.get("Jami Kirim (UZS)", 0) or 0
    chiqim = current_pnl.get("Jami Chiqim (UZS)", 0) or 0
    sof = current_pnl.get("SOLIQDAN KEYINGI SOF FOYDA (UZS)", 0) or 0
    zaxira = current_pnl.get("TAQSIMLANMAGAN FOYDA (UZS)", 0) or 0

    lines = [
        f"📊 <b>HAFTALIK MOLIYA VA BUDJET MONITORINGI</b>\n"
        f"🗓 <b>Davr:</b> {current_month_name}\n\n"
        f"💵 <b>Jami Kirim:</b> {kirim:,.0f} UZS\n"
        f"💸 <b>Jami Chiqim:</b> {chiqim:,.0f} UZS\n"
        f"💰 <b>Sof Foyda:</b> {sof:,.0f} UZS\n"
        f"🏦 <b>Zaxira Kapitali:</b> {zaxira:,.0f} UZS\n\n"
        f"📋 <b>Kategoriyalar bo‘yicha budjet ijrosi:</b>"
    ]

    warnings = []
    for b in budgets:
        f = b["fields"]
        raw_cat = f.get("Kategoriya")
        if isinstance(raw_cat, list) and raw_cat:
            nomi = cat_names.get(raw_cat[0], "Kategoriya")
        elif isinstance(raw_cat, str):
            nomi = cat_names.get(raw_cat, raw_cat)
        else:
            nomi = f.get("Budjet nomi", "Kategoriya")
        reja = f.get("Reja (UZS)", 0) or 0
        fakt = f.get("Fakt (UZS)", 0) or 0
        if reja > 0:
            foiz = (fakt / reja) * 100
            if foiz > 100:
                status = f"🔴 <b>Oshib ketdi ({foiz:.0f}%)</b>"
                warnings.append(f"⚠️ <b>{nomi}:</b> Reja: {reja:,.0f} UZS, Fakt: {fakt:,.0f} UZS (+{fakt - reja:,.0f} UZS)")
            elif foiz >= 80:
                status = f"🟡 <b>Limitga yaqin ({foiz:.0f}%)</b>"
            else:
                status = f"🟢 <b>Rejada ({foiz:.0f}%)</b>"
            lines.append(f"• {nomi}: {status} — {fakt:,.0f} / {reja:,.0f} UZS")

    if warnings:
        lines.append("\n🚨 <b>DIQQAT TALAB XARAJATLAR:</b>")
        lines.extend(warnings)
    else:
        lines.append("\n✅ <i>Barcha xarajatlar belgilangan oylik me’yor ichida.</i>")

    return "\n".join(lines)
