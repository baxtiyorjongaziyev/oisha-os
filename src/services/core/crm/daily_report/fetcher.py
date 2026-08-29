"""
AmoCRM stats fetching and aggregation mixin.
"""
import asyncio
import logging
import requests
from datetime import date, datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.time_utils import get_local_now
from src.services.core.crm.daily_report.models import (
    CRMStats,
    CRMWeeklyStats,
    _ts_today,
    _ts_yesterday,
    previous_week_range,
)

logger = logging.getLogger(__name__)


class AmoFetcherMixin:
    """Handles AmoCRM leads, calls, notes, and metrics fetching."""

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
                logger.error("Exception handled in %s", __name__, exc_info=True)
                stats.top_manager = f"Manager #{top_uid}"

        # Bog'lanish tezligi — avg (first_contact_at - created_at) for leads with notes
        stats.avg_response_sec = await self._calc_avg_response(leads)

        # Calls — try /api/v4/calls if available
        stats.incoming_calls = await self._get_calls_count(t_from, t_to)

        # Cache to history DB (offload sync SQLite off the event loop)
        await asyncio.to_thread(self._save_stats, target, stats)
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
            logger.error("Exception handled in %s", __name__, exc_info=True)
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
            logger.debug(
                "Failed to fetch calls count from AmoCRM API",
                exc_info=True,
            )
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

