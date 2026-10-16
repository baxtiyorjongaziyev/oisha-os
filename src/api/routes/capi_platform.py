"""Private CAPI console and authenticated server intake (no browser secrets)."""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import ValidationError

from src.api.capi_console_view import render_console
from src.api.rbac import Permission, has_permission, require_any_permission
from src.services.core.marketing import capi_platform as platform
from src.services.core.marketing.capi_platform_schema import Conversion

logger = logging.getLogger(__name__)


async def worker():
    """Background worker draining due CAPI conversions every 30 seconds."""
    while True:
        try:
            if platform.meta_capi.is_enabled():
                await platform.dispatch_due()
        except Exception as exc:
            logger.warning("CAPI worker unavailable: %s", type(exc).__name__)
        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app):
    """Lifecycle manager running the CAPI dispatch worker in background."""
    task = asyncio.create_task(worker(), name="capi-platform")
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


router = APIRouter(prefix="/api/marketing/capi", tags=["CAPI Platform"], lifespan=lifespan)
# Targetolog and Marketing role can view console, check status, and dispatch/retry queue
read_access = require_any_permission(Permission.SYSTEM_READ, Permission.MARKETING_READ)
write_access = require_any_permission(Permission.SYSTEM_DEPLOY, Permission.MARKETING_MANAGE)


def same_origin(request: Request):
    """CSRF and origin validation for authenticated mutations."""
    origin = request.headers.get("origin")
    if request.cookies.get("oisha_token") and not origin:
        raise HTTPException(403, "Origin header required for cookie authentication")
    if origin and (urlsplit(origin).netloc != request.url.netloc
                   or urlsplit(origin).scheme != request.url.scheme):
        raise HTTPException(403, "Cross-origin operation denied")


@router.get("/console", response_class=HTMLResponse)
async def console(request: Request):
    """Interactive Oisha CAPI web console for targetologists and administrators."""
    from src.api.security import authorize_connection

    principal = authorize_connection(request)
    if principal is None:
        accept = request.headers.get("accept", "")
        if "text/html" in accept and not request.headers.get("authorization"):
            return RedirectResponse(
                url="/api/auth/telegram/login?next=/api/marketing/capi/console",
                status_code=303,
            )
        raise HTTPException(401, "Unauthorized")
    if not (
        has_permission(principal, Permission.SYSTEM_READ)
        or has_permission(principal, Permission.MARKETING_READ)
    ):
        raise HTTPException(403, "Targetolog yoki Admin ruxsati talab qilinadi")
    can_manage = (
        has_permission(principal, Permission.SYSTEM_DEPLOY)
        or has_permission(principal, Permission.MARKETING_MANAGE)
    )
    return HTMLResponse(render_console(can_manage=can_manage), headers={"Cache-Control": "no-store"})


@router.get("/jon-capi.js")
async def get_jon_capi_script():
    """Serve standalone client-side tracking snippet for external websites."""
    from fastapi.responses import Response
    from pathlib import Path
    path = Path(__file__).resolve().parent.parent / "templates" / "jon_capi.js"
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    return Response(
        content=content,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=3600", "Access-Control-Allow-Origin": "*"},
    )


@router.get("/status", dependencies=[read_access])
async def status(request: Request, days: int | None = None, project_id: str | None = None):
    """Current configuration, website conversions queue, CRM conversions log, and full-funnel analytics."""
    try:
        from src.api.security import authorize_connection
        principal = authorize_connection(request)
        user_id = principal.subject if principal else "anonymous"
        is_admin = principal.role.value in ("owner", "admin") if principal else False
        safe_days = days if (days is not None and 1 <= int(days) <= 3650) else None
        return JSONResponse(
            await platform.snapshot(days=safe_days, project_id=project_id, user_id=user_id, is_admin=is_admin),
            headers={"Cache-Control": "no-store"},
        )
    except Exception as exc:
        raise HTTPException(503, "CAPI history unavailable") from exc


@router.get("/summary", dependencies=[read_access])
async def summary():
    """Aggregated telemetry and health summary for Targetologs and automated reports."""
    try:
        data = await platform.snapshot()
        events = data.get("events", [])
        crm_events = data.get("crm_events", [])

        status_counts: dict[str, int] = {}
        type_counts: dict[str, int] = {}
        for ev in events:
            st = str(ev.get("status") or "unknown")
            nm = str(ev.get("event_name") or "unknown")
            status_counts[st] = status_counts.get(st, 0) + 1
            type_counts[nm] = type_counts.get(nm, 0) + 1

        crm_counts: dict[str, int] = {}
        for ev in crm_events:
            st = str(ev.get("status") or "unknown")
            crm_counts[st] = crm_counts.get(st, 0) + 1

        return JSONResponse(
            {
                "configuration": data.get("configuration", {}),
                "total_website_events": len(events),
                "total_crm_events": len(crm_events),
                "website_status_counts": status_counts,
                "crm_status_counts": crm_counts,
                "event_type_counts": type_counts,
                "observed_at": data.get("observed_at"),
            },
            headers={"Cache-Control": "no-store"},
        )
    except Exception as exc:
        raise HTTPException(503, "CAPI summary unavailable") from exc


