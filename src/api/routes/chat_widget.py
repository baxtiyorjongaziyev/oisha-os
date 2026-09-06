"""Web chat widget + lead creation routes."""
from __future__ import annotations

import hmac
import logging
import os
import secrets
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from src.api.auth_service import decode_widget_jwt, issue_widget_jwt
from src.api.rbac import Permission, require_permissions
from src.api.routes.state import api_state
from src.settings import settings

router = APIRouter(
    tags=["chat"],
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


class WidgetAuthContext:
    def __init__(
        self,
        is_master: bool = False,
        bound_session_id: Optional[str] = None,
        role: Optional[str] = None,
    ):
        self.is_master = is_master
        self.bound_session_id = bound_session_id
        self.role = role


def _get_widget_jwt_secret() -> str:
    raw = os.environ.get("JWT_SECRET") or os.environ.get("OISHA_API_SECRET")
    secret = str(
        getattr(raw, "get_secret_value", lambda: raw)()
        if hasattr(raw, "get_secret_value")
        else raw or ""
    ).strip()
    if len(secret.encode("utf-8")) < 32:
        raise HTTPException(
            status_code=503,
            detail="JWT secret is not configured or shorter than 32 bytes",
        )
    return secret


def _authenticate_request(
    secret_key: Optional[str] = None,
    x_secret_key: Optional[str] = None,
    authorization: Optional[str] = None,
) -> WidgetAuthContext:
    master_secret = os.environ.get("OISHA_API_SECRET")
    widget_secret = os.environ.get("OISHA_WIDGET_SECRET")

    token = None
    if isinstance(x_secret_key, str) and x_secret_key:
        token = x_secret_key.strip()
    elif isinstance(authorization, str) and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    elif isinstance(secret_key, str) and secret_key:
        token = secret_key.strip()

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if master_secret and hmac.compare_digest(token, master_secret):
        return WidgetAuthContext(is_master=True, role="master")

    if widget_secret and hmac.compare_digest(token, widget_secret):
        return WidgetAuthContext(is_master=True, role="master")

    try:
        jwt_secret = _get_widget_jwt_secret()
        payload = decode_widget_jwt(token, jwt_secret)
    except Exception:
        payload = None

    if payload and (
        "chat:write" in payload.get("scopes", [])
        or payload.get("role") == "widget_guest"
    ):
        sess = payload.get("session_id") or ""
        return WidgetAuthContext(
            is_master=False,
            bound_session_id=str(sess),
            role="widget_guest",
        )

    raise HTTPException(
        status_code=401,
        detail="Unauthorized: invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _check_secret(
    secret_key: Optional[str] = None,
    x_secret_key: Optional[str] = None,
    authorization: Optional[str] = None,
) -> bool:
    try:
        _authenticate_request(secret_key=secret_key, x_secret_key=x_secret_key, authorization=authorization)
        return True
    except HTTPException:
        return False


def _require_secret(
    secret_key: Optional[str] = None,
    x_secret_key: Optional[str] = None,
    authorization: Optional[str] = None,
) -> WidgetAuthContext:
    return _authenticate_request(secret_key=secret_key, x_secret_key=x_secret_key, authorization=authorization)


@router.post("/api/chat/token")
async def get_widget_token():
    """Issue a scoped, short-lived JWT for web chat widget visitors (zero master secret exposure)."""
    raw_hex = secrets.token_hex(16)
    session_id = f"web_{raw_hex}"
    jwt_secret = _get_widget_jwt_secret()
    token = issue_widget_jwt(session_id=session_id, secret=jwt_secret, ttl_seconds=86400)
    return {
        "token": token,
        "session_id": session_id,
        "token_type": "Bearer",
        "role": "widget_guest",
    }


@router.get("/api/chat/lookup/{phone}")
async def lookup_user_by_phone(
    phone: str,
    secret_key: Optional[str] = None,
    x_secret_key: Optional[str] = Header(None, alias="X-Secret-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    auth = _require_secret(secret_key=secret_key, x_secret_key=x_secret_key, authorization=authorization)
    if not auth.is_master:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: master access required for user lookup",
        )
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
    auth = _require_secret(secret_key=secret_key, x_secret_key=x_secret_key, authorization=authorization)
    if not auth.is_master:
        req_id = str(user_id)
        bound = auth.bound_session_id or ""
        is_same = (
            req_id == bound
            or req_id == f"web_{bound}"
            or bound == f"web_{req_id}"
        )
        if not is_same:
            raise HTTPException(
                status_code=403,
                detail="Forbidden: cannot access history of another session",
            )

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
    auth = _require_secret(
        secret_key=request.secret_key,
        x_secret_key=x_secret_key,
        authorization=authorization,
    )

    user_id_str = str(request.user_id)

    if not auth.is_master:
        bound = auth.bound_session_id or ""
        is_same = (
            user_id_str == bound
            or user_id_str == f"web_{bound}"
            or bound == f"web_{user_id_str}"
        )
        if not is_same or not user_id_str.startswith("web_"):
            raise HTTPException(
                status_code=403,
                detail="Forbidden: widget token can only send messages within its own web session",
            )

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
    auth = _require_secret(
        secret_key=request.secret_key,
        x_secret_key=x_secret_key,
        authorization=authorization,
    )
    if not auth.is_master:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: master access required for direct lead creation",
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
