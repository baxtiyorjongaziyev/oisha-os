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
    is_conf = bool(cfg["dataset_id"] and cfg["token"])
    return {
        "enabled": cfg["enabled"],
        "configured": is_conf,
        "dataset_configured": is_conf,
        "dataset_id": cfg["dataset_id"] or None,
        "mode": "test" if cfg["test_code"] else "live",
        "ingest_configured": bool(os.getenv("OISHA_CAPI_INGEST_SECRET")),
        "qualified_status_ids": sorted(_qualified_status_ids()),
        "checked_at": store.now(),
        "delivery_verified": None,
    }


async def accept(conversion: Conversion, project: dict | None = None):
    cfg = meta_capi._config()
    dataset_id = (project.get("dataset_id") if project else "") or cfg["dataset_id"]
    token = (project.get("access_token") if project else "") or cfg["token"]
    test_code = (project.get("test_code") if project else "") or cfg["test_code"]
    if not (dataset_id and token):
        raise ValueError("not_configured")
    mode = "test" if test_code else "live"
    created = await store.enqueue(conversion.meta_event(), conversion.source, dataset_id, mode)
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

    if is_admin:
        target_id = project_id if (project_id and project_id != "none") else "default"
        project = await get_project(target_id)
        if not project and target_id == "default":
            project = {
                "id": "default",
                "name": "Jon Branding (Asosiy)",
                "dataset_id": "1134785364752294",
                "ad_account_id": "act_370591433710957",
            }
    else:
        user_projects = await list_projects_for_user(str(user_id or ""), is_admin=False)
        project = None
        if project_id and project_id not in ("default", "none"):
            for up in user_projects:
                if up.get("id") == project_id:
                    project = await get_project(project_id)
                    break
        if project is None and user_projects:
            project = await get_project(user_projects[0]["id"])
        if project is None:
            project = {
                "id": "none",
                "name": "Yangi loyiha qo'shing",
                "dataset_id": "",
                "ad_account_id": "",
                "crm_pipeline_id": "none",
            }

    dataset_id = project.get("dataset_id") if project else None

    records = await store.events()
    if project and project.get("id") != "default":
        records = [r for r in records if dataset_id and r.get("dataset_id") == dataset_id]

    await meta_capi_store.ensure_table()
    crm_rows = []
    if is_admin and (not project or project.get("id") == "default"):
        legacy = await meta_capi_store._pool().execute(
            "SELECT leadgen_id,event_name,amo_lead_id,status,updated_at,sent_at FROM capi_events "
            "ORDER BY updated_at DESC LIMIT 100"
        )
        crm_rows = [dict(row) for row in legacy]

    analytics = build_dashboard_analytics(crm_rows, records, days=days, project=project)
    cfg = configuration()
    if project:
        cfg["project_id"] = project.get("id")
        cfg["project_name"] = project.get("name")
        if project.get("id") != "default":
            p_ds = str(project.get("dataset_id") or "").strip()
            p_tok = bool(project.get("has_token") or project.get("access_token"))
            cfg["dataset_id"] = p_ds or None
            cfg["dataset_configured"] = bool(p_ds)
            cfg["configured"] = bool(p_ds and p_tok)
            cfg["enabled"] = bool(p_ds and p_tok)
            cfg["ingest_secret"] = project.get("ingest_secret") or ""
            cfg["ad_account_id"] = project.get("ad_account_id") or None
            cfg["crm_pipeline_id"] = project.get("crm_pipeline_id") or None
        else:
            if project.get("dataset_id"):
                cfg["dataset_id"] = project.get("dataset_id")
                cfg["dataset_configured"] = True
                cfg["configured"] = True
            if project.get("ingest_secret"):
                cfg["ingest_secret"] = project.get("ingest_secret")
            if project.get("ad_account_id"):
                cfg["ad_account_id"] = project.get("ad_account_id")
            if project.get("crm_pipeline_id"):
                cfg["crm_pipeline_id"] = project.get("crm_pipeline_id")
    return {"configuration": cfg, "events": records,
            "crm_events": crm_rows,
            "analytics": analytics,
            "coverage": "latest 100 events per source; CRM history has no dataset/mode provenance",
            "observed_at": store.now()}
