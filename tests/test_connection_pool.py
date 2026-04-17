"""
Unit tests for database connection pooling.
Tests: Pool creation, connection acquisition, SQLite optimizations.
"""
import pytest
import asyncio
import os
import tempfile
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestConnectionPool:
    """Test connection pool functionality."""

    @pytest.fixture
    async def temp_pool(self):
        """Create a temporary connection pool."""
        from database_pool import ConnectionPool, PoolConfig
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            
            pool = ConnectionPool(
                sqlite_path=db_path,
                config=PoolConfig(min_size=2, max_size=5)
            )
            await pool.initialize()
            
            yield pool
            
            await pool.close()

    @pytest.mark.asyncio
    async def test_pool_initialization(self, temp_pool):
        """Test that pool initializes successfully."""
        assert temp_pool._pool is not None
        assert temp_pool._is_postgres is False

    @pytest.mark.asyncio
    async def test_connection_acquisition(self, temp_pool):
        """Test acquiring connections from pool."""
        async with temp_pool.acquire() as conn:
            assert conn is not None
            
            # Test connection works
            from database_pool import HAS_SQLITE
            if HAS_SQLITE:
                import aiosqlite
                if isinstance(conn, aiosqlite.Connection):
                    async with conn.execute("SELECT 1") as cursor:
                        result = await cursor.fetchone()
                        assert result[0] == 1

    @pytest.mark.asyncio
    async def test_multiple_connections(self, temp_pool):
        """Test acquiring multiple concurrent connections."""
        connections = []
        
        # Acquire multiple connections
        for _ in range(3):
            conn = await temp_pool._pool.acquire()
            connections.append(conn)
        
        # Verify all are different connections
        assert len(set(id(c) for c in connections)) == 3
        
        # Release them
        for conn in connections:
            await temp_pool._pool.release(conn)

    @pytest.mark.asyncio
    async def test_connection_reuse(self, temp_pool):
        """Test that connections are reused."""
        # Acquire and release
        conn1 = await temp_pool._pool.acquire()
        conn1_id = id(conn1)
        await temp_pool._pool.release(conn1)
        
        # Acquire again - should potentially reuse
        conn2 = await temp_pool._pool.acquire()
        
        # Release
        await temp_pool._pool.release(conn2)

    @pytest.mark.asyncio
    async def test_execute_query(self, temp_pool):
        """Test executing queries through pool."""
        # Create a test table
        await temp_pool.execute(
            "CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY, name TEXT)"
        )
        
        # Insert data
        await temp_pool.execute(
            "INSERT INTO test (name) VALUES (?)",
            "test_name"
        )
        
        # Fetch
        result = await temp_pool.fetchone(
            "SELECT * FROM test WHERE name = ?",
            "test_name"
        )
        
        assert result is not None
        assert result['name'] == 'test_name'

    @pytest.mark.asyncio
    async def test_fetchall(self, temp_pool):
        """Test fetching multiple rows."""
        # Create table and insert data
        await temp_pool.execute(
            "CREATE TABLE IF NOT EXISTS test_fetch (id INTEGER PRIMARY KEY, val INTEGER)"
        )
        
        for i in range(5):
            await temp_pool.execute(
                "INSERT INTO test_fetch (val) VALUES (?)", i
            )
        
        # Fetch all
        results = await temp_pool.fetchall(
            "SELECT * FROM test_fetch ORDER BY val"
        )
        
        assert len(results) == 5
        for i, row in enumerate(results):
            assert row['val'] == i


class TestSQLitePool:
    """Test SQLite-specific pool features."""

    @pytest.mark.asyncio
    async def test_wal_mode_enabled(self):
        """Test that WAL mode is enabled for SQLite."""
        from database_pool import SQLiteConnectionPool
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "wal_test.db")
            pool = SQLiteConnectionPool(db_path, max_connections=3)
            await pool.initialize()
            
            # Acquire connection and check journal mode
            conn = await pool.acquire()
            try:
                async with conn.execute("PRAGMA journal_mode") as cursor:
                    result = await cursor.fetchone()
                    assert result[0].upper() == "WAL"
            finally:
                await pool.release(conn)
                await pool.close()

    @pytest.mark.asyncio
    async def test_foreign_keys_enabled(self):
        """Test that foreign keys are enabled."""
        from database_pool import SQLiteConnectionPool
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "fk_test.db")
            pool = SQLiteConnectionPool(db_path, max_connections=3)
            await pool.initialize()
            
            conn = await pool.acquire()
            try:
                async with conn.execute("PRAGMA foreign_keys") as cursor:
                    result = await cursor.fetchone()
                    assert result[0] == 1  # Enabled
            finally:
                await pool.release(conn)
                await pool.close()


class TestPoolConfiguration:
    """Test pool configuration."""

    def test_pool_config_defaults(self):
        """Test default pool configuration."""
        from database_pool import PoolConfig
        
        config = PoolConfig()
        assert config.min_size == 2
        assert config.max_size == 10
        assert config.command_timeout == 60.0

    def test_postgres_detection(self):
        """Test PostgreSQL URL detection."""
        from database_pool import ConnectionPool
        
        pool = ConnectionPool(database_url="postgresql://user:pass@localhost/db")
        assert pool._is_postgres is True

    def test_sqlite_fallback(self):
        """Test SQLite fallback when no PostgreSQL URL."""
        from database_pool import ConnectionPool
        
        with patch.dict(os.environ, {}, clear=True):
            pool = ConnectionPool(sqlite_path="test.db")
            assert pool._is_postgres is False


class TestGlobalPool:
    """Test global pool instance management."""

    @pytest.mark.asyncio
    async def test_get_pool_singleton(self):
        """Test that get_pool returns singleton."""
        from database_pool import get_pool, close_pool, _pool_instance
        
        # Close any existing pool
        await close_pool()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "global.db")
            
            # Get pool twice
            pool1 = await get_pool(sqlite_path=db_path)
            pool2 = await get_pool(sqlite_path=db_path)
            
            # Should be same instance
            assert pool1 is pool2
            
            await close_pool()

    @pytest.mark.asyncio
    async def test_close_pool_cleanup(self):
        """Test that close_pool properly cleans up."""
        import database_pool
        
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db_path = os.path.join(tmpdir, "cleanup.db")
            
            # Create pool
            await database_pool.get_pool(sqlite_path=db_path)
            assert database_pool._pool_instance is not None
            
            # Close pool
            await database_pool.close_pool()
            assert database_pool._pool_instance is None
        
        # On Windows, we might need a tiny delay for aiosqlite threads to release the file
        await asyncio.sleep(0.1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
