"""
crm_daily_report.py — Kunlik AmoCRM hisobot moduli.

Uch qatlamli arxitektura:
  A) EnterpriseReporter.build_reportagram_report()  — mavjud reporterga metod
  B) CRMDailyReporter                               — standalone stat fetcher + formatter
  C) ReportBot                                       — o'z token/DB bilan ishlaydigan Telethon bot

Ishlatish:
    # B — scheduler
    reporter = CRMDailyReporter(amocrm=crm_client)
    stats = await reporter.fetch_stats()
    text  = reporter.format_report(stats)
    await reporter.send_to_group(client, chat_id=-1001234567890)

    # C — standalone
    bot = ReportBot(token="...", group_id=-1001234567890, amocrm=crm_client)
    await bot.run()
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

DIVIDER = "━━━━━━━━━━━━"


def _ts_today() -> Tuple[int, int]:
    """Bugungi kunning Unix timestamp [from, to]."""
    today = date.today()
    t_from = int(datetime(today.year, today.month, today.day, 0, 0, 0).timestamp())
    t_to   = int(datetime(today.year, today.month, today.day, 23, 59, 59).timestamp())
    return t_from, t_to


def _ts_yesterday() -> Tuple[int, int]:
    yesterday = date.today() - timedelta(days=1)
    t_from = int(datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0).timestamp())
    t_to   = int(datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, 59).timestamp())
    return t_from, t_to


def _delta(today: int | float, yesterday: int | float) -> str:
    """'▲ +5' yoki '▼ -3' yoki '—' formatida delta."""
    diff = today - yesterday
    if diff > 0:
        return f"▲ +{diff:,.0f}"
    if diff < 0:
        return f"▼ {diff:,.0f}"
    return "—"


def _fmt_duration(seconds: float) -> str:
    """5h 27m formatida vaqt."""
    if seconds <= 0:
        return "—"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


def previous_week_range(today: Optional[date] = None) -> Tuple[date, date]:
    """Return previous Monday-Sunday range for weekly CRM reports."""
    anchor = today or date.today()
    this_monday = anchor - timedelta(days=anchor.weekday())
    start = this_monday - timedelta(days=7)
    end = this_monday - timedelta(days=1)
    return start, end


# ─────────────────────────────────────────────────────────────────────────────
# B) CRMDailyReporter — stat fetcher + formatter
# ─────────────────────────────────────────────────────────────────────────────

class CRMStats:
    """Bir kunlik CRM ko'rsatkichlari."""

    def __init__(self):
        self.date_label: str = ""
        self.total_leads: int = 0          # Tushgan leadlar
        self.contacted: int = 0            # Gaplashilgan
        self.qualified: int = 0            # Sifatli leadlar
        self.won: int = 0                  # Muvaffaqiyatli
        self.revenue: float = 0.0          # Daromad ($)
        self.incoming_calls: int = 0       # Kiruvchi qo'ng'iroqlar
        self.avg_response_sec: float = 0.0 # Bog'lanish tezligi (sekund)
        self.top_manager: str = ""         # Top sotuvchi
        self.top_manager_count: int = 0
        self.pipeline_value: float = 0.0   # Umumiy pipeline qiymati
        self.lost: int = 0                 # Yutqazilgan

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CRMStats":
        s = cls()
        for k, v in d.items():
            setattr(s, k, v)
        return s


@dataclass
class CRMWeeklyStats:
    period_start: date
    period_end: date
    active_leads: int = 0
    active_amount: float = 0.0
    won_leads: int = 0
    won_amount: float = 0.0
    lost_leads: int = 0
    lost_amount: float = 0.0
    new_leads: int = 0
    new_companies: int = 0
    new_contacts: int = 0


