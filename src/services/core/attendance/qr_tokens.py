"""Dinamik QR: server imzolagan, 30 soniyada eskiradigan, qayta ishlatib bo'lmaydigan token.

Token formati: ``base64url(payload_json).base64url(hmac_sha256)``.
Kalit: ``ATTENDANCE_QR_SECRET`` (kamida 32 belgi). Kalit yo'q bo'lsa — fail-closed.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

MIN_SECRET_LEN = 32
DEFAULT_TTL_S = 30
CLOCK_LEEWAY_S = 5


class QrError(Exception):
    """Sabab kodi ``code`` da: bad_format, bad_signature, expired, wrong_branch, replayed, not_configured."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class QrClaims:
    branch_id: int
    kiosk_id: str
    nonce: str
    issued_at: datetime
    expires_at: datetime


def _secret(explicit: str | None = None) -> bytes:
    value = (explicit if explicit is not None else os.getenv("ATTENDANCE_QR_SECRET", "")).strip()
    if len(value) < MIN_SECRET_LEN:
        raise QrError("not_configured")
    return value.encode()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(body: str, key: bytes) -> str:
    return _b64(hmac.new(key, body.encode(), hashlib.sha256).digest())


def issue(branch_id: int, kiosk_id: str, now: datetime, ttl_s: int = DEFAULT_TTL_S,
          secret: str | None = None) -> tuple[str, QrClaims]:
    key = _secret(secret)
    claims = QrClaims(branch_id, kiosk_id, secrets.token_urlsafe(16), now, now + timedelta(seconds=ttl_s))
    payload = {
        "b": branch_id, "k": kiosk_id, "n": claims.nonce,
        "iat": int(now.timestamp()), "exp": int(claims.expires_at.timestamp()),
    }
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    return f"{body}.{_sign(body, key)}", claims


def verify(token: str, expected_branch_id: int, now: datetime, secret: str | None = None) -> QrClaims:
    """Imzo, muddat va filialni tekshiradi. Bir martalikni ``redeem`` ta'minlaydi."""
    key = _secret(secret)
    if not isinstance(token, str) or len(token) > 512 or token.count(".") != 1:
        raise QrError("bad_format")
    body, sig = token.split(".")
    if not hmac.compare_digest(sig, _sign(body, key)):
        raise QrError("bad_signature")
    try:
        p = json.loads(_unb64(body))
        claims = QrClaims(
            int(p["b"]), str(p["k"]), str(p["n"]),
            datetime.fromtimestamp(int(p["iat"]), timezone.utc),
            datetime.fromtimestamp(int(p["exp"]), timezone.utc),
        )
    except (ValueError, KeyError, TypeError):
        raise QrError("bad_format") from None
    if now > claims.expires_at + timedelta(seconds=CLOCK_LEEWAY_S):
        raise QrError("expired")
    if now < claims.issued_at - timedelta(seconds=CLOCK_LEEWAY_S):
        raise QrError("bad_format")
    if claims.branch_id != expected_branch_id:
        raise QrError("wrong_branch")
    return claims


async def record_issued(db, claims: QrClaims) -> None:
    await db.execute(
        "INSERT INTO qr_challenges (branch_id, nonce, kiosk_id, issued_at, expires_at) VALUES (?, ?, ?, ?, ?)",
        [claims.branch_id, claims.nonce, claims.kiosk_id,
         claims.issued_at.isoformat(), claims.expires_at.isoformat()],
    )
    await db.commit()


async def redeem(db, claims: QrClaims, employee_id: int, session_id: str) -> None:
    """Atomik bir martalik ishlatish. Parallel so'rovlardan faqat bittasi o'tadi (UNIQUE)."""
    rows = await db.execute(
        "INSERT INTO qr_redemptions (challenge_id, employee_id, session_id)"
        " SELECT id, ?, ? FROM qr_challenges WHERE nonce = ? AND branch_id = ?"
        " ON CONFLICT DO NOTHING RETURNING id",
        [employee_id, session_id, claims.nonce, claims.branch_id],
    )
    await db.commit()
    if not rows:
        raise QrError("replayed")
