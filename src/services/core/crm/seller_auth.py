"""CRM Seller Authentication & Session Guard for Jon CRM.

Ushbu modul har bir sotuvchi (Shahnoza, Rayxona, Mumtozmaxal, Baxtiyorjon va h.k.)
uchun alohida maxfiy PIN/parollarni PBKDF2-SHA256 xesh orqali xavfsiz saqlaydi
va barcha CRM API larini ruxsatsiz kirishlardan to'liq himoya qiladi (Fail-Closed).
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from typing import Any, Dict, List, Optional
from fastapi import Header, HTTPException, Request

DB_PATH = "data/crm_dialer.db"

# Standart dastlabki xodimlar va ularning boshlang'ich maxfiy PIN kodlari
INITIAL_SELLERS: List[Dict[str, Any]] = [
    {
        "slug": "baxtiyorjon",
        "name": "Baxtiyorjon Gaziyev",
        "rep_id": 8128012,
        "phone": "+998336450097",
        "tg": "@baxtiyorjongaziyev",
        "role": "admin",
        "default_pin": "8128",
    },
    {
        "slug": "shahnoza",
        "name": "Shahnoza Abdijabborova",
        "rep_id": 13021974,
        "phone": "+998773220042",
        "tg": "@jonbranding_assistant",
        "role": "seller",
        "default_pin": "1302",
    },
    {
        "slug": "rayxona",
        "name": "Rayxona Rahimova",
        "rep_id": 9000001,
        "phone": "+998777411397",
        "tg": "@RayxonJonbranding",
        "role": "seller",
        "default_pin": "9001",
    },
    {
        "slug": "mumtozmaxal",
        "name": "Mumtozmaxal Normurodova",
        "rep_id": 9000002,
        "phone": "+998773220098",
        "tg": "@MumtozmaxalJonbranding",
        "role": "seller",
        "default_pin": "9002",
    },
    {
        "slug": "hasanboy",
        "name": "Hasanboy Gaziyev",
        "rep_id": 9000003,
        "phone": "+998973355900",
        "tg": "@hasan_yahyo",
        "role": "specialist",
        "default_pin": "9003",
    },
]


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
            conn.commit()

            # Boshlang'ich sotuvchilarni yuklash
            count = conn.execute("SELECT COUNT(*) as c FROM crm_seller_accounts").fetchone()["c"]
            if count == 0:
                for s in INITIAL_SELLERS:
                    hashed = _hash_pin(s["default_pin"])
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
                    hashed_h = _hash_pin("9003")
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

        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM crm_seller_accounts WHERE slug = ?", (clean_slug,)
            ).fetchone()
            if not row:
                return None

            if not _verify_pin(clean_pin, row["pin_hash"]):
                return None

            # Yangi xavfsiz tasodifiy sessiya tokeni yaratish
            token = secrets.token_urlsafe(32)
            now = time.time()
            expires_at = now + (ttl_days * 86400)

            # Eskirgan sessiyalarni tozalash
            conn.execute("DELETE FROM crm_seller_sessions WHERE expires_at < ?", (now,))
            conn.execute(
                """
                INSERT INTO crm_seller_sessions (token, seller_slug, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (token, clean_slug, now, expires_at),
            )
            conn.commit()

            return {
                "token": token,
                "expires_at": expires_at,
                "seller": {
                    "slug": row["slug"],
                    "name": row["name"],
                    "rep_id": row["rep_id"],
                    "phone": row["phone"],
                    "tg": row["tg"],
                    "role": row["role"],
                },
            }

    def validate_session(self, token: str) -> Optional[Dict[str, Any]]:
        """Sessiya tokenini tekshirish."""
        clean_token = str(token or "").strip()
        if not clean_token:
            return None

        now = time.time()
        with self._get_conn() as conn:
            row = conn.execute(
                """
                SELECT s.slug, s.name, s.rep_id, s.phone, s.tg, s.role, sess.expires_at
                FROM crm_seller_sessions sess
                JOIN crm_seller_accounts s ON s.slug = sess.seller_slug
                WHERE sess.token = ? AND sess.expires_at > ?
                """,
                (clean_token, now),
            ).fetchone()
            if not row:
                return None
            return dict(row)

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
        if len(new_pin or "") < 4:
            return False

        with self._get_conn() as conn:
            row = conn.execute("SELECT pin_hash FROM crm_seller_accounts WHERE slug = ?", (clean_slug,)).fetchone()
            if not row or not _verify_pin(old_pin, row["pin_hash"]):
                return False

            new_hash = _hash_pin(new_pin)
            conn.execute(
                "UPDATE crm_seller_accounts SET pin_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE slug = ?",
                (new_hash, clean_slug),
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
    
    Agar foydalanuvchida yaroqli sessiya cookie yoki Bearer token bo'lmasa,
    darhol 401 Unauthorized qaytariladi va hech qanday ma'lumot berilmaydi!
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
