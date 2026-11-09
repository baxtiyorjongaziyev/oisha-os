"""Seed data, PIN hashing and login throttling for CRM seller accounts."""
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

logger = logging.getLogger(__name__)

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


def create_seller_schema(conn: sqlite3.Connection) -> None:
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
    account_cols = {r["name"] for r in conn.execute("PRAGMA table_info(crm_seller_accounts)")}
    if "must_change_pin" not in account_cols:
        conn.execute(
            "ALTER TABLE crm_seller_accounts ADD COLUMN must_change_pin INTEGER NOT NULL DEFAULT 0"
        )
    # One-time: sessions opened before weak-PIN enforcement carry no flag, so
    # log everyone out once and let the next login apply the PIN rules.
    if conn.execute("PRAGMA user_version").fetchone()[0] < 1:
        conn.execute("DELETE FROM crm_seller_sessions")
        conn.execute("PRAGMA user_version = 1")


def seed_or_refresh_sellers(conn: sqlite3.Connection) -> None:
    insert_sql = """
        INSERT INTO crm_seller_accounts (slug, name, rep_id, phone, tg, role, pin_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    count = conn.execute("SELECT COUNT(*) as c FROM crm_seller_accounts").fetchone()["c"]
    if count == 0:
        for s in INITIAL_SELLERS:
            conn.execute(
                insert_sql,
                (s["slug"], s["name"], s["rep_id"], s["phone"], s["tg"], s["role"], _initial_pin_hash(s["slug"])),
            )
        return

    # Tasdiqlangan ism, telefon va Telegram maʼlumotlarini yangilash.
    for s in INITIAL_SELLERS:
        conn.execute(
            "UPDATE crm_seller_accounts SET name = ?, phone = ?, tg = ? WHERE slug = ?",
            (s["name"], s["phone"], s["tg"], s["slug"]),
        )
    # Ishdan ketgan xodimlar: akkaunt va sessiyalar oʻchiriladi.
    conn.execute("DELETE FROM crm_seller_sessions WHERE seller_slug IN ('oydin', 'farangiz')")
    conn.execute("DELETE FROM crm_seller_accounts WHERE slug IN ('oydin', 'farangiz')")
    # Hasanboy keyin qoʻshilgan: eski bazada boʻlmasligi mumkin.
    hasanboy = next(s for s in INITIAL_SELLERS if s["slug"] == "hasanboy")
    if not conn.execute("SELECT 1 FROM crm_seller_accounts WHERE slug = 'hasanboy'").fetchone():
        conn.execute(
            insert_sql,
            (
                hasanboy["slug"], hasanboy["name"], hasanboy["rep_id"], hasanboy["phone"],
                hasanboy["tg"], hasanboy["role"], _initial_pin_hash("hasanboy"),
            ),
        )
    conn.execute("UPDATE crm_seller_accounts SET tg = '' WHERE tg LIKE '%_jb'")


def unlock_sellers_from_env(conn: sqlite3.Connection) -> None:
    """Accounts seeded without a PIN unlock once the env value is provided."""
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
