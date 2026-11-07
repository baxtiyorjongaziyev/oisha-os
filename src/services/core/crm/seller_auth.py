"""CRM Seller Authentication & Session Guard for Jon CRM.

Ushbu modul har bir sotuvchi (Shahnoza, Rayxona, Mumtozmaxal, Baxtiyorjon va h.k.)
uchun alohida maxfiy PIN/parollarni PBKDF2-SHA256 xesh orqali xavfsiz saqlaydi
va barcha CRM API larini ruxsatsiz kirishlardan to'liq himoya qiladi (Fail-Closed).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional
from fastapi import Header, HTTPException, Request

logger = logging.getLogger(__name__)

DB_PATH = "data/crm_dialer.db"

# Standart dastlabki xodimlar. PIN kodlar kodda saqlanmaydi: birinchi ishga
# tushishda CRM_SELLER_PIN_<SLUG> env qiymatidan olinadi (masalan
# CRM_SELLER_PIN_SHAHNOZA). Env boʻlmasa akkaunt PIN oʻrnatilguncha qulflangan.
INITIAL_SELLERS: List[Dict[str, Any]] = [
    {
        "slug": "baxtiyorjon",
        "name": "Baxtiyorjon Gaziyev",
        "rep_id": 8128012,
        "phone": "+998336450097",
        "tg": "@baxtiyorjongaziyev",
        "role": "admin",
    },
    {
        "slug": "shahnoza",
        "name": "Shahnoza Abdijabborova",
        "rep_id": 13021974,
        "phone": "+998773220042",
        "tg": "@jonbranding_assistant",
        "role": "seller",
    },
    {
        "slug": "rayxona",
        "name": "Rayxona Rahimova",
        "rep_id": 9000001,
        "phone": "+998777411397",
        "tg": "@RayxonJonbranding",
        "role": "seller",
    },
    {
        "slug": "mumtozmaxal",
        "name": "Mumtozmaxal Normurodova",
        "rep_id": 9000002,
        "phone": "+998773220098",
        "tg": "@MumtozmaxalJonbranding",
        "role": "seller",
    },
    {
        "slug": "hasanboy",
        "name": "Hasanboy Gaziyev",
        "rep_id": 9000003,
        "phone": "+998973355900",
        "tg": "@hasan_yahyo",
        "role": "specialist",
    },
]

# Hash with no "$" separator: _verify_pin always rejects it.
LOCKED_PIN_HASH = "!locked"
MIN_PIN_LENGTH = 4
# Sessions opened with a shorter PIN (e.g. the old 4-digit defaults) may only
# call /me, /change-pin and /logout until the seller sets a stronger PIN.
STRONG_PIN_MIN_LENGTH = 6
PIN_CHANGE_REQUIRED = "pin_change_required"

# Brute-force guard: a 4-digit PIN has only 10k values, so failed logins are
# throttled per seller (not per IP: behind the reverse proxy every client
# shares 127.0.0.1).
MAX_FAILED_LOGINS = 10
LOGIN_LOCKOUT_WINDOW_SECONDS = 15 * 60


def _initial_pin_env_name(slug: str) -> str:
    return f"CRM_SELLER_PIN_{slug.upper()}"


def _initial_pin_hash(slug: str) -> str:
    pin = os.getenv(_initial_pin_env_name(slug), "").strip()
    if len(pin) < MIN_PIN_LENGTH:
        logger.warning(
            "CRM seller %s has no initial PIN (%s unset); account stays locked",
            slug,
            _initial_pin_env_name(slug),
        )
        return LOCKED_PIN_HASH
    return _hash_pin(pin)


class LoginThrottle:
    """In-memory sliding-window counter of failed logins per key."""

    def __init__(
        self,
        max_failures: int = MAX_FAILED_LOGINS,
        window_seconds: int = LOGIN_LOCKOUT_WINDOW_SECONDS,
    ) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._failures: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> List[float]:
        stamps = [t for t in self._failures.get(key, []) if now - t < self.window_seconds]
        if stamps:
            self._failures[key] = stamps
        else:
            self._failures.pop(key, None)
        return stamps

    def retry_after(self, key: str) -> int:
        """Seconds until the key may try again; 0 when not locked."""
        now = time.time()
        with self._lock:
            stamps = self._recent(key, now)
            if len(stamps) < self.max_failures:
                return 0
            return int(self.window_seconds - (now - stamps[0])) + 1

    def record_failure(self, key: str) -> None:
        now = time.time()
        with self._lock:
            self._failures[key] = self._recent(key, now) + [now]

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


def _hash_pin(pin: str, salt: Optional[str] = None) -> str:
    s = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), s.encode("utf-8"), 100_000)
    return f"{s}${dk.hex()}"


def _verify_pin(pin: str, stored_hash: str) -> bool:
    if "$" not in stored_hash:
        return False
    salt, _ = stored_hash.split("$", 1)
    expected = _hash_pin(pin, salt=salt)
    return hmac.compare_digest(expected, stored_hash)


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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS crm_seller_accounts (
                    slug TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    rep_id INTEGER NOT NULL,
                    phone TEXT NOT NULL,
                    tg TEXT,
                    role TEXT NOT NULL DEFAULT 'seller',
                    pin_hash TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS crm_seller_sessions (
                    token TEXT PRIMARY KEY,
                    seller_slug TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    FOREIGN KEY (seller_slug) REFERENCES crm_seller_accounts(slug)
                );
                """
            )
            session_cols = {r["name"] for r in conn.execute("PRAGMA table_info(crm_seller_sessions)")}
            if "must_change_pin" not in session_cols:
                conn.execute(
                    "ALTER TABLE crm_seller_sessions ADD COLUMN must_change_pin INTEGER NOT NULL DEFAULT 0"
                )
            conn.commit()

            # Boshlang'ich sotuvchilarni yuklash
            count = conn.execute("SELECT COUNT(*) as c FROM crm_seller_accounts").fetchone()["c"]
            if count == 0:
                for s in INITIAL_SELLERS:
                    hashed = _initial_pin_hash(s["slug"])
                    conn.execute(
                        """
                        INSERT INTO crm_seller_accounts (slug, name, rep_id, phone, tg, role, pin_hash)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (s["slug"], s["name"], s["rep_id"], s["phone"], s["tg"], s["role"], hashed),
                    )
                conn.commit()
            else:
                # Xodimlarning tasdiqlangan telefon va ismlarini yangilash
                conn.execute(
                    "UPDATE crm_seller_accounts SET name = 'Baxtiyorjon Gaziyev', phone = '+998336450097', tg = '@baxtiyorjongaziyev' WHERE slug = 'baxtiyorjon'"
                )
                conn.execute(
                    "UPDATE crm_seller_accounts SET name = 'Shahnoza Abdijabborova', phone = '+998773220042', tg = '@jonbranding_assistant' WHERE slug = 'shahnoza'"
                )
                conn.execute(
                    "UPDATE crm_seller_accounts SET name = 'Rayxona Rahimova', phone = '+998777411397', tg = '@RayxonJonbranding' WHERE slug = 'rayxona'"
                )
                conn.execute(
                    "UPDATE crm_seller_accounts SET name = 'Mumtozmaxal Normurodova', phone = '+998773220098', tg = '@MumtozmaxalJonbranding' WHERE slug = 'mumtozmaxal'"
                )
                # Bo'shatilgan xodimlarni bazadan to'liq o'chirish va sessiyalarini bekor qilish
                conn.execute("DELETE FROM crm_seller_sessions WHERE seller_slug IN ('oydin', 'farangiz')")
                conn.execute("DELETE FROM crm_seller_accounts WHERE slug IN ('oydin', 'farangiz')")
                # Hasanboy Gaziyev mavjud bo'lmasa kiritish, bo'lsa yangilash
                has_h = conn.execute("SELECT COUNT(*) as c FROM crm_seller_accounts WHERE slug = 'hasanboy'").fetchone()["c"]
                if has_h == 0:
                    hashed_h = _initial_pin_hash("hasanboy")
                    conn.execute(
                        """
                        INSERT INTO crm_seller_accounts (slug, name, rep_id, phone, tg, role, pin_hash)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        ("hasanboy", "Hasanboy Gaziyev", 9000003, "+998973355900", "@hasan_yahyo", "specialist", hashed_h),
                    )
                else:
                    conn.execute(
                        "UPDATE crm_seller_accounts SET name = 'Hasanboy Gaziyev', phone = '+998973355900', tg = '@hasan_yahyo' WHERE slug = 'hasanboy'"
                    )
                conn.execute(
                    "UPDATE crm_seller_accounts SET tg = '' WHERE tg LIKE '%_jb'"
                )
                conn.commit()

            # Unlock accounts seeded without a PIN once the env value is provided.
            locked = conn.execute(
                "SELECT slug FROM crm_seller_accounts WHERE pin_hash = ?", (LOCKED_PIN_HASH,)
            ).fetchall()
            for row in locked:
                env_pin = os.getenv(_initial_pin_env_name(row["slug"]), "").strip()
                if len(env_pin) >= MIN_PIN_LENGTH:
                    conn.execute(
                        "UPDATE crm_seller_accounts SET pin_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE slug = ?",
                        (_hash_pin(env_pin), row["slug"]),
                    )
            conn.commit()

    def list_public_sellers(self) -> List[Dict[str, Any]]:
        """Kirish ekrani uchun sotuvchilar ro'yxati (PIN-kodlar mutlaqo berilmaydi)."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT slug, name, rep_id, phone, tg, role FROM crm_seller_accounts ORDER BY rep_id ASC"
            ).fetchall()
            return [dict(r) for r in rows]

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
            must_change_pin = len(clean_pin) < STRONG_PIN_MIN_LENGTH

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

    def change_seller_pin(self, slug: str, old_pin: str, new_pin: str) -> bool:
        """Sotuvchi o'z PIN-kodini yangilashi."""
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

            new_hash = _hash_pin(clean_new)
            conn.execute(
                "UPDATE crm_seller_accounts SET pin_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE slug = ?",
                (new_hash, clean_slug),
            )
            conn.execute(
                "UPDATE crm_seller_sessions SET must_change_pin = 0 WHERE seller_slug = ?",
                (clean_slug,),
            )
            conn.commit()
            return True


# Global xizmat nusxasi
seller_auth_service = SellerAuthService()


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
