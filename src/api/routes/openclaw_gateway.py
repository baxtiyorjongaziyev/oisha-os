"""OpenClaw gateway + OpenAI-compatible routes."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from typing import Dict, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.time_utils import get_local_now

router = APIRouter(tags=["openclaw"])
logger = logging.getLogger(__name__)

_bot2bot_tracker: Dict[str, list] = {}
BOT2BOT_MAX_ROUNDS = 3
BOT2BOT_COOLDOWN_SEC = 300


class OpenClawMessage(BaseModel):
    message: str
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None


class OpenClawResponse(BaseModel):
    reply: str
    conversation_id: Optional[str] = None


def _bot2bot_allowed(from_id: str, chat_id: str) -> bool:
    import time
    key = f"{from_id}:{chat_id}"
    now = time.time()
    entries = _bot2bot_tracker.get(key, [])
    entries = [t for t in entries if now - t < BOT2BOT_COOLDOWN_SEC]
    if len(entries) >= BOT2BOT_MAX_ROUNDS:
        return False
    entries.append(now)
    _bot2bot_tracker[key] = entries
    return True


def _resolve_bridge_db():
    try:
        from src.api.routes.state import api_state

        if getattr(api_state, "db_instance", None) is not None:
            return api_state.db_instance
        ctrl = getattr(api_state, "msg_controller", None)
        if ctrl is not None and getattr(ctrl, "db", None) is not None:
            return ctrl.db
    except Exception:
        logger.debug("[OpenClaw] db resolve skipped", exc_info=True)
    return None


@router.post("/webhook/openclaw")
async def openclaw_webhook(request: Request):
    try:
        body = await request.body()
        signature = request.headers.get("x-openclaw-signature", "")

        # Fail closed: secret bo'lmasa endpoint agent orkestratoriga anonim
        # kirish beradi (CRM ma'lumotlari, pullik LLM chaqiruvlari).
        openclaw_secret = os.environ.get("OPENCLAW_SECRET", "")
        if not openclaw_secret:
            return JSONResponse(status_code=503, content={"error": "OpenClaw not configured"})
        expected_sig = hmac.new(
            openclaw_secret.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return JSONResponse(status_code=403, content={"error": "Invalid signature"})

        data = json.loads(body)
        if not isinstance(data, dict):
            return JSONResponse(status_code=400, content={"error": "Invalid payload"})

        text = str(data.get("text") or data.get("message") or "").strip()
        if not text:
            return JSONResponse(status_code=400, content={"error": "Message text is required"})

        sender_id = str(data.get("sender_id") or data.get("user_id") or "openclaw_user")
        sender = str(data.get("sender") or data.get("user_id") or sender_id)
        channel = str(data.get("channel") or "telegram")
        session = str(data.get("session") or data.get("conversation_id") or "oisha-main")
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}

        from src.openclaw_bridge import handle_openclaw_message

        reply = await handle_openclaw_message(
            text=text,
            sender=sender,
            sender_id=sender_id,
            channel=channel,
            session=session,
            db=_resolve_bridge_db(),
            metadata=metadata,
            persona="mrjon",
        )

        return {"reply": reply, "status": "ok"}
    except Exception as exc:
        logger.error("[OpenClaw] Error: %s", exc)
        return JSONResponse(status_code=500, content={"error": "Internal service error"})


@router.get("/webhook/openclaw/health")
async def openclaw_health():
    return {
        "status": "ok",
        "service": "openclaw-gateway",
        "timestamp": get_local_now().isoformat(),
    }


@router.get("/v1/models")
async def v1_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "oisha-enterprise",
                "object": "model",
                "owned_by": "jonbranding",
            }
        ],
    }


@router.post("/v1/chat/completions")
async def v1_chat_completions(request: Request):
    try:
        data = await request.json()
        messages = data.get("messages", [])
        if not messages:
            return JSONResponse(status_code=400, content={"error": "No messages provided"})

        last_entry = messages[-1] if isinstance(messages[-1], dict) else {}
        last_msg = str(last_entry.get("content") or "").strip()
        if not last_msg:
            return JSONResponse(status_code=400, content={"error": "Last message content is empty"})

        user_id = str(data.get("user") or "openai_compat_user")
        session = str(data.get("model") or "oisha-enterprise")

        from src.openclaw_bridge import handle_openclaw_message

        reply = await handle_openclaw_message(
            text=last_msg,
            sender=user_id,
            sender_id=user_id,
            channel="webchat",
            session=session,
            db=_resolve_bridge_db(),
            persona="mrjon",
        )

        return {
            "id": "chatcmpl-oisha",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": reply},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
    except Exception as exc:
        logger.error("[V1] Error: %s", exc)
        return JSONResponse(status_code=500, content={"error": "Internal service error"})