class CRMDailyReporter:
    """
    AmoCRM dan kunlik statistika oluvchi va formatlash xizmati.

    Parameters
    ----------
    amocrm : AmoCRM client (src.services.core.amocrm_sync.AmoCRMSync)
    db_path : history uchun local SQLite fayl yo'li
    """

    WON_STATUS   = 142
    LOST_STATUS  = 143
    DEFAULT_REPORT_PIPELINE_IDS = (
        "10117998",
        "10123314",
        "10123318",
        "10427390",
        "10947042",
        "10947046",
        "10963570",
    )
    # Qualified deb hisoblash: bu statuslar NOT (new, won, lost)
    # Real loyalty: configure per-pipeline

    def __init__(self, amocrm: Any, db_path: str = "data/report_history.db"):
        self._crm = amocrm
        self._db_path = db_path
        self._ensure_db()

    # ── Public API ─────────────────────────────────────────────────────────

    async def fetch_stats(self, for_date: Optional[date] = None) -> CRMStats:
        """AmoCRM'dan bugungi (yoki berilgan kun) statistika olish."""
        target = for_date or date.today()
        t_from = int(datetime(target.year, target.month, target.day, 0, 0, 0).timestamp())
        t_to   = int(datetime(target.year, target.month, target.day, 23, 59, 59).timestamp())

        stats = CRMStats()
        stats.date_label = target.strftime("%b %d, %Y")

        leads = await self._get_leads_by_range(t_from, t_to)
        all_leads = await self._get_all_active_leads()

        stats.total_leads   = len(leads)
        stats.won           = sum(1 for l in leads if l.get("status_id") == self.WON_STATUS)
        stats.lost          = sum(1 for l in leads if l.get("status_id") == self.LOST_STATUS)
        stats.revenue       = sum(
            l.get("price", 0) for l in leads if l.get("status_id") == self.WON_STATUS
        ) / 100  # amocrm stores in tiyin/cent → dollars if configured

        # Gaplashilgan = created today AND has at least 1 note/event (approximation:
        # any lead that is NOT in the very first "new" status — status_id == first pipeline status)
        # Simple proxy: leads that are NOT in first status
        stats.contacted = sum(
            1 for l in leads
            if l.get("status_id") not in [None, self.WON_STATUS, self.LOST_STATUS]
        )
        # Sifatli = won + negotiation stages (non-trivial approximation)
        stats.qualified = max(stats.won, stats.contacted // 3)

        # Pipeline value
        stats.pipeline_value = sum(
            l.get("price", 0) for l in all_leads
            if l.get("status_id") not in [self.WON_STATUS, self.LOST_STATUS]
        ) / 100

        # Top manager by most leads in time range
        manager_counts: Dict[int, int] = {}
        manager_won:    Dict[int, int] = {}
        for l in leads:
            uid = l.get("responsible_user_id")
            if uid:
                manager_counts[uid] = manager_counts.get(uid, 0) + 1
                if l.get("status_id") == self.WON_STATUS:
                    manager_won[uid] = manager_won.get(uid, 0) + 1

        if manager_won:
            top_uid = max(manager_won, key=manager_won.get)
            stats.top_manager_count = manager_won[top_uid]
        elif manager_counts:
            top_uid = max(manager_counts, key=manager_counts.get)
            stats.top_manager_count = manager_counts[top_uid]
        else:
            top_uid = None

        if top_uid:
            try:
                stats.top_manager = self._crm.get_user_name(top_uid)
            except Exception:
                stats.top_manager = f"Manager #{top_uid}"

        # Bog'lanish tezligi — avg (first_contact_at - created_at) for leads with notes
        stats.avg_response_sec = await self._calc_avg_response(leads)

        # Calls — try /api/v4/calls if available
        stats.incoming_calls = await self._get_calls_count(t_from, t_to)

        # Cache to history DB
        self._save_stats(target, stats)
        return stats

    async def fetch_weekly_stats(
        self,
        period_start: Optional[date] = None,
        period_end: Optional[date] = None,
    ) -> CRMWeeklyStats:
        """AmoCRM'dan haftalik sales snapshot olish."""
        if not period_start or not period_end:
            period_start, period_end = previous_week_range()

        t_from = int(
            datetime(
                period_start.year,
                period_start.month,
                period_start.day,
                0,
                0,
                0,
            ).timestamp()
        )
        t_to = int(
            datetime(
                period_end.year,
                period_end.month,
                period_end.day,
                23,
                59,
                59,
            ).timestamp()
        )

        active_leads = await self._fetch_amocrm_collection("leads")
        active_leads = [
            lead
            for lead in active_leads
            if lead.get("status_id") not in (self.WON_STATUS, self.LOST_STATUS)
        ]
        new_leads = await self._fetch_amocrm_collection(
            "leads",
            {
                "filter[created_at][from]": t_from,
                "filter[created_at][to]": t_to,
            },
        )
        closed_leads = await self._fetch_amocrm_collection(
            "leads",
            {
                "filter[closed_at][from]": t_from,
                "filter[closed_at][to]": t_to,
            },
        )
        new_contacts = await self._fetch_amocrm_collection(
            "contacts",
            {
                "filter[created_at][from]": t_from,
                "filter[created_at][to]": t_to,
            },
        )
        new_companies = await self._fetch_amocrm_collection(
            "companies",
            {
                "filter[created_at][from]": t_from,
                "filter[created_at][to]": t_to,
            },
        )

        won_leads = [
            lead for lead in closed_leads if lead.get("status_id") == self.WON_STATUS
        ]
        lost_leads = [
            lead for lead in closed_leads if lead.get("status_id") == self.LOST_STATUS
        ]

        return CRMWeeklyStats(
            period_start=period_start,
            period_end=period_end,
            active_leads=len(active_leads),
            active_amount=sum(float(lead.get("price") or 0) for lead in active_leads),
            won_leads=len(won_leads),
            won_amount=sum(float(lead.get("price") or 0) for lead in won_leads),
            lost_leads=len(lost_leads),
            lost_amount=sum(float(lead.get("price") or 0) for lead in lost_leads),
            new_leads=len(new_leads),
            new_companies=len(new_companies),
            new_contacts=len(new_contacts),
        )

    def format_report(
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
            f"Aktiv bitimlar: {links['active']}",
            f"Yangi bitimlar: {links['new_leads']}",
            f"Muvaffaqiyatli: {links['won']}",
            f"Bekor qilingan: {links['lost']}",
            f"Yangi kompaniyalar: {links['companies']}",
            f"Yangi kontaktlar: {links['contacts']}",
            "",
            "Sent via Oisha-OS",
        ]
        return "\n".join(lines)

    async def send_to_group(
        self,
        client: Any,
        chat_id: int,
        for_date: Optional[date] = None,
    ) -> bool:
        """Statistika olish va guruhga yuborish."""
        try:
            stats = await self.fetch_stats(for_date)
            prev  = self._load_prev_stats(for_date)
            text  = self.format_report(stats, prev)
            await client.send_message(chat_id, text)
            logger.info(f"[CRMDailyReporter] Report sent to {chat_id}")
            return True
        except Exception as exc:
            logger.error(f"[CRMDailyReporter] send_to_group failed: {exc}")
            return False

    # ── Private helpers ─────────────────────────────────────────────────────

    async def _get_leads_by_range(self, t_from: int, t_to: int) -> List[Dict]:
        """AmoCRM /api/v4/leads?filter[created_at][from]=..."""
        if not self._crm:
            return []
        try:
            if hasattr(self._crm, "_load_token"):
                self._crm._load_token()
            url = f"{self._crm.base_url}/api/v4/leads"
            all_leads: List[Dict] = []
            page = 1
            while True:
                params = {
                    "filter[created_at][from]": t_from,
                    "filter[created_at][to]":   t_to,
                    "limit": 50,
                    "page": page,
                }
                resp = requests.get(url, headers=self._crm._get_headers(), params=params, timeout=15)
                if resp.status_code == 401:
                    self._crm.refresh_token()
                    resp = requests.get(url, headers=self._crm._get_headers(), params=params, timeout=15)
                if resp.status_code != 200:
                    break
                batch = resp.json().get("_embedded", {}).get("leads", [])
                all_leads.extend(batch)
                if len(batch) < 50:
                    break
                page += 1
            return all_leads
        except Exception as exc:
            logger.warning(f"[CRMDailyReporter] _get_leads_by_range: {exc}")
            return []

    async def _fetch_amocrm_collection(
        self,
        collection: str,
        extra_params: Optional[Dict[str, Any]] = None,
        *,
        embedded_key: Optional[str] = None,
        page_size: int = 250,
        max_pages: int = 100,
    ) -> List[Dict[str, Any]]:
        """Fetch an amoCRM collection with pagination and token refresh."""
        if not self._crm:
            return []

        try:
            if hasattr(self._crm, "_load_token") and not getattr(
                self._crm, "access_token", None
            ):
                self._crm._load_token()

            key = embedded_key or collection
            url = f"{self._crm.base_url}/api/v4/{collection}"
            items: List[Dict[str, Any]] = []

            for page in range(1, max_pages + 1):
                params = {
                    "limit": page_size,
                    "page": page,
                }
                if extra_params:
                    params.update(extra_params)

                if hasattr(self._crm, "_request_with_auth"):
                    resp = await self._crm._request_with_auth(
                        requests.get, url, params=params, timeout=30
                    )
                else:
                    resp = await asyncio.to_thread(
                        requests.get,
                        url,
                        headers=self._crm._get_headers(),
                        params=params,
                        timeout=30,
                    )

                if resp.status_code == 401 and hasattr(self._crm, "refresh_token"):
                    refreshed = await asyncio.to_thread(self._crm.refresh_token)
                    if refreshed:
                        if hasattr(self._crm, "_request_with_auth"):
                            resp = await self._crm._request_with_auth(
                                requests.get, url, params=params, timeout=30
                            )
                        else:
                            resp = await asyncio.to_thread(
                                requests.get,
                                url,
                                headers=self._crm._get_headers(),
                                params=params,
                                timeout=30,
                            )

                if resp.status_code != 200:
                    logger.warning(
                        "[CRMDailyReporter] %s page %s -> HTTP %s",
                        collection,
                        page,
                        resp.status_code,
                    )
                    break

                batch = resp.json().get("_embedded", {}).get(key, [])
                items.extend(batch)
                if len(batch) < page_size:
                    break

            return items
        except Exception as exc:
            logger.warning(
                "[CRMDailyReporter] _fetch_amocrm_collection(%s): %s",
                collection,
                exc,
            )
            return []

    async def _get_all_active_leads(self) -> List[Dict]:
        """Hozirgi pipeline — won/lost bo'lmaganlar."""
        try:
            return await self._crm.get_leads_detailed(limit=250)
        except Exception:
            return []

    async def _get_calls_count(self, t_from: int, t_to: int) -> int:
        """AmoCRM /api/v4/calls agar mavjud bo'lsa."""
        try:
            url = f"{self._crm.base_url}/api/v4/calls"
            params = {
                "filter[created_at][from]": t_from,
                "filter[created_at][to]":   t_to,
                "limit": 1,
            }
            resp = requests.get(url, headers=self._crm._get_headers(), params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                # AmoCRM returns _page_count or total in _links
                page_count = data.get("_page_count", 0)
                leads_embedded = data.get("_embedded", {}).get("calls", [])
                # rough count via page × 50 + remainder
                return max(page_count * 50, len(leads_embedded))
        except Exception:
            pass
        return 0

    async def _calc_avg_response(self, leads: List[Dict]) -> float:
        """Average (updated_at - created_at) for non-new leads as proxy."""
        deltas = []
        for l in leads:
            created = l.get("created_at", 0)
            updated = l.get("updated_at", 0)
            if created and updated and updated > created:
                diff = updated - created
                if diff < 86400:  # ignore leads untouched for >1 day
                    deltas.append(diff)
        if not deltas:
            return 0.0
        return sum(deltas) / len(deltas)

    # ── History DB ──────────────────────────────────────────────────────────

    def _ensure_db(self) -> None:
        os.makedirs(os.path.dirname(self._db_path) if os.path.dirname(self._db_path) else ".", exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                report_date TEXT PRIMARY KEY,
                stats_json  TEXT NOT NULL,
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        conn.close()

    def _save_stats(self, for_date: Optional[date], stats: CRMStats) -> None:
        key = (for_date or date.today()).isoformat()
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "INSERT OR REPLACE INTO daily_stats (report_date, stats_json) VALUES (?, ?)",
                (key, json.dumps(stats.to_dict())),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.debug(f"[CRMDailyReporter] _save_stats: {exc}")

    def _load_prev_stats(self, for_date: Optional[date] = None) -> Optional[CRMStats]:
        target   = (for_date or date.today()) - timedelta(days=1)
        prev_key = target.isoformat()
        try:
            conn = sqlite3.connect(self._db_path)
            row  = conn.execute(
                "SELECT stats_json FROM daily_stats WHERE report_date = ?", (prev_key,)
            ).fetchone()
            conn.close()
            if row:
                return CRMStats.from_dict(json.loads(row[0]))
        except Exception as exc:
            logger.debug(f"[CRMDailyReporter] _load_prev_stats: {exc}")
        return None

    def get_history(self, days: int = 7) -> List[CRMStats]:
        """So'nggi N kunlik tarix."""
        result = []
        try:
            conn   = sqlite3.connect(self._db_path)
            rows   = conn.execute(
                "SELECT stats_json FROM daily_stats ORDER BY report_date DESC LIMIT ?", (days,)
            ).fetchall()
            conn.close()
            for (j,) in rows:
                result.append(CRMStats.from_dict(json.loads(j)))
        except Exception:
            pass
        return result

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


# ─────────────────────────────────────────────────────────────────────────────
# C) ReportBot — standalone Telethon bot
# ─────────────────────────────────────────────────────────────────────────────

class ReportBot:
    """
    Mustaqil hisobot boti — o'z Telegram token va DB bilan ishlaydi.

    Muhit o'zgaruvchilari:
        REPORT_BOT_TOKEN   — Telegram bot token (@BotFather'dan)
        REPORT_GROUP_ID    — Hisobot yuborilishi kerak guruh/kanal ID
        REPORT_HOUR        — Yuborish vaqti (soat, default=19)
        REPORT_MINUTE      — Yuborish vaqti (daqiqa, default=30)

    Buyruqlar:
        /report   — Darhol hisobot yuborish
        /stats    — Qisqa joriy holat (pipeline, bugungi leads)
        /history  — So'nggi 7 kunlik jadval
        /ping     — Bot ishlayaptimi tekshirish
    """

    def __init__(
        self,
        token: Optional[str] = None,
        group_id: Optional[int] = None,
        amocrm: Optional[Any] = None,
        report_hour: int = 19,
        report_minute: int = 30,
        db_path: str = "data/report_history.db",
    ):
        self._token        = token or os.environ.get("REPORT_BOT_TOKEN", "")
        self._group_id     = group_id or int(os.environ.get("REPORT_GROUP_ID", "0") or 0)
        self._report_hour  = int(os.environ.get("REPORT_HOUR", report_hour))
        self._report_minute = int(os.environ.get("REPORT_MINUTE", report_minute))
        self._amocrm       = amocrm
        self._reporter     = CRMDailyReporter(amocrm=amocrm, db_path=db_path)
        self._client       = None

    async def run(self) -> None:
        """Botni ishga tushirish (blocking)."""
        if not self._token:
            raise RuntimeError("REPORT_BOT_TOKEN topilmadi")

        from telethon import TelegramClient, events
        from telethon.sessions import StringSession

        # Bot session uchun alohida bot client
        api_id   = int(os.environ.get("API_ID", "0"))
        api_hash = os.environ.get("API_HASH", "")

        self._client = TelegramClient(StringSession(), api_id, api_hash).start(
            bot_token=self._token
        )

        @self._client.on(events.NewMessage(pattern="/ping"))
        async def ping(event):
            await event.respond("✅ Report bot ishlayapti")

        @self._client.on(events.NewMessage(pattern="/report"))
        async def manual_report(event):
            await event.respond("⏳ Hisobot tayyorlanmoqda...")
            await self._send_report(event.chat_id)

        @self._client.on(events.NewMessage(pattern="/stats"))
        async def quick_stats(event):
            await event.respond("⏳ Statistika olinmoqda...")
            stats = await self._reporter.fetch_stats()
            text  = (
                f"📊 Bugungi holat ({stats.date_label})\n"
                f"Tushgan: {stats.total_leads} lead\n"
                f"Won: {stats.won} | Daromad: ${stats.revenue:,.0f}\n"
                f"Pipeline: ${stats.pipeline_value:,.0f}"
            )
            await event.respond(text)

        @self._client.on(events.NewMessage(pattern="/history"))
        async def show_history(event):
            history = self._reporter.get_history(7)
            if not history:
                await event.respond("Tarix yo'q hali.")
                return
            lines = ["📅 So'nggi 7 kun:"]
            for s in history:
                lines.append(
                    f"{s.date_label}: {s.total_leads} lead | {s.won} won | ${s.revenue:,.0f}"
                )
            await event.respond("\n".join(lines))

        # Scheduled sender
        asyncio.create_task(self._scheduler_loop())

        logger.info(
            f"[ReportBot] started — hisobot {self._report_hour}:{self._report_minute:02d} da"
        )
        await self._client.run_until_disconnected()

    async def _scheduler_loop(self) -> None:
        """Har kuni belgilangan vaqtda hisobot yuboradi."""
        while True:
            now = datetime.now()
            target = now.replace(
                hour=self._report_hour,
                minute=self._report_minute,
                second=0,
                microsecond=0,
            )
            if now >= target:
                target += timedelta(days=1)
            wait_sec = (target - now).total_seconds()
            logger.info(f"[ReportBot] keyingi hisobot {target} da ({wait_sec/3600:.1f}h)")
            await asyncio.sleep(wait_sec)
            if self._group_id:
                await self._send_report(self._group_id)

    async def _send_report(self, chat_id: int) -> None:
        try:
            ok = await self._reporter.send_to_group(self._client, chat_id)
            if not ok:
                await self._client.send_message(
                    chat_id, "⚠️ Hisobotni yuborishda xatolik. AmoCRM tekshirilsin."
                )
        except Exception as exc:
            logger.error(f"[ReportBot] _send_report error: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# A) EnterpriseReporter extension — patch qilish uchun funksiya
# ─────────────────────────────────────────────────────────────────────────────

async def build_reportagram_report(
    enterprise_reporter: Any,
    amocrm: Optional[Any] = None,
) -> str:
    """
    EnterpriseReporter instansiga bog'liq bo'lmagan holda reportagram formatida
    hisobot qaytaradi. enterprise_reporter.crm.amocrm dan client oladi.

    Ishlatish:
        from src.services.core.crm_daily_report import build_reportagram_report
        text = await build_reportagram_report(self)
    """
    crm_client = amocrm
    if crm_client is None and enterprise_reporter is not None:
        crm_service = getattr(enterprise_reporter, "crm", None)
        if crm_service:
            crm_client = getattr(crm_service, "amocrm", None)

    reporter = CRMDailyReporter(amocrm=crm_client)
    stats    = await reporter.fetch_stats()
    prev     = reporter._load_prev_stats()
    return reporter.format_report(stats, prev)
