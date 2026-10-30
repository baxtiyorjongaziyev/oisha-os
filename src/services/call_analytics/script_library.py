"""Transactional, versioned script examples grouped by call purpose and service."""
from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import time

DEFAULT_LIBRARY = Path("data/winning_sales_scripts.sqlite3")
MIN_WON_LEADS = 3
EVIDENCE_TTL = 86400


class ScriptLibrary:
    def __init__(self, path: Path = DEFAULT_LIBRARY):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS samples (
                    call_id TEXT PRIMARY KEY, lead_id INTEGER NOT NULL,
                    group_key TEXT NOT NULL, score REAL NOT NULL,
                    occurred_at INTEGER NOT NULL, examples TEXT NOT NULL,
                    won INTEGER DEFAULT 0, checked_at INTEGER DEFAULT 0,
                    attempted_at INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS versions (
                    id INTEGER PRIMARY KEY, group_key TEXT NOT NULL,
                    digest TEXT NOT NULL, content TEXT NOT NULL, created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS active (
                    group_key TEXT PRIMARY KEY, version_id INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS history_imports (
                    call_id TEXT PRIMARY KEY, attempted_at INTEGER NOT NULL, complete INTEGER NOT NULL
                );
            """)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(samples)")}
            if "attempted_at" not in columns:
                conn.execute("ALTER TABLE samples ADD COLUMN attempted_at INTEGER DEFAULT 0")
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def capture(self, sample: dict) -> bool:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO samples "
                "(call_id, lead_id, group_key, score, occurred_at, examples) VALUES (?, ?, ?, ?, ?, ?)",
                (sample["call_id"], sample["lead_id"], sample["group_key"], sample["score"],
                 sample["occurred_at"], json.dumps(sample["examples"], ensure_ascii=False)),
            )
            return cur.rowcount == 1

    def next_leads(self, limit: int = 20, due_before: int | None = None) -> list[int]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT lead_id FROM samples GROUP BY lead_id HAVING MIN(attempted_at) <= ? "
                "ORDER BY MIN(attempted_at), lead_id LIMIT ?",
                (int(time.time()) if due_before is None else due_before, max(1, min(limit, 100))),
            ).fetchall()
            return [row["lead_id"] for row in rows]

    def samples_for_lead(self, lead_id: int) -> list[dict]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM samples WHERE lead_id = ?", (lead_id,))]

    def verify(self, call_id: str, won: bool, checked_at: int) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE samples SET won = ?, checked_at = ?, attempted_at = ? WHERE call_id = ?",
                         (int(won), checked_at, checked_at, call_id))

    def mark_attempt(self, lead_id: int, now: int) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE samples SET attempted_at = ? WHERE lead_id = ?", (now, lead_id))

    def rebuild(self, now: int | None = None) -> int:
        """One sample per distinct won lead; append a version only on change."""
        now = int(time.time()) if now is None else now
        changed = 0
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            groups = conn.execute("SELECT DISTINCT group_key FROM samples").fetchall()
            for group in groups:
                key = group["group_key"]
                rows = conn.execute(
                    "SELECT * FROM samples WHERE group_key = ? AND won = 1 AND checked_at >= ? "
                    "ORDER BY score DESC, call_id", (key, now - EVIDENCE_TTL),
                ).fetchall()
                chosen = {}
                for row in rows:
                    chosen.setdefault(row["lead_id"], dict(row))
                if len(chosen) < MIN_WON_LEADS:
                    conn.execute("DELETE FROM active WHERE group_key = ?", (key,))
                    continue
                changed += self._publish(conn, key, self._content(key, list(chosen.values())[:10]), now)
        return changed

    @staticmethod
    def _content(key: str, rows: list[dict]) -> dict:
        return {
            "group": key, "evidence_source": "amocrm_closed_won",
            "payment_verified": False, "distinct_won_leads": len(rows),
            "examples": [
                {"call_id": r["call_id"], "lead_id": r["lead_id"], "score": r["score"],
                 "phrases": json.loads(r["examples"])} for r in rows
            ],
            "usage": "Private coaching examples; adapt to context. Correlation is not causal proof.",
        }

    @staticmethod
    def _publish(conn, key: str, content: dict, now: int) -> int:
        raw = json.dumps(content, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(raw.encode()).hexdigest()
        previous = conn.execute(
            "SELECT v.digest FROM versions v JOIN active a ON a.version_id = v.id WHERE a.group_key = ?",
            (key,),
        ).fetchone()
        if previous and previous["digest"] == digest:
            return 0
        cur = conn.execute("INSERT INTO versions (group_key, digest, content, created_at) VALUES (?, ?, ?, ?)",
                           (key, digest, raw, now))
        conn.execute("INSERT OR REPLACE INTO active VALUES (?, ?)", (key, cur.lastrowid))
        return 1

    def current(self, now: int | None = None) -> list[dict]:
        now = int(time.time()) if now is None else now
        self.rebuild(now)
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT v.* FROM versions v JOIN active a ON a.version_id = v.id ORDER BY a.group_key"
            ).fetchall()
            return [{"version": r["id"], **json.loads(r["content"])} for r in rows]

    def history(self, group: str) -> list[dict]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT id, digest, created_at FROM versions WHERE group_key = ? ORDER BY id", (group,),
            )]

    def history_due(self, call_id: str, now: int) -> bool:
        with self.connect() as conn:
            if conn.execute("SELECT 1 FROM samples WHERE call_id = ?", (call_id,)).fetchone():
                return False
            row = conn.execute("SELECT * FROM history_imports WHERE call_id = ?", (call_id,)).fetchone()
            return row is None or (not row["complete"] and row["attempted_at"] <= now - 3600)

    def mark_history(self, call_id: str, now: int, complete: bool) -> None:
        with self.connect() as conn:
            conn.execute("INSERT OR REPLACE INTO history_imports VALUES (?, ?, ?)", (call_id, now, int(complete)))
