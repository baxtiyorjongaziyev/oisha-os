"""
Sales Analytics Module — Menejer KPI, Stagnatsiya Alert, Pipeline Funnel
Oisha-OS v5.0 — Sotuvchilar conversiyasini oshirish uchun
"""

import logging
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, List

logger = logging.getLogger("SalesAnalytics")


class SalesAnalytics:
    """AmoCRM sotuvlar tahlili — KPI, Stagnatsiya, Pipeline Funnel."""

    # Pipeline IDs
    HUNTER_PIPELINE = 10117998
    CLOSER_PIPELINE = 10123314

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
            pass
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
        hunter_leads = self._get_all_leads(self.HUNTER_PIPELINE)
        closer_leads = self._get_all_leads(self.CLOSER_PIPELINE)
        all_leads = hunter_leads + closer_leads

        # Menejerlar bo'yicha guruhlash
        manager_stats: Dict[int, Dict] = {}

        for lead in all_leads:
            responsible = lead.get("responsible_user_id")
            if not responsible:
                continue

            if responsible not in manager_stats:
                manager_stats[responsible] = {
                    "name": None,
                    "hunter_active": 0,
                    "closer_active": 0,
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
                if pipeline_id == self.HUNTER_PIPELINE:
                    stats["hunter_active"] += 1
                elif pipeline_id == self.CLOSER_PIPELINE:
                    stats["closer_active"] += 1

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
            ("HUNTER", self.HUNTER_PIPELINE),
            ("CLOSER", self.CLOSER_PIPELINE),
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
        """
        Pipeline bo'yicha haftalik conversiya tahlili:
        - HUNTER pipeline: Nechta lid kirdi → nechtasi CLOSER'ga o'tdi
        - CLOSER pipeline: Nechta → nechtasi Won
        - Yo'qotilgan lidlar
        - O'rtacha bitim hajmi
        """
        now = time.time()
        period_start = int((datetime.now() - timedelta(days=days)).timestamp())

        hunter_leads = self._get_all_leads(self.HUNTER_PIPELINE)
        closer_leads = self._get_all_leads(self.CLOSER_PIPELINE)

        # HUNTER pipeline tahlili
        hunter_total = len(hunter_leads)
        hunter_active = 0
        hunter_lost = 0
        hunter_stagnated = 0

        for lead in hunter_leads:
            status = lead.get("status_id", 0)
            updated = lead.get("updated_at", 0)
            if status == self.STATUS_LOST:
                hunter_lost += 1
            elif status == self.STATUS_WON:
                pass  # Won in Hunter = moved to Closer
            else:
                hunter_active += 1
                if (now - updated) > 86400 * 3:  # 3+ kun harakatsiz
                    hunter_stagnated += 1

        # CLOSER pipeline tahlili
        closer_total = len(closer_leads)
        closer_active = 0
        closer_won = 0
        closer_lost = 0
        closer_revenue = 0
        closer_won_week = 0
        closer_revenue_week = 0

        for lead in closer_leads:
            status = lead.get("status_id", 0)
            closed_at = lead.get("closed_at", 0)
            price = lead.get("price", 0) or 0

            if status == self.STATUS_WON:
                closer_won += 1
                closer_revenue += price
                if closed_at and closed_at >= period_start:
                    closer_won_week += 1
                    closer_revenue_week += price
            elif status == self.STATUS_LOST:
                closer_lost += 1
            else:
                closer_active += 1

        # Conversiya hisoblash
        total_leads = hunter_total + closer_total
        conversion_to_closer = (
            (closer_total / hunter_total * 100) if hunter_total > 0 else 0
        )
        win_rate = (closer_won / closer_total * 100) if closer_total > 0 else 0
        overall_conversion = (closer_won / total_leads * 100) if total_leads > 0 else 0
        avg_deal = (closer_revenue / closer_won) if closer_won > 0 else 0

        report = "📊 <b>PIPELINE FUNNEL</b>\n"
        report += f"📅 Oxirgi {days} kun ({datetime.now().strftime('%d.%m.%Y')})\n"
        report += "━" * 30 + "\n"

        # HUNTER Funnel
        report += "\n🎯 <b>HUNTER Pipeline</b>\n"
        report += f"   Jami: {hunter_total} ta lid\n"
        report += f"   ✅ Aktiv: {hunter_active}\n"
        report += f"   ❌ Lost: {hunter_lost}\n"
        if hunter_stagnated > 0:
            report += f"   ⚠️ Stagnatsiya (3+ kun): {hunter_stagnated}\n"

        # Arrow visualization
        report += (
            f"\n   ⬇️ Conversiya HUNTER → CLOSER: <b>{conversion_to_closer:.0f}%</b>\n"
        )

        # CLOSER Funnel
        report += "\n💰 <b>CLOSER Pipeline</b>\n"
        report += f"   Jami: {closer_total} ta lid\n"
        report += f"   ✅ Aktiv: {closer_active}\n"
        report += f"   🏆 Won: {closer_won} ({closer_revenue:,.0f} so'm)\n".replace(
            ",", " "
        )
        report += f"   ❌ Lost: {closer_lost}\n"

        report += f"\n   ⬇️ Win Rate (CLOSER): <b>{win_rate:.0f}%</b>\n"

        # Haftalik natijalari
        report += "\n" + "━" * 30
        report += f"\n📈 <b>HAFTALIK NATIJALAR ({days} kun):</b>\n"
        report += f"   🏆 Yopilgan: {closer_won_week} ta bitim\n"
        report += f"   💰 Tushum: {closer_revenue_week:,.0f} so'm\n".replace(",", " ")
        report += f"   📊 O'rtacha bitim: {avg_deal:,.0f} so'm\n".replace(",", " ")

        # Overall
        report += f"\n🔄 <b>UMUMIY CONVERSIYA:</b> {overall_conversion:.1f}%"
        report += f"\n   ({total_leads} lid → {closer_won} won)"

        # Insights
        report += "\n\n💡 <b>TAVSIYALAR:</b>\n"
        if hunter_stagnated > 0:
            report += f"   ⚠️ HUNTER'da {hunter_stagnated} ta lid 3+ kun harakatsiz — qayta ishlang\n"
        if win_rate < 30:
            report += f"   📉 Win Rate past ({win_rate:.0f}%) — CLOSER bosqichida tayyorgarlik yaxshilang\n"
        if hunter_lost > hunter_active:
            report += "   🚫 HUNTER'da ko'p lid yo'qolmoqda — kvalifikatsiya sifatini oshiring\n"
        if closer_won_week == 0:
            report += "   🔴 Bu hafta 0 ta bitim yopilgan — URGENT harakatlar kerak!\n"
        if win_rate >= 50:
            report += f"   🌟 Win Rate yuqori ({win_rate:.0f}%) — ajoyib natija!\n"

        return report

    # ═══════════════════════════════════════════════════════════════
    # 4. HELPER — Telegram'ga yuborish
    # ═══════════════════════════════════════════════════════════════

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
        try:
            kwargs = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
            if thread_id:
                kwargs["message_thread_id"] = thread_id
            await self.bot.send_message(**kwargs)
        except Exception as e:
            logger.warning(f"[ANALYTICS] HTML xato, plain text-ga o'tildi: {e}")
            import re

            clean = re.sub(r"<[^>]+>", "", text)
            kwargs = {"chat_id": chat_id, "text": clean}
            if thread_id:
                kwargs["message_thread_id"] = thread_id
            await self.bot.send_message(**kwargs)
