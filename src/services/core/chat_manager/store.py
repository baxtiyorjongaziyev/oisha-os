"""Dialoglar, xabarlar, zayavkalar va agent sozlamalari — lokal SQLite.

`web_auth_store` kabi alohida fayl (`data/chat_manager.db`): Turso uzilsa ham
kiruvchi xabarlar yo'qolmaydi. Funksiyalar sinxron; async koddan
`asyncio.to_thread` orqali chaqiriladi. Yo'l `OISHA_CHAT_DB_PATH` bilan
almashtiriladi (testlar uchun).
"""
from __future__ import annotations

import json
import os
import pathlib
import sqlite3
import time
from typing import Any, Dict, List, Optional

CHANNELS = ("telegram", "instagram")
MODES = ("ai", "operator")
REQUEST_CATEGORIES = {
    "lead": "Zayavka",
    "interested": "Qiziqqan mijoz",
    "complaint": "E'tiroz va shikoyat",
    "suggestion": "Taklif",
}
REQUEST_STATUSES = ("open", "taken", "done")

# docs/reveo-clone-spec.md 3.5 — panel "Sozlamalar → Agent" maydonlari.
DEFAULT_SETTINGS: Dict[str, Any] = {
    "auto_reply": False,
    "messages_per_reply": 1,
    "pause_before_reply_sec": 3,
    "pause_between_messages_sec": 0.7,
    "video_analysis": False,
    "follow_ups": False,
    "language": "uz",
    "agent_type": "balanced",
    "informativeness": 3,
    "reply_length": 3,
    "sales_goal": (
        "Lidni malakalash, savollarga javob berish va qiziqqan mijozni keyingi "
        "foydali qadamga olib borish."
    ),
    "offer_rules": (
        "Narx, kafolat, chegirma, muddat yoki to'lov shartini o'ylab topma. "
        "Javob joriy biznes ma'lumotiga bog'liq bo'lsa, menejerdan tasdiq so'ra."
    ),
    "qualification": (
        "Bir vaqtda bitta savol ber: ehtiyoj, muddat, byudjet, joylashuv yoki kontakt."
    ),
    "handoff": (
        "Mijoz odam, to'lov, shartnoma so'rasa yoki ma'lum faktlardan tashqari "
        "savol bersa — menejerga ber."
    ),
    "tone": "Do'stona, qisqa, hurmat bilan (siz).",
}
_SETTING_LIMITS = {
    "messages_per_reply": (1, 3),
    "pause_before_reply_sec": (0, 60),
    "pause_between_messages_sec": (0, 10),
    "informativeness": (1, 5),
    "reply_length": (1, 5),
}


def _db_path() -> pathlib.Path:
    return pathlib.Path(os.getenv("OISHA_CHAT_DB_PATH", "data/chat_manager.db"))


