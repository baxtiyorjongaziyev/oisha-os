"""
Daily and team sales efficiency reporting mixin for Enterprise Reporter.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)


class EfficiencyMixin:
    """Handles daily and team efficiency analytics and accountability segments."""

    async def get_daily_efficiency_report(self):
        """Kunlik hisobot: faqat bugungi o'zgarishlar va umumiy holat."""
        now = get_local_now()
        today_str = now.strftime("%Y-%m-%d")
        month_str = now.strftime("%Y-%m")
        report = [f"📊 <b>KUNLIK ENTERPRISE HISOBOT</b> ({today_str})\n"]

        # 1. SALES (AmoCRM)
        if self.crm:
            # Bugungi yopilgan bitimlar (Won)
            report.append("💰 <b>Sales Performance (Bugun):</b>")
            try:
                # Real-time data from AmoCRM
                leads = asyncio.run_coroutine_threadsafe(
                    self.crm.amocrm.get_leads_detailed(limit=50),
                    asyncio.get_event_loop(),
                ).result()
                won_today = [lead for lead in leads if lead.get("status_id") == self.WON_STATUS]
                lost_today = [lead for lead in leads if lead.get("status_id") == self.LOST_STATUS]
                active_leads = [
                    lead for lead in leads
                    if lead.get("status_id") not in (self.WON_STATUS, self.LOST_STATUS)
                ]
                total_sum = sum(lead.get("price", 0) for lead in won_today)
                pipeline_value = sum(lead.get("price", 0) for lead in active_leads)
                win_rate = (
                    round(len(won_today) / (len(won_today) + len(lost_today)) * 100)
                    if (won_today or lost_today)
                    else 0
                )

                report.append(f"- Yangi lidlar: <b>{len(leads)} ta</b>")
                report.append(
                    f"- Yopilgan bitimlar: <b>{len(won_today)} ta</b> ({total_sum:,.0f} so'm)"
                )
                report.append(f"- Win rate: <b>{win_rate}%</b>")
                report.append(f"- Aktiv pipeline: <b>{pipeline_value:,.0f} so'm</b> ({len(active_leads)} lid)")
            except Exception as e:
                logger.warning(f"Error getting lead statistics: {e}")
                report.append("- Ma'lumotlar olinmoqda... ⏳")

            # Plan-Fakt (Monthly context)
            targets = await self.db.get_department_targets(month_str)
            sales_target = next(
                (t["value"] for t in targets if t["dept"] == "Sales"), 0
            )
            if sales_target > 0:
                report.append(f"- Oylik reja: {sales_target:,.0f} so'm")

        # 2. PM (Airtable)
        if self.airtable:
            report.append("\n🏗 <b>Production (Airtable):</b>")
            try:
                from src.services.core.airtable_sync import AirtableSync as _AT
                projects = self.airtable.get_projects()
                overdue = self.airtable.get_overdue_projects()
                active_projects = [
                    p for p in projects
                    if _AT._get_field(p.get("fields", {}), "stage") not in _AT.DONE_STAGES
                ]
                report.append(f"- Aktiv loyihalar: <b>{len(active_projects)} ta</b>")
                if overdue:
                    report.append(f"- 🔴 Muddati o'tgan: <b>{len(overdue)} ta</b>")
                    for p in overdue[:3]:
                        fields = p.get("fields", {})
                        name = _AT._get_field(fields, "project_name") or "Nomsiz"
                        pm = _AT.resolve_pm_handle(_AT._get_field(fields, "manager")) or "Noma'lum"
                        report.append(f"  • {name} ({pm})")
                pm_set = set()
                for p in active_projects:
                    pm_val = _AT._get_field(p.get("fields", {}), "manager")
                    pm_handle = _AT.resolve_pm_handle(pm_val)
                    if pm_handle:
                        pm_set.add(pm_handle)
                if pm_set:
                    report.append(f"- PM lar: {', '.join(sorted(pm_set))}")
            except Exception as _pm_exc:
                logger.warning("[REPORTER] PM section error: %s", _pm_exc)
                projects = self.airtable.get_projects()
                report.append(f"- Aktiv loyihalar: {len(projects)} ta")

        # 3. FINANCE (Airtable)
        if self.airtable:
            finance_records = self.airtable.get_finance_records()
            today_income = 0
            today_expense = 0

            for rec in finance_records:
                f = rec.get("fields", {})
                rec_type = rec.get("_record_type", "")
                if rec_type == "income":
                    date_str = f.get("To'lov sanasi") or f.get("Sana") or ""
                    amount = f.get("To'lov miqdori") or f.get("Summa") or 0
                    if date_str and date_str.startswith(today_str):
                        today_income += amount
                elif rec_type == "expense":
                    date_str = f.get("Chiqim sanasi") or f.get("Sana") or ""
                    amount = f.get("Chiqim miqdori") or f.get("Summa") or 0
                    if date_str and date_str.startswith(today_str):
                        today_expense += amount

            if today_income > 0 or today_expense > 0:
                report.append("\n💰 <b>Moliya (Bugun):</b>")
                report.append(f"- Kirim: {today_income:,.0f} so'm".replace(",", " "))
                report.append(f"- Chiqim: {today_expense:,.0f} so'm".replace(",", " "))
                report.append(
                    f"- Net Foyda: <b>{(today_income - today_expense):,.0f} so'm</b>".replace(
                        ",", " "
                    )
                )

        # Pipeline Analyst metrics (agency-agents Pipeline Analyst framework)
        if self.crm:
            try:
                leads = asyncio.run_coroutine_threadsafe(
                    self.crm.amocrm.get_leads_detailed(limit=200),
                    asyncio.get_event_loop(),
                ).result()
                if leads:
                    active = [
                        l for l in leads
                        if l.get("status_id") not in (self.WON_STATUS, self.LOST_STATUS)
                    ]
                    won = [l for l in leads if l.get("status_id") == self.WON_STATUS]
                    lost = [l for l in leads if l.get("status_id") == self.LOST_STATUS]
                    avg_deal = (
                        sum(l.get("price", 0) for l in won) / len(won) if won else 0
                    )
                    win_rate_all = (
                        len(won) / (len(won) + len(lost)) if (won or lost) else 0
                    )
                    # Pipeline Velocity = (Qualified Opps × Avg Deal Size × Win Rate) / Avg Cycle Days
                    avg_cycle_days = 14  # baseline; refine with historical data
                    velocity = (
                        len(active) * avg_deal * win_rate_all / avg_cycle_days
                        if avg_cycle_days > 0
                        else 0
                    )
                    # Forecast tiers (simplified: Commit=Won, Best Case=active high-value, Upside=rest)
                    commit_value = sum(l.get("price", 0) for l in won)
                    best_case = sum(
                        l.get("price", 0) for l in active if l.get("price", 0) > avg_deal
                    )
                    report.append("\n📈 <b>Pipeline Velocity (Pipeline Analyst):</b>")
                    report.append(
                        f"- Velocity: <b>{velocity:,.0f} so'm/kun</b>"
                        f" ({len(active)} aktiv lid × {avg_deal:,.0f} avg × {win_rate_all:.0%} win rate)"
                    )
                    report.append(f"- Commit (Won): <b>{commit_value:,.0f} so'm</b>")
                    report.append(f"- Best Case (>avg deal): <b>{best_case:,.0f} so'm</b>")
            except Exception as exc:
                logger.debug(f"[REPORTER] Pipeline velocity calc skipped: {exc}")

        report.append(
            "\n🌙 <i>Bugungi kun uchun rahmat! Ertaga yanada yaxshiroq bo'lamiz.</i>"
        )
        return "\n".join(report)

    async def get_team_efficiency_report(self) -> str:
        """Jamoa va bo'limlar uchun umumiy samaradorlik hisoboti."""
        now = get_local_now()
        month_str = now.strftime("%Y-%m")

        report = []
        report.append("🏢 <b>Oisha-OS: Enterprise Audit</b>")
        report.append(f"⏱ <i>Hisobot vaqti: {now.strftime('%Y-%m-%d %H:%M')}</i>\n")

        # 1. SALES & MARKETING (AmoCRM)
        # Reja-fakt hisoblash
        targets = await self.db.get_department_targets(month_str)
        sales_target = next(
            (t["value"] for t in targets if t["dept"] == "Sales"), 80_000_000
        )

        leads = await self.crm.amocrm.get_leads_detailed(limit=100)

        # Oylik yopilgan bitimlar summasi (Fact)
        # Eslatma: AmoCRM API limitlari tufayli 'Won' larni alohida filtrlab olish kerak bo'lishi mumkin
        won_leads = [lead for lead in leads if lead.get("status_id") == self.WON_STATUS]
        total_won_sum = sum(lead.get("price", 0) for lead in won_leads)

        active_leads = len(
            [
                lead
                for lead in leads
                if lead.get("status_id") not in [self.WON_STATUS, self.LOST_STATUS]
            ]
        )

        report.append("💰 <b>Sales Performance:</b>")
        report.append(f"- Oylik Reja: {sales_target:,.0f} so'm".replace(",", " "))
        report.append(f"- Amalda (Won): {total_won_sum:,.0f} so'm".replace(",", " "))

        progress_pct = (total_won_sum / sales_target * 100) if sales_target > 0 else 0
        report.append(
            f"- Reja bajarilishi: <b>{progress_pct:.1f}%</b> {'✅' if progress_pct >= 100 else '📈'}"
        )
        report.append(f"- Aktiv lidlar: {active_leads} ta")

        # 2. MARKETING (Channels)
        # Manbalar tahlili (Tags orqali)
        channels = {}
        for lead in leads:
            # AmoCRM tags structure: _embedded.tags
            tags = lead.get("_embedded", {}).get("tags", [])
            for tag in tags:
                tag_name = tag.get("name", "Noma'lum")
                channels[tag_name] = channels.get(tag_name, 0) + 1

        if channels:
            top_channel = max(channels, key=channels.get)
            report.append("\n📢 <b>Marketing Awareness:</b>")
            report.append(
                f"- Top kanal: <b>{top_channel}</b> ({channels[top_channel]} lid)"
            )

        # 3. PRODUCTION & PM (Airtable)
        if self.airtable:
            projects = self.airtable.get_projects()
            overdue = self.airtable.get_overdue_projects()
            report.append("\n🏗 <b>Production & PM (Airtable):</b>")
            if not projects:
                report.append("- Airtable ma'lumoti olinmadi (API limit yoki ulanish xatosi)")
            else:
                report.append(f"- Aktiv loyihalar: {len(projects)} ta")

            # 3 kunlik ishlab chiqarish qoidasi (SLA: 3 days)
            urgent_projects = []
            now_dt = get_local_now()

            from src.services.core.airtable_sync import AirtableSync as _AT

            for p in projects:
                fields = p.get("fields", {})
                created_str = _AT._get_field(fields, "start_date")
                stage = _AT._get_field(fields, "stage") or ""

                if stage in _AT.DONE_STAGES:
                    continue

                if created_str:
                    try:
                        created_dt = datetime.datetime.fromisoformat(
                            created_str.replace("Z", "+00:00")
                        )
                        if created_dt.tzinfo:
                            now_utc = datetime.datetime.now(datetime.timezone.utc)
                            diff = now_utc - created_dt
                        else:
                            diff = now_dt - created_dt

                        if diff.days >= 2:
                            proj_name = (
                                _AT._get_field(fields, "project_name") or "Nomsiz"
                            )
                            urgent_projects.append(
                                f"{proj_name} ({diff.days} kun o'tdi)"
                            )
                    except (ValueError, TypeError, KeyError):
                        continue

            if overdue:
                report.append(f"- Muddati o'tgan: {len(overdue)} ta ⚠️")
                report.append(
                    f"- <b>SLA xavfi (3 kundan oshish arafasida):</b> {len(urgent_projects)} ta"
                )
                pm_mentions = set()
                for p in overdue:
                    fields = p.get("fields", {})
                    pm_value = _AT._get_field(fields, "manager")
                    pm_mention = _AT.resolve_pm_handle(pm_value)
                    if pm_mention:
                        pm_mentions.add(pm_mention)
                if pm_mentions:
                    mentions_str = ", ".join(sorted(pm_mentions))
                    report.append(f"  <i>(Iltimos, {mentions_str} nazoratga oling)</i>")
            elif projects:
                report.append("- Muddati o'tgan loyihalar yo'q ✅")

        # 4. FINANCE SUMMARY (Airtable — Kirim + Chiqim)
        if self.airtable:
            finance_records = self.airtable.get_finance_records()
            month_income = 0
            month_expense = 0
            current_month = datetime.datetime.now().strftime("%Y-%m")

            for rec in finance_records:
                f = rec.get("fields", {})
                rec_type = rec.get("_record_type", "")
                if rec_type == "income":
                    date_str = f.get("To'lov sanasi") or f.get("Sana") or ""
                    amount = f.get("To'lov miqdori") or f.get("Summa") or 0
                    if date_str and date_str.startswith(current_month):
                        month_income += amount
                elif rec_type == "expense":
                    date_str = f.get("Chiqim sanasi") or f.get("Sana") or ""
                    amount = f.get("Chiqim miqdori") or f.get("Summa") or 0
                    if date_str and date_str.startswith(current_month):
                        month_expense += amount

            report.append(f"\n📈 <b>Oylik Moliya ({current_month}):</b>")
            report.append(f"- Jami tushum: {month_income:,.0f} so'm".replace(",", " "))
            report.append(
                f"- Jami xarajat: {month_expense:,.0f} so'm".replace(",", " ")
            )
            net_profit = month_income - month_expense
            report.append(
                f"- <b>Sof Foyda: {net_profit:,.0f} so'm</b> {'🔥' if net_profit > 0 else '📉'}"
            )

        # 5. ACCOUNTABILITY (Tasks & Reports)
        report.append("\n" + await self.get_accountability_segment())

        report.append("\n👑 <b>XULOSA</b>")
        report.append(
            f"<i>Oisha-OS avtomatik hisobot — {get_local_now().strftime('%Y-%m-%d %H:%M')}</i>"
        )

        report.append("\n💡 <i>Tizimli yondashuv — o'sish poydevori!</i>")
        return "\n".join(report)

    async def get_accountability_segment(self) -> str:
        """Topshiriqlarni va hisobotlarni o'z vaqtida bajarmayotganlarni aniqlash."""
        report = []
        report.append("⚖️ <b>Accountability & Discipline:</b>")

        # 1. Muddati o'tgan vazifalar
        overdue_tasks = await self.db.get_overdue_tasks()
        task_count = await self.db.get_task_count()
        if overdue_tasks:
            report.append(
                f"- <b>Muddati o'tgan vazifalar:</b> {len(overdue_tasks)} ta ⚠️"
            )
            for t in overdue_tasks[:3]:
                name = t.get("name") or t.get("username") or "Unknown"
                task_label = t.get("title") or t.get("description") or "Vazifa"
                report.append(f"  • {task_label} — <i>{name}</i>")
            if len(overdue_tasks) > 3:
                report.append(f"  ... va yana {len(overdue_tasks)-3} ta.")
        elif task_count == 0:
            report.append("- Vazifalar tizimiga ma'lumot kiritilmagan")
        else:
            report.append("- Barcha vazifalar o'z vaqtida! ✅")

        # 2. Topshirilmagan hisobotlar (Bugun uchun)
        missing_reports = await self.db.get_missing_reports()
        if missing_reports:
            if missing_reports[0].get("username") == "N/A":
                report.append("- Jamoa tarkibi aniqlanmagan (users.role ma'lumoti yo'q)")
            else:
                names = [
                    f"@{m['username']}" if m["username"] else m["name"]
                    for m in missing_reports
                ]
                report.append(f"- <b>Bugun hisobot bermaganlar:</b> {', '.join(names)} 🛑")
        else:
            report.append("- Hamma hisobot topshirdi! 🌟")

        return "\n".join(report)
