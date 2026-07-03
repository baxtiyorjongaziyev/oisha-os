"""Telegram integration + webhook routes."""
from __future__ import annotations

import asyncio
import hmac
import logging
import os
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

from src.api.routes.state import api_state
from src.settings import settings
from src.time_utils import get_local_now

router = APIRouter(prefix="/api/telegram", tags=["telegram"])
logger = logging.getLogger(__name__)


@router.get("/status")
async def telegram_status():
    """Diagnostic info for Telegram Bot API 10.0 integration."""
    try:
        from src.services.core.telegram.telegram_ai_features import (
            TelegramBotAPI10Client,
            build_live_feature_status,
        )
        token = os.environ.get("BOT_TOKEN") or settings.BOT_TOKEN.get_secret_value()
        client = TelegramBotAPI10Client(token)
        me = await client.get_me()
        webhook_info = await client.get_webhook_info()
        return {
            "status": "online",
            "bot": build_live_feature_status(me),
            "webhook": webhook_info,
            "api_10_ready": True,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/group-access")
async def telegram_group_access(refresh: bool = False):
    """Return the cached userbot group/topic snapshot or refresh it."""
    if refresh:
        from src.api_server import refresh_userbot_group_access_snapshot
        return await refresh_userbot_group_access_snapshot()
    return dict(api_state._userbot_group_access_snapshot)


@router.get("/ai-features")
async def telegram_ai_features():
    """Current status of Bot API 10.0 AI features."""
    from src.services.core.telegram.telegram_ai_features import (
        build_live_feature_status,
        build_offline_feature_status,
    )
    try:
        from src.services.core.agent_runtime import get_runtime_context
        runtime = get_runtime_context()
        if runtime.get("userbot_authorized"):
            token = os.environ.get("BOT_TOKEN") or settings.BOT_TOKEN.get_secret_value()
            from src.services.core.telegram.telegram_ai_features import TelegramBotAPI10Client
            client = TelegramBotAPI10Client(token)
            me = await client.get_me()
            return {
                "status": "live",
                "features": build_live_feature_status(me),
            }
        return {
            "status": "offline",
            "features": build_offline_feature_status(),
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
