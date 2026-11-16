"""Process-wide widget router for the Oisha bot token.

Feature modules register handlers with ``get_widget_router().register(...)``.
Only OWNER_ID and WHITELIST_IDS may trigger widget actions.
"""
from __future__ import annotations

import os
import time
from typing import List, Optional

from src.services.core.telegram.ai_features.bot_api_client import TelegramBotAPI10Client
from src.services.core.telegram.widgets.client import WidgetClient
from src.services.core.telegram.widgets.router import WidgetQuery, WidgetQueryRouter

_router: Optional[WidgetQueryRouter] = None


def _bot_token() -> str:
    token = os.environ.get("BOT_TOKEN", "")
    if token:
        return token
    from src.settings import settings

    secret = getattr(settings, "BOT_TOKEN", None)
    return secret.get_secret_value() if secret else ""


def _allowed_ids() -> List[int]:
    from src.settings import settings

    ids = [int(getattr(settings, "OWNER_ID", 0) or 0)]
    ids.extend(int(i) for i in (getattr(settings, "WHITELIST_IDS", None) or []))
    return [i for i in ids if i]


async def _ping(query: WidgetQuery) -> str:
    return "pong " + time.strftime("%H:%M:%S")


def build_widget_router(token: str, allowed_ids: List[int]) -> WidgetQueryRouter:
    router = WidgetQueryRouter(
        WidgetClient(TelegramBotAPI10Client(token)),
        allowed_user_ids=allowed_ids,
    )
    router.register("ping", _ping)
    return router


def get_widget_router() -> WidgetQueryRouter:
    global _router
    if _router is None:
        allowed = _allowed_ids()
        if not allowed:
            # Fail closed: without OWNER_ID nobody may run widget actions.
            allowed = [-1]
        _router = build_widget_router(_bot_token(), allowed)
    return _router


def reset_widget_router() -> None:
    global _router
    _router = None
