"""
Call and lead processing endpoints for AI Analytics.
"""
from __future__ import annotations
import os
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()

def _check_auth(request: Request) -> bool:
    auth = request.headers.get("Authorization", "")
    secret = os.getenv("OISHA_API_SECRET", "")
    if secret:
        return auth == f"Bearer {secret}"
    return bool(auth)

@router.post("/process-call")
async def process_call(request: Request):
    if not _check_auth(request):
        return JSONResponse(status_code=401, content={"error": "unauthorized"})
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not body or not body.get("call_id"):
        return JSONResponse(status_code=400, content={"error": "call_id_required"})
    return {"success": True, "call_id": body.get("call_id"), "status": "processed"}

@router.post("/lead-classifier/tag")
async def tag_lead(request: Request):
    if not _check_auth(request):
        return JSONResponse(status_code=401, content={"error": "unauthorized"})
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not body or not body.get("lead_id"):
        return JSONResponse(status_code=400, content={"error": "lead_id_required"})
    return {"success": True, "lead_id": body.get("lead_id"), "tags": body.get("tags", [])}
