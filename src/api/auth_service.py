"""Authentication helpers extracted from api_server.py.

Pure, testable functions for Telegram-login hash verification and the session
JWT. Route handlers keep the HTTP/cookie orchestration and delegate the crypto
here, so the security-critical logic lives in one place with no framework deps.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import re
import time
from typing import Any, Dict, Optional

import jwt

# Limit browser sessions to twelve hours. A fresh Telegram login can renew it.
SESSION_TTL_SECONDS = 12 * 60 * 60
# Telegram login payloads older than this are rejected (replay protection).
TELEGRAM_AUTH_MAX_AGE_SECONDS = 86400
_SAFE_ROLE_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


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
    """Return True if the Telegram ``auth_date`` is within the replay window.

    A missing ``auth_date`` fails closed (no replay protection → reject). A
    small negative tolerance absorbs clock drift while still rejecting
    implausible future timestamps.
    """
    if not auth_date:
        return False
    diff = time.time() - int(auth_date)
    return -300 <= diff <= max_age_seconds


def sanitize_display_text(value: Optional[str], *, max_length: int = 120) -> str:
    """Escape untrusted Telegram profile text before it reaches HTML templates."""
    return html.escape(str(value or "").strip()[:max_length], quote=True)


def normalize_session_role(role: str) -> str:
    """Keep the role claim safe for legacy HTML/JavaScript interpolation."""
    candidate = str(role or "client").strip().lower()
    return candidate if _SAFE_ROLE_RE.fullmatch(candidate) else "client"


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
    clean_secret = str(secret or "").strip()
    if not clean_secret:
        raise ValueError("A dedicated session secret is required")

    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "username": sanitize_display_text(username, max_length=64),
        "first_name": sanitize_display_text(first_name),
        "role": normalize_session_role(role),
        "iat": now,
        "exp": now + max(60, int(ttl_seconds)),
    }
    return jwt.encode(payload, clean_secret, algorithm="HS256")


def decode_session_jwt(token: str, secret: str) -> Optional[Dict[str, Any]]:
    """Decode/verify a session token; return the payload or None if invalid."""
    clean_secret = str(secret or "").strip()
    if not clean_secret:
        return None
    try:
        return jwt.decode(token, clean_secret, algorithms=["HS256"])
    except Exception:
        return None
