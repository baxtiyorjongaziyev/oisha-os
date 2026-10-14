"""CAPI orchestration; configuration never implies confirmed Meta delivery."""
from __future__ import annotations

import asyncio
import json
import os
import time

from src.services.core.marketing import capi_platform_store as store
from src.services.core.marketing import meta_capi, meta_capi_store
from src.services.core.marketing.capi_platform_schema import Conversion
from src.services.core.marketing.meta_capi_triggers import _qualified_status_ids


def configuration():
    cfg = meta_capi._config()
    return {"enabled": cfg["enabled"], "configured": bool(cfg["dataset_id"] and cfg["token"]),
            "dataset_id": cfg["dataset_id"] or None, "mode": "test" if cfg["test_code"] else "live",
            "ingest_configured": bool(os.getenv("OISHA_CAPI_INGEST_SECRET")),
            "qualified_status_ids": sorted(_qualified_status_ids()), "checked_at": store.now(),
            "delivery_verified": None}


async def accept(conversion: Conversion):
    cfg = meta_capi._config()
    if not (cfg["dataset_id"] and cfg["token"]):
        raise ValueError("not_configured")
    mode = "test" if cfg["test_code"] else "live"
    created = await store.enqueue(conversion.meta_event(), conversion.source, cfg["dataset_id"], mode)
    # Durable intake acknowledges queueing only; external delivery is explicitly separate.
    return {"event_id": conversion.event_id, "event_name": conversion.event_name,
            "status": "queued" if created else "duplicate", "mode": mode}


async def dispatch(event_id: str, event_name: str):
    cfg = meta_capi._config()
    if not meta_capi.is_enabled():
        return {"status": "disabled"}
    mode = "test" if cfg["test_code"] else "live"
    key = (event_id, event_name, cfg["dataset_id"], mode)
    claimed = await store.claim(*key)
    if not claimed:
        return {"status": "not_due"}
    lease, row = claimed
    event = json.loads(row["payload"])
    if event["event_time"] < int(time.time()) - 7 * 86400:
        result = {"ok": False, "error": "event_expired"}
    else:
        try:
            result = await asyncio.to_thread(meta_capi._post_events, cfg, event)
        except Exception:
            result = {"ok": False, "error": "transport_failure"}
    ok = bool(result.get("ok") and (result.get("response") or {}).get("events_received") == 1)
    error = "" if ok else (result.get("error") or "event_acceptance_unconfirmed")
    # Only our fixed errors or HTTP status survive; no response/customer/token text.
    safe_error = error if not error or error.startswith("HTTP ") or error in {
        "event_expired", "transport_failure", "event_acceptance_unconfirmed"
    } else "transport_failure"
    status = "sent" if ok else ("rejected" if safe_error.startswith("HTTP 4") else "failed")
    await store.finish(key, lease, ok, safe_error, row["attempts"])
    return {"status": status, "error": safe_error}


async def dispatch_due():
    cfg = meta_capi._config()
    mode = "test" if cfg["test_code"] else "live"
    rows = await store.due(cfg["dataset_id"], mode)
    return [await dispatch(row["event_id"], row["event_name"]) for row in rows]


async def snapshot():
    records = await store.events()
    await meta_capi_store.ensure_table()
    legacy = await meta_capi_store._pool().execute(
        "SELECT leadgen_id,event_name,amo_lead_id,status,updated_at,sent_at FROM capi_events "
        "ORDER BY updated_at DESC LIMIT 100"
    )
    return {"configuration": configuration(), "events": records,
            "crm_events": [dict(row) for row in legacy],
            "coverage": "latest 100 events per source; CRM history has no dataset/mode provenance",
            "observed_at": store.now()}
