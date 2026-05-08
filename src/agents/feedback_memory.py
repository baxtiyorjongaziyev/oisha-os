"""
feedback_memory — Persistent per-user conversation history for multi-agent feedback loops.

Stores (message, response, assessment) triples per user in SQLite so
NegotiationEngine always has full context across restarts.

API:
    from src.agents.feedback_memory import FeedbackMemory

    mem = FeedbackMemory(db)
    await mem.append(user_id, role="user", text="Narx necha?", assessment=asmt)
    history = await mem.get(user_id, limit=10)
    await mem.clear(user_id)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Max turns retained per user to bound DB growth
MAX_HISTORY_PER_USER = 50


class FeedbackMemory:
    """SQLite-backed per-user conversation history with assessment metadata."""

    def __init__(self, db: Any):
        self._db = db
        self._ensured = False

    async def _ensure_table(self) -> None:
        if self._ensured:
            return
        try:
            async with self._db.get_conn() as conn:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversation_memory (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id     INTEGER NOT NULL,
                        role        TEXT    NOT NULL CHECK(role IN ('user','assistant')),
                        text        TEXT    NOT NULL,
                        assessment  TEXT,           -- JSON NegotiationAssessment or null
                        created_at  TEXT    DEFAULT (datetime('now'))
                    )
                    """
                )
                await conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_conv_mem_user "
                    "ON conversation_memory(user_id, id DESC)"
                )
                await conn.commit()
            self._ensured = True
        except Exception as exc:
            logger.warning(f"[FeedbackMemory] table init failed: {exc}")

    async def append(
        self,
        user_id: int,
        role: str,
        text: str,
        assessment: Optional[Any] = None,
    ) -> None:
        """Append a turn to the user's history."""
        await self._ensure_table()
        assessment_json: Optional[str] = None
        if assessment is not None:
            try:
                payload = (
                    assessment.to_payload()
                    if hasattr(assessment, "to_payload")
                    else assessment
                )
                assessment_json = json.dumps(payload, ensure_ascii=False)
            except Exception:
                pass
        try:
            async with self._db.get_conn() as conn:
                await conn.execute(
                    """
                    INSERT INTO conversation_memory (user_id, role, text, assessment)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_id, role, text, assessment_json),
                )
                # Trim oldest rows beyond MAX_HISTORY_PER_USER
                await conn.execute(
                    """
                    DELETE FROM conversation_memory
                    WHERE user_id = ?
                      AND id NOT IN (
                          SELECT id FROM conversation_memory
                          WHERE user_id = ?
                          ORDER BY id DESC
                          LIMIT ?
                      )
                    """,
                    (user_id, user_id, MAX_HISTORY_PER_USER),
                )
                await conn.commit()
        except Exception as exc:
            logger.debug(f"[FeedbackMemory] append failed (non-fatal): {exc}")

    async def get(
        self,
        user_id: int,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Return the last `limit` turns for the user, oldest first."""
        await self._ensure_table()
        try:
            async with self._db.get_conn() as conn:
                cursor = await conn.execute(
                    """
                    SELECT role, text, assessment, created_at
                    FROM (
                        SELECT role, text, assessment, created_at, id
                        FROM conversation_memory
                        WHERE user_id = ?
                        ORDER BY id DESC
                        LIMIT ?
                    ) ORDER BY id ASC
                    """,
                    (user_id, limit),
                )
                rows = await cursor.fetchall()
        except Exception as exc:
            logger.debug(f"[FeedbackMemory] get failed (non-fatal): {exc}")
            return []

        result = []
        for role, text, assessment_json, created_at in rows:
            entry: Dict[str, Any] = {
                "role": role,
                "text": text,
                "created_at": created_at,
            }
            if assessment_json:
                try:
                    entry["assessment"] = json.loads(assessment_json)
                except Exception:
                    pass
            result.append(entry)
        return result

    async def get_as_negotiation_history(
        self, user_id: int, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Return history in the format NegotiationEngine.assess_async expects."""
        raw = await self.get(user_id, limit=limit)
        return [{"role": r["role"], "content": r["text"]} for r in raw]

    async def clear(self, user_id: int) -> None:
        """Delete all history for a user (e.g. after CLOSED_WON)."""
        await self._ensure_table()
        try:
            async with self._db.get_conn() as conn:
                await conn.execute(
                    "DELETE FROM conversation_memory WHERE user_id = ?", (user_id,)
                )
                await conn.commit()
        except Exception as exc:
            logger.debug(f"[FeedbackMemory] clear failed (non-fatal): {exc}")

    async def get_last_assessment(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Return the most recent assessment dict for the user, or None."""
        await self._ensure_table()
        try:
            async with self._db.get_conn() as conn:
                cursor = await conn.execute(
                    """
                    SELECT assessment FROM conversation_memory
                    WHERE user_id = ? AND assessment IS NOT NULL
                    ORDER BY id DESC LIMIT 1
                    """,
                    (user_id,),
                )
                row = await cursor.fetchone()
                if row and row[0]:
                    return json.loads(row[0])
        except Exception as exc:
            logger.debug(f"[FeedbackMemory] get_last_assessment failed: {exc}")
        return None