def _conn() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS dialogs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT NOT NULL,
            external_id TEXT NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            mode TEXT NOT NULL DEFAULT 'ai',
            starred INTEGER NOT NULL DEFAULT 0,
            unread INTEGER NOT NULL DEFAULT 0,
            last_text TEXT NOT NULL DEFAULT '',
            last_direction TEXT NOT NULL DEFAULT 'in',
            last_at REAL NOT NULL,
            extracted_at REAL NOT NULL DEFAULT 0,
            UNIQUE(channel, external_id)
        );
        CREATE TABLE IF NOT EXISTS dialog_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dialog_id INTEGER NOT NULL,
            direction TEXT NOT NULL,
            author TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_dialog_messages_dialog
            ON dialog_messages(dialog_id, created_at);
        CREATE TABLE IF NOT EXISTS chat_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dialog_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            summary TEXT NOT NULL,
            phone TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'open',
            amocrm_lead_id INTEGER,
            created_at REAL NOT NULL,
            UNIQUE(dialog_id, category)
        );
        CREATE TABLE IF NOT EXISTS agent_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            data TEXT NOT NULL,
            updated_at REAL NOT NULL
        );
        """
    )
    return conn


def _row(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    return dict(row) if row is not None else None


def record_message(
    channel: str,
    external_id: str,
    text: str,
    *,
    direction: str = "in",
    author: str = "client",
    name: str = "",
    phone: str = "",
    now: Optional[float] = None,
) -> int:
    """Xabarni saqlaydi va dialog id'sini qaytaradi.

    direction: "in" (mijoz) yoki "out" (AI qoralama / operator).
    author: "client", "ai_draft", "operator".
    """
    if channel not in CHANNELS:
        raise ValueError(f"unknown channel: {channel}")
    text = (text or "").strip()
    if not text:
        raise ValueError("empty message")
    ts = now if now is not None else time.time()
    unread_inc = 1 if direction == "in" else 0
    # AI qoralamasi mijozga ketmaydi — dialog hali "javob kutmoqda" bo'lib qoladi.
    state_direction = "in" if author == "ai_draft" else direction
    with _conn() as c:
        c.execute(
            """
            INSERT INTO dialogs (channel, external_id, name, phone, last_text,
                                 last_direction, last_at, unread)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(channel, external_id) DO UPDATE SET
                name = CASE WHEN excluded.name != '' THEN excluded.name ELSE dialogs.name END,
                phone = CASE WHEN excluded.phone != '' THEN excluded.phone ELSE dialogs.phone END,
                last_text = excluded.last_text,
                last_direction = excluded.last_direction,
                last_at = excluded.last_at,
                unread = dialogs.unread + ?
            """,
            (channel, str(external_id), name or "", phone or "", text[:300],
             state_direction, ts, unread_inc, unread_inc),
        )
        dialog_id = c.execute(
            "SELECT id FROM dialogs WHERE channel = ? AND external_id = ?",
            (channel, str(external_id)),
        ).fetchone()["id"]
        c.execute(
            "INSERT INTO dialog_messages (dialog_id, direction, author, text, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (dialog_id, direction, author, text[:4000], ts),
        )
    return int(dialog_id)


_FILTERS = {
    "all": "",
    "waiting": "AND last_direction = 'in'",
    "operator": "AND mode = 'operator'",
    "unread": "AND unread > 0",
}


def list_dialogs(
    *, filter_key: str = "all", query: str = "", limit: int = 100
) -> List[Dict[str, Any]]:
    clause = _FILTERS.get(filter_key)
    if clause is None:
        raise ValueError(f"unknown filter: {filter_key}")
    params: List[Any] = []
    if query.strip():
        clause += " AND (name LIKE ? OR last_text LIKE ? OR phone LIKE ?)"
        like = f"%{query.strip()}%"
        params += [like, like, like]
    params.append(max(1, min(limit, 500)))
    with _conn() as c:
        rows = c.execute(
            f"SELECT * FROM dialogs WHERE 1=1 {clause} ORDER BY last_at DESC LIMIT ?",  # nosec B608
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def dialog_counts() -> Dict[str, int]:
    with _conn() as c:
        return {
            key: c.execute(
                f"SELECT COUNT(*) FROM dialogs WHERE 1=1 {clause}"  # nosec B608
            ).fetchone()[0]
            for key, clause in _FILTERS.items()
        }


def get_dialog(dialog_id: int) -> Optional[Dict[str, Any]]:
    with _conn() as c:
        return _row(c.execute("SELECT * FROM dialogs WHERE id = ?", (dialog_id,)).fetchone())


def get_messages(dialog_id: int, limit: int = 200) -> List[Dict[str, Any]]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM (SELECT * FROM dialog_messages WHERE dialog_id = ? "
            "ORDER BY created_at DESC, id DESC LIMIT ?) ORDER BY created_at, id",
            (dialog_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_read(dialog_id: int) -> None:
    with _conn() as c:
        c.execute("UPDATE dialogs SET unread = 0 WHERE id = ?", (dialog_id,))


def set_mode(dialog_id: int, mode: str) -> bool:
    if mode not in MODES:
        raise ValueError(f"unknown mode: {mode}")
    with _conn() as c:
        cur = c.execute("UPDATE dialogs SET mode = ? WHERE id = ?", (mode, dialog_id))
        return cur.rowcount > 0


def set_starred(dialog_id: int, starred: bool) -> bool:
    with _conn() as c:
        cur = c.execute(
            "UPDATE dialogs SET starred = ? WHERE id = ?", (int(starred), dialog_id)
        )
        return cur.rowcount > 0


def dialogs_needing_extraction(min_idle_sec: float = 300, now: Optional[float] = None,
                               limit: int = 20) -> List[Dict[str, Any]]:
    """Yangi mijoz xabari bor va kamida `min_idle_sec` jim turgan dialoglar."""
    ts = now if now is not None else time.time()
    with _conn() as c:
        rows = c.execute(
            """
            SELECT d.* FROM dialogs d
            WHERE d.last_at <= ?
              AND EXISTS (SELECT 1 FROM dialog_messages m WHERE m.dialog_id = d.id
                          AND m.direction = 'in' AND m.created_at > d.extracted_at)
            ORDER BY d.last_at LIMIT ?
            """,
            (ts - min_idle_sec, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_extracted(dialog_id: int, now: Optional[float] = None) -> None:
    with _conn() as c:
        c.execute(
            "UPDATE dialogs SET extracted_at = ? WHERE id = ?",
            (now if now is not None else time.time(), dialog_id),
        )


def upsert_request(dialog_id: int, category: str, summary: str, phone: str = "",
                   now: Optional[float] = None) -> tuple[int, bool]:
    """(request_id, yangi_mi). Bir dialogda bir kategoriya — bitta zayavka."""
    if category not in REQUEST_CATEGORIES:
        raise ValueError(f"unknown category: {category}")
    ts = now if now is not None else time.time()
    with _conn() as c:
        existing = c.execute(
            "SELECT id FROM chat_requests WHERE dialog_id = ? AND category = ?",
            (dialog_id, category),
        ).fetchone()
        if existing:
            c.execute(
                "UPDATE chat_requests SET summary = ?, "
                "phone = CASE WHEN ? != '' THEN ? ELSE phone END WHERE id = ?",
                (summary[:500], phone, phone, existing["id"]),
            )
            return int(existing["id"]), False
        cur = c.execute(
            "INSERT INTO chat_requests (dialog_id, category, summary, phone, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (dialog_id, category, summary[:500], phone, ts),
        )
        return int(cur.lastrowid), True


def set_request_lead(request_id: int, lead_id: int) -> None:
    with _conn() as c:
        c.execute(
            "UPDATE chat_requests SET amocrm_lead_id = ? WHERE id = ?", (lead_id, request_id)
        )


def list_requests(dialog_id: Optional[int] = None) -> List[Dict[str, Any]]:
    sql = (
        "SELECT r.*, d.name, d.channel FROM chat_requests r "
        "JOIN dialogs d ON d.id = r.dialog_id"
    )
    params: tuple = ()
    if dialog_id is not None:
        sql += " WHERE r.dialog_id = ?"
        params = (dialog_id,)
    with _conn() as c:
        rows = c.execute(sql + " ORDER BY r.created_at DESC", params).fetchall()
    return [dict(r) for r in rows]


def get_settings() -> Dict[str, Any]:
    with _conn() as c:
        row = c.execute("SELECT data FROM agent_settings WHERE id = 1").fetchone()
    stored = json.loads(row["data"]) if row else {}
    return {**DEFAULT_SETTINGS, **{k: v for k, v in stored.items() if k in DEFAULT_SETTINGS}}


def update_settings(changes: Dict[str, Any]) -> Dict[str, Any]:
    unknown = set(changes) - set(DEFAULT_SETTINGS)
    if unknown:
        raise ValueError(f"unknown settings: {sorted(unknown)}")
    merged = get_settings()
    for key, value in changes.items():
        default = DEFAULT_SETTINGS[key]
        if isinstance(default, bool):
            if not isinstance(value, bool):
                raise ValueError(f"{key} must be bool")
        elif isinstance(default, (int, float)):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{key} must be a number")
            low, high = _SETTING_LIMITS[key]
            if not low <= value <= high:
                raise ValueError(f"{key} must be between {low} and {high}")
            value = int(value) if isinstance(default, int) else float(value)
        else:
            if not isinstance(value, str) or len(value) > 2000:
                raise ValueError(f"{key} must be text up to 2000 chars")
            value = value.strip()
        merged[key] = value
    with _conn() as c:
        c.execute(
            "INSERT INTO agent_settings (id, data, updated_at) VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
            (json.dumps(merged, ensure_ascii=False), time.time()),
        )
    return merged
