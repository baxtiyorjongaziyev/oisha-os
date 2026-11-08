"""CRM Seller Authentication & Session Guard for Jon CRM.

Ushbu modul har bir sotuvchi (Shahnoza, Rayxona, Mumtozmaxal, Baxtiyorjon va h.k.)
uchun alohida maxfiy PIN/parollarni PBKDF2-SHA256 xesh orqali xavfsiz saqlaydi
va barcha CRM API larini ruxsatsiz kirishlardan to'liq himoya qiladi (Fail-Closed).
"""
from __future__ import annotations

import logging
import os
import secrets
import sqlite3
import time
from typing import Any, Dict, List, Optional
from fastapi import Header, HTTPException, Request

from src.services.core.crm.seller_auth_support import (
    LOCKED_PIN_HASH,
    PIN_CHANGE_REQUIRED,
    STRONG_PIN_MIN_LENGTH,
    LoginThrottle,
    _hash_pin,
    _verify_pin,
    create_seller_schema,
    seed_or_refresh_sellers,
    unlock_sellers_from_env,
)

logger = logging.getLogger(__name__)

DB_PATH = "data/crm_dialer.db"
TEMP_PIN_DIGITS = 8


class SellerAuthService:
    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path
        self.login_throttle = LoginThrottle()
        self._init_tables()

    def _get_conn(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self) -> None:
        with self._get_conn() as conn:
            create_seller_schema(conn)
            seed_or_refresh_sellers(conn)
            unlock_sellers_from_env(conn)
            conn.commit()

    def list_public_sellers(self) -> List[Dict[str, Any]]:
        """Kirish ekrani uchun ochiq roʻyxat: faqat slug va ism.

        Bu endpoint login talab qilmaydi, shuning uchun telefon, Telegram va rol
        bu yerda qaytarilmaydi.
        """
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT slug, name FROM crm_seller_accounts ORDER BY rep_id ASC"
            ).fetchall()
            return [dict(r) for r in rows]

    def list_sellers_for_admin(self) -> List[Dict[str, Any]]:
        """Administrator uchun xodimlar va PIN holati (xesh qaytarilmaydi)."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT slug, name, role, phone, tg, pin_hash, must_change_pin
                FROM crm_seller_accounts ORDER BY rep_id ASC
                """
            ).fetchall()
        sellers = []
        for row in rows:
            status = "active"
            if row["pin_hash"] == LOCKED_PIN_HASH:
                status = "locked"
            elif row["must_change_pin"]:
                status = "change_required"
            sellers.append({
                "slug": row["slug"],
                "name": row["name"],
                "role": row["role"],
                "phone": row["phone"],
                "tg": row["tg"],
                "pin_status": status,
            })
        return sellers

    def find_slug_by_phone(self, phone: str) -> Optional[str]:
        """Match on the 9-digit national number; blank or short phones never match."""
        digits = "".join(filter(str.isdigit, str(phone or "")))
        if len(digits) < 9:
            return None
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT slug, phone FROM crm_seller_accounts ORDER BY rep_id ASC"
            ).fetchall()
        for row in rows:
            seller_digits = "".join(filter(str.isdigit, row["phone"] or ""))
            if len(seller_digits) >= 9 and digits[-9:] == seller_digits[-9:]:
                return row["slug"]
        return None

    def authenticate_seller(self, slug: str, pin: str, ttl_days: int = 30) -> Optional[Dict[str, Any]]:
        """Sotuvchi kiritgan PIN-kodni xavfsiz tekshirish va sessiya tokeni berish."""
        clean_slug = str(slug or "").strip().lower()
        clean_pin = str(pin or "").strip()
        if not clean_slug or not clean_pin:
            return None
        if self.login_retry_after(clean_slug):
            return None

        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM crm_seller_accounts WHERE slug = ?", (clean_slug,)
            ).fetchone()
            if not row:
                return None

            if not _verify_pin(clean_pin, row["pin_hash"]):
                self.login_throttle.record_failure(clean_slug)
                return None
            self.login_throttle.reset(clean_slug)

            # Yangi xavfsiz tasodifiy sessiya tokeni yaratish
            token = secrets.token_urlsafe(32)
            now = time.time()
            expires_at = now + (ttl_days * 86400)
            must_change_pin = len(clean_pin) < STRONG_PIN_MIN_LENGTH or bool(row["must_change_pin"])

            # Eskirgan sessiyalarni tozalash
            conn.execute("DELETE FROM crm_seller_sessions WHERE expires_at < ?", (now,))
            conn.execute(
                """
                INSERT INTO crm_seller_sessions (token, seller_slug, created_at, expires_at, must_change_pin)
                VALUES (?, ?, ?, ?, ?)
                """,
                (token, clean_slug, now, expires_at, int(must_change_pin)),
            )
            conn.commit()

            return {
                "token": token,
                "expires_at": expires_at,
                "must_change_pin": must_change_pin,
                "seller": {
                    "slug": row["slug"],
                    "name": row["name"],
                    "rep_id": row["rep_id"],
                    "phone": row["phone"],
                    "tg": row["tg"],
                    "role": row["role"],
                },
            }

    def login_retry_after(self, slug: str) -> int:
        """Seconds the seller must wait before the next PIN attempt (0 = allowed)."""
        return self.login_throttle.retry_after(str(slug or "").strip().lower())

    def validate_session(self, token: str) -> Optional[Dict[str, Any]]:
        """Sessiya tokenini tekshirish."""
        clean_token = str(token or "").strip()
        if not clean_token:
            return None

        now = time.time()
        with self._get_conn() as conn:
            row = conn.execute(
                """
                SELECT s.slug, s.name, s.rep_id, s.phone, s.tg, s.role, sess.expires_at,
                       sess.must_change_pin
                FROM crm_seller_sessions sess
                JOIN crm_seller_accounts s ON s.slug = sess.seller_slug
                WHERE sess.token = ? AND sess.expires_at > ?
                """,
                (clean_token, now),
            ).fetchone()
            if not row:
                return None
            seller = dict(row)
            seller["must_change_pin"] = bool(seller.get("must_change_pin"))
            return seller

    def revoke_session(self, token: str) -> bool:
        """Sessiyani yakunlash (Logout)."""
        clean_token = str(token or "").strip()
        if not clean_token:
            return False
        with self._get_conn() as conn:
            conn.execute("DELETE FROM crm_seller_sessions WHERE token = ?", (clean_token,))
            conn.commit()
            return True

    def change_seller_pin(
        self, slug: str, old_pin: str, new_pin: str, keep_token: Optional[str] = None
    ) -> bool:
        """Sotuvchi oʻz PIN-kodini yangilashi.

        Only the session in `keep_token` survives: anyone else logged in with the
        old PIN is logged out instead of being unlocked along with the owner.
        """
        clean_slug = str(slug or "").strip().lower()
        clean_old = str(old_pin or "").strip()
        clean_new = str(new_pin or "").strip()
        if len(clean_new) < STRONG_PIN_MIN_LENGTH or clean_new == clean_old:
            return False
        if self.login_retry_after(clean_slug):
            return False

        with self._get_conn() as conn:
            row = conn.execute("SELECT pin_hash FROM crm_seller_accounts WHERE slug = ?", (clean_slug,)).fetchone()
            if not row:
                return False
            if not _verify_pin(clean_old, row["pin_hash"]):
                self.login_throttle.record_failure(clean_slug)
                return False

            conn.execute(
                """
                UPDATE crm_seller_accounts
                SET pin_hash = ?, must_change_pin = 0, updated_at = CURRENT_TIMESTAMP
                WHERE slug = ?
                """,
                (_hash_pin(clean_new), clean_slug),
            )
            conn.execute(
                "DELETE FROM crm_seller_sessions WHERE seller_slug = ? AND token != ?",
                (clean_slug, keep_token or ""),
            )
            conn.execute(
                "UPDATE crm_seller_sessions SET must_change_pin = 0 WHERE token = ?",
                (keep_token or "",),
            )
            conn.commit()
            return True

    def reset_seller_pin(self, slug: str) -> Optional[str]:
        """Administrator: yangi vaqtinchalik PIN berish.

        The old PIN and every session of that seller stop working at once. The
        seller must replace the temporary PIN at first login. Returns the PIN
        once; it is stored only as a hash and must never be logged.
        """
        clean_slug = str(slug or "").strip().lower()
        temp_pin = f"{secrets.randbelow(10**TEMP_PIN_DIGITS):0{TEMP_PIN_DIGITS}d}"
        with self._get_conn() as conn:
            updated = conn.execute(
                """
                UPDATE crm_seller_accounts
                SET pin_hash = ?, must_change_pin = 1, updated_at = CURRENT_TIMESTAMP
                WHERE slug = ?
                """,
                (_hash_pin(temp_pin), clean_slug),
            ).rowcount
            if not updated:
                return None
            conn.execute("DELETE FROM crm_seller_sessions WHERE seller_slug = ?", (clean_slug,))
            conn.commit()
        self.login_throttle.reset(clean_slug)
        return temp_pin


