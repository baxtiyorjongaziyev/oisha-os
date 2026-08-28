"""ProposalRepository must migrate the legacy improvement_proposals table.

CREATE TABLE IF NOT EXISTS is a no-op against an existing table, so a database
created from the earlier draft schema kept its old columns while init_table went
on to build indexes over columns that were never added. On Turso that surfaced
as: `SQLite input error: no such column: severity (at offset 76)`, which killed
the self-improvement scheduler on every boot.
"""

import aiosqlite
import pytest

from src.db.repositories.proposals import ProposalRepository

LEGACY_SCHEMA = """
    CREATE TABLE improvement_proposals (
        id TEXT PRIMARY KEY,
        title TEXT,
        problem TEXT,
        status TEXT DEFAULT 'proposed',
        created_at TEXT
    )
"""


class _StubDatabase:
    def __init__(self, conn):
        self._conn = conn

    async def get_connection(self):
        return self._conn


@pytest.fixture
async def legacy_db(tmp_path):
    async with aiosqlite.connect(tmp_path / "legacy.db") as conn:
        await conn.execute(LEGACY_SCHEMA)
        await conn.execute(
            "INSERT INTO improvement_proposals (id, title, created_at) "
            "VALUES ('DIAG-1', 'Eski taklif', '2026-08-01T00:00:00+05:00')"
        )
        await conn.commit()
        yield conn


async def _columns(conn, table):
    cursor = await conn.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in await cursor.fetchall()}


@pytest.mark.asyncio
async def test_init_table_adds_missing_columns_to_legacy_schema(legacy_db):
    repo = ProposalRepository(_StubDatabase(legacy_db))

    await repo.init_table()

    columns = await _columns(legacy_db, "improvement_proposals")
    for expected in (
        "severity",
        "category",
        "fingerprint",
        "affected_files",
        "evidence",
        "occurrence_count",
        "resolved_at",
        "rejection_reason",
    ):
        assert expected in columns, f"{expected} was not migrated"


@pytest.mark.asyncio
async def test_init_table_creates_severity_index_on_legacy_schema(legacy_db):
    """This is the statement that raised "no such column: severity"."""
    repo = ProposalRepository(_StubDatabase(legacy_db))

    await repo.init_table()

    cursor = await legacy_db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
        ("idx_proposals_severity",),
    )
    assert await cursor.fetchone() is not None


@pytest.mark.asyncio
async def test_init_table_backfills_not_null_columns(legacy_db):
    """severity/category are NOT NULL in the target schema — no NULLs may remain."""
    repo = ProposalRepository(_StubDatabase(legacy_db))

    await repo.init_table()

    cursor = await legacy_db.execute(
        "SELECT category, severity, title, status FROM improvement_proposals "
        "WHERE id = 'DIAG-1'"
    )
    category, severity, title, status = await cursor.fetchone()
    assert (category, severity, status) == ("unknown", "medium", "proposed")
    assert title == "Eski taklif"


@pytest.mark.asyncio
async def test_init_table_is_idempotent(legacy_db):
    repo = ProposalRepository(_StubDatabase(legacy_db))

    await repo.init_table()
    await repo.init_table()

    columns = await _columns(legacy_db, "improvement_proposals")
    assert "severity" in columns
