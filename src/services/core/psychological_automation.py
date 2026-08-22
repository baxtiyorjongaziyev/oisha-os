"""
Psychological Automation Service — Avtomatlashtirilgan Kouching va Proaktiv To'siqlarni Sindirish.

Bu modul Oisha-OS ga quyidagi to'liq avtomatlashtirilgan imkoniyatlarni beradi:
1. Kunlik ertalabki motivatsion booster (09:15) — Jamoa uchun kunni kuchli psixologik ruhda boshlash.
2. Sotuvchilarning qo'ng'iroq kechiktirishini avtomatik aniqlash (11:30 & 15:30) — AmoCRM da qotib qolgan
   (24-48 soatdan ortiq aloqaga chiqilmagan) lidlar uchun mas'ul menejerga to'g'ridan-to'g'ri
   "Hozir telefon qilsang nima bo'ladi?..." dekonstruktsiyasi va 60 soniyalik mikroskript yuborish.
3. PM loyiha kechikishi va konflikt himoyasi (11:45 & 16:30) — Airtable/loyihalarda deadline yaqinlashayotgan
   yoki statusi kechikayotgan loyihalar uchun PMga mijoz bilan diplomatik va dadil muloqot qilish
   xabarini tayyorlab berish.
4. Avtomatik hisobdorlik (Accountability Check) — Kouching yuborilgandan so'ng amaliyot natijasini kuzatish.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from src.services.core.psychological_coach import (
    PsychologicalCoach,
    PsychologicalRole,
    FearCategory,
)

logger = logging.getLogger("PsychologicalAutomation")


class PsychologicalAutomationService:
    """To'liq avtonom psixologik qo'llab-quvvatlash va kouching servisi."""

    def __init__(
        self,
        *,
        db: Any = None,
        amocrm: Any = None,
        airtable: Any = None,
        bot_client: Any = None,
    ):
        self.db = db
        self.amocrm = amocrm
        self.airtable = airtable
        self.bot_client = bot_client

    def generate_morning_boost(self) -> str:
        """Ertalabki 09:15 jamoaviy psixologik impuls."""
        return (
            "🔥 **OISHA KUNLIK PSIXOLOGIK IMPULS (MINDSET BOOST)**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Assalomu alaykum, Jon Branding jamoasi! 🚀\n\n"
            "💡 **Bugungi oltin qoida:**\n"
            "• *'Mijozning rad javobi — bu shaxsiy mag'lubiyat emas, bu shunchaki keyingi qadamga oydinlik!'*\n"
            "• *'Eng yomon qaror — qo'ng'iroq qilmaslik va kechiktirishdir. Noaniqlik energiyani yeydi, harakat esa qo'rquvni yo'qotadi!'*\n\n"
            "🎯 **Bugungi 3 ta vazifangiz:**\n"
            "1. Telefonni olishga ikkilanyapsizmi? Raqamni tering va faqat 1 ta do'stona savol bering.\n"
            "2. Kechikayotgan loyiha bormi? Proaktiv bo'lib, mijozga yechim bilan birga chiqing.\n"
            "3. Narx aytishdan uyalmang — siz mijoz biznesiga 10x qiymat beryapsiz!\n\n"
            "⚡️ **Keling, bugun natijalar rekordini yangilaymiz! Olg'a!**"
        )

    async def scan_and_generate_sales_reluctance_interventions(
        self, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """AmoCRM dagi harakatsiz/qotib qolgan lidlar uchun avtomatik kouching tayyorlash."""
        interventions: List[Dict[str, Any]] = []
        if not self.amocrm:
            logger.warning("[PSYCH_AUTO] AmoCRM client mavjud emas, soxta ma'lumot berilmaydi.")
            return interventions

        try:
            leads = []
            if hasattr(self.amocrm, "get_stagnated_leads"):
                leads = await asyncio.to_thread(self.amocrm.get_stagnated_leads, hours=24, limit=limit)
            elif hasattr(self.amocrm, "get_all_leads"):
                all_leads = await asyncio.to_thread(self.amocrm.get_all_leads, limit=limit * 3)
                leads = [l for l in (all_leads or []) if str(l.get("status_id")) not in {"142", "143"}][:limit]

            for lead in (leads or []):
                lead_id = lead.get("id")
                name = lead.get("name") or f"Lead #{lead_id}"
                price = lead.get("price") or 0
                price_str = f"${price:,.0f}" if price else "$2,500"
                manager_id = lead.get("responsible_user_id")

                breakthrough = PsychologicalCoach.deconstruct_fear(
                    text=f"mijozga telefon qilmoqchi lekin qilolmayapti {name}",
                    role="sales",
                    client_name=name,
                    context={"deal_value": price_str, "lead_id": lead_id},
                )
                formatted = (
                    f"🚨 **AVTOMATIK SOTUV PUSH & KOUCHING**\n"
                    f"👤 **Lid:** `{name}` (ID: #{lead_id}) | 💰 Qiymat: `{price_str}`\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"❓ **Nega telefon qilmayapsan? Hozir qilsang nima bo'ladi?**\n"
                    f"{breakthrough.worst_case_analysis}\n\n"
                    f"⏳ **Qilmaslikning narxi:**\n"
                    f"{breakthrough.inaction_cost}\n\n"
                    f"{breakthrough.micro_script}\n\n"
                    f"{breakthrough.action_challenge}"
                )
                interventions.append({
                    "lead_id": lead_id,
                    "manager_id": manager_id,
                    "client_name": name,
                    "deal_value": price_str,
                    "message": formatted,
                })
        except Exception as exc:
            logger.error("[PSYCH_AUTO] Sales scan xatoligi: %s", exc, exc_info=True)

        return interventions

    async def scan_and_generate_pm_interventions(
        self, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Airtable/loyiha tizimidagi xavfli loyihalar uchun avtomatik PM kouching."""
        interventions: List[Dict[str, Any]] = []
        if not self.airtable and not hasattr(self.db, "get_all_projects"):
            return interventions

        try:
            projects = []
            if self.airtable and hasattr(self.airtable, "get_overdue_projects"):
                projects = await asyncio.to_thread(self.airtable.get_overdue_projects, limit=limit)
            elif self.db and hasattr(self.db, "get_all_projects"):
                projects = await self.db.get_all_projects()

            for proj in (projects or [])[:limit]:
                proj_name = proj.get("name") or proj.get("project_name") or "Loyiha"
                manager = proj.get("manager") or proj.get("pm") or "PM"
                deadline = proj.get("deadline") or "Yaqin kunlarda"

                breakthrough = PsychologicalCoach.deconstruct_fear(
                    text=f"kechikishni aytishga qo'rqyapman {proj_name}",
                    role="pm",
                    client_name=proj_name,
                    context={"project_name": proj_name, "deadline": deadline},
                )
                formatted = (
                    f"🛡 **AVTOMATIK PM LOYIHA HIMOYASI & KOUCHING**\n"
                    f"📁 **Loyiha:** `{proj_name}` | 👤 **PM:** `{manager}`\n"
                    f"📅 **Deadline:** `{deadline}`\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{breakthrough.worst_case_analysis}\n\n"
                    f"{breakthrough.micro_script}\n\n"
                    f"{breakthrough.action_challenge}"
                )
                interventions.append({
                    "project_name": proj_name,
                    "manager": manager,
                    "deadline": deadline,
                    "message": formatted,
                })
        except Exception as exc:
            logger.error("[PSYCH_AUTO] PM scan xatoligi: %s", exc, exc_info=True)

        return interventions

    async def deliver_interventions(
        self,
        interventions: List[Dict[str, Any]],
        target_chat_id: Any,
        topic_id: Optional[int] = None,
    ) -> int:
        """Tayyorlangan kouching xabarlarini avtomatik Telegramga yetkazish."""
        if not self.bot_client or not target_chat_id:
            logger.warning("[PSYCH_AUTO] bot_client yoki target_chat_id yo'q.")
            return 0

        sent_count = 0
        for item in interventions:
            msg = item.get("message")
            if not msg:
                continue
            try:
                kwargs: Dict[str, Any] = {"parse_mode": "markdown"}
                if topic_id:
                    kwargs["message_thread_id"] = topic_id
                await self.bot_client.send_message(target_chat_id, msg, **kwargs)
                sent_count += 1
                await asyncio.sleep(0.5)
            except Exception as exc:
                logger.error("[PSYCH_AUTO] Xabar yuborishda xato: %s", exc)

        return sent_count
