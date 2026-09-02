"""Instagram / Meta webhook routes."""
from __future__ import annotations

import asyncio
import json
import logging
import os

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from src.settings import settings

router = APIRouter(prefix="/api/instagram", tags=["instagram"])
logger = logging.getLogger(__name__)


def _secret_text(value) -> str:
    getter = getattr(value, "get_secret_value", None)
    return str(getter() if callable(getter) else value or "").strip()


@router.get("/webhook")
async def instagram_webhook_verify(
    hub_mode: str = "",
    hub_verify_token: str = "",
    hub_challenge: str = "",
):
    """Meta webhook verification (GET)."""
    expected = (
        _secret_text(getattr(settings, "META_VERIFY_TOKEN", None))
        or os.environ.get("META_VERIFY_TOKEN", "").strip()
        or os.environ.get("INSTAGRAM_VERIFY_TOKEN", "").strip()
    )
    if expected and hub_mode == "subscribe" and hub_verify_token == expected:
        return PlainTextResponse(content=hub_challenge)
    return PlainTextResponse(status_code=403, content="Verification token mismatch")


@router.post("/webhook")
async def instagram_webhook(request: Request):
    """Meta webhook events (POST)."""
    raw_body = await request.body()
    try:
        body = json.loads(raw_body)
    except Exception:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return {"status": "error", "message": "Invalid JSON"}

    signature = request.headers.get("X-Hub-Signature-256", "")

    try:
        from src.services.core.instagram_agent import verify_signature, process_instagram_webhook
        if not verify_signature(raw_body, signature):
            return PlainTextResponse(status_code=403, content="Invalid signature")

        asyncio.create_task(process_instagram_webhook(body))
    except ImportError:
        logger.warning("[INSTAGRAM] instagram_agent not available")
    except Exception as exc:
        logger.error("[INSTAGRAM] webhook error: %s", exc)

    return {"status": "ok"}
