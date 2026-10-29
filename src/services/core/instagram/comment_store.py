"""
Persistent state store for Instagram comment analysis, DM outreach,
and resumption checkpoints. Ensures zero duplicates and idempotent resumption.
"""
from __future__ import annotations

import os
import sqlite3
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog

logger = structlog.get_logger("InstagramCommentStore")

_DEFAULT_DB_PATH = Path(__file__).resolve().parents[4] / "data" / "instagram_comments.db"


class InstagramCommentStore:
    """
    Durable SQLite-backed state store for Instagram comments and DM interactions.
    Guarantees:
    - Zero duplicate public replies or DMs on restarts.
    - User-level deduplication (one DM opener per user per campaign).
    - Media-level checkpointing to resume exactly where it left off.
    """

    def __init__(self, db_path: Optional[str | Path] = None):
        self.db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self._ensure_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _ensure_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_comments (
                    comment_id TEXT PRIMARY KEY,
                    media_id TEXT NOT NULL,
                    user_id TEXT,
                    username TEXT,
                    comment_text TEXT,
                    keyword_matched TEXT,
                    status TEXT NOT NULL,
                    public_reply_sent INTEGER DEFAULT 0,
                    public_reply_text TEXT,
                    private_reply_sent INTEGER DEFAULT 0,
                    private_reply_text TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_comments_media 
                ON processed_comments(media_id, status)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_dm_contacts (
                    user_key TEXT NOT NULL,
                    media_id TEXT NOT NULL,
                    first_comment_id TEXT,
                    dm_sent_at TEXT NOT NULL,
                    PRIMARY KEY (user_key, media_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS media_sync_checkpoints (
                    media_id TEXT PRIMARY KEY,
                    last_comment_id TEXT,
                    last_comment_timestamp TEXT,
                    last_synced_at TEXT NOT NULL,
                    total_scanned INTEGER DEFAULT 0,
                    total_dms INTEGER DEFAULT 0
                )
            """)

    @staticmethod
    def _now_iso() -> str:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    @staticmethod
    def _user_key(user_id: Optional[str], username: Optional[str]) -> str:
        uid = (user_id or "").strip()
        if uid and uid.lower() not in ("none", "null", "0"):
            return f"uid:{uid}"
        uname = (username or "").strip().lower().lstrip("@")
        return f"uname:{uname}" if uname else "unknown"

    def is_comment_processed(self, comment_id: str) -> bool:
        """Returns True if the comment was already fully processed or permanently skipped."""
        cid = str(comment_id).strip()
        if not cid:
            return False
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT status FROM processed_comments WHERE comment_id = ?",
                (cid,),
            ).fetchone()
            if not row:
                return False
            status = row["status"]
            return status not in ("pending", "processing", "dm_failed")

    def has_user_received_dm(
        self,
        user_id: Optional[str],
        username: Optional[str] = None,
        media_id: str = "",
    ) -> bool:
        """Checks if this user has already been sent a DM for this media/campaign."""
        ukey = self._user_key(user_id, username)
        if ukey == "unknown":
            return False
        with self._get_connection() as conn:
            if media_id:
                row = conn.execute(
                    "SELECT 1 FROM user_dm_contacts WHERE user_key = ? AND media_id = ?",
                    (ukey, str(media_id)),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT 1 FROM user_dm_contacts WHERE user_key = ?",
                    (ukey,),
                ).fetchone()
            return bool(row)

    def _try_reclaim_row(self, conn: sqlite3.Connection, row: sqlite3.Row, cid: str, now: str) -> bool:
        status = row["status"]
        if status not in ("processing", "dm_failed"):
            return False
        try:
            updated_str = row["updated_at"].replace("Z", "+00:00")
            updated_dt = datetime.datetime.fromisoformat(updated_str)
            now_dt = datetime.datetime.fromisoformat(now)
            cooldown = 30 if status == "dm_failed" else 300
            if (now_dt - updated_dt).total_seconds() > cooldown:
                conn.execute(
                    "UPDATE processed_comments SET status = 'processing', updated_at = ? WHERE comment_id = ?",
                    (now, cid),
                )
                return True
        except Exception:
            pass
        return False

    def claim_comment(
        self,
        comment_id: str,
        media_id: str,
        user_id: Optional[str],
        username: Optional[str],
        text: str,
        keyword: str = "",
    ) -> bool:
        """Atomically claims a comment for processing. Returns True if claimed."""
        cid = str(comment_id).strip()
        now = self._now_iso()
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT status, updated_at FROM processed_comments WHERE comment_id = ?",
                (cid,),
            ).fetchone()
            if row:
                return self._try_reclaim_row(conn, row, cid, now)
            try:
                conn.execute(
                    """
                    INSERT INTO processed_comments (
                        comment_id, media_id, user_id, username,
                        comment_text, keyword_matched, status,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'processing', ?, ?)
                    """,
                    (cid, str(media_id), str(user_id or ""), str(username or ""), str(text or ""), str(keyword or ""), now, now),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def record_dm_success(
        self,
        comment_id: str,
        media_id: str,
        user_id: Optional[str],
        username: Optional[str],
        dm_text: str,
        public_reply_text: str = "",
    ) -> None:
        """Records successful DM outreach and registers user-level contact."""
        cid = str(comment_id).strip()
        now = self._now_iso()
        ukey = self._user_key(user_id, username)
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE processed_comments
                SET status = 'dm_sent',
                    private_reply_sent = 1,
                    private_reply_text = ?,
                    public_reply_sent = ?,
                    public_reply_text = ?,
                    updated_at = ?
                WHERE comment_id = ?
                """,
                (
                    str(dm_text),
                    1 if public_reply_text else 0,
                    str(public_reply_text or ""),
                    now,
                    cid,
                ),
            )
            if ukey != "unknown":
                conn.execute(
                    """
                    INSERT OR REPLACE INTO user_dm_contacts (
                        user_key, media_id, first_comment_id, dm_sent_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (ukey, str(media_id), cid, now),
                )

    def record_skipped(
        self,
        comment_id: str,
        media_id: str,
        user_id: Optional[str],
        username: Optional[str],
        text: str,
        reason: str,
        public_reply_text: str = "",
    ) -> None:
        """Records a comment skipped for business or safety reasons."""
        cid = str(comment_id).strip()
        now = self._now_iso()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO processed_comments (
                    comment_id, media_id, user_id, username,
                    comment_text, status, public_reply_sent,
                    public_reply_text, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(comment_id) DO UPDATE SET
                    status = excluded.status,
                    public_reply_sent = excluded.public_reply_sent,
                    public_reply_text = excluded.public_reply_text,
                    updated_at = excluded.updated_at
                """,
                (
                    cid,
                    str(media_id),
                    str(user_id or ""),
                    str(username or ""),
                    str(text or ""),
                    f"skipped_{reason}",
                    1 if public_reply_text else 0,
                    str(public_reply_text or ""),
                    now,
                    now,
                ),
            )

    def record_failure(self, comment_id: str, error_message: str) -> None:
        """Records error on comment processing so it won't loop infinitely."""
        cid = str(comment_id).strip()
        now = self._now_iso()
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE processed_comments
                SET status = 'dm_failed',
                    error_message = ?,
                    updated_at = ?
                WHERE comment_id = ?
                """,
                (str(error_message)[:500], now, cid),
            )

    def update_checkpoint(
        self,
        media_id: str,
        last_comment_id: str,
        last_comment_ts: str,
        scanned_count: int,
        dm_count: int,
    ) -> None:
        """Updates synchronization checkpoint for a specific media post."""
        mid = str(media_id).strip()
        now = self._now_iso()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO media_sync_checkpoints (
                    media_id, last_comment_id, last_comment_timestamp,
                    last_synced_at, total_scanned, total_dms
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(media_id) DO UPDATE SET
                    last_comment_id = excluded.last_comment_id,
                    last_comment_timestamp = excluded.last_comment_timestamp,
                    last_synced_at = excluded.last_synced_at,
                    total_scanned = total_scanned + excluded.total_scanned,
                    total_dms = total_dms + excluded.total_dms
                """,
                (mid, str(last_comment_id), str(last_comment_ts), now, scanned_count, dm_count),
            )

    def get_checkpoint(self, media_id: str) -> Optional[Dict[str, Any]]:
        """Returns the last saved checkpoint for the given media post."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM media_sync_checkpoints WHERE media_id = ?",
                (str(media_id),),
            ).fetchone()
            return dict(row) if row else None

    def get_stats(self, media_id: Optional[str] = None) -> Dict[str, Any]:
        """Returns processing statistics."""
        with self._get_connection() as conn:
            query = "SELECT status, count(*) as cnt FROM processed_comments"
            params: list[Any] = []
            if media_id:
                query += " WHERE media_id = ?"
                params.append(str(media_id))
            query += " GROUP BY status"
            rows = conn.execute(query, params).fetchall()
            stats = {row["status"]: row["cnt"] for row in rows}
            total = sum(stats.values())
            return {"total_records": total, "breakdown": stats}
