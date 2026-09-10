"""AI ROP AmoCRM reads — the ONLY I/O module. Bounded, non-raising (except the
first active-leads page). Worst-case ~25 sequential GETs on the evening slot."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from src.services.core.crm.amocrm_pipeline_config import (
    SALES_PIPELINE_ID,
    STATUS_LOST,
    STATUS_WON,
)

logger = logging.getLogger("RopFetcher")
_TZ = ZoneInfo("Asia/Tashkent")
_TIMEOUT = 30


class RopFetchError(RuntimeError):
    """Raised only when the first active-leads page cannot be read."""


def _tashkent_day_start_epoch(now: datetime) -> int:
    local = now.astimezone(_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(local.timestamp())


class RopFetcher:
    def __init__(self, amocrm, *, session=None):
        self._amo = amocrm
        self._session = session or requests

    async def _get(self, url, params=None):
        return await asyncio.to_thread(
            self._session.get,
            url,
            headers=self._amo._get_headers(),
            params=params,
            timeout=_TIMEOUT,
        )

    async def _paged(self, url, params, key, *, max_pages, embed, raise_on_first=False):
        out: list[dict] = []
        page_url, page_params = url, dict(params)
        for i in range(max_pages):
            try:
                resp = await self._get(page_url, page_params)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[ROP] %s page %s failed: %s", url, i, exc)
                break
            if resp.status_code != 200:
                logger.warning("[ROP] %s page %s -> HTTP %s", url, i, resp.status_code)
                if i == 0 and raise_on_first:
                    raise RopFetchError(f"{url} -> {resp.status_code}")
                break
            body = resp.json()
            out.extend(body.get("_embedded", {}).get(embed, []))
            nxt = body.get("_links", {}).get("next", {}).get("href")
            if not nxt:
                break
            page_url, page_params = nxt, None
        return out

    async def fetch_active_sales_leads(self) -> list[dict]:
        try:
            leads = await self._paged(
                f"{self._amo.base_url}/api/v4/leads",
                {"filter[pipeline_id]": SALES_PIPELINE_ID, "with": "contacts", "limit": 250},
                key="leads", max_pages=4, embed="leads", raise_on_first=True,
            )
        except RopFetchError:
            raise
        return [l for l in leads if l.get("status_id") not in (STATUS_WON, STATUS_LOST)]

    async def fetch_open_tasks_for_leads(self, lead_ids):
        rows = await self._paged(
            f"{self._amo.base_url}/api/v4/tasks",
            {"filter[entity_type]": "leads", "filter[is_completed]": 0, "limit": 250},
            key="tasks", max_pages=4, embed="tasks",
        )
        want = set(lead_ids)
        grouped: dict[int, list[dict]] = {}
        for t in rows:
            eid = t.get("entity_id")
            if eid in want:
                grouped.setdefault(eid, []).append(t)
        return grouped

    async def fetch_today_completed_tasks(self, user_ids, *, now=None):
        now = now or datetime.now(_TZ)
        since = _tashkent_day_start_epoch(now)
        rows = await self._paged(
            f"{self._amo.base_url}/api/v4/tasks",
            {"filter[entity_type]": "leads", "filter[is_completed]": 1,
             "filter[updated_at][from]": since, "limit": 250},
            key="tasks", max_pages=4, embed="tasks",
        )
        want = set(user_ids)
        by_entity: dict[int, list[dict]] = {}
        by_user: dict[int, list[dict]] = {}
        for t in rows:
            if t.get("responsible_user_id") not in want:
                continue
            by_entity.setdefault(t.get("entity_id"), []).append(t)
            by_user.setdefault(t.get("responsible_user_id"), []).append(t)
        return by_entity, by_user

    async def fetch_today_events(self, lead_ids, *, now=None):
        now = now or datetime.now(_TZ)
        since = _tashkent_day_start_epoch(now)
        rows = await self._paged(
            f"{self._amo.base_url}/api/v4/events",
            {"filter[entity]": "lead", "filter[created_at][from]": since, "limit": 100},
            key="events", max_pages=3, embed="events",
        )
        want = set(lead_ids)
        grouped: dict[int, list[dict]] = {}
        for e in rows:
            eid = e.get("entity_id")
            if eid in want:
                grouped.setdefault(eid, []).append(e)
        return grouped

    async def fetch_recent_events(self, lead_ids, since_epoch):
        rows = await self._paged(
            f"{self._amo.base_url}/api/v4/events",
            {"filter[entity]": "lead", "filter[created_at][from]": since_epoch,
             "filter[type]": "lead_status_changed", "limit": 250},
            key="events", max_pages=4, embed="events",
        )
        want = set(lead_ids)
        grouped: dict[int, list[dict]] = {}
        for e in rows:
            eid = e.get("entity_id")
            if eid in want:
                grouped.setdefault(eid, []).append(e)
        return grouped

    async def fetch_won_leads_since(self, since_epoch):
        return await self._paged(
            f"{self._amo.base_url}/api/v4/leads",
            {"filter[pipeline_id]": SALES_PIPELINE_ID,
             "filter[statuses][0][status_id]": STATUS_WON,
             "filter[closed_at][from]": since_epoch, "limit": 250},
            key="leads", max_pages=4, embed="leads",
        )

    async def fetch_notes_for_leads(self, lead_ids):
        grouped: dict[int, list[dict]] = {}
        ids = list(lead_ids)[:300]
        requests_made = 0
        for start in range(0, len(ids), 50):
            if requests_made >= 6:
                break
            batch = ids[start:start + 50]
            params = {"limit": 250}
            for i, lid in enumerate(batch):
                params[f"filter[entity_id][{i}]"] = lid
            rows = await self._paged(
                f"{self._amo.base_url}/api/v4/leads/notes",
                params, key="notes", max_pages=1, embed="notes",
            )
            requests_made += 1
            for n in rows:
                eid = n.get("entity_id")
                grouped.setdefault(eid, []).append(n)
        return grouped

    async def fetch_user_names(self, user_ids):
        out: dict[int, str] = {}
        for uid in list(user_ids)[:30]:
            try:
                resp = await self._get(f"{self._amo.base_url}/api/v4/users/{uid}")
                if resp.status_code == 200:
                    out[uid] = resp.json().get("name") or f"Menejer_{uid}"
                    continue
            except Exception:  # noqa: BLE001
                pass
            out[uid] = f"Menejer_{uid}"
        return out
