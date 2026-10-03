"""Fireflies.ai integration and webhook routes."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from src.settings import settings

router = APIRouter(tags=["fireflies"])
logger = logging.getLogger(__name__)


@router.post("/api/integrations/fireflies/webhook")
async def fireflies_webhook_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
    x_webhook_secret: Optional[str] = Header(None),
):
    """Handle incoming Fireflies.ai meeting done webhook."""
    expected_secret = getattr(settings, "FIREFLIES_WEBHOOK_SECRET", None)
    if expected_secret:
        sec_val = (
            expected_secret.get_secret_value()
            if hasattr(expected_secret, "get_secret_value")
            else str(expected_secret)
        )
        if sec_val and x_webhook_secret != sec_val:
            raise HTTPException(status_code=401, detail="Invalid webhook secret")

    try:
        data = await request.json()
    except Exception:
        data = {}

    transcript_id = (
        data.get("meetingId")
        or data.get("transcriptId")
        or data.get("id")
        or (data.get("data", {}).get("transcriptId") if isinstance(data.get("data"), dict) else None)
    )

    if not transcript_id:
        return {"status": "ignored", "message": "No transcriptId found in payload"}

    from src.services.core.integrations.fireflies_sync import get_fireflies_sync

    fireflies_sync = get_fireflies_sync()
    background_tasks.add_task(fireflies_sync.process_transcript, str(transcript_id))
    return {"status": "accepted", "transcript_id": transcript_id}
