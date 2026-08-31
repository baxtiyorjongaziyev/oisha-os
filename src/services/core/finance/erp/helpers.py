"""
Internal helpers for ERP command handlers.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)


async def _reply(message, text: str, parse_mode: str = "markdown") -> None:
    fn = (
        getattr(message, "answer", None)
        or getattr(message, "reply", None)
        or getattr(message, "respond", None)
    )
    if callable(fn):
        try:
            await fn(text, parse_mode=parse_mode)
        except TypeError:
            await fn(text)
    else:
        logger.warning("_reply: cannot find a send method on %r", type(message))


def _sender_id(message) -> Optional[int]:
    from_user = getattr(message, "from_user", None)
    if from_user is not None:
        return getattr(from_user, "id", None)
    sender_id = getattr(message, "sender_id", None)
    if sender_id is not None:
        return int(sender_id)
    return None


async def _check_permission(message) -> bool:
    try:
        from src.settings import settings
        whitelist = getattr(settings, "WHITELIST_IDS", None) or []
        if not whitelist:
            return True
        sender = _sender_id(message)
        return sender in whitelist
    except Exception:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return True


def _current_period() -> str:
    return date.today().strftime("%Y-%m")