@router.get("/projects", dependencies=[read_access])
async def list_projects(request: Request):
    """List projects accessible to the current operator."""
    from src.api.security import authorize_connection
    from src.services.core.marketing.capi_project_store import list_projects_for_user
    principal = authorize_connection(request)
    user_id = principal.subject if principal else "anonymous"
    is_admin = principal.role.value in ("owner", "admin") if principal else False
    return JSONResponse(await list_projects_for_user(user_id, is_admin=is_admin))


@router.post("/projects", dependencies=[read_access])
async def create_new_project(request: Request):
    """Register a new project for multi-tenant CAPI and attribution tracking."""
    same_origin(request)
    from src.api.security import authorize_connection
    from src.services.core.marketing.capi_project_store import create_project
    principal = authorize_connection(request)
    user_id = principal.subject if principal else "anonymous"
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")
    name = str(body.get("name") or "").strip()
    if not name:
        raise HTTPException(422, "Project name is required")
    created = await create_project(
        name=name,
        owner_id=user_id,
        dataset_id=str(body.get("dataset_id") or "").strip(),
        access_token=str(body.get("access_token") or "").strip(),
        ad_account_id=str(body.get("ad_account_id") or "").strip(),
        crm_pipeline_id=str(body.get("crm_pipeline_id") or "").strip(),
    )
    return JSONResponse(created, status_code=201)


@router.post("/events", status_code=202)
async def intake(request: Request):
    global_sec = os.getenv("OISHA_CAPI_INGEST_SECRET", "")
    bearer = request.headers.get("authorization", "")
    token = bearer[7:].strip() if bearer.startswith("Bearer ") else ""
    if not token and not global_sec:
        raise HTTPException(503, "CAPI intake not configured")

    from src.services.core.marketing.capi_project_store import get_project_by_secret, increment_project_usage
    project = await get_project_by_secret(token) if token else None
    if not project:
        if not global_sec or not hmac.compare_digest(token.encode(), global_sec.encode()):
            raise HTTPException(401, "Unauthorized")

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 16384:
            raise HTTPException(413, "Event too large")
    try:
        conversion = Conversion.model_validate(json.loads(body))
    except (ValidationError, ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(422, "Invalid CAPI event; see integration contract") from exc
    if conversion.source != "website":
        raise HTTPException(403, "Website credential not authorized for non-website source")
    try:
        res = await platform.accept(conversion)
        if project:
            await increment_project_usage(project["id"])
        return res
    except ValueError as exc:
        if str(exc) == "event_id_conflict":
            raise HTTPException(409, "Event ID conflict") from exc
        raise HTTPException(503, "Meta dataset and credential required") from exc
    except Exception as exc:
        raise HTTPException(503, "CAPI queue unavailable") from exc


@router.post("/dispatch", dependencies=[write_access])
async def dispatch(request: Request):
    same_origin(request)
    try:
        return {"results": await platform.dispatch_due()}
    except Exception as exc:
        raise HTTPException(503, "CAPI queue unavailable") from exc


@router.post("/crm/{leadgen_id}/{event_name}/retry", dependencies=[write_access])
async def retry_crm(leadgen_id: str, event_name: str, request: Request):
    same_origin(request)
    from src.services.core.marketing import meta_capi_store, meta_capi_triggers
    if not leadgen_id.isdigit() or event_name not in {"Lead", "QualifiedLead", "Purchase"}:
        raise HTTPException(422, "Invalid CRM event")
    if await meta_capi_store.get_event_status(leadgen_id, event_name) != "failed":
        raise HTTPException(409, "Only failed CRM events can be retried")
    rows = await meta_capi_store._pool().execute(
        "SELECT amo_lead_id FROM capi_events WHERE leadgen_id=? AND event_name=?",
        [leadgen_id, event_name],
    )
    amo_id = rows[0]["amo_lead_id"]
    value = await meta_capi_triggers._amo_lead_price(amo_id) if event_name == "Purchase" else None
    result = await platform.meta_capi.send_crm_event(
        leadgen_id, event_name, amo_lead_id=amo_id, value=value, source="capi_console_retry",
    )
    return {"status": result.status, "reason": result.reason}
