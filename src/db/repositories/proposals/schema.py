"""
Schema initialization and legacy migration for Proposals table.
"""
from __future__ import annotations

import logging
from typing import Any

from src.db.repositories.proposals.constants import _LEGACY_AGENT_TABLE_MARKERS

logger = logging.getLogger(__name__)


async def rename_away_incompatible_legacy_table(repo: Any, conn: Any) -> None:
    existing_columns = await repo._get_table_columns("improvement_proposals")
    if not existing_columns:
        return
    if "category" in existing_columns:
        return
    if not _LEGACY_AGENT_TABLE_MARKERS.issubset(existing_columns):
        return
    for suffix in range(10):
        legacy_name = "agent_improvement_proposals_legacy" + (
            f"_{suffix}" if suffix else ""
        )
        if not await repo._get_table_columns(legacy_name):
            break
    else:
        logger.error(
            "[DB] Could not find a free name to rename the legacy "
            "improvement_proposals table aside; leaving it in place"
        )
        return
    logger.warning(
        "[DB] improvement_proposals has the legacy SelfImprovementAgent "
        "schema (area/gap/proposal, INTEGER PK) — renaming it to %s "
        "so the current schema can be created",
        legacy_name,
    )
    await repo._execute(
        f"ALTER TABLE improvement_proposals RENAME TO {legacy_name}"
    )


async def init_proposal_tables(repo: Any) -> None:
    conn = await repo._get_conn()
    await rename_away_incompatible_legacy_table(repo, conn)
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

    existing_columns = await repo._get_table_columns("improvement_proposals")
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
        await repo._add_column_if_missing(
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
