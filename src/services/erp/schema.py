from __future__ import annotations

from typing import Any


ERP_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS erp_events (
        event_id TEXT PRIMARY KEY,
        event_type TEXT NOT NULL,
        source TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        occurred_at TEXT NOT NULL,
        correlation_id TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        raw_hash TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS erp_identities (
        identity_id TEXT PRIMARY KEY,
        identity_type TEXT NOT NULL,
        canonical_name TEXT,
        classification TEXT NOT NULL DEFAULT 'unknown',
        confidence REAL NOT NULL DEFAULT 0,
        attributes_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS erp_identity_links (
        link_id TEXT PRIMARY KEY,
        identity_id TEXT NOT NULL,
        source TEXT NOT NULL,
        external_id TEXT NOT NULL,
        confidence REAL NOT NULL DEFAULT 0,
        evidence_json TEXT NOT NULL DEFAULT '{}',
        verified_at TEXT,
        created_at TEXT NOT NULL,
        UNIQUE(source, external_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS erp_workflows (
        workflow_id TEXT PRIMARY KEY,
        workflow_type TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        correlation_id TEXT NOT NULL,
        status TEXT NOT NULL,
        data_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS erp_workflow_steps (
        step_id TEXT PRIMARY KEY,
        workflow_id TEXT NOT NULL,
        step_type TEXT NOT NULL,
        status TEXT NOT NULL,
        data_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS erp_actions (
        action_id TEXT PRIMARY KEY,
        workflow_id TEXT NOT NULL,
        action_type TEXT NOT NULL,
        target TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        risk_level TEXT NOT NULL,
        idempotency_key TEXT NOT NULL UNIQUE,
        expected_result_json TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'pending',
        available_at TEXT,
        lease_owner TEXT,
        lease_expires_at TEXT,
        attempt_count INTEGER NOT NULL DEFAULT 0,
        last_error TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS erp_action_attempts (
        attempt_id TEXT PRIMARY KEY,
        action_id TEXT NOT NULL,
        attempt_number INTEGER NOT NULL,
        status TEXT NOT NULL,
        result_json TEXT NOT NULL DEFAULT '{}',
        error TEXT,
        started_at TEXT NOT NULL,
        finished_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS erp_verifications (
        verification_id TEXT PRIMARY KEY,
        action_id TEXT NOT NULL,
        success BOOLEAN NOT NULL,
        source TEXT NOT NULL,
        expected_json TEXT NOT NULL DEFAULT '{}',
        actual_json TEXT NOT NULL DEFAULT '{}',
        reason TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS erp_approvals (
        approval_id TEXT PRIMARY KEY,
        action_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        requested_from TEXT,
        decided_by TEXT,
        reason TEXT,
        expires_at TEXT,
        created_at TEXT NOT NULL,
        decided_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS erp_dead_letters (
        dead_letter_id TEXT PRIMARY KEY,
        action_id TEXT NOT NULL,
        reason TEXT NOT NULL,
        payload_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        resolved_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS erp_metric_snapshots (
        snapshot_id TEXT PRIMARY KEY,
        metric_name TEXT NOT NULL,
        source TEXT NOT NULL,
        value_json TEXT NOT NULL,
        fresh_at TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_erp_events_correlation ON erp_events(correlation_id)",
    "CREATE INDEX IF NOT EXISTS idx_erp_events_entity ON erp_events(entity_type, entity_id)",
    "CREATE INDEX IF NOT EXISTS idx_erp_workflows_entity ON erp_workflows(entity_type, entity_id)",
    "CREATE INDEX IF NOT EXISTS idx_erp_workflows_status ON erp_workflows(status)",
    "CREATE INDEX IF NOT EXISTS idx_erp_actions_workflow ON erp_actions(workflow_id)",
    "CREATE INDEX IF NOT EXISTS idx_erp_actions_status ON erp_actions(status)",
    "CREATE INDEX IF NOT EXISTS idx_erp_verifications_action ON erp_verifications(action_id)",
)

ERP_SCHEMA_MIGRATIONS = (
    "ALTER TABLE erp_actions ADD COLUMN available_at TEXT",
    "ALTER TABLE erp_actions ADD COLUMN lease_owner TEXT",
    "ALTER TABLE erp_actions ADD COLUMN lease_expires_at TEXT",
    "ALTER TABLE erp_actions ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE erp_actions ADD COLUMN last_error TEXT",
)


async def initialize_erp_schema(conn: Any) -> None:
    for statement in ERP_SCHEMA_STATEMENTS:
        await conn.execute(statement)
    for statement in ERP_SCHEMA_MIGRATIONS:
        try:
            await conn.execute(statement)
        except Exception:
            # Existing installations already have the column after the first
            # successful migration. SQLite/libSQL both report duplicates.
            pass
