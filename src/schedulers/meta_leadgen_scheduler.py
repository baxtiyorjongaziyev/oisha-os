"""Autonomous 24/7 background scheduler for Meta Lead Ads.

This scheduler polls active leadgen forms on Meta every 60 seconds to ensure
zero lost leads, even if webhooks are delayed, offline, or dropped.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Set

import requests

from src.services.core.instagram.leadgen_dedup import (
    get_all_processed_ids,
    is_leadgen_processed,
)

logger = logging.getLogger("MetaLeadgenScheduler")

_INTERVAL_SEC = int(os.getenv("META_LEADGEN_POLL_INTERVAL_SEC", "60"))
_PROCESSED_LEADGEN_IDS: Set[str] = get_all_processed_ids()


def _get_page_token() -> str:
    from src.services.core.instagram.graph_client import InstagramGraphClient
    return os.getenv("META_PAGE_ACCESS_TOKEN", "").strip() or InstagramGraphClient().access_token


def _get_pages(url: str, token: str, fields: str) -> list[dict]:
    rows = []
    params = {"access_token": token, "fields": fields, "limit": 100}
    seen = set()
    while True:
        response = requests.get(url, params=params, timeout=20)
        if response.status_code != 200:
            raise RuntimeError(f"Meta HTTP {response.status_code}")
        payload = response.json()
        rows.extend(payload.get("data", []))
        paging = payload.get("paging", {})
        after = paging.get("cursors", {}).get("after")
        if not paging.get("next") or not after or after in seen:
            return rows
        seen.add(after)
        params["after"] = after


def _get_active_form_ids(token: str, version: str) -> list[str]:
    page_id = os.getenv("META_PAGE_ID", "103894334533931").strip()
    url = f"https://graph.facebook.com/{version}/{page_id}/leadgen_forms"
    try:
        forms = _get_pages(url, token, "id,status")
        return [str(f["id"]) for f in forms if f.get("status") == "ACTIVE" and f.get("id")]
    except Exception as exc:
        logger.warning("[META LEADGEN POLL] Form listing failed: %s", type(exc).__name__)

    return [
        "1973180183373812",
        "24790817803944095",
        "1165829001516157",
        "1335807947087538",
        "878493490402510",
        "322093186721815",
    ]


async def poll_leadgen_forms_once() -> int:
    """Poll active leadgen forms and route any new leads."""
    token = _get_page_token()
    if not token:
        return 0

    version = os.getenv("META_GRAPH_API_VERSION", "v19.0").strip() or "v19.0"
    form_ids = await asyncio.to_thread(_get_active_form_ids, token, version)

    from src.services.core.instagram.leadgen_router import route_leadgen_event

    routed_count = 0
    for form_id in form_ids:
        url = f"https://graph.facebook.com/{version}/{form_id}/leads"
        try:
            leads = await asyncio.to_thread(
                _get_pages, url, token, "id,created_time,field_data,ad_id,form_id",
            )
            for lead in leads:
                leadgen_id = str(lead.get("id") or "").strip()
                if not leadgen_id or is_leadgen_processed(leadgen_id):
                    continue

                event = {**lead, "leadgen_id": leadgen_id}
                res = await route_leadgen_event(event, token)
                if res.get("ok"):
                    routed_count += 1
                    logger.info(
                        "[META LEADGEN POLL] Routed lead: leadgen_id=%s amo_id=%s",
                        leadgen_id,
                        res.get("lead_id"),
                    )
        except Exception as err:
            logger.warning("[META LEADGEN POLL] Error polling form %s: %s", form_id, type(err).__name__)

    return routed_count


async def meta_leadgen_loop() -> None:
    """24/7 background worker polling Meta Lead Ads."""
    logger.info("[META LEADGEN POLL] Loop started (interval=%ds)", _INTERVAL_SEC)
    await asyncio.sleep(5)

    while True:
        try:
            await poll_leadgen_forms_once()
        except asyncio.CancelledError:
            logger.info("[META LEADGEN POLL] Cancelled")
            break
        except Exception as exc:
            logger.error("[META LEADGEN POLL] Unexpected error: %s", exc, exc_info=True)
        await asyncio.sleep(_INTERVAL_SEC)
