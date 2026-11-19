"""Oisha Connect jadvallari va DB amallari (Turso/SQLite, ``db_pool`` interfeysi)."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from typing import Any, Optional

from src.services.core.card_watch import vault as _vault

KEY_ENV = "TG_CONNECT_SESSION_KEY"
_SLOT = "tgc"  # vault ichidagi egasi prefiksi: tgc<telegram_id>

DDL = (
    """CREATE TABLE IF NOT EXISTS tg_connect_accounts (
        telegram_id INTEGER PRIMARY KEY,
        employee_id INTEGER,
        tg_username TEXT,
        session_enc TEXT,
        status TEXT NOT NULL DEFAULT 'connected',
        mcp_token_hash TEXT UNIQUE,
        connected_at INTEGER NOT NULL,
        revoked_at INTEGER)""",
    """CREATE TABLE IF NOT EXISTS tg_connect_chats (
        telegram_id INTEGER NOT NULL,
        chat_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        kind TEXT NOT NULL,
        allowed INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (telegram_id, chat_id))""",
    """CREATE TABLE IF NOT EXISTS tg_connect_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        detail TEXT,
        actor TEXT NOT NULL,
        ip TEXT,
        created_at INTEGER NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS idx_tgc_audit_tg ON tg_connect_audit(telegram_id, id)",
)


# Mavjud jadvallarga ustun qoʻshish (idempotent: ustun bor boʻlsa xato eʼtiborsiz).
MIGRATIONS = (
    "ALTER TABLE tg_connect_chats ADD COLUMN autonomous INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE tg_connect_accounts ADD COLUMN all_chats INTEGER NOT NULL DEFAULT 0",
)


async def init_tables(db) -> None:
    for ddl in DDL:
        await db.execute(ddl)
    for ddl in MIGRATIONS:
        try:
            await db.execute(ddl)
        except Exception as exc:  # noqa: BLE001 - "duplicate column" kutilgan holat
            if "duplicate" not in str(exc).lower():
                raise
    from src.services.core.tg_connect.actions import DDL as ACTIONS_DDL

    for ddl in ACTIONS_DDL:
        await db.execute(ddl)
    await db.commit()


def _key() -> str:
    key = os.getenv(KEY_ENV, "").strip()
    if not key:
        raise _vault.SessionVaultError(f"{KEY_ENV} is not set")
    return key


def encrypt_session(telegram_id: int, session: str) -> str:
    return _vault.encrypt(f"{_SLOT}{telegram_id}", session, key=_key())


