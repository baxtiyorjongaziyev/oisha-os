"""Authentication helpers extracted from api_server.py.

Pure, testable functions for Telegram-login hash verification and the session
JWT. Route handlers keep the HTTP/cookie orchestration and delegate the crypto
here, so the security-critical logic lives in one place with no framework deps.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Dict, Optional

import jwt

# Default session lifetime: 30 days.
SESSION_TTL_SECONDS = 30 * 24 * 3600
# Telegram login payloads older than this are rejected (replay protection).
TELEGRAM_AUTH_MAX_AGE_SECONDS = 86400


def build_telegram_data_check_string(fields: Dict[str, Optional[str]]) -> str:
    """Build Telegram's data-check-string: sorted ``key=value`` lines."""
    parts = [f"{key}={val}" for key, val in sorted(fields.items()) if val is not None]
    return "\n".join(parts)


def verify_telegram_hash(
    fields: Dict[str, Optional[str]], bot_token: str, provided_hash: str
) -> bool:
    """Return True iff ``provided_hash`` matches Telegram's HMAC over ``fields``.

    Uses a constant-time comparison to avoid timing leaks.
    """
    data_check_string = build_telegram_data_check_string(fields)
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    expected_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_hash, provided_hash or "")


def is_auth_date_fresh(
    auth_date: Optional[int], max_age_seconds: int = TELEGRAM_AUTH_MAX_AGE_SECONDS
) -> bool:
    """Return True if the Telegram ``auth_date`` is within the replay window."""
    if not auth_date:
        return True
    return (time.time() - int(auth_date)) <= max_age_seconds


def issue_session_jwt(
    *,
    user_id: int,
    username: Optional[str],
    first_name: Optional[str],
    role: str,
    secret: str,
    ttl_seconds: int = SESSION_TTL_SECONDS,
) -> str:
    """Encode the signed session token stored in the ``oisha_token`` cookie."""
    payload = {
        "sub": str(user_id),
        "username": username,
        "first_name": first_name,
        "role": role,
        "exp": int(time.time()) + ttl_seconds,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_session_jwt(token: str, secret: str) -> Optional[Dict[str, Any]]:
    """Decode/verify a session token; return the payload or None if invalid."""
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except Exception:
        return None
