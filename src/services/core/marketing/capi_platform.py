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


async def snapshot(days: int | None = None, project_id: str | None = None, user_id: str | None = None, is_admin: bool = False):
    from src.services.core.marketing.capi_dashboard_data import build_dashboard_analytics
    from src.services.core.marketing.capi_project_store import get_project, list_projects_for_user

    target_id = project_id
    if not is_admin and (not target_id or target_id == "default"):
        user_projects = await list_projects_for_user(user_id or "anonymous", is_admin=False)
        target_id = user_projects[0]["id"] if user_projects else "none"

    project = await get_project(target_id) if target_id and target_id != "none" else None
    dataset_id = project.get("dataset_id") if project else None

    records = await store.events()
    if not is_admin or (project and project.get("id") != "default"):
        records = [r for r in records if r.get("dataset_id") == dataset_id] if dataset_id else []

    await meta_capi_store.ensure_table()
    crm_rows = []
    if is_admin and (not project or project.get("id") == "default"):
        legacy = await meta_capi_store._pool().execute(
            "SELECT leadgen_id,event_name,amo_lead_id,status,updated_at,sent_at FROM capi_events "
            "ORDER BY updated_at DESC LIMIT 100"
        )
        crm_rows = [dict(row) for row in legacy]

    analytics = build_dashboard_analytics(crm_rows, records, days=days, project=project if (is_admin or (project and project.get("id") != "default")) else {"id": "sandbox_empty"})
    cfg = configuration()
    if project:
        cfg["project_id"] = project.get("id")
        cfg["project_name"] = project.get("name")
        if project.get("dataset_id"):
            cfg["dataset_id"] = project.get("dataset_id")
        cfg["ingest_secret"] = project.get("ingest_secret")
        cfg["crm_pipeline_id"] = project.get("crm_pipeline_id")
    return {"configuration": cfg, "events": records,
            "crm_events": crm_rows,
            "analytics": analytics,
            "coverage": "latest 100 events per source; CRM history has no dataset/mode provenance",
            "observed_at": store.now()}
