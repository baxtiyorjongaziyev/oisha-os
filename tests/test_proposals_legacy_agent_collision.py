"""ProposalRepository must survive colliding with SelfImprovementAgent's table.

Before ProposalRepository existed, SelfImprovementAgent.ensure_tables()
(src/services/core/self_improvement_agent.py) already created an
`improvement_proposals` table under the same name, with an incompatible
schema: `id INTEGER PRIMARY KEY AUTOINCREMENT` plus NOT NULL `area`/`gap`/
`proposal` columns. ALTER TABLE ADD COLUMN cannot reconcile that: inserting
ProposalRepository's TEXT ids (e.g. "DIAG-1") into an INTEGER PRIMARY KEY
column raises a datatype mismatch, and the legacy NOT NULL columns have no
default for new inserts to satisfy.

The agent itself now writes to `agent_improvement_proposals`, closing the
collision for new installs, but any install that ever ran the old code still
has this table sitting under the old name — init_table() must move it aside
automatically rather than crash.
"""

import aiosqlite
import pytest

from src.db.repositories.proposals import ProposalRepository

# Exact schema from SelfImprovementAgent.ensure_tables() before the rename.
LEGACY_AGENT_SCHEMA = """
    CREATE TABLE improvement_proposals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        area TEXT NOT NULL,
        gap TEXT NOT NULL,
        proposal TEXT NOT NULL,
        ai_agent_help TEXT,
        priority TEXT DEFAULT 'medium',
        impact TEXT,
        status TEXT DEFAULT 'proposed',
        signals_json TEXT,
        created_at TEXT,
        updated_at TEXT
    )
"""


class _StubDatabase:
    def __init__(self, conn):
        self._conn = conn

    async def get_connection(self):
        return self._conn


@pytest.fixture
async def legacy_agent_db(tmp_path):
    async with aiosqlite.connect(tmp_path / "legacy_agent.db") as conn:
        await conn.execute(LEGACY_AGENT_SCHEMA)
        await conn.execute(
            """INSERT INTO improvement_proposals
               (area, gap, proposal, priority, status, created_at, updated_at)
               VALUES ('lead followup', 'eski gap', 'eski proposal',
                       'high', 'proposed', '2026-08-01T00:00:00+05:00',
                       '2026-08-01T00:00:00+05:00')"""
        )
        await conn.commit()
        yield conn


async def _columns(conn, table):
    cursor = await conn.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in await cursor.fetchall()}


async def _table_exists(conn, table):
    cursor = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return await cursor.fetchone() is not None


@pytest.mark.asyncio
async def test_init_table_moves_legacy_agent_table_aside(legacy_agent_db):
    repo = ProposalRepository(_StubDatabase(legacy_agent_db))

    await repo.init_table()

    assert await _table_exists(legacy_agent_db, "agent_improvement_proposals_legacy")
    columns = await _columns(legacy_agent_db, "improvement_proposals")
    assert "category" in columns
    assert "area" not in columns


@pytest.mark.asyncio
async def test_init_table_preserves_legacy_agent_data(legacy_agent_db):
    repo = ProposalRepository(_StubDatabase(legacy_agent_db))

    await repo.init_table()

    cursor = await legacy_agent_db.execute(
        "SELECT area, gap, proposal FROM agent_improvement_proposals_legacy"
    )
    row = await cursor.fetchone()
    assert row == ("lead followup", "eski gap", "eski proposal")


@pytest.mark.asyncio
async def test_init_table_can_insert_text_id_after_migration(legacy_agent_db):
    """This is the exact failure Codex flagged: a datatype mismatch inserting
    a TEXT id into what used to be an INTEGER PRIMARY KEY column."""
    repo = ProposalRepository(_StubDatabase(legacy_agent_db))
    await repo.init_table()

    now = "2026-08-28T00:00:00+05:00"
    await legacy_agent_db.execute(
        """INSERT INTO improvement_proposals
           (id, category, severity, title, status, created_at)
           VALUES ('DIAG-1', 'unknown', 'medium', 'Yangi taklif', 'proposed', ?)""",
        (now,),
    )
    await legacy_agent_db.commit()

    cursor = await legacy_agent_db.execute(
        "SELECT id, title FROM improvement_proposals WHERE id = 'DIAG-1'"
    )
    row = await cursor.fetchone()
    assert row == ("DIAG-1", "Yangi taklif")


@pytest.mark.asyncio
async def test_init_table_is_idempotent_after_collision_fix(legacy_agent_db):
    repo = ProposalRepository(_StubDatabase(legacy_agent_db))

    await repo.init_table()
    await repo.init_table()  # must not re-rename or fail the second time

    columns = await _columns(legacy_agent_db, "improvement_proposals")
    assert "category" in columns
    # Only one legacy backup should exist — no _1, _2 suffix pile-up.
    assert await _table_exists(legacy_agent_db, "agent_improvement_proposals_legacy")
    assert not await _table_exists(
        legacy_agent_db, "agent_improvement_proposals_legacy_1"
    )