def decrypt_session(telegram_id: int, stored: str) -> str:
    return _vault.decrypt(f"{_SLOT}{telegram_id}", stored, key=_key())


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def audit(db, telegram_id: int, action: str, actor: str,
                detail: Optional[dict[str, Any]] = None, ip: Optional[str] = None) -> None:
    await db.execute(
        "INSERT INTO tg_connect_audit (telegram_id, action, detail, actor, ip, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        [telegram_id, action, json.dumps(detail or {}, ensure_ascii=False), actor, ip, int(time.time())])
    await db.commit()


async def audit_log(db, telegram_id: int, limit: int = 50) -> list[dict]:
    rows = await db.execute(
        "SELECT action, detail, actor, created_at FROM tg_connect_audit"
        " WHERE telegram_id = ? ORDER BY id DESC LIMIT ?", [telegram_id, limit])
    return [{"action": r["action"], "detail": json.loads(r["detail"] or "{}"),
             "actor": r["actor"], "at": r["created_at"]} for r in rows]


async def account(db, telegram_id: int) -> Optional[dict]:
    rows = await db.execute(
        "SELECT telegram_id, employee_id, tg_username, session_enc, status, connected_at, revoked_at"
        " FROM tg_connect_accounts WHERE telegram_id = ?", [telegram_id])
    return dict(rows[0]) if rows else None


async def save_connected(db, telegram_id: int, employee_id: Optional[int],
                         username: Optional[str], session: str) -> None:
    enc = encrypt_session(telegram_id, session)
    await db.execute(
        "INSERT INTO tg_connect_accounts (telegram_id, employee_id, tg_username, session_enc, status,"
        " connected_at, revoked_at, mcp_token_hash) VALUES (?, ?, ?, ?, 'connected', ?, NULL, NULL)"
        " ON CONFLICT(telegram_id) DO UPDATE SET employee_id = excluded.employee_id,"
        " tg_username = excluded.tg_username, session_enc = excluded.session_enc,"
        " status = 'connected', connected_at = excluded.connected_at, revoked_at = NULL,"
        " mcp_token_hash = NULL",
        [telegram_id, employee_id, username, enc, int(time.time())])
    await db.commit()


async def mark_revoked(db, telegram_id: int) -> None:
    """Sessiya va MCP token butunlay oʻchiriladi; chat tanlovi ham tozalanadi."""
    await db.execute(
        "UPDATE tg_connect_accounts SET status = 'revoked', session_enc = NULL, mcp_token_hash = NULL, all_chats = 0,"
        " revoked_at = ? WHERE telegram_id = ?", [int(time.time()), telegram_id])
    await db.execute("DELETE FROM tg_connect_chats WHERE telegram_id = ?", [telegram_id])
    await db.commit()


async def replace_chats(db, telegram_id: int, chats: list[dict]) -> None:
    """Dialoglar roʻyxatini yangilaydi, oldingi ``allowed`` tanlovini saqlab qoladi."""
    # ``allowed`` hech qachon qayta yozilmaydi: parallel "Saqlash" tanlovi bekor boʻlmasin.
    ids = [int(c["id"]) for c in chats]
    for c in chats:
        await db.execute(
            "INSERT INTO tg_connect_chats (telegram_id, chat_id, title, kind, allowed) VALUES (?, ?, ?, ?, 0)"
            " ON CONFLICT(telegram_id, chat_id) DO UPDATE SET title = excluded.title, kind = excluded.kind",
            [telegram_id, int(c["id"]), str(c["title"])[:200], c["kind"]])
    rows = await db.execute("SELECT chat_id FROM tg_connect_chats WHERE telegram_id = ?", [telegram_id])
    keep = set(ids)
    for r in rows:
        if int(r["chat_id"]) not in keep:
            await db.execute("DELETE FROM tg_connect_chats WHERE telegram_id = ? AND chat_id = ?",
                             [telegram_id, int(r["chat_id"])])
    await db.commit()


async def chats(db, telegram_id: int) -> list[dict]:
    rows = await db.execute(
        "SELECT chat_id, title, kind, allowed, autonomous FROM tg_connect_chats WHERE telegram_id = ?"
        " ORDER BY allowed DESC, title", [telegram_id])
    return [{"id": r["chat_id"], "title": r["title"], "kind": r["kind"], "allowed": bool(r["allowed"]),
             "autonomous": bool(r["autonomous"])} for r in rows]


async def set_autonomous(db, telegram_id: int, chat_ids: list[int]) -> int:
    """AI tasdiqsiz yoza oladigan chatlar (menejer oʻzi belgilaydi)."""
    await db.execute("UPDATE tg_connect_chats SET autonomous = 0 WHERE telegram_id = ?", [telegram_id])
    count = 0
    for cid in chat_ids:
        rows = await db.execute(
            "UPDATE tg_connect_chats SET autonomous = 1 WHERE telegram_id = ? AND chat_id = ? RETURNING chat_id",
            [telegram_id, int(cid)])
        count += len(rows)
    await db.commit()
    return count


async def all_chats(db, telegram_id: int) -> bool:
    rows = await db.execute("SELECT all_chats FROM tg_connect_accounts WHERE telegram_id = ?", [telegram_id])
    return bool(rows and rows[0]["all_chats"])


async def set_all_chats(db, telegram_id: int, on: bool) -> None:
    await db.execute("UPDATE tg_connect_accounts SET all_chats = ? WHERE telegram_id = ?",
                     [int(bool(on)), telegram_id])
    await db.commit()


async def set_allowed(db, telegram_id: int, chat_ids: list[int]) -> int:
    await db.execute("UPDATE tg_connect_chats SET allowed = 0 WHERE telegram_id = ?", [telegram_id])
    count = 0
    for cid in chat_ids:
        rows = await db.execute(
            "UPDATE tg_connect_chats SET allowed = 1 WHERE telegram_id = ? AND chat_id = ? RETURNING chat_id",
            [telegram_id, int(cid)])
        count += len(rows)
    await db.commit()
    return count


async def issue_mcp_token(db, telegram_id: int) -> str:
    """Yangi shaxsiy MCP token (faqat bir marta koʻrsatiladi; DB da faqat hash)."""
    token = "oc_" + secrets.token_urlsafe(32)
    rows = await db.execute(
        "UPDATE tg_connect_accounts SET mcp_token_hash = ? WHERE telegram_id = ? AND status = 'connected'"
        " RETURNING telegram_id", [hash_token(token), telegram_id])
    await db.commit()
    if not rows:
        raise LookupError("not_connected")
    return token


async def account_by_mcp_token(db, token: str) -> Optional[dict]:
    if not token.startswith("oc_"):
        return None
    rows = await db.execute(
        "SELECT telegram_id FROM tg_connect_accounts WHERE mcp_token_hash = ? AND status = 'connected'",
        [hash_token(token)])
    return dict(rows[0]) if rows else None
