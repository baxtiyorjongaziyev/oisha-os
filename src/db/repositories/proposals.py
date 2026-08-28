"""Persistence for Oisha improvement proposals and owner decisions."""

from __future__ import annotations

import datetime
import json
import logging
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

from src.db.repositories.base import BaseRepository

logger = logging.getLogger(__name__)

VALID_STATUSES = {
    "proposed",
    "accepted",
    "queued",
    "in_progress",
    "done",
    "failed",
    "rejected",
    "deferred",
}

ALLOWED_TRANSITIONS = {
    "proposed": {"accepted", "rejected", "deferred"},
    "deferred": {"proposed", "accepted", "rejected"},
    "accepted": {"queued", "in_progress", "deferred", "rejected"},
    "queued": {"in_progress", "failed", "deferred"},
    "in_progress": {"done", "failed", "deferred"},
    "failed": {"accepted", "deferred", "rejected"},
    "done": set(),
    "rejected": set(),
}


class ProposalRepository(BaseRepository):
    """Deduplicated proposal storage with auditable status transitions."""

    def __init__(self, database_or_manager):
        database = (
            database_or_manager
            if hasattr(database_or_manager, "get_connection")
            else None
        )
        conn_manager = getattr(database_or_manager, "conn_manager", database_or_manager)
        super().__init__(conn_manager)
        if database is not None:
            self.set_connection_factory(database.get_connection)

    async def init_table(self) -> None:
        conn = await self._get_conn()
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS improvement_proposals (
                id TEXT PRIMARY KEY,
                fingerprint TEXT,
                category TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                problem TEXT,
                proposed_solution TEXT,
                affected_files TEXT,
                estimated_effort TEXT,
                suggested_agent TEXT,
                evidence TEXT,
                status TEXT DEFAULT 'proposed',
                created_at TEXT,
                first_seen_at TEXT,
                last_seen_at TEXT,
                occurrence_count INTEGER DEFAULT 1,
                deferred_until TEXT,
                resolved_at TEXT,
                resolved_by TEXT,
                rejection_reason TEXT
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS improvement_proposal_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposal_id TEXT NOT NULL,
                old_status TEXT,
                new_status TEXT NOT NULL,
                actor_id TEXT,
                note TEXT,
                created_at TEXT NOT NULL
            )
            """
        )

        # Safe, idempotent migration for the earlier draft schema. CREATE TABLE
        # IF NOT EXISTS is a no-op on an existing table, so a legacy table keeps
        # its old columns and the indexes below fail with "no such column".
        # NOT NULL columns are added nullable here and backfilled after — SQLite
        # rejects ALTER TABLE ADD COLUMN ... NOT NULL without a default.
        existing_columns = await self._get_table_columns("improvement_proposals")
        for column, column_type in (
            ("fingerprint", "TEXT"),
            ("category", "TEXT"),
            ("severity", "TEXT"),
            ("title", "TEXT"),
            ("problem", "TEXT"),
            ("proposed_solution", "TEXT"),
            ("affected_files", "TEXT"),
            ("estimated_effort", "TEXT"),
            ("suggested_agent", "TEXT"),
            ("evidence", "TEXT"),
            ("status", "TEXT DEFAULT 'proposed'"),
            ("created_at", "TEXT"),
            ("first_seen_at", "TEXT"),
            ("last_seen_at", "TEXT"),
            ("occurrence_count", "INTEGER DEFAULT 1"),
            ("deferred_until", "TEXT"),
            ("resolved_at", "TEXT"),
            ("resolved_by", "TEXT"),
            ("rejection_reason", "TEXT"),
        ):
            if column in existing_columns:
                continue
            await self._add_column_if_missing(
                "improvement_proposals", column, column_type
            )

        await conn.execute(
            """
            UPDATE improvement_proposals
            SET category = COALESCE(category, 'unknown'),
                severity = COALESCE(severity, 'medium'),
                title = COALESCE(title, 'Untitled proposal'),
                status = COALESCE(status, 'proposed')
            WHERE category IS NULL
               OR severity IS NULL
               OR title IS NULL
               OR status IS NULL
            """
        )

        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_proposals_status "
            "ON improvement_proposals (status)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_proposals_severity "
            "ON improvement_proposals (severity)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_proposals_fingerprint "
            "ON improvement_proposals (fingerprint)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_proposal_events_proposal "
            "ON improvement_proposal_events (proposal_id, created_at)"
        )
        await conn.execute(
            """
            UPDATE improvement_proposals
            SET first_seen_at = COALESCE(first_seen_at, created_at),
                last_seen_at = COALESCE(last_seen_at, created_at),
                occurrence_count = COALESCE(occurrence_count, 1)
            """
        )
        await conn.commit()
        logger.info("[DB] improvement proposal tables initialized")

    @staticmethod
    def _as_dict(proposal: Any) -> Dict[str, Any]:
        if isinstance(proposal, dict):
            return dict(proposal)
        if hasattr(proposal, "to_dict"):
            return dict(proposal.to_dict())
        if is_dataclass(proposal):
            return asdict(proposal)
        raise TypeError("proposal must be a dict or dataclass-like object")

    @staticmethod
    def _json_value(value: Any, fallback: Any) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(value if value is not None else fallback, ensure_ascii=False)

    @classmethod
    def _values(cls, proposal: Any, now: str) -> tuple:
        data = cls._as_dict(proposal)
        proposal_id = str(data.get("id") or "").strip()
        if not proposal_id:
            raise ValueError("proposal id is required")
        status = str(data.get("status") or "proposed")
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid proposal status: {status}")
        created_at = str(data.get("created_at") or now)
        fingerprint = str(data.get("fingerprint") or proposal_id.removeprefix("DIAG-"))
        return (
            proposal_id,
            fingerprint,
            str(data.get("category") or "unknown"),
            str(data.get("severity") or "medium"),
            str(data.get("title") or "Nomsiz taklif"),
            str(data.get("problem") or ""),
            str(data.get("proposed_solution") or ""),
            cls._json_value(data.get("affected_files"), []),
            str(data.get("estimated_effort") or "1h"),
            str(data.get("suggested_agent") or "Coordinator"),
            cls._json_value(data.get("evidence"), {}),
            status,
            created_at,
            created_at,
            now,
            data.get("deferred_until"),
            data.get("resolved_at"),
            data.get("resolved_by"),
            data.get("rejection_reason"),
        )

    async def save_proposal(self, proposal: Any) -> None:
        await self.save_proposals([proposal])

    async def save_proposals(self, proposals: Iterable[Any]) -> None:
        """Persist one diagnosis atomically while preserving owner decisions."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        values = [self._values(proposal, now) for proposal in proposals]
        if not values:
            return

        conn = await self._get_conn()
        sql = """
            INSERT INTO improvement_proposals
            (id, fingerprint, category, severity, title, problem,
             proposed_solution, affected_files, estimated_effort,
             suggested_agent, evidence, status, created_at, first_seen_at,
             last_seen_at, occurrence_count, deferred_until, resolved_at,
             resolved_by, rejection_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                fingerprint = excluded.fingerprint,
                category = excluded.category,
                severity = excluded.severity,
                title = excluded.title,
                problem = excluded.problem,
                proposed_solution = excluded.proposed_solution,
                affected_files = excluded.affected_files,
                estimated_effort = excluded.estimated_effort,
                suggested_agent = excluded.suggested_agent,
                evidence = excluded.evidence,
                last_seen_at = excluded.last_seen_at,
                occurrence_count = improvement_proposals.occurrence_count + 1
        """
        try:
            for item in values:
                await conn.execute(sql, item)
            await conn.commit()
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            rollback = getattr(conn, "rollback", None)
            if rollback is not None:
                await rollback()
            raise

    async def get_proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        row = await self._fetch_one(
            "SELECT * FROM improvement_proposals WHERE id = ?", (proposal_id,)
        )
        return self._deserialize(row) if row else None

    async def get_proposals(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        statuses: Optional[Sequence[str]] = None,
        actionable_only: bool = False,
    ) -> List[Dict[str, Any]]:
        conditions: List[str] = []
        params: List[Any] = []
        selected_statuses = list(statuses or ([] if status is None else [status]))
        for candidate in selected_statuses:
            if candidate not in VALID_STATUSES:
                raise ValueError(f"invalid proposal status: {candidate}")
        if selected_statuses:
            placeholders = ",".join("?" for _ in selected_statuses)
            conditions.append(f"status IN ({placeholders})")
            params.extend(selected_statuses)
        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        if actionable_only:
            conditions.append(
                "(status != 'deferred' OR deferred_until IS NULL OR deferred_until <= ?)"
            )
            params.append(datetime.datetime.now(datetime.timezone.utc).isoformat())

        query = "SELECT * FROM improvement_proposals"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += (
            " ORDER BY CASE severity "
            "WHEN 'critical' THEN 0 WHEN 'high' THEN 1 "
            "WHEN 'medium' THEN 2 ELSE 3 END, last_seen_at DESC LIMIT ?"
        )
        params.append(max(1, min(int(limit), 200)))
        rows = await self._fetch_all(query, tuple(params))
        return [self._deserialize(row) for row in rows]

    async def update_proposal_status(
        self,
        proposal_id: str,
        status: str,
        resolved_by: Optional[str] = None,
        rejection_reason: Optional[str] = None,
        deferred_until: Optional[str] = None,
        note: Optional[str] = None,
    ) -> bool:
        """Apply an atomic, single-use workflow transition and audit it."""
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid proposal status: {status}")
        current = await self.get_proposal(proposal_id)
        if not current:
            return False
        old_status = str(current.get("status") or "proposed")
        if status == old_status or status not in ALLOWED_TRANSITIONS.get(
            old_status, set()
        ):
            return False

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        terminal = status in {"done", "rejected"}
        conn = await self._get_conn()
        cursor = await conn.execute(
            """
            UPDATE improvement_proposals
            SET status = ?, deferred_until = ?,
                resolved_at = ?, resolved_by = ?, rejection_reason = ?
            WHERE id = ? AND status = ?
            """,
            (
                status,
                deferred_until if status == "deferred" else None,
                now if terminal else None,
                resolved_by,
                rejection_reason,
                proposal_id,
                old_status,
            ),
        )
        rowcount = getattr(cursor, "rowcount", None)
        if rowcount in (None, -1):
            changes_cursor = await conn.execute("SELECT changes()")
            changes_row = await changes_cursor.fetchone()
            if isinstance(changes_row, dict):
                rowcount = int(next(iter(changes_row.values()), 0) or 0)
            else:
                rowcount = int(changes_row[0] if changes_row else 0)
        if int(rowcount or 0) == 0:
            rollback = getattr(conn, "rollback", None)
            if rollback is not None:
                await rollback()
            return False
        await conn.execute(
            """
            INSERT INTO improvement_proposal_events
            (proposal_id, old_status, new_status, actor_id, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (proposal_id, old_status, status, resolved_by, note, now),
        )
        await conn.commit()
        return True

    async def get_stats(self, days: int = 7) -> Dict[str, int]:
        safe_days = max(1, min(int(days), 365))
        since = (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=safe_days)
        ).isoformat()
        rows = await self._fetch_all(
            """
            SELECT status, COUNT(*) AS cnt
            FROM improvement_proposals
            WHERE first_seen_at > ?
            GROUP BY status
            """,
            (since,),
        )
        stats = {
            str(row["status"]): int(row["cnt"]) for row in rows if isinstance(row, dict)
        }
        stats["total"] = sum(stats.values())
        return stats

    @classmethod
    def _deserialize(cls, row: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(row)
        for key, fallback in (("affected_files", []), ("evidence", {})):
            value = data.get(key)
            if isinstance(value, str):
                try:
                    data[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    data[key] = fallback
            elif value is None:
                data[key] = fallback
        return data
