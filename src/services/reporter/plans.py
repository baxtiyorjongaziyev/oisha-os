"""
Morning plan generation, plan-fact reporting, and weekly Uzbek markdown digests.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)


class PlansMixin:
    """Handles morning plan prompting, plan-fact validation, and weekly reporting."""

    async def generate_morning_plan(self, distribution: Dict[int, List[Dict]]) -> str:
        """Ertalabki 'Plan' hisoboti."""
        now = get_local_now()
        report = [
            f"☀️ <b>{now.strftime('%d.%m.%Y')} — YANGI KUN, YANGI G'ALABALAR!</b>",
            "🚀 Oisha-OS jamoani jangovar shay holatga keltiradi.\n",
            "📌 <b>BUGUNGI VAZIFALAR (MISSION CONTROL):</b>",
        ]

        for m_id, missions in distribution.items():
            m_info = await self.db.get_user_info(m_id)
            name = m_info.get("first_name") if m_info else f"Manager_{m_id}"
            if (
                "pm" in name.lower()
                or "dilbar" in name.lower()
                or str(m_id) == "8611068511"
            ):
                name = "👩‍💼 PM Dilbar"

            report.append(f"\n👤 <b>{name}</b>")
            if not missions:
                report.append(
                    "  ▫️ Bugun yangi lidlar yo'q. Eski loyihalar ustida ishlang."
                )
            else:
                # Voronkalarni guruhlash (Refined with Role logic)
                hunters = [
                    m
                    for m in missions
                    if m.get("role") == "HUNTER"
                    or any(
                        x in (m.get("pipeline") or "").lower()
                        for x in ["hunter", "so'rov", "qual"]
                    )
                ]
                setters = [m for m in missions if m not in hunters]

                if hunters:
                    report.append("  🏹 <b>HUNTER MISSIONS:</b>")
                    for i, m in enumerate(hunters, 1):
                        report.append(
                            f"    {i}. {m['lead_name']} — {m['mission']} <a href='{m['link']}'>[CRM]</a>"
                        )

                if setters:
                    report.append("  🎯 <b>SETTER / CLOSER MISSIONS:</b>")
                    for i, m in enumerate(setters, 1):
                        report.append(
                            f"    {i}. {m['lead_name']} — {m['mission']} <a href='{m['link']}'>[CRM]</a>"
                        )

        return "\n".join(report)

    async def generate_plan_fact_report(self) -> str:
        """Kechki 'Plan-Fakt' hisoboti."""
        today = get_local_now().strftime("%Y-%m-%d")
        plans = await self.db.get_daily_plan(today)

        if not plans:
            # Vazifalar rejalashtirilmagan - jamoadan talab qilish
            return await self.generate_missing_plan_demand()

        report = [
            f"🌙 <b>{get_local_now().strftime('%d.%m.%Y')} — KUNLIK PLAN-FAKT TAHLILI</b>",
            "🧐 Oisha-OS natijalarni tekshirmoqda...\n",
        ]

        results = {}

        for p in plans:
            m_id = p["manager_id"]
            if m_id not in results:
                results[m_id] = {"total": 0, "achieved": 0, "leads": []}

            lead_id = p["lead_id"]
            status = "🔴 Bajarilmadi"

            try:
                lead = await self.crm.amocrm.get_lead(lead_id)
                if not lead:
                    status = "❓ Noma'lum"
                else:
                    current_status = lead.get("status_id")
                    current_pipeline = lead.get("pipeline_id")
                    src = (p.get("source_pipeline") or "").upper() or None

                    if current_status == self.WON_STATUS:
                        status = "✅ SHARTNOMA! (+)"
                        results[m_id]["achieved"] += 1
                    elif current_status == self.LOST_STATUS:
                        status = "⚫ Yutqazilgan"
                    elif src == "HUNTER":
                        if current_pipeline != self.HUNTER_PIPELINE_ID:
                            status = "✅ Oldinga siljish (Hunter → boshqa pipeline)"
                            results[m_id]["achieved"] += 1
                    elif src == "CLOSER":
                        pass
                    else:
                        if (
                            current_pipeline == self.CLOSER_PIPELINE_ID
                            and current_status != self.WON_STATUS
                        ):
                            pass
                        elif current_pipeline != self.HUNTER_PIPELINE_ID:
                            status = "✅ Oldinga siljish"
                            results[m_id]["achieved"] += 1
            except Exception as e:
                logger.warning(f"[PLAN-FACT] lead {lead_id}: {e}")
                status = "❓ Noma'lum"

            results[m_id]["total"] += 1
            results[m_id]["leads"].append(f"  ▫️ {p['lead_name']}: {status}")

        for m_id, data in results.items():
            m_info = await self.db.get_user_info(m_id)
            name = m_info.get("first_name") if m_info else f"Manager_{m_id}"
            if (
                "pm" in name.lower()
                or "dilbar" in name.lower()
                or str(m_id) == "8611068511"
            ):
                name = "👩‍💼 PM Dilbar"

            pct = (data["achieved"] / data["total"] * 100) if data["total"] > 0 else 0
            emoji = "🔥" if pct >= 80 else "⚠️" if pct >= 50 else "❄️"

            report.append(f"👤 <b>{name}</b> {emoji}")
            report.append(
                f"📊 KPI: <b>{data['achieved']}/{data['total']}</b> ({pct:.1f}%)"
            )
            report.append("\n".join(data["leads"]))
            report.append("")

        total_total = sum(d["total"] for d in results.values())
        total_achieved = sum(d["achieved"] for d in results.values())
        total_pct = (total_achieved / total_total * 100) if total_total > 0 else 0

        if total_pct >= 80:
            report.append(
                "🌟 <b>DAHSHAT!</b> Jamoa bugun haqiqiy professionalizm ko'rsatdi. Sizlar bilan faxrlanaman!"
            )
        elif total_pct >= 50:
            report.append(
                "👍 <b>Yaxshi.</b> Lekin ertaga bundan ham ko'proq natija kutaman. Bo'shashmang!"
            )
        else:
            report.append(
                "📢 <b>DIQQAT!</b> Bugungi natijalar kutilganidan past. Ertaga har bir bitim uchun jang qilishingizni so'rayman!"
            )

        return "\n".join(report)

    async def generate_missing_plan_demand(self) -> str:
        """Vazifalar rejalashtirilmaganda jamoadan talab qilish xabari."""
        now = get_local_now()

        # Real ma'lumotlarni olish
        try:
            leads = await self.crm.amocrm.get_leads_detailed(limit=50)
            active_leads = [
                lead
                for lead in leads
                if lead.get("status_id") not in [self.WON_STATUS, self.LOST_STATUS]
            ]
            total_value = sum(int(lead.get("price", 0) or 0) for lead in active_leads)
        except Exception as e:
            logger.warning(f"[MISSING PLAN] Lead fetch failed: {e}")
            active_leads = []
            total_value = 0

        report = [
            f"🌙 <b>{now.strftime('%d.%m.%Y')} — KUNLIK REJA TALAB ETILMOQDA</b>",
            "📢 <b>DIQQAT!</b> Bugun uchun rejalashtirilgan vazifalar topilmadi.\n",
            "🎯 <b>HAR BIR MENEJERDAN REJA KUTILYAPTI:</b>",
            "• Bugun qaysi lidlarga ishlayapsiz?",
            "• Qanday natijalar kutyapsiz?",
            "• Qanday yordam kerak?\n",
        ]

        if active_leads:
            report.append(
                f"💼 <b>AKTIV BITIMLAR:</b> {len(active_leads)} ta (qiymati: {total_value:,.0f} so'm)".replace(
                    ",", " "
                )
            )
            report.append(
                "📊 <i>CRM'dagi aktiv lidlaringiz bo'yicha rejani yuboring!</i>\n"
            )

        report.extend(
            [
                "✍️ <b>JAVOB FORMATI:</b>",
                "<code>PLAN:</code>",
                "<code>1) Asosiy vazifa</code>",
                "<code>2) Bugun yopiladigan bitim</code>",
                "<code>3) Kerakli yordam</code>\n",
                "⏰ <b>DEADLINE:</b> Kechki hisobotdan oldin (20:00)",
                "👑 <b>@baxtiyorjong_gaziyev nazorat qilmoqda</b>",
            ]
        )

        return "\n".join(report)

    async def generate_proactive_vision(self) -> str:
        """Vazifa bo'lmaganda jamoaga strategik yo'nalish va 'Growth Missions' berish."""
        logger.info("[PROACTIVE] Generating strategic vision since no plans found.")

        now = get_local_now()
        report = [
            f"🌙 <b>{now.strftime('%d.%m.%Y')} — STRATEGIK O'SISH IMKONIYaTI</b>",
            "Biron bir konkret vazifa rejalashtirilmaganligi bizga to'xtash uchun sabab emas. Dunyodagi eng zo'r jamoa bunday vaqtda o'sish ustida ishlaydi! 🚀\n",
        ]

        try:
            # 1. CRM Diagnostika
            leads = await self.crm.amocrm.get_leads_detailed(limit=50)
            [
                lead
                for lead in leads
                if lead.get("status_id") not in [self.WON_STATUS, self.LOST_STATUS]
            ]

            # 2. AI orqali strategik maslahat olish

            getattr(
                self.crm.amocrm, "api_key", None
            )  # Internal fallback or use prompt
            # Aslida API key Enterprise uchun global bo'lishi kerak.
            # Biz buni advisor_agent orqali ham qilishimiz mumkin, lekin Reporter o'zida bo'lgani yaxshi.


            # Note: We need a client. If not passed, we'll try to get it from context.
            # For robustness in this module, we use a simple set of hardcoded best practices if AI fails.

            missions = [
                "🔥 **Mission: Revival** — Oxirgi 30 kundagi 'Lost' bo'lgan lidlarni qayta ko'rib chiqing va kamida 5 tasiga qayta aloqaga chiqing.",
                "🧹 **Mission: CRM Hygiene** — Barcha aktiv bitimlardagi eslatmalarni yangilang va kutilayotgan summalarni aniqlashtiring.",
                "🧠 **Mission: Brainstorm** — Keyingi hafta uchun 3 ta yangi marketing gipotezasini ishlab chiqing.",
            ]

            # If we wanted purely AI (Ideal State):
            # client = genai.Client(api_key=...)
            # res = await safe_ai_call(...)

            report.append("🎯 **BUGUNGI GROWTH MISSIONS:**")
            for m in missions:
                report.append(f"  ▫️ {m}")

            report.append(
                '\n💡 <i>"Katta natijalar kichik, lekin muntazam harakatlardan boshlanadi."</i>'
            )
            report.append(
                "\n@baxtiyorjong_gaziyev, jamoa bugun o'z ustida ishlashga shay!"
            )

        except Exception as e:
            logger.error(f"[PROACTIVE VISION ERROR] {e}")
            report.append(
                "🚀 Bugun o'z ustimizda ishlash va CRM ni tozalash kuni. Olaysizlar!"
            )

        return "\n".join(report)

    async def generate_weekly_report_uz(
        self,
        period_start: str,
        period_end: str,
        active_deals: int,
        active_value: int,
        completed_deals: int,
        completed_value: int,
        lost_deals: int,
        lost_value: int,
        new_deals: int,
        new_companies: int,
        new_contacts: int,
    ) -> str:
        """Generate weekly CRM report in Uzbek language.

        Args:
            period_start: Start date (DD.MM.YYYY)
            period_end: End date (DD.MM.YYYY)
            active_deals: Number of active deals at end of period
            active_value: Value of active deals in UZS
            completed_deals: Number of successfully completed deals
            completed_value: Value of completed deals
            lost_deals: Number of unrealized deals
            lost_value: Value of lost deals
            new_deals: New deals created
            new_companies: New companies created
            new_contacts: New contacts created

        Returns:
            Formatted report string in Uzbek
        """

        # Format numbers with spaces for thousands
        def format_money(amount: int) -> str:
            if amount == 0:
                return "0"
            return f"{amount:,}".replace(",", " ")

        report = []

        # Header
        report.append("📊 *HAFTALIK HISOBOT*")
        report.append(f"📅 *Davri: {period_start} - {period_end}*\n")

        # Active deals section
        report.append("💼 *AKTIV BITIMLAR (davr oxirida):*")
        report.append(f"• Jami: *{active_deals} ta*")
        report.append(f"• Qiymati: *{format_money(active_value)} soʻm*\n")

        # Completed deals section
        report.append("✅ *YOPILGAN BITIMLAR:*")
        if completed_deals > 0:
            report.append(
                f"• Muvaffaqiyatli: *{completed_deals} ta* ({format_money(completed_value)} soʻm)"
            )
        else:
            report.append("• Muvaffaqiyatli: *0 ta* ⚠️")

        if lost_deals > 0:
            report.append(
                f"• Bekor qilingan: *{lost_deals} ta* ({format_money(lost_value)} soʻm)"
            )
        report.append("")

        # New entries section
        report.append("🆕 *YANGI YARATILGAN:*")
        report.append(f"• Bitimlar: *{new_deals} ta* 📈")
        report.append(f"• Kompaniyalar: *{new_companies} ta* 🏢")
        report.append(f"• Kontaktlar: *{new_contacts} ta* 👥\n")

        # Summary analysis
        report.append("📈 *OISHA TAHLILI:*")

        if new_deals > 100:
            report.append(
                f"_✅ Ajoyib! Haftada {new_deals} ta yangi bitim - aktiv sotuv jarayoni._"
            )
        elif new_deals > 50:
            report.append(
                "_🟡 O'rtacha. Yangi bitimlar oqimi yaxshi, lekin yanada kuchaytirish mumkin._"
            )
        else:
            report.append(
                "_🔴 Diqqat! Yangi leadlar kam. Marketing kanallarini ko'rib chiqish vaqt._"
            )

        if completed_deals == 0 and active_deals > 100:
            report.append(
                f"_⚠️ {active_deals} ta aktiv bitim ichida yopilgan yo'q - menejerlar nazoratini kuchaytiring._"
            )

        report.append("\n📊 *Davom ettirish uchun @baxtiyorjong_gaziyev nazoratida* 👑")

    async def build_reportagram_report(self) -> str:
        """Reportagram.com uslubida kunlik AmoCRM hisoboti.

        Qaytaradi:
            AmoCRM Kunlik Hisobot | 📅 May 21, 2026
            ━━━━━━━━━━━━
            Tushgan Leadlar: 127  ▲ +12
            ...
        """
        from src.services.core.crm.crm_daily_report import build_reportagram_report
        return await build_reportagram_report(self)