# Global xizmat nusxasi
seller_auth_service = SellerAuthService()


def extract_session_token(request: Request, authorization: Optional[str] = None) -> str:
    """Session token from the cookie, Authorization or X-CRM-Session-Token header."""
    token = ""
    # 1. Cookie dan qidirish
    cookie_token = request.cookies.get("crm_session_token")
    if cookie_token:
        token = cookie_token

    # 2. Authorization sarlavhasidan qidirish
    if not token and authorization:
        if authorization.startswith("Bearer "):
            token = authorization[7:].strip()
        else:
            token = authorization.strip()

    # 3. Custom Header
    if not token:
        custom_header = request.headers.get("X-CRM-Session-Token")
        if custom_header:
            token = custom_header.strip()
    return token


def get_current_crm_seller(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """FastAPI Dependency: Barcha CRM yo'llari uchun qat'iy sessiya tekshiruvi.

    401 without a valid session; 403 ``pin_change_required`` while the session
    was opened with a weak PIN (only /me, /change-pin, /logout work then).
    """
    seller = get_crm_seller_session(request, authorization)
    if seller.get("must_change_pin"):
        raise HTTPException(
            status_code=403,
            detail={
                "code": PIN_CHANGE_REQUIRED,
                "message": "Xavfsizlik uchun PIN-kodni yangilang (kamida 6 belgi).",
            },
        )
    return seller


def get_crm_seller_session(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Valid session regardless of the PIN-change flag (for /me, /change-pin).

    Agar foydalanuvchida yaroqli sessiya cookie yoki Bearer token boʻlmasa,
    darhol 401 Unauthorized qaytariladi.
    """
    token = extract_session_token(request, authorization)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="CRM ga kirish uchun ruxsat berilmagan. Avval tizimga kiring.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    seller = seller_auth_service.validate_session(token)
    if not seller:
        raise HTTPException(
            status_code=401,
            detail="Sessiya eskirgan yoki yaroqsiz. Qaytadan PIN-kod bilan kiring.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return seller
