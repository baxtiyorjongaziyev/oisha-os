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
