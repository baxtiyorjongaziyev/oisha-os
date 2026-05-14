import pytest

from src.database import Database, TursoAdapter, _normalize_turso_url
from src.database_pool import db_pool

try:
    import libsql
except ImportError:  # pragma: no cover - environment specific
    libsql = None


pytestmark = pytest.mark.asyncio


async def test_turso_url_normalization_supports_secret_manager_format():
    assert _normalize_turso_url("libsql://example.turso.io") == "https://example.turso.io"
    assert _normalize_turso_url("https://example.turso.io") == "https://example.turso.io"
    assert _normalize_turso_url(":memory:") == ":memory:"


def _require_libsql():
    if libsql is None:
        pytest.skip("libsql is not installed")


async def test_turso_adapter_handles_empty_pragma_cursor(monkeypatch):
    _require_libsql()

    # Force db_pool to use memory for testing
    monkeypatch.setattr(db_pool, "url", ":memory:")
    monkeypatch.setattr(db_pool, "auth_token", "")
    db_pool._connection = None

    adapter = TursoAdapter()
    cursor = await adapter.execute("PRAGMA journal_mode=WAL")

    assert await cursor.fetchone() is None
    assert await cursor.fetchall() == []


async def test_turso_adapter_handles_select_create_and_alter(monkeypatch):
    _require_libsql()

    # Force db_pool to use memory for testing
    monkeypatch.setattr(db_pool, "url", ":memory:")
    monkeypatch.setattr(db_pool, "auth_token", "")
    db_pool._connection = None

    adapter = TursoAdapter()

    await adapter.execute("CREATE TABLE users (user_id INTEGER PRIMARY KEY)")
    await adapter.execute("ALTER TABLE users ADD COLUMN first_name TEXT")

    select_cursor = await adapter.execute("SELECT 1")
    row = await select_cursor.fetchone()

    # SmartRow supports indexing
    assert row[0] == 1

    pragma_cursor = await adapter.execute("SELECT name FROM pragma_table_info('users')")
    column_names = {row[0] for row in await pragma_cursor.fetchall()}
    assert "first_name" in column_names


async def test_database_init_instance_succeeds_with_turso_adapter(monkeypatch):
    _require_libsql()

    # Force db_pool to use memory for testing
    monkeypatch.setattr(db_pool, "url", ":memory:")
    monkeypatch.setattr(db_pool, "auth_token", "")
    db_pool._connection = None

    adapter = TursoAdapter()
    
    # Pre-populate schema for test
    await adapter.execute("""
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
    """)

    db = Database(":memory:")

    async def fake_get_connection():
        return adapter

    monkeypatch.setattr(db, "get_connection", fake_get_connection)

    await db.init_instance()

    cursor = await adapter.execute("SELECT name FROM pragma_table_info('users')")
    column_names = {row[0] for row in await cursor.fetchall()}

    assert "journey_stage" in column_names
    assert "lifecycle_updated_at" in column_names


async def test_database_falls_back_to_sqlite_when_turso_probe_fails(monkeypatch, tmp_path):
    _require_libsql()

    from src import database as database_module

    db = Database(str(tmp_path / "fallback.db"))

    original_url = database_module.settings.TURSO_DATABASE_URL
    original_token = database_module.settings.TURSO_AUTH_TOKEN

    class DummySecret:
        def __init__(self, value):
            self._value = value

        def get_secret_value(self):
            return self._value

        def __bool__(self):
            return bool(self._value)

        def __str__(self):
            return self._value

        def startswith(self, prefix):
            return self._value.startswith(prefix)

        def replace(self, old, new):
            return self._value.replace(old, new)

        def __getitem__(self, item):
            return self._value[item]

    monkeypatch.setattr(database_module.settings, "TURSO_DATABASE_URL", DummySecret("libsql://broken.example"))
    monkeypatch.setattr(database_module.settings, "TURSO_AUTH_TOKEN", DummySecret("broken-token"))

    class BrokenTursoConnection:
        def execute(self, sql, parameters=None):
            raise ValueError("JWT error: InvalidToken")

        def close(self):
            return None

    monkeypatch.setattr(database_module.libsql, "connect", lambda *args, **kwargs: BrokenTursoConnection())

    try:
        conn = await db.get_connection()
        assert not isinstance(conn, TursoAdapter)
        assert db.get_backend_name() == "sqlite"

        cursor = await conn.execute("SELECT 1")
        assert (await cursor.fetchone())[0] == 1
    finally:
        monkeypatch.setattr(database_module.settings, "TURSO_DATABASE_URL", original_url)
        monkeypatch.setattr(database_module.settings, "TURSO_AUTH_TOKEN", original_token)
        await db.close()


async def test_database_reuses_existing_turso_adapter(monkeypatch, tmp_path):
    _require_libsql()

    from src import database as database_module

    db = Database(str(tmp_path / "reuse.db"))
    original_url = database_module.settings.TURSO_DATABASE_URL
    original_token = database_module.settings.TURSO_AUTH_TOKEN

    class DummySecret:
        def __init__(self, value):
            self._value = value

        def get_secret_value(self):
            return self._value

        def __bool__(self):
            return bool(self._value)

    calls = 0
    original_connect = database_module.libsql.connect

    def counting_connect(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_connect(":memory:")

    monkeypatch.setattr(database_module.settings, "TURSO_DATABASE_URL", DummySecret(":memory:"))
    monkeypatch.setattr(database_module.settings, "TURSO_AUTH_TOKEN", DummySecret("test-token"))
    monkeypatch.setattr(database_module.libsql, "connect", counting_connect)

    try:
        first = await db.get_connection()
        second = await db.get_connection()

        assert isinstance(first, TursoAdapter)
        assert second is first
        assert calls == 1
    finally:
        monkeypatch.setattr(database_module.settings, "TURSO_DATABASE_URL", original_url)
        monkeypatch.setattr(database_module.settings, "TURSO_AUTH_TOKEN", original_token)
        await db.close()


async def test_api_exposes_health_aliases():
    from src.api_server import app

    paths = {getattr(route, "path", None) for route in app.routes}

    assert "/health" in paths
    assert "/healthz" in paths
    assert "/healthz/" in paths


async def test_api_exposes_runtime_context_setter():
    from src import api_server

    previous = api_server.get_runtime_context()
    try:
        updated = api_server.set_runtime_context(
            service_name="test-service",
            scheduler_mode="control-plane",
            userbot_authorized=False,
        )
    finally:
        api_server.set_runtime_context(**previous)

    assert updated["service_name"] == "test-service"
    assert updated["scheduler_mode"] == "control-plane"
    assert updated["userbot_authorized"] is False
