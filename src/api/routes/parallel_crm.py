"""Authenticated Oisha CRM console, mirror reads and explicit operator edits."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from src.api.rbac import (
    Permission, Principal, has_permission, require_any_permission, require_permissions,
)
from src.services.core.crm.parallel import runtime
from src.services.core.crm.parallel.schema import EditRequest, baseline, revision

router = APIRouter(prefix="/api/crm/parallel", tags=["Parallel CRM"],
                   lifespan=runtime.lifespan)
read_access = require_any_permission(Permission.LEAD_READ_ALL, Permission.LEAD_READ_ASSIGNED)
write_access = require_permissions(Permission.LEAD_WRITE)
manage_access = require_permissions(Permission.USERS_MANAGE_LIMITED)
templates = Path(__file__).resolve().parent.parent / "templates"
HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


def same_origin(request: Request):
    origin = request.headers.get("origin")
    # Browser cookie and proxy identities both need CSRF protection.
    if request.headers.get("x-oisha-crm") != "1":
        raise HTTPException(403, "CRM request header required")
    if origin:
        parsed = urlsplit(origin)
        if parsed.scheme != request.url.scheme or parsed.netloc != request.url.netloc:
            raise HTTPException(403, "Cross-origin operation denied")
    elif not request.headers.get("authorization"):
        raise HTTPException(403, "Origin header required")


def public_operation(operation):
    return {key: operation.get(key) for key in (
        "id", "lead_id", "state", "reason", "created_at", "changed_at",
    )}


@router.get("/console", response_class=HTMLResponse, dependencies=[read_access])
async def console():
    return HTMLResponse((templates / "parallel_crm.html").read_text(encoding="utf-8"),
                        headers={**HEADERS, "Content-Security-Policy":
                                 "default-src 'self'; script-src 'self'; style-src 'self'; "
                                 "img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'"})


@router.get("/assets/{asset}", dependencies=[read_access])
async def asset(asset: str):
    if asset not in {"parallel_crm.css", "parallel_crm.js"}:
        raise HTTPException(404)
    return Response((templates / asset).read_text(encoding="utf-8"),
                    media_type="text/css" if asset.endswith(".css") else "text/javascript",
                    headers=HEADERS)


@router.get("/snapshot")
async def snapshot(principal: Principal = read_access, offset: int = Query(0, ge=0),
                   q: str = Query("", max_length=100)):
    store = await runtime.get_store()
    owner = runtime.seller_id(principal)
    leads, total = await store.entities("leads", owner=owner, limit=200, offset=offset, query=q)
    pipelines, _ = await store.entities("pipelines", limit=1000)
    users, _ = await store.entities("users", limit=1000)
    sync = await store.meta("sync", {"state": "never_synced"})
    account = await store.meta("account")
    return JSONResponse({
        "mode": "parallel", "enabled": runtime.enabled(), "writeback": runtime.writable(),
        "can_write": has_permission(principal, Permission.LEAD_WRITE),
        "can_manage": has_permission(principal, Permission.USERS_MANAGE_LIMITED),
        "sync": sync, "account": account,
        "source_url": (account or {}).get("source_url"),
        "leads_checked_at": await store.meta("checked_leads"),
        "leads": [{**lead, "revision": revision(lead)} for lead in leads],
        "loaded_total": total, "offset": offset, "limit": 200,
        "pipelines": pipelines, "users": [{"id": u["id"], "name": u.get("name")}
                                         for u in users],
        "operations": [public_operation(op) for op in await store.operations(owner=owner)],
    }, headers=HEADERS)


@router.get("/leads/{lead_id}")
async def detail(lead_id: int, principal: Principal = read_access):
    store = await runtime.get_store()
    lead = await runtime.owned_lead(store, lead_id, principal)
    contacts = []
    for ref in lead.get("_embedded", {}).get("contacts", []):
        contact = await store.get("contacts", ref["id"])
        if contact:
            contacts.append(contact)
    tasks = await store.tasks_for(lead_id)
    return JSONResponse({"lead": {**lead, "revision": revision(lead)},
                         "contacts": contacts, "tasks": tasks,
                         "tasks_total": await store.task_count(lead_id)}, headers=HEADERS)


@router.get("/leads/{lead_id}/notes")
async def notes(lead_id: int, principal: Principal = read_access):
    store = await runtime.get_store()
    await runtime.owned_lead(store, lead_id, principal)
    remote = runtime.get_remote()
    try:
        current = await remote.lead(lead_id)
        owner = runtime.seller_id(principal)
        if owner is not None and current["responsible_user_id"] != owner:
            raise HTTPException(404, "Bitim topilmadi")
        return JSONResponse({"notes": await remote.notes(lead_id),
                             "scope": "latest_50"}, headers=HEADERS)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, "Izohlarni amoCRM'dan olib bo'lmadi") from exc


@router.patch("/leads/{lead_id}", status_code=202)
async def edit(lead_id: int, body: EditRequest, request: Request,
               principal: Principal = write_access):
    same_origin(request)
    if not runtime.writable():
        raise HTTPException(409, "Tahrirlash hali yoqilmagan")
    store = await runtime.get_store()
    lead = await runtime.owned_lead(store, lead_id, principal)
    patch = body.patch.model_dump(exclude_unset=True)
    request_id = str(body.request_id)
    existing = await store.operation(request_id)
    if existing:
        if (existing["actor"] != principal.subject or existing["lead_id"] != lead_id
                or json.loads(existing["patch"]) != patch):
            raise HTTPException(409, "Request ID conflict")
        return public_operation(existing)
    if revision(lead) != body.revision:
        raise HTTPException(409, "Bitim yangilangan. Qayta oching.")
    if "status_id" in patch:
        pipeline = await store.get("pipelines", lead["pipeline_id"])
        stages = (pipeline or {}).get("_embedded", {}).get("statuses", [])
        if patch["status_id"] not in {stage["id"] for stage in stages}:
            raise HTTPException(422, "Bosqich bu voronkaga tegishli emas")
    try:
        operation = await store.enqueue(request_id, lead_id, principal.subject,
                                        baseline(lead), patch)
    except Exception as exc:
        raise HTTPException(409, "Bu bitimda kutilayotgan o'zgarish bor") from exc
    runtime.wake()
    return public_operation(operation)


@router.post("/operations/{operation_id}/discard")
async def discard(operation_id: str, request: Request,
                  principal: Principal = write_access):
    same_origin(request)
    store = await runtime.get_store()
    operation = await store.operation(operation_id)
    if operation is None:
        raise HTTPException(404)
    await runtime.owned_lead(store, operation["lead_id"], principal)
    if not await store.discard(operation_id):
        raise HTTPException(409, "Hozir bu o'zgarishni bekor qilib bo'lmaydi")
    return {"state": "discarded"}


@router.post("/sync", status_code=202)
async def sync(request: Request, principal: Principal = manage_access):
    same_origin(request)
    if not runtime.enabled():
        raise HTTPException(409, "Sinxronlash hali yoqilmagan")
    runtime.wake()
    return {"state": "requested"}
