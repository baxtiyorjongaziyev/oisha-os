"""
AmoCRM Online Chat (amoJo) Webhook & Dispatcher Router.
Replaces Wazzup24 & ChatApp with native 0$ Oisha-Chat engine.

Handles:
1. Outbound messages from amoCRM (when sales manager types in amoCRM deal chat) -> sends to Telegram/WhatsApp.
2. Inbound sync helper from Telegram/WhatsApp -> pushes to amoCRM deal chat tab.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from email.utils import parsedate_to_datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from src.context import app_ctx
from src.settings import settings

logger = logging.getLogger("AmoCRMChatsRouter")

router = APIRouter(prefix="/webhook/amocrm/chats", tags=["amocrm_chats"])

_MAX_BODY_BYTES = 64 * 1024
_MAX_CLOCK_SKEW_SECONDS = 300
_MAX_TEXT_LENGTH = 4096


def _verify_amojo_signature(
    body_bytes: bytes,
    signature_header: Optional[str],
    date_header: Optional[str],
    content_md5_header: Optional[str],
    channel_secret: str,
    path: str = "/webhook/amocrm/chats",
    method: str = "POST",
) -> bool:
    """Verify an amoJo request without ever accepting an unsigned fallback."""
    if not channel_secret:
        return False

    if not signature_header or not date_header or not content_md5_header:
        logger.warning("[AMOCRM CHAT] Required signature headers are missing.")
        return False

    calculated_md5 = hashlib.md5(body_bytes, usedforsecurity=False).hexdigest().lower()
    if not hmac.compare_digest(content_md5_header.lower(), calculated_md5):
        logger.warning("[AMOCRM CHAT] Content-MD5 mismatch.")
        return False

    try:
        request_time = parsedate_to_datetime(date_header).timestamp()
    except (TypeError, ValueError, OverflowError):
        logger.warning("[AMOCRM CHAT] Invalid Date header.")
        return False
    if abs(time.time() - request_time) > _MAX_CLOCK_SKEW_SECONDS:
        logger.warning("[AMOCRM CHAT] Stale Date header.")
        return False

    content_type = "application/json"
    signature_string = f"{method}\n{calculated_md5}\n{content_type}\n{date_header}\n{path}"

    expected_sig = hmac.new(
        channel_secret.encode("utf-8"),
        signature_string.encode("utf-8"),
        hashlib.sha1,
    ).hexdigest().lower()

    return hmac.compare_digest(signature_header.lower(), expected_sig)


@router.post("")
@router.post("/")
async def handle_amocrm_chat_outbound(
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    date: Optional[str] = Header(None, alias="Date"),
    content_md5: Optional[str] = Header(None, alias="Content-MD5"),
):
    """
    Webhook triggered by amoCRM when a sales manager sends a message from amoCRM chat.
    Dispatches the message to Telegram/WhatsApp.
    """
    body_bytes = await request.body()
    if len(body_bytes) > _MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload too large")

    channel_secret = getattr(settings, "AMOCRM_CHAT_CHANNEL_SECRET", "")
    if hasattr(channel_secret, "get_secret_value"):
        channel_secret = channel_secret.get_secret_value()
    channel_secret = str(channel_secret or "")

    if not channel_secret:
        logger.error("[AMOCRM CHAT] AMOCRM_CHAT_CHANNEL_SECRET is not configured.")
        raise HTTPException(status_code=503, detail="Chat webhook is not configured")
    if not _verify_amojo_signature(
        body_bytes,
        x_signature,
        date,
        content_md5,
        channel_secret,
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Parse payload
    try:
        data = json.loads(body_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("[AMOCRM CHAT] Invalid JSON payload.")
        return JSONResponse(status_code=400, content={"error": "invalid_json"})

    if not isinstance(data, dict):
        return JSONResponse(status_code=400, content={"error": "invalid_payload"})

    message = data.get("message", {})
    text = message.get("text", "")
    if not isinstance(message, dict) or not isinstance(text, str):
        return JSONResponse(status_code=400, content={"error": "invalid_message"})
    if not text or len(text) > _MAX_TEXT_LENGTH:
        return JSONResponse(status_code=400, content={"error": "invalid_text"})
    receiver = message.get("receiver", {})
    conversation = message.get("conversation", {})
    if not isinstance(receiver, dict) or not isinstance(conversation, dict):
        return JSONResponse(status_code=400, content={"error": "invalid_recipient"})
    client_id = conversation.get("client_id") or receiver.get("id")

    if not client_id:
        logger.warning("[AMOCRM CHAT] Missing recipient client_id in chat message payload.")
        return JSONResponse(content={"status": "ok", "warning": "no_recipient"})

    # Send to Telegram via BotRuntime
    bot_runtime = getattr(app_ctx, "bot_runtime", None)
    if not bot_runtime:
        raise HTTPException(status_code=503, detail="Message runtime unavailable")
    if bot_runtime and text:
        try:
            tg_user_id = int(client_id)
            if tg_user_id <= 0:
                raise ValueError("Telegram user id must be positive")
            await bot_runtime.send_message(
                chat_id=tg_user_id,
                text=text,
                parse_mode=None,
            )
            logger.info("[AMOCRM CHAT] Dispatched signed outbound message.")
            return JSONResponse(content={"status": "ok", "msg_id": message.get("msg_id")})
        except ValueError:
            logger.warning("[AMOCRM CHAT] Recipient is not a valid Telegram user id.")
            return JSONResponse(status_code=400, content={"error": "invalid_recipient"})
        except Exception as e:
            logger.error("[AMOCRM CHAT] Dispatch failed: %s", type(e).__name__)
            raise HTTPException(status_code=502, detail="Message dispatch failed") from None

    raise HTTPException(status_code=500, detail="Unexpected chat dispatch state")
