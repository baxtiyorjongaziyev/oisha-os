"""
Unit tests for Database operations.
Tests: Connection pooling, CRUD operations, index optimization.
"""
import pytest
import asyncio
import os
import tempfile
import sys
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestDatabaseConnection:
    """Test database connection management."""

    @pytest.fixture
    async def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        from database import Database
        db = Database(db_path)
        await db.init_db()
        
        yield db
        
        # Cleanup
        await db.close()
        os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_connection_creation(self, temp_db):
        """Test that database connection is created successfully."""
        conn = await temp_db.get_connection()
        assert conn is not None
        
        # Test connection is alive
        async with conn.execute("SELECT 1") as cursor:
            result = await cursor.fetchone()
            assert result[0] == 1

    @pytest.mark.asyncio
    async def test_connection_reuse(self, temp_db):
        """Test that connections are reused (basic pooling simulation)."""
        conn1 = await temp_db.get_connection()
        conn2 = await temp_db.get_connection()
        
        # Should return same connection if alive
        assert conn1 is conn2

    @pytest.mark.asyncio
    async def test_user_crud(self, temp_db):
        """Test user CRUD operations."""
        # Create
        await temp_db.upsert_user(
            user_id=12345,
            first_name="Test",
            username="testuser",
            phone="+998901234567"
        )
        
        # Read
        user_info = await temp_db.get_user_info(12345)
        assert user_info is not None
        assert user_info['first_name'] == "Test"
        
        # Update
        await temp_db.upsert_user(
            user_id=12345,
            first_name="Updated",
            username="testuser",
            phone="+998901234567"
        )
        
        user_info = await temp_db.get_user_info(12345)
        assert user_info['first_name'] == "Updated"

    @pytest.mark.asyncio
    async def test_get_user_by_phone(self, temp_db):
        """Test user lookup by phone number."""
        await temp_db.upsert_user(
            user_id=99988,
            first_name="PhoneTest",
            phone="+998909999999"
        )
        
        user_id = await temp_db.get_user_id_by_phone("+998909999999")
        assert user_id == 99988

    @pytest.mark.asyncio
    async def test_message_logging(self, temp_db):
        """Test message logging functionality."""
        await temp_db.log_message(
            user_id=12345,
            message_text="Test message",
            is_ai_reply=False
        )
        
        messages = await temp_db.get_recent_messages(12345, limit=10)
        assert len(messages) >= 1


class TestDatabaseIndexes:
    """Test that database indexes are created."""

    @pytest.mark.asyncio
    async def test_indexes_exist(self):
        """Verify all expected indexes are created."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            from database import Database
            db = Database(db_path)
            await db.init_db()
            
            conn = await db.get_connection()
            
            # Get all indexes
            async with conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
            ) as cursor:
                indexes = [row[0] for row in await cursor.fetchall()]
            
            # Check expected indexes exist
            expected_indexes = [
                'idx_users_phone',
                'idx_users_intent',
                'idx_users_crm_synced',
                'idx_messages_user_id',
                'idx_tasks_status',
                'idx_agent_actions_user_id',
                'idx_daily_plans_manager'
            ]
            
            for idx in expected_indexes:
                assert idx in indexes, f"Index {idx} not found"
            
            await db.close()
        finally:
            os.unlink(db_path)


class TestDatabaseErrorHandling:
    """Test database error handling."""

    @pytest.mark.asyncio
    async def test_specific_exceptions_caught(self):
        """Test that specific exceptions are caught, not bare except."""
        import aiosqlite
        
        # The database.py should use specific exceptions
        db_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'database.py')
        with open(db_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should use aiosqlite.Error instead of bare except
        assert 'except aiosqlite.Error:' in content or 'except (aiosqlite.Error' in content
        
        # Should not have bare except: pass patterns
        lines = content.split('\n')
        for line in lines:
            if 'except:' in line and 'pass' in line:
                pytest.fail(f"Bare except: pass found in database.py: {line}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
