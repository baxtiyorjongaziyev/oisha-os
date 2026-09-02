"""Web chat widget + lead creation routes."""
from __future__ import annotations

import hmac
import json
import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from src.api.rbac import Permission, require_permissions
from src.api.routes.state import api_state
from src.settings import settings

router = APIRouter(
    tags=["chat"],
    dependencies=[require_permissions(Permission.LEAD_READ_ALL)],
)
logger = logging.getLogger(__name__)


class CreateLeadRequest(BaseModel):
    name: str
    phone: str
    note: Optional[str] = None
    secret_key: Optional[str] = None


class SendMessageRequest(BaseModel):
    user_id: Any
    text: str
    secret_key: Optional[str] = None
    model: Optional[str] = getattr(settings, "GEMINI_CALL_MODEL", None)


def _check_secret(
    secret_key: Optional[str] = None,
    x_secret_key: Optional[str] = None,
    authorization: Optional[str] = None,
) -> bool:
    expected = os.environ.get("OISHA_API_SECRET")
    actual = None
    if isinstance(x_secret_key, str) and x_secret_key:
        actual = x_secret_key
    elif isinstance(authorization, str) and authorization.startswith("Bearer "):
        actual = authorization[7:].strip()
    elif isinstance(secret_key, str) and secret_key:
        actual = secret_key
    return bool(expected and actual and hmac.compare_digest(actual, expected))


def _require_secret(
    secret_key: Optional[str] = None,
    x_secret_key: Optional[str] = None,
    authorization: Optional[str] = None,
) -> None:
    if not _check_secret(secret_key=secret_key, x_secret_key=x_secret_key, authorization=authorization):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/api/chat/lookup/{phone}")
async def lookup_user_by_phone(
    phone: str,
    secret_key: Optional[str] = None,
    x_secret_key: Optional[str] = Header(None, alias="X-Secret-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    _require_secret(secret_key=secret_key, x_secret_key=x_secret_key, authorization=authorization)
    if not api_state.db_instance:
        return {"error": "Database not connected"}

    user_id = await api_state.db_instance.get_user_id_by_phone(phone)
    if user_id:
        return {"user_id": user_id, "status": "found"}
    return {"status": "not_found"}


@router.get("/api/chat/history/{user_id}")
async def get_chat_history(
    user_id: str,
    secret_key: Optional[str] = None,
    x_secret_key: Optional[str] = Header(None, alias="X-Secret-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    _require_secret(secret_key=secret_key, x_secret_key=x_secret_key, authorization=authorization)
    if not api_state.db_instance:
        return {"error": "Database not connected"}

    try:
        parsed_id = int(user_id)
    except (ValueError, TypeError):
        parsed_id = user_id

    history = await api_state.db_instance.get_recent_messages(parsed_id, limit=30)
    return {"history": history}


@router.post("/api/chat/send")
async def send_chat_message(
    request: SendMessageRequest,
    x_secret_key: Optional[str] = Header(None, alias="X-Secret-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    _require_secret(
        secret_key=request.secret_key,
        x_secret_key=x_secret_key,
        authorization=authorization,
    )

    user_id_str = str(request.user_id)

    if user_id_str.startswith("web_"):
        from src.agents.autonomous_sales_agent import AutonomousSalesAgent as _Agent
        _db = api_state.db_instance
        if _db:
            await _db.log_message(user_id_str, request.text, is_ai=False)
        agent = _Agent(db=_db)
        try:
            result = await agent.handle_incoming(user_id_str, request.text)
            response_text = result.get("response", "") if isinstance(result, dict) else str(result)
        except Exception as exc:
            logger.error("[CHAT] Web AI error: %s", exc)
            response_text = "Xatolik yuz berdi."
        if _db:
            await _db.log_message(user_id_str, response_text, is_ai=True)
        return {"status": "success", "response": response_text}

    try:
        user_id = int(request.user_id)
    except (ValueError, TypeError):
        return {"error": "Invalid user_id"}

    await api_state.command_queue.put({
        "action": "send_message",
        "user_id": user_id,
        "text": request.text,
    })

    from src.api.routes.state import api_state as _s
    from src.time_utils import get_local_now
    activity = {
        "timestamp": get_local_now().strftime("%H:%M:%S"),
        "action": "💬 Widget Message",
        "details": f"To user {user_id}: {request.text[:50]}...",
        "type": "info",
    }
    _s.system_activities.insert(0, activity)
    if len(_s.system_activities) > 100:
        _s.system_activities.pop()

    return {"status": "queued", "user_id": user_id}


@router.post("/api/leads")
async def create_amo_lead(
    request: CreateLeadRequest,
    x_secret_key: Optional[str] = Header(None, alias="X-Secret-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    _require_secret(
        secret_key=request.secret_key,
        x_secret_key=x_secret_key,
        authorization=authorization,
    )

    from src.services.core.crm.amocrm_sync import AmoCRMSync
    from src.time_utils import get_local_now

    amocrm = AmoCRMSync(
        subdomain=getattr(settings, "AMOCRM_SUBDOMAIN", ""),
        client_id=getattr(settings, "AMOCRM_CLIENT_ID", ""),
        # AmoCRMSync SecretStr'ni o'zi ochadi (_plain_secret), shu sababli
        # bu yerda xom qiymat uzatish xavfsiz.
        client_secret=getattr(settings, "AMOCRM_CLIENT_SECRET", "") or "",
        redirect_url=getattr(settings, "AMOCRM_REDIRECT_URL", ""),
    )

    logger.info("[API] Website Lead qabul qilindi: %s", request.name)
    lead_id = await amocrm.ensure_lead(name=request.name, phone=request.phone, note=request.note)

    if lead_id:
        activity = {
            "timestamp": get_local_now().strftime("%H:%M:%S"),
            "action": "🚀 Lead Created",
            "details": f"Website lead: {request.name}",
            "type": "success",
        }
        api_state.system_activities.insert(0, activity)
        if len(api_state.system_activities) > 100:
            api_state.system_activities.pop()
        return {"status": "success", "lead_id": lead_id}
    return {"error": "Lead creation failed"}
