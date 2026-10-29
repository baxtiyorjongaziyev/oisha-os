"""
Meta/Instagram webhook signature verification utility.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Optional
import structlog

from src.settings import settings

logger = structlog.get_logger("InstagramVerifier")


def verify_signature(payload: Any, signature: str, app_secret: Optional[str] = None) -> bool:
    """Verifies the SHA256 signature from Meta webhook requests."""
    secret = app_secret
    if secret is None:
        secret = settings.META_APP_SECRET.get_secret_value() if settings.META_APP_SECRET else ""

    if not secret:
        logger.error("[META] APP_SECRET not set, rejecting webhook")
        return False

    if not signature:
        logger.warning("[META] Signature header missing")
        return False

    if signature.startswith("sha256="):
        signature = signature[7:]

    if isinstance(payload, bytes):
        payload_bytes = payload
    elif isinstance(payload, str):
        payload_bytes = payload.encode("utf-8")
    else:
        payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    expected = hmac.new(
        secret.encode("utf-8"), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


import re
import time
from collections import defaultdict, deque

_UNSAFE_PUBLIC_REPLY = re.compile(
    r"https?://|www\.|t\.me/|\b[\w-]+\.(?:com|uz|ru|net|org|io|me|link|app)\b|@\w{3,}|\+?\d[\d\s-]{7,}",
    re.IGNORECASE,
)
MAX_PUBLIC_REPLY_CHARS = 400
AUTO_REPLY_LIMIT_PER_HOUR = 3
_auto_reply_log: dict[str, deque] = defaultdict(deque)


def is_safe_public_reply(text: str) -> bool:
    """AI javobini brend nomidan ommaviy joylashdan oldin tekshiradi."""
    t = (text or "").strip()
    return bool(t) and len(t) <= MAX_PUBLIC_REPLY_CHARS and not _UNSAFE_PUBLIC_REPLY.search(t)


def allow_auto_reply(commenter_id: str, now: Optional[float] = None) -> bool:
    """Bitta izohlovchiga soatiga ko'pi bilan AUTO_REPLY_LIMIT_PER_HOUR ta avto-javob."""
    now = time.time() if now is None else now
    log = _auto_reply_log[commenter_id]
    while log and now - log[0] > 3600:
        log.popleft()
    if len(log) >= AUTO_REPLY_LIMIT_PER_HOUR:
        return False
    log.append(now)
    return True

