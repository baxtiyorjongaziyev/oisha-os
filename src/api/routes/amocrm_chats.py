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
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from src.context import app_ctx
from src.services.core.crm.amocrm_chat import AmoCRMChatClient
from src.settings import settings

logger = logging.getLogger("AmoCRMChatsRouter")

router = APIRouter(prefix="/webhook/amocrm/chats", tags=["amocrm_chats"])


def _verify_amojo_signature(
    body_bytes: bytes,
    signature_header: Optional[str],
    date_header: Optional[str],
    content_md5_header: Optional[str],
    channel_secret: str,
    path: str = "/webhook/amocrm/chats",
    method: str = "POST",
) -> bool:
    """Verify amoJo HMAC-SHA1 signature if channel_secret is configured."""
    if not channel_secret:
        return True

    if not signature_header:
        logger.warning("[AMOCRM CHAT] Missing X-Signature header.")
        return False

    calculated_md5 = hashlib.md5(body_bytes, usedforsecurity=False).hexdigest().lower()
    if content_md5_header and content_md5_header.lower() != calculated_md5:
        logger.warning("[AMOCRM CHAT] Content-MD5 mismatch.")
        return False

    date_str = date_header or ""
    content_type = "application/json"
    signature_string = f"{method}\n{calculated_md5}\n{content_type}\n{date_str}\n{path}"

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
    channel_secret = (
        getattr(settings, "AMOCRM_CHAT_CHANNEL_SECRET", "")
        or getattr(settings, "AMOCRM_CLIENT_SECRET", "")
    )
    if hasattr(channel_secret, "get_secret_value"):
        channel_secret = channel_secret.get_secret_value()
    channel_secret = str(channel_secret or "")

    # Parse payload
    try:
        data = json.loads(body_bytes.decode("utf-8"))
    except Exception as e:
        logger.error(f"[AMOCRM CHAT] Invalid JSON payload: {e}")
        return JSONResponse(status_code=400, content={"error": "invalid_json"})

    logger.info(f"[AMOCRM CHAT] Received outbound message from amoCRM: {data}")

    message = data.get("message", {})
    text = message.get("text", "")
    msg_type = message.get("type", "text")
    receiver = message.get("receiver", {})
    conversation = message.get("conversation", {})
    client_id = conversation.get("client_id") or receiver.get("id")

    if not client_id:
        logger.warning("[AMOCRM CHAT] Missing recipient client_id in chat message payload.")
        return JSONResponse(content={"status": "ok", "warning": "no_recipient"})

    # Send to Telegram via BotRuntime
    bot_runtime = getattr(app_ctx, "bot_runtime", None)
    if bot_runtime and text:
        try:
            tg_user_id = int(client_id)
            await bot_runtime.send_message(
                chat_id=tg_user_id,
                text=text,
                parse_mode="HTML",
            )
            logger.info(f"[AMOCRM CHAT] Successfully dispatched message to Telegram user {tg_user_id}")
            return JSONResponse(content={"status": "ok", "msg_id": message.get("msg_id")})
        except ValueError:
            logger.warning(f"[AMOCRM CHAT] Client ID {client_id} is not numeric Telegram user_id. Phone/WhatsApp routing.")
        except Exception as e:
            logger.error(f"[AMOCRM CHAT] Failed to dispatch message to Telegram: {e}")

    return JSONResponse(content={"status": "ok"})
