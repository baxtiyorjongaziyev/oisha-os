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
from src.api.routes.state import api_state
from src.settings import settings

router = APIRouter(tags=["chat"])
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


def _secret_text(value: Any) -> str:
    getter = getattr(value, "get_secret_value", None)
    return str(getter() if callable(getter) else value or "").strip()


def _get_widget_jwt_secret() -> str:
    """Return a server-only signing key; never fall back to a public constant.

    JWT_SECRET is preferred. OISHA_API_SECRET is retained as a server-side
    compatibility fallback until production has a dedicated JWT secret.
    """
    raw = os.environ.get("JWT_SECRET") or os.environ.get("OISHA_API_SECRET")
    secret = _secret_text(raw)
    if len(secret.encode("utf-8")) < 32:
        raise RuntimeError("JWT_SECRET or OISHA_API_SECRET must be at least 32 bytes")
    return secret


def _extract_token(
    secret_key: Optional[str] = None,
    x_secret_key: Optional[str] = None,
    authorization: Optional[str] = None,
) -> str:
    if isinstance(x_secret_key, str) and x_secret_key:
        return x_secret_key.strip()
    if isinstance(authorization, str) and authorization.startswith("Bearer "):
        return authorization[7:].strip()
    if isinstance(secret_key, str) and secret_key:
        return secret_key.strip()
    return ""


def _is_privileged_token(token: str) -> bool:
    """Accept only server/operator secrets for privileged chat operations."""
    if not token:
        return False
    for candidate in (
        os.environ.get("OISHA_API_SECRET"),
        os.environ.get("OISHA_WIDGET_SECRET"),
    ):
        if candidate and hmac.compare_digest(token, candidate):
            return True
    return False


def _widget_payload(token: str) -> Optional[dict[str, Any]]:
    if not token:
        return None
    try:
        return decode_widget_jwt(token, _get_widget_jwt_secret())
    except RuntimeError:
        logger.error("[CHAT] Widget JWT signing secret is not configured securely")
        return None


def _require_privileged(
    secret_key: Optional[str] = None,
    x_secret_key: Optional[str] = None,
    authorization: Optional[str] = None,
) -> None:
    token = _extract_token(secret_key, x_secret_key, authorization)
    if not _is_privileged_token(token):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _require_web_session(
    user_id: str,
    *,
    secret_key: Optional[str] = None,
    x_secret_key: Optional[str] = None,
    authorization: Optional[str] = None,
) -> None:
    """Allow a widget JWT to access only the web session it was issued for.

    Privileged server/operator secrets remain valid for support/admin tooling.
    """
    token = _extract_token(secret_key, x_secret_key, authorization)
    if _is_privileged_token(token):
        return

    payload = _widget_payload(token)
    session_id = str(payload.get("session_id", "")) if payload else ""
    expected_user_id = f"web_{session_id}" if session_id else ""
    if not expected_user_id or not hmac.compare_digest(str(user_id), expected_user_id):
        raise HTTPException(
            status_code=403,
            detail="Widget token is not valid for this chat session",
        )


@router.post("/api/chat/token")
async def get_widget_token():
    """Issue a short-lived JWT for one anonymous web-chat session."""
    session_id = secrets.token_hex(16)
    try:
        jwt_secret = _get_widget_jwt_secret()
    except RuntimeError as exc:
        logger.error("[CHAT] Refusing to issue widget token: %s", exc)
        raise HTTPException(status_code=503, detail="Chat authentication is not configured") from exc

    token = issue_widget_jwt(session_id=session_id, secret=jwt_secret, ttl_seconds=3600)
    return {"token": token, "session_id": f"web_{session_id}"}


@router.get("/api/chat/lookup/{phone}")
async def lookup_user_by_phone(
    phone: str,
    secret_key: Optional[str] = None,
    x_secret_key: Optional[str] = Header(None, alias="X-Secret-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    # Phone lookup exposes CRM identity data and is never available to an
    # anonymous widget JWT.
    _require_privileged(secret_key, x_secret_key, authorization)
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
    if str(user_id).startswith("web_"):
        _require_web_session(
            str(user_id),
            secret_key=secret_key,
            x_secret_key=x_secret_key,
            authorization=authorization,
        )
    else:
        _require_privileged(secret_key, x_secret_key, authorization)

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
    user_id_str = str(request.user_id)

    if user_id_str.startswith("web_"):
        _require_web_session(
            user_id_str,
            secret_key=request.secret_key,
            x_secret_key=x_secret_key,
            authorization=authorization,
        )

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

    # Non-web IDs map to real Telegram users. Anonymous widget credentials must
    # never be able to enqueue messages to them.
    _require_privileged(
        secret_key=request.secret_key,
        x_secret_key=x_secret_key,
        authorization=authorization,
    )

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
    # Lead creation mutates CRM state and therefore requires a privileged
    # server/operator credential, not an anonymous widget JWT.
    _require_privileged(request.secret_key, x_secret_key, authorization)

    from src.services.core.crm.amocrm_sync import AmoCRMSync
    from src.time_utils import get_local_now

    amocrm = AmoCRMSync(
        subdomain=getattr(settings, "AMOCRM_SUBDOMAIN", ""),
        client_id=getattr(settings, "AMOCRM_CLIENT_ID", ""),
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
