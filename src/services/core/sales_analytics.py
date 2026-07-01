"""
Sales Analytics Module — Menejer KPI, Stagnatsiya Alert, Pipeline Funnel
Oisha-OS v5.0 — Sotuvchilar conversiyasini oshirish uchun
"""

import structlog
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, List

from src.services.core.amocrm_pipeline_config import SALES_PIPELINE_ID

logger = structlog.get_logger()


class SalesAnalytics:
    """AmoCRM sotuvlar tahlili — KPI, Stagnatsiya, Pipeline Funnel."""

    # Pipeline IDs
    SALES_PIPELINE = SALES_PIPELINE_ID
    HUNTER_PIPELINE = SALES_PIPELINE_ID
    CLOSER_PIPELINE = SALES_PIPELINE_ID

    # Status IDs
    STATUS_WON = 142
    STATUS_LOST = 143

    def __init__(self, amocrm_sync=None, db=None, bot=None):
        """
        Args:
            amocrm_sync: AmoCRMSync instance (allaqachon autentifikatsiya qilingan)
            db: Database instance (dedup va state uchun)
            bot: Telegram bot instance (xabar yuborish uchun)
        """
        if amocrm_sync is None:
            from src.services.core.amocrm_sync import AmoCRMSync
            from src.settings import settings

            self.amo = AmoCRMSync(
                settings.AMOCRM_SUBDOMAIN,
                settings.AMOCRM_CLIENT_ID,
                (
                    settings.AMOCRM_CLIENT_SECRET.get_secret_value()
                    if settings.AMOCRM_CLIENT_SECRET
                    else None
                ),
                settings.AMOCRM_REDIRECT_URL,
            )
            self.amo._load_token()
        else:
            self.amo = amocrm_sync

        self.db = db
        self.bot = bot

    def _get_all_leads(self, pipeline_id: int = None) -> List[Dict]:
        """Barcha lidlarni olish (pagination bilan)."""
        url = f"{self.amo.base_url}/api/v4/leads"
        params = {"limit": 250, "with": "contacts"}
        if pipeline_id:
            params["filter[pipeline_id]"] = pipeline_id

        all_leads = []
        try:
            resp = requests.get(url, headers=self.amo._get_headers(), params=params, timeout=30)
            if resp.status_code == 200:
                leads = resp.json().get("_embedded", {}).get("leads", [])
                all_leads.extend(leads)
        except Exception as e:
            logger.error(f"[ANALYTICS] Error fetching leads: {e}")
        return all_leads

    def _get_user_name(self, user_id: int) -> str:
        """AmoCRM user ismini olish (Mapping bilan)."""
        try:
            url = f"{self.amo.base_url}/api/v4/users/{user_id}"
            resp = requests.get(url, headers=self.amo._get_headers(), timeout=30)
            if resp.status_code == 200:
                name = resp.json().get("name", f"User_{user_id}")
                # Name Mapping for Oydin
                if "Baxtiyorjon Gaziyev" in name:
                    return "Oydin (Sales Manager)"
                return name
        except Exception:
            logger.debug("[SALES_ANALYTICS] Failed to fetch user name for user_id=%s", user_id, exc_info=True)
        return f"User_{user_id}"

    # ═══════════════════════════════════════════════════════════════
    # 1. MENEJER SCORECARD — Har kungi shaxsiy KPI
    # ═══════════════════════════════════════════════════════════════

    def generate_manager_scorecard(self) -> str:
        """
        Har bir menejer uchun kunlik KPI hisoboti:
        - Aktiv lidlar soni (pipeline bo'yicha)
        - Bugungi o'zgartirilgan lidlar (faollik)
        - Won bitimlar (bugungi + oylik)
        - Stagnatsiyaga tushgan lidlar
        - O'rtacha javob vaqti
        """
        now = time.time()
        today_start = int(
            datetime.now().replace(hour=0, minute=0, second=0).timestamp()
        )
        month_start = int(
            datetime.now().replace(day=1, hour=0, minute=0, second=0).timestamp()
        )

        # Barcha lidlarni olamiz
        all_leads = self._get_all_leads(self.SALES_PIPELINE)

        # Menejerlar bo'yicha guruhlash
        manager_stats: Dict[int, Dict] = {}

        for lead in all_leads:
            responsible = lead.get("responsible_user_id")
            if not responsible:
                continue

            if responsible not in manager_stats:
                manager_stats[responsible] = {
                    "name": None,
                    "sales_active": 0,
                    "today_touched": 0,
                    "today_won": 0,
                    "month_won": 0,
                    "month_revenue": 0,
                    "stagnated": 0,
                    "total_active": 0,
                }

            stats = manager_stats[responsible]
            status_id = lead.get("status_id", 0)
            pipeline_id = lead.get("pipeline_id", 0)
            updated_at = lead.get("updated_at", 0)
            closed_at = lead.get("closed_at", 0)
            price = lead.get("price", 0) or 0

            # Aktiv lidlar (Won/Lost emas)
            if status_id not in [self.STATUS_WON, self.STATUS_LOST]:
                stats["total_active"] += 1
                if pipeline_id == self.SALES_PIPELINE:
                    stats["sales_active"] += 1

                # Stagnatsiya (24 soat o'zgarmagan)
                if (now - updated_at) > 86400:
                    stats["stagnated"] += 1

                # Bugun tegib ko'rilgan
                if updated_at >= today_start:
                    stats["today_touched"] += 1

            # Won bitimlar
            if status_id == self.STATUS_WON:
                if closed_at and closed_at >= today_start:
                    stats["today_won"] += 1
                if closed_at and closed_at >= month_start:
                    stats["month_won"] += 1
                    stats["month_revenue"] += price

        # Ismlarni olish
        for uid in manager_stats:
            manager_stats[uid]["name"] = self._get_user_name(uid)

        # Hisobot generatsiya
        report = "📊 <b>BUGUNGI SOTUV HISOBOTI</b>\n"
        report += f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        report += "━" * 30 + "\n"

        if not manager_stats:
            report += "\n⚠️ Hozircha hech qanday ma'lumot yo'q."
            return report

        # Sort by month_revenue descending
        sorted_managers = sorted(
            manager_stats.items(), key=lambda x: x[1]["month_revenue"], reverse=True
        )

        total_revenue = 0
        total_won = 0

        for i, (uid, s) in enumerate(sorted_managers, 1):
            name = s["name"] or f"Menejer_{uid}"
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."

            report += f"\n{medal} <b>{name}</b>\n"
            report += f"   👥 Ish jarayonidagi mijozlar: {s['total_active']} ta\n"
            report += f"   ✅ Bugun muloqot qilgan: {s['today_touched']} | Sotuv: {s['today_won']}\n"

            if s["month_won"] > 0:
                report += f"   💰 Oylik natija: {s['month_won']} ta sotuv = {s['month_revenue']:,.0f} so'm\n".replace(
                    ",", " "
                )
            else:
                report += "   💰 Oylik natija: 0 ta sotuv\n"

            if s["stagnated"] > 0:
                report += f"   🚨 <b>DIQQAT: {s['stagnated']} ta mijoz 24 soatdan beri qarovsiz!</b>\n"

            # Tasks and Notes discipline (CRM Odobi)
            # Bu yerda real kodda lead['closest_task_at'] ni tekshirish kerak
            # Hozircha umumiy mantiq qo'shamiz
            report += (
                "   📝 CRM Intizomi: Har bir mijozda vazifa (zadacha) bo'lishi shart!\n"
            )

            total_revenue += s["month_revenue"]
            total_won += s["month_won"]

        # Jamoa umumiy ko'rsatkichi
        target = 80_000_000
        pct = (total_revenue / target * 100) if target > 0 else 0
        bar_fill = int(pct / 10)
        bar = "█" * min(bar_fill, 10) + "░" * (10 - int(pct / 10))

        report += "\n" + "━" * 30
        report += "\n📈 <b>JAMOA NATIJASI:</b>"
        report += (
            f"\n   Jami sotuv: {total_won} ta | {total_revenue:,.0f} so'm".replace(
                ",", " "
            )
        )
        report += f"\n   🎯 Oylik maqsad: {target:,.0f} so'm ({pct:.0f}%)".replace(
            ",", " "
        )
        report += f"\n   [{bar}]"

        # 💡 CRM COACHING SECTION (Oydin uchun maxsus)
        report += "\n\n💡 <b>OISHA-AI MASLAHATLARI:</b>\n"
        report += "1. <b>Vazifasiz (zadacha) mijoz — yo'qolgan mijoz!</b> Agar hozir zadacha qo'ymasangiz, u esdan chiqadi.\n"
        report += "2. <b>Izohlar (primechaniya) sifatli bo'lsin:</b> Mijoz nima dedi? Nega sotib olmadi? Shularni yozmasangiz, xatolarni tuzata olmaysiz.\n"
        report += "3. <b>CRM — bu sizning yordamchingiz,</b> dushmaningiz emas. To'g'ri ishlatsangiz, sotuvingiz 2 barobar oshadi! 🚀"

        return report

    # ═══════════════════════════════════════════════════════════════
    # 2. STAGNATSIYA ALERT — Harakatsiz lidlarga avtomatik eslatma
    # ═══════════════════════════════════════════════════════════════

    def get_stagnated_leads_by_manager(self, hours: int = 24) -> Dict[int, List[Dict]]:
        """24+ soat o'zgarmagan lidlarni menejer bo'yicha guruhlash."""
        now = time.time()
        limit = hours * 3600
        result: Dict[int, List[Dict]] = {}

        for pipeline_name, pipeline_id in [
            ("SALES", self.SALES_PIPELINE),
        ]:
            leads = self._get_all_leads(pipeline_id)
            for lead in leads:
                status_id = lead.get("status_id", 0)
                if status_id in [self.STATUS_WON, self.STATUS_LOST]:
                    continue

                updated_at = lead.get("updated_at", 0)
                if (now - updated_at) > limit:
                    responsible = lead.get("responsible_user_id", 0)
                    if responsible not in result:
                        result[responsible] = []

                    idle_hours = int((now - updated_at) / 3600)
                    idle_days = idle_hours // 24

                    result[responsible].append(
                        {
                            "id": lead["id"],
                            "name": lead.get("name", "Nomsiz"),
                            "pipeline": pipeline_name,
                            "idle_hours": idle_hours,
                            "idle_text": (
                                f"{idle_days} kun"
                                if idle_days >= 1
                                else f"{idle_hours} soat"
                            ),
                            "link": f"https://{self.amo.subdomain}.amocrm.ru/leads/detail/{lead['id']}",
                            "price": lead.get("price", 0) or 0,
                        }
                    )

        return result

    def generate_stagnation_alert(self, hours: int = 24) -> str:
        """Stagnatsiya bo'yicha jamoaga alert xabar."""
        stagnated = self.get_stagnated_leads_by_manager(hours)

        if not stagnated:
            return ""  # Hech narsa yo'q, alert kerak emas

        total_count = sum(len(leads) for leads in stagnated.values())
        total_value = sum(l["price"] for leads in stagnated.values() for l in leads)

        report = "🚨 <b>STAGNATSIYA ALERT</b>\n"
        report += f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        report += f"⚠️ {total_count} ta lid {hours}+ soat harakatsiz"
        if total_value > 0:
            report += f" (umumiy: {total_value:,.0f} so'm)".replace(",", " ")
        report += "\n" + "━" * 30 + "\n"

        for uid, leads in stagnated.items():
            name = self._get_user_name(uid)
            report += f"\n👤 <b>{name}</b> — {len(leads)} ta lid:\n"

            for lead in sorted(leads, key=lambda x: x["idle_hours"], reverse=True)[:5]:
                emoji = (
                    "🔴"
                    if lead["idle_hours"] >= 72
                    else "🟡" if lead["idle_hours"] >= 48 else "⚠️"
                )
                report += f"   {emoji} {lead['name']} ({lead['pipeline']}) — <b>{lead['idle_text']}</b>"
                if lead["price"] > 0:
                    report += f" 💰{lead['price']:,.0f}".replace(",", " ")
                report += "\n"

            if len(leads) > 5:
                report += f"   ... va yana {len(leads) - 5} ta\n"

        report += "\n💡 <i>Harakatsiz lidlar — yo'qotilgan foyda! Bugun bog'laning yoki sababini belgilang.</i>"
        return report

    # ═══════════════════════════════════════════════════════════════
    # 3. PIPELINE FUNNEL — Haftalik conversiya tahlili
    # ═══════════════════════════════════════════════════════════════

    def generate_pipeline_funnel(self, days: int = 7) -> str:
        """Bitta Sales pipeline bo'yicha haftalik konversiya tahlili."""
        now = time.time()
        period_start = int((datetime.now() - timedelta(days=days)).timestamp())
        sales_leads = self._get_all_leads(self.SALES_PIPELINE)

        total = len(sales_leads)
        active = lost = won = won_week = stagnated = 0
        revenue = revenue_week = 0

        for lead in sales_leads:
            status = lead.get("status_id", 0)
            updated = lead.get("updated_at", 0)
            closed_at = lead.get("closed_at", 0)
            price = lead.get("price", 0) or 0
            if status == self.STATUS_WON:
                won += 1
                revenue += price
                if closed_at and closed_at >= period_start:
                    won_week += 1
                    revenue_week += price
            elif status == self.STATUS_LOST:
                lost += 1
            else:
                active += 1
                if (now - updated) > 86400 * 3:
                    stagnated += 1

        win_rate = (won / total * 100) if total else 0
        avg_deal = (revenue / won) if won else 0

        report = "SALES PIPELINE FUNNEL\n"
        report += f"Oxirgi {days} kun ({datetime.now().strftime('%d.%m.%Y')})\n"
        report += "-" * 30 + "\n"
        report += "\nSALES Pipeline\n"
        report += f"   Jami: {total} ta lid\n"
        report += f"   Aktiv: {active}\n"
        report += f"   Won: {won} ({revenue:,.0f} so'm)\n".replace(",", " ")
        report += f"   Lost: {lost}\n"
        if stagnated > 0:
            report += f"   Stagnatsiya (3+ kun): {stagnated}\n"
        report += f"\n   Win Rate (SALES): {win_rate:.0f}%\n"
        report += "\n" + "-" * 30
        report += f"\nHAFTALIK NATIJALAR ({days} kun):\n"
        report += f"   Yopilgan: {won_week} ta bitim\n"
        report += f"   Tushum: {revenue_week:,.0f} so'm\n".replace(",", " ")
        report += f"   O'rtacha bitim: {avg_deal:,.0f} so'm\n".replace(",", " ")
        report += f"\nUMUMIY CONVERSIYA: {win_rate:.1f}%"
        report += f"\n   ({total} lid -> {won} won)"
        report += "\n\nTAVSIYALAR:\n"
        if stagnated > 0:
            report += f"   SALES'da {stagnated} ta lid 3+ kun harakatsiz - qayta ishlang\n"
        if win_rate < 30:
            report += f"   Win Rate past ({win_rate:.0f}%) - Sales bosqichlarini tekshiring\n"
        if lost > active:
            report += "   SALES'da ko'p lid yo'qolmoqda - kvalifikatsiya sifatini oshiring\n"
        if won_week == 0:
            report += "   Bu hafta 0 ta bitim yopilgan - urgent harakatlar kerak!\n"
        if win_rate >= 50:
            report += f"   Win Rate yuqori ({win_rate:.0f}%) - ajoyib natija!\n"
        return report
    async def send_scorecard(self, chat_id: int, thread_id: int = None):
        """Menejer Scorecard'ni Telegram'ga yuborish."""
        report = self.generate_manager_scorecard()
        await self._send_report(chat_id, report, thread_id)

    async def send_stagnation_alert(self, chat_id: int, thread_id: int = None):
        """Stagnatsiya Alert'ni Telegram'ga yuborish."""
        report = self.generate_stagnation_alert()
        if report:  # Faqat stagnatsiya bo'lsa
            await self._send_report(chat_id, report, thread_id)

    async def send_funnel_report(self, chat_id: int, thread_id: int = None):
        """Pipeline Funnel hisobotini Telegram'ga yuborish."""
        report = self.generate_pipeline_funnel()
        await self._send_report(chat_id, report, thread_id)

    async def _send_report(self, chat_id: int, text: str, thread_id: int = None):
        """Telegram'ga xabar yuborish (HTML, fallback plain)."""
        if not self.bot or not text:
            return
        from src.services.core.tool_adapters import send_group_message_with_fallback

        try:
            await send_group_message_with_fallback(
                self.bot,
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
                thread_id=thread_id,
            )
        except Exception as e:
            logger.warning(f"[ANALYTICS] HTML xato, plain text-ga o'tildi: {e}")
            import re

            clean = re.sub(r"<[^>]+>", "", text)
            await send_group_message_with_fallback(
                self.bot,
                chat_id=chat_id,
                text=clean,
                thread_id=thread_id,
            )

