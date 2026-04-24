"""
Unit tests for database connection pooling.
Tests: DatabasePool singleton, SmartRow behavior, and execution via libsql.
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database_pool import DatabasePool, SmartRow, get_db_connection


class TestSmartRow:
    """Test the SmartRow dict/list hybrid class."""
    
    def test_smart_row_dict_access(self):
        row = SmartRow([1, "Alice"], ["id", "name"])
        assert row["id"] == 1
        assert row["name"] == "Alice"
        assert row.get("id") == 1
        
    def test_smart_row_index_access(self):
        row = SmartRow([1, "Alice"], ["id", "name"])
        assert row[0] == 1
        assert row[1] == "Alice"
        
    def test_smart_row_keys(self):
        row = SmartRow([1, "Alice"], ["id", "name"])
        assert list(row.keys()) == ["id", "name"]


class TestDatabasePool:
    """Test the DatabasePool singleton."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        # Reset the singleton state before each test
        DatabasePool._instance = None
        DatabasePool._connection = None

    @patch("database_pool.libsql.connect")
    def test_singleton_instance(self, mock_connect):
        pool1 = DatabasePool()
        pool2 = DatabasePool()
        assert pool1 is pool2

    @patch("database_pool.libsql.connect")
    @patch("database_pool._setting_text")
    def test_get_connection_auth(self, mock_setting, mock_connect):
        # Setup mocks
        mock_setting.side_effect = ["https://mock.turso.io", "mock-token"]
        
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        pool = DatabasePool()
        conn = pool.get_connection()
        
        assert conn is mock_conn
        mock_connect.assert_called_once_with("https://mock.turso.io", auth_token="mock-token")
        
        # Second call should reuse the connection
        conn2 = pool.get_connection()
        assert conn2 is mock_conn
        assert mock_connect.call_count == 1

    @pytest.mark.asyncio
    @patch("database_pool.libsql.connect")
    async def test_execute_query(self, mock_connect):
        mock_conn = MagicMock()
        mock_res = MagicMock()
        mock_res.columns = ["id", "val"]
        mock_res.fetchall.return_value = [(1, "A"), (2, "B")]
        mock_conn.execute.return_value = mock_res
        mock_connect.return_value = mock_conn
        
        pool = DatabasePool()
        
        rows = await pool.execute("SELECT * FROM test WHERE val = ?", ["A"])
        
        assert len(rows) == 2
        assert isinstance(rows[0], SmartRow)
        assert rows[0]["id"] == 1
        assert rows[0]["val"] == "A"
        assert rows[0][0] == 1
        assert rows[1]["val"] == "B"

    @pytest.mark.asyncio
    @patch("database_pool.libsql.connect")
    async def test_get_db_connection_context(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        async with get_db_connection() as conn:
            assert conn is mock_conn


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
