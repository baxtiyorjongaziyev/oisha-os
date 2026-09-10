"""
Report formatting in Uzbek Markdown and Telegram delivery mixin.
"""
import asyncio
import logging
import os
from datetime import date
from typing import Any, Dict, Optional

from src.services.core.crm.daily_report.models import (
    CRMStats,
    CRMWeeklyStats,
    PeriodType,
    PeriodMetrics,
    compute_deltas,
    _delta,
    _fmt_duration,
)

logger = logging.getLogger(__name__)

DIVIDER = "────────────────────────────"

_UZ_MONTHS = [
    "", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr",
]


class FormatMixin:
    """Handles daily and weekly report formatting and Telegram group dispatch."""

    def format_report(self, *args):
        """Dispatch: PeriodType-first -> period report; else legacy daily report."""
        if args and isinstance(args[0], PeriodType):
            ptype, current, previous = (args + (None,))[:3]
            return self.format_period_report(ptype, current, previous)
        stats = args[0]
        prev = args[1] if len(args) > 1 else None
        return self._format_legacy_report(stats, prev)

    def _format_legacy_report(
        self,
        stats: CRMStats,
        prev: Optional[CRMStats] = None,
    ) -> str:
        """Reportagram formatida hisobot matni."""
        lines = [
            f"AmoCRM Kunlik Hisobot | 📅 {stats.date_label}",
            DIVIDER,
            f"Tushgan Leadlar: {stats.total_leads}"
            + (f"  {_delta(stats.total_leads, prev.total_leads)}" if prev else ""),
            f"Gaplashilgan Leadlar: {stats.contacted}"
            + (f"  {_delta(stats.contacted, prev.contacted)}" if prev else ""),
            f"Sifatli Leadlar: {stats.qualified}"
            + (f"  {_delta(stats.qualified, prev.qualified)}" if prev else ""),
            f"Muvaffaqiyatli: {stats.won}"
            + (f"  {_delta(stats.won, prev.won)}" if prev else ""),
            f"Daromad: ${stats.revenue:,.0f}"
            + (f"  {_delta(stats.revenue, prev.revenue)}" if prev else ""),
        ]

        if stats.incoming_calls:
            lines.append(
                f"Kiruvchi Qo'ng'iroqlar: {stats.incoming_calls}"
                + (f"  {_delta(stats.incoming_calls, prev.incoming_calls)}" if prev else "")
            )

        if stats.avg_response_sec > 0:
            lines.append(f"Bog'lanish tezligi: {_fmt_duration(stats.avg_response_sec)}")

        if stats.top_manager:
            lines.append(f"Top Sotuvchi: {stats.top_manager} ({stats.top_manager_count})")

        if stats.pipeline_value > 0:
            lines.append(f"Pipeline qiymati: ${stats.pipeline_value:,.0f}")

        lines.append("")
        lines.append("Sent via Oisha-OS")
        return "\n".join(lines)

    def format_weekly_report_uz(self, stats: CRMWeeklyStats) -> str:
        """Reportagramga yaqin, ammo o'zbekcha haftalik hisobot."""
        start = stats.period_start.strftime("%d.%m.%Y")
        end = stats.period_end.strftime("%d.%m.%Y")
        links = self._weekly_report_links(stats.period_start, stats.period_end)

        lines = [
            f"AmoCRM Haftalik Hisobot | {start} - {end}",
            DIVIDER,
            f"Aktiv bitimlar davr oxirida: {stats.active_leads:,}".replace(",", " "),
            f"Aktiv bitimlar summasi: {self._fmt_money(stats.active_amount)} so'm",
            f"Muvaffaqiyatli yopilgan bitimlar: {stats.won_leads:,}".replace(",", " "),
            f"Muvaffaqiyatli yopilgan summa: {self._fmt_money(stats.won_amount)} so'm",
            f"Bekor qilingan bitimlar: {stats.lost_leads:,}".replace(",", " "),
            f"Bekor qilingan summa: {self._fmt_money(stats.lost_amount)} so'm",
            f"Yangi bitimlar: {stats.new_leads:,}".replace(",", " "),
            f"Yangi kompaniyalar: {stats.new_companies:,}".replace(",", " "),
            f"Yangi kontaktlar: {stats.new_contacts:,}".replace(",", " "),
            "",
            self._weekly_summary_line(stats),
            "",
            "Havolalar:",
            f"[Aktiv bitimlar]({links['active']})",
            f"[Yangi bitimlar]({links['new_leads']})",
            f"[Muvaffaqiyatli]({links['won']})",
            f"[Bekor qilingan]({links['lost']})",
            f"[Yangi kompaniyalar]({links['companies']})",
            f"[Yangi kontaktlar]({links['contacts']})",
            "",
            "Sent via Oisha-OS",
        ]
        return "\n".join(lines)

    @staticmethod
    def _delta_str(cur, prev):
        if prev is None:
            return ""
        diff = cur - prev
        if abs(diff) < 1e-9:
            return "  —"
        sign = "▲ +" if diff > 0 else "▼ "
        return f"  {sign}{diff:,.0f}".replace(",", " ")

    @staticmethod
    def _period_heading(ptype):
        return {
            PeriodType.DAILY: "KUNLIK HISOBOT",
            PeriodType.WEEKLY: "HAFTALIK HISOBOT",
            PeriodType.MONTHLY: "OYLIK HISOBOT",
        }[ptype]

    @staticmethod
    def _period_label(ptype, start, end):
        if ptype == PeriodType.DAILY:
            return start.strftime("%d.%m.%Y")
        if ptype == PeriodType.WEEKLY:
            return f"{start.strftime('%d.%m')} - {end.strftime('%d.%m.%Y')}"
        return f"{_UZ_MONTHS[start.month]} {start.year}"

    def format_period_report(self, ptype, current, previous):
        p = previous
        d = self._delta_str
        m = current

        def pv(field):
            return getattr(p, field) if p is not None else None

        lines = [
            f"📊 AmoCRM {self._period_heading(ptype)} | {self._period_label(ptype, m.period_start, m.period_end)}",
            DIVIDER,
            "🎯 BITIMLAR",
            f"  Yangi bitimlar: {m.new_leads}{d(m.new_leads, pv('new_leads'))}",
            f"  Faol bitimlar: {m.active_count} ({self._fmt_money(m.active_amount)} so'm)",
            f"  Yutilgan: {m.won_count} ({self._fmt_money(m.won_amount)} so'm){d(m.won_count, pv('won_count'))}",
            f"  Yutqazilgan: {m.lost_count} ({self._fmt_money(m.lost_amount)} so'm){d(m.lost_count, pv('lost_count'))}",
            f"  Win rate: {m.win_rate:.0f}%{d(m.win_rate, pv('win_rate'))}",
            f"  O'rtacha yutilgan bitim: {self._fmt_money(m.avg_won_deal)} so'm",
            f"  Pipeline qiymati: {self._fmt_money(m.pipeline_value)} so'm",
            f"  ⚠️ Stagnatsiya (3+ kun): {m.stagnated_count}",
            "",
            "📞 ALOQA",
            f"  Yangi kontaktlar: {m.new_contacts}{d(m.new_contacts, pv('new_contacts'))}",
            f"  Yangi kompaniyalar: {m.new_companies}",
            f"  Kiruvchi qo'ng'iroqlar: {m.incoming_calls}{d(m.incoming_calls, pv('incoming_calls'))}",
            "",
            "✅ ZADACHALAR",
            f"  Yaratilgan: {m.tasks_created}{d(m.tasks_created, pv('tasks_created'))}",
            f"  Bajarilgan: {m.tasks_completed}",
            f"  Ochiq: {m.tasks_open}",
            f"  🔴 Muddati o'tgan: {m.tasks_overdue}",
            f"  🚨 Zadachasiz ochiq bitimlar: {m.leads_without_task}",
            "",
            "🏆 MENEJERLAR (yutilgan bo'yicha)",
        ]

        medals = ["🥇", "🥈", "🥉"]
        if not m.managers:
            lines.append("  Ma'lumot yo'q")
        for i, mr in enumerate(m.managers):
            badge = medals[i] if i < 3 else f"  {i + 1}."
            lines.append(
                f"  {badge} {mr.name} — {mr.won_count} ta / {self._fmt_money(mr.won_amount)} so'm"
            )
            if mr.open_tasks or mr.overdue_tasks:
                lines.append(
                    f"     └ ochiq zadacha: {mr.open_tasks} | muddati o'tgan: {mr.overdue_tasks}"
                )

        links = self._period_links(ptype, m.period_start, m.period_end)
        lines += [
            "",
            DIVIDER,
            "🔗 AmoCRM'da ochish:",
            f"  [Yangi bitimlar]({links['new_leads']}) · [Yutilgan]({links['won']}) · [Yutqazilgan]({links['lost']})",
            "",
            "Oisha-OS orqali yuborilgan",
        ]
        return "\n".join(lines)

    def _period_links(self, ptype, start, end):
        # reuse existing _weekly_report_links machinery for date filters
        return self._weekly_report_links(start, end)

    async def send_to_group(
        self,
        client: Any,
        chat_id: int,
        for_date: Optional[date] = None,
    ) -> bool:
        """Statistika olish va guruhga yuborish."""
        try:
            stats = await self.fetch_stats(for_date)
            prev  = await asyncio.to_thread(self._load_prev_stats, for_date)
            text  = self.format_report(stats, prev)
            await client.send_message(chat_id, text)
            logger.info(f"[CRMDailyReporter] Report sent to {chat_id}")
            return True
        except Exception as exc:
            logger.error(f"[CRMDailyReporter] send_to_group failed: {exc}")
            return False


    @staticmethod
    def _fmt_money(value: float) -> str:
        return f"{int(round(value)):,}".replace(",", " ")

    def _weekly_report_links(self, period_start: date, period_end: date) -> Dict[str, str]:
        base_url = getattr(self._crm, "base_url", "") if self._crm else ""
        if not base_url:
            subdomain = os.getenv("AMOCRM_SUBDOMAIN", "").strip()
            base_url = f"https://{subdomain}.amocrm.ru" if subdomain else ""

        start = period_start.strftime("%d.%m.%Y")
        end = period_end.strftime("%d.%m.%Y")
        pipeline_ids = [
            raw.strip()
            for raw in os.getenv(
                "CRM_REPORT_PIPELINE_IDS", ",".join(self.DEFAULT_REPORT_PIPELINE_IDS)
            ).split(",")
            if raw.strip()
        ]

        def status_url(status_id: int) -> str:
            query = (
                f"{base_url}/gtd/leads/list/?useFilter=y"
                f"&filter_date_switch=closed"
                f"&filter_date_from={start}&filter_date_to={end}"
            )
            for pipeline_id in pipeline_ids:
                query += f"&filter%5Bpipe%5D%5B{pipeline_id}%5D%5B0%5D={status_id}"
            return query

        return {
            "active": (
                f"{base_url}/gtd/leads/list/?filter%5Bstatus%5D=opened"
                f"&filter_date_from={start}&filter_date_to={end}"
            ),
            "new_leads": (
                f"{base_url}/gtd/leads/list/?useFilter=y&show_all_leads=y"
                f"&filter_date_switch=created"
                f"&filter_date_from={start}&filter_date_to={end}"
            ),
            "won": status_url(self.WON_STATUS),
            "lost": status_url(self.LOST_STATUS),
            "companies": (
                f"{base_url}/gtd/contacts/list/companies/?useFilter=y"
                f"&filter_date_switch=created"
                f"&filter_date_from={start}&filter_date_to={end}"
            ),
            "contacts": (
                f"{base_url}/gtd/contacts/list/contacts/?useFilter=y"
                f"&filter_date_switch=created"
                f"&filter_date_from={start}&filter_date_to={end}"
            ),
        }

    @staticmethod
    def _weekly_summary_line(stats: CRMWeeklyStats) -> str:
        if stats.new_leads and not stats.won_leads and not stats.lost_leads:
            return (
                "Xulosa: hafta davomida yangi bitimlar tushgan, lekin yopilishlar "
                "CRMda qayd etilmagan. Menejerlar keyingi qadam va statuslarni "
                "yangilashi kerak."
            )
        if stats.won_leads:
            conversion = (stats.won_leads / max(stats.new_leads, 1)) * 100
            return f"Xulosa: haftalik yutish ko'rsatkichi taxminan {conversion:.1f}%."
        return "Xulosa: hafta bo'yicha CRM snapshot tayyor."

