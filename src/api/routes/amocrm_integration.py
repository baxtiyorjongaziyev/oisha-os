"""AmoCRM integration + webhook routes."""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from src.api.routes.state import api_state
from src.settings import settings
from src.time_utils import get_local_now

router = APIRouter(tags=["amocrm"])
logger = logging.getLogger(__name__)

_CALL_BACKFILL_LAST_STARTED_KEY = "amocrm_call_backfill:last_started_ts"
_CALL_BACKFILL_LAST_FINISHED_KEY = "amocrm_call_backfill:last_finished_ts"
_CALL_BACKFILL_LAST_RESULT_KEY = "amocrm_call_backfill:last_result"
_CALL_BACKFILL_LAST_ERROR_KEY = "amocrm_call_backfill:last_error"


def _get_cron_secret_value() -> str:
    from src.api_server import _secret_setting_text
    cron_secret = _secret_setting_text(getattr(settings, "AMOCRM_CRON_SECRET", None))
    if cron_secret:
        return cron_secret
    return (os.environ.get("OISHA_API_SECRET") or "").strip()


def _is_authorized_cron_request(request: Request) -> bool:
    secret = _get_cron_secret_value()
    if not secret:
        return False
    auth_header = request.headers.get("Authorization", "")
    return hmac.compare_digest(auth_header, f"Bearer {secret}")


def _get_amocrm_instance():
    from src.services.core.crm.amocrm_sync import AmoCRMSync
    from src.api_server import _setting_text, _secret_setting_text

    if api_state.amocrm_instance:
        return api_state.amocrm_instance

    api_state.amocrm_instance = AmoCRMSync(
        subdomain=_setting_text(settings.AMOCRM_SUBDOMAIN),
        client_id=_setting_text(settings.AMOCRM_CLIENT_ID),
        client_secret=_secret_setting_text(settings.AMOCRM_CLIENT_SECRET),
        redirect_url=_setting_text(settings.AMOCRM_REDIRECT_URL),
    )
    return api_state.amocrm_instance


async def _get_db_instance():
    if api_state.db_instance:
        return api_state.db_instance
    from src.database import Database
    api_state.db_instance = Database()
    await api_state.db_instance.init_instance()
    return api_state.db_instance


@router.post("/api/amocrm-refresh")
async def refresh_amocrm_token(request: Request):
    auth_header = request.headers.get("Authorization")
    cron_secret = (
        settings.AMOCRM_CRON_SECRET.get_secret_value()
        if settings.AMOCRM_CRON_SECRET
        else None
    )
    if not cron_secret:
        return {"ok": False, "error": "CRON_SECRET not configured"}
    if not auth_header or auth_header != f"Bearer {cron_secret}":
        return {"ok": False, "error": "Unauthorized"}

    amocrm = _get_amocrm_instance()
    success = amocrm.refresh_token()
    if success:
        return {"ok": True, "expires_at": amocrm.token_data.get("expires_at", "unknown")}
    return {"ok": False, "error": amocrm.last_error or "Refresh failed"}


@router.post("/api/amocrm-call-analysis/run")
async def run_amocrm_call_analysis_job(
    request: Request,
    limit: Optional[int] = Query(None, ge=1, le=250),
    wait: bool = Query(False),
    force: bool = Query(False),
):
    if not _is_authorized_cron_request(request):
        return JSONResponse(status_code=401, content={"ok": False, "error": "Unauthorized"})

    runtime_db = api_state.db_instance or await _get_db_instance()

    if wait:
        if api_state._call_backfill_task and not api_state._call_backfill_task.done():
            return JSONResponse(status_code=409, content={"ok": False, "error": "already_running"})
        stats = await _run_amocrm_call_backfill(runtime_db, reason="manual_api_wait", limit=limit)
        return {"ok": bool(stats.get("ok")), "mode": "wait", "stats": stats}

    queued = await _schedule_amocrm_call_backfill(runtime_db, reason="manual_api", limit=limit, force=force)
    return {"ok": bool(queued.get("queued")), **queued}


@router.get("/api/amocrm-call-analysis/status")
async def get_amocrm_call_analysis_status(request: Request):
    if not _is_authorized_cron_request(request):
        return JSONResponse(status_code=401, content={"ok": False, "error": "Unauthorized"})
    runtime_db = api_state.db_instance or await _get_db_instance()
    return await _build_amocrm_call_analysis_status(runtime_db)


@router.post("/webhook/amocrm")
async def amocrm_webhook(request: Request):
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
        else:
            form_data = await request.form()
            data = dict(form_data)

        logger.info("[Webhook] AmoCRM event received: %s", list(data.keys()))
        asyncio.create_task(_process_amocrm_event(data))
        return {"status": "ok", "message": "Event queued"}
    except Exception as e:
        logger.error("[Webhook] Error: %s", e)
        return {"status": "error", "message": str(e)}


