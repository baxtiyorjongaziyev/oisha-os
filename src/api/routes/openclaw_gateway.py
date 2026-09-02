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


@router.post("/webhook/openclaw")
async def openclaw_webhook(request: Request):
    try:
        body = await request.body()
        signature = request.headers.get("x-openclaw-signature", "")

        openclaw_secret = os.environ.get("OPENCLAW_SECRET", "")
        if openclaw_secret:
            expected_sig = hmac.new(
                openclaw_secret.encode(), body, hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected_sig):
                return JSONResponse(status_code=403, content={"error": "Invalid signature"})

        data = json.loads(body)
        message = data.get("message", "")
        user_id = data.get("user_id", "openclaw_user")

        from src.openclaw_bridge import handle_openclaw_message
        reply = await handle_openclaw_message(message, user_id=user_id)

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

        last_msg = messages[-1].get("content", "")

        from src.openclaw_bridge import handle_openclaw_message
        reply = await handle_openclaw_message(last_msg)

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
