import pytest

from src.database import Database, TursoAdapter

try:
    import libsql
except ImportError:  # pragma: no cover - environment specific
    libsql = None


pytestmark = pytest.mark.asyncio


def _require_libsql():
    if libsql is None:
        pytest.skip("libsql is not installed")


async def test_turso_adapter_handles_empty_pragma_cursor():
    _require_libsql()

    adapter = TursoAdapter(libsql.connect(":memory:"))
    cursor = await adapter.execute("PRAGMA journal_mode=WAL")

    assert await cursor.fetchone() is None
    assert await cursor.fetchall() == []


async def test_turso_adapter_handles_select_create_and_alter():
    _require_libsql()

    adapter = TursoAdapter(libsql.connect(":memory:"))

    await adapter.execute("CREATE TABLE users (user_id INTEGER PRIMARY KEY)")
    await adapter.execute("ALTER TABLE users ADD COLUMN first_name TEXT")

    select_cursor = await adapter.execute("SELECT 1")
    row = await select_cursor.fetchone()

    assert row[0] == 1

    pragma_cursor = await adapter.execute("SELECT name FROM pragma_table_info('users')")
    column_names = {row[0] for row in await pragma_cursor.fetchall()}
    assert "first_name" in column_names


async def test_database_init_instance_succeeds_with_turso_adapter(monkeypatch):
    _require_libsql()

    connection = libsql.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            phone TEXT,
            business_type TEXT,
            region TEXT,
            brand_name TEXT,
            service_type TEXT,
            deadline TEXT,
            role TEXT,
            is_lead_forwarded BOOLEAN DEFAULT 0,
            last_seen DATETIME,
            created_at DATETIME
        )
        """
    )

    adapter = TursoAdapter(connection)
    db = Database(":memory:")

    async def fake_get_connection():
        return adapter

    monkeypatch.setattr(db, "get_connection", fake_get_connection)

    await db.init_instance()

    cursor = await adapter.execute("SELECT name FROM pragma_table_info('users')")
    column_names = {row[0] for row in await cursor.fetchall()}

    assert "journey_stage" in column_names
    assert "lifecycle_updated_at" in column_names