async def _process_amocrm_event(data: Dict[str, Any]):
    try:
        lead_id = None
        for key in data.keys():
            if "leads[" in key and "][id]" in key:
                lead_id = data[key]
                break
        if not lead_id:
            return

        amocrm = _get_amocrm_instance()
        runtime_db = api_state.db_instance or await _get_db_instance()

        from src.agents.autonomous_sales_agent import AutonomousSalesAgent
        agent = AutonomousSalesAgent(db=runtime_db)

        lead_data = await amocrm.get_lead(int(lead_id))
        if not lead_data:
            return

        phone = amocrm.get_lead_phone(int(lead_id))

        if getattr(settings, "ENABLE_AMOCRM_LEAD_ENRICHMENT", True):
            try:
                from src.services.core.crm.amocrm_lead_enrichment import AmoCRMLeadEnricher
                enricher = AmoCRMLeadEnricher(amocrm=amocrm, db=runtime_db, user_client=api_state.user_client)
                enrichment_result = await enricher.enrich_lead(lead_id=int(lead_id), lead_data=lead_data, phone=phone)
                logger.info("[Webhook] AmoCRM enrichment result: %s", enrichment_result.to_dict())
            except Exception as enrich_exc:
                logger.error("[Webhook] AmoCRM enrichment failed for lead %s: %s", lead_id, enrich_exc, exc_info=True)

        if getattr(settings, "ENABLE_AMOCRM_CALL_ANALYSIS", True) and getattr(settings, "AMOCRM_CALL_ANALYSIS_ON_WEBHOOK", True):
            try:
                from src.services.core.call_analyzer import CallAnalyzer
                call_analyzer = CallAnalyzer(amocrm=amocrm, db=runtime_db)
                calls_processed = await call_analyzer.process_call_recordings_for_lead(
                    lead_id=int(lead_id), caller_phone=phone or "",
                    responsible_user_id=lead_data.get("responsible_user_id"),
                )
                logger.info("[Webhook] AmoCRM call analysis result: lead_id=%s processed=%s", lead_id, calls_processed)
            except Exception as call_exc:
                logger.error("[Webhook] AmoCRM call analysis failed for lead %s: %s", lead_id, call_exc, exc_info=True)

        await agent.process_new_lead(lead_id=int(lead_id), lead_data=lead_data)

    except Exception as exc:
        logger.error("[Webhook] process_amocrm_event failed: %s", exc, exc_info=True)


async def _run_amocrm_call_backfill(runtime_db, *, reason: str = "unknown", limit: int = None):
    from src.api_server import _get_call_backfill_limit, _timestamp_to_iso
    limit = _get_call_backfill_limit(limit)
    started_at = datetime.now(timezone.utc)
    api_state._call_backfill_last_status = {"started_at": started_at.isoformat(), "reason": reason, "limit": limit}

    try:
        amocrm = _get_amocrm_instance()
        from src.services.core.call_analyzer import CallAnalyzer
        analyzer = CallAnalyzer(amocrm=amocrm, db=runtime_db)
        result = await analyzer.backfill_call_recordings(limit=limit)

        finished_at = datetime.now(timezone.utc)
        api_state._call_backfill_last_status = {
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_sec": round((finished_at - started_at).total_seconds(), 1),
            "reason": reason,
            "limit": limit,
            **result,
        }
        return api_state._call_backfill_last_status
    except Exception as exc:
        finished_at = datetime.now(timezone.utc)
        api_state._call_backfill_last_status = {
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "error": str(exc),
            "reason": reason,
        }
        return api_state._call_backfill_last_status


async def _schedule_amocrm_call_backfill(runtime_db, *, reason: str = "unknown", limit: int = None, force: bool = False):
    if api_state._call_backfill_task and not api_state._call_backfill_task.done():
        if not force:
            return {"queued": False, "reason": "already_running"}

    api_state._call_backfill_task = asyncio.create_task(
        _run_amocrm_call_backfill(runtime_db, reason=reason, limit=limit)
    )
    return {"queued": True, "reason": reason}


async def _build_amocrm_call_analysis_status(runtime_db) -> dict:
    from src.api_server import _parse_state_json, _timestamp_to_iso

    last_started_raw = None
    last_finished_raw = None
    last_error = ""
    last_result_raw = ""

    if runtime_db:
        try:
            conn = await runtime_db.get_connection()
            r = conn.execute("SELECT value FROM kv_store WHERE key = ?", (_CALL_BACKFILL_LAST_STARTED_KEY,))
            if hasattr(r, "__await__"):
                r = await r
            row = r.fetchone() if hasattr(r, "fetchone") else None
            if row:
                last_started_raw = row[0] if isinstance(row, (tuple, list)) else row.get("value")
        except Exception as exc:
            logger.debug("[amocrm-backfill] get state failed: %s", exc)

    return {
        "last_started_at": _timestamp_to_iso(last_started_raw),
        "last_finished_at": _timestamp_to_iso(last_finished_raw),
        "last_error": last_error,
        "running": bool(api_state._call_backfill_task and not api_state._call_backfill_task.done()),
    }
