"""
Unit tests for API Server security and endpoints.
Updated for Eagle Architecture (Cloud Userbot Enabled).
"""
import pytest
import os
from unittest.mock import patch, MagicMock
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestAPISecurity:
    """Test API security features."""

    def test_api_secret_required_from_env(self):
        """API secret must be loaded from environment only."""
        with patch.dict(os.environ, {}, clear=True):
            from src.api_server import lookup_user_by_phone
            import asyncio
            
            result = asyncio.run(lookup_user_by_phone("+1234567890", "any_secret"))
            assert result == {"error": "Unauthorized"}

    def test_api_secret_mismatch_blocks_access(self):
        """Wrong API secret must return Unauthorized."""
        with patch.dict(os.environ, {"OISHA_API_SECRET": "correct_secret"}):
            from src.api_server import lookup_user_by_phone
            import asyncio
            
            result = asyncio.run(lookup_user_by_phone("+1234567890", "wrong_secret"))
            assert result == {"error": "Unauthorized"}

    def test_api_secret_match_allows_access(self):
        """Correct API secret should proceed to DB check."""
        with patch.dict(os.environ, {"OISHA_API_SECRET": "correct_secret"}):
            from src.api_server import lookup_user_by_phone
            import asyncio
            
            # Should pass secret check but fail on DB (no db_instance)
            result = asyncio.run(lookup_user_by_phone("+1234567890", "correct_secret"))
            assert result == {"error": "Database not connected"}

    def test_no_hardcoded_secret_default(self):
        """Ensure no hardcoded default secret exists."""
        api_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'api_server.py')
        with open(api_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'oisha_safe_123' not in content, "Hardcoded secret found!"
        assert 'os.environ.get("OISHA_API_SECRET", "")' not in content, "Empty default found!"

    def test_health_check_implementation_exists(self):
        """Ensure health check is implemented with proper validation."""
        api_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'api_server.py')
        with open(api_file, 'r', encoding='utf-8') as f:
            content = f.read()

        assert "async def liveness_probe" in content
        assert "db_ok" in content

    def test_database_pool_has_no_hardcoded_turso_token(self):
        """Turso token must come from environment/Secret Manager, never source code."""
        pool_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'database_pool.py')
        with open(pool_file, 'r', encoding='utf-8') as f:
            content = f.read()

        assert "settings.TURSO_AUTH_TOKEN" in content
        assert "eyJhbGci" not in content

    def test_deploy_workflow_allows_cloud_userbot(self):
        """Cloud Run is now allowed to run the userbot session (Eagle Mode)."""
        workflow_file = os.path.join(os.path.dirname(__file__), '..', '.github', 'workflows', 'deploy.yml')
        with open(workflow_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Eagle Mode: Userbot is enabled on Cloud Run
        assert "CLOUD_RUN_CONTROL_PLANE_ONLY=False" in content
        assert "ENABLE_CLOUD_USERBOT=True" in content
        assert "python -m pytest -q" in content


class TestAPIEndpoints:
    """Test API endpoint functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database instance."""
        mock = MagicMock()
        async def mock_get_user_id(phone): return 12345
        async def mock_get_recent(user_id, limit=30):
            return [
                {"text": "Hello", "is_ai": False, "created_at": "2024-01-01 10:00:00"},
                {"text": "Hi there", "is_ai": True, "created_at": "2024-01-01 10:05:00"}
            ]
        
        mock.get_user_id_by_phone = mock_get_user_id
        mock.get_recent_messages = mock_get_recent
        return mock

    def test_lookup_user_found(self, mock_db):
        """Test user lookup when user exists."""
        with patch.dict(os.environ, {"OISHA_API_SECRET": "test_secret"}):
            with patch('src.api_server.db_instance', mock_db):
                from src.api_server import lookup_user_by_phone
                import asyncio
                
                result = asyncio.run(lookup_user_by_phone("+998901234567", "test_secret"))
                assert result["status"] == "found"
                assert result["user_id"] == 12345

    def test_lookup_user_not_found(self, mock_db):
        """Test user lookup when user doesn't exist."""
        async def mock_none(phone): return None
        mock_db.get_user_id_by_phone = mock_none
        
        with patch.dict(os.environ, {"OISHA_API_SECRET": "test_secret"}):
            with patch('src.api_server.db_instance', mock_db):
                from src.api_server import lookup_user_by_phone
                import asyncio
                
                result = asyncio.run(lookup_user_by_phone("+99999999999", "test_secret"))
                assert result["status"] == "not_found"

    def test_chat_history_endpoint(self, mock_db):
        """Test chat history retrieval."""
        with patch.dict(os.environ, {"OISHA_API_SECRET": "test_secret"}):
            with patch('src.api_server.db_instance', mock_db):
                from src.api_server import get_chat_history
                import asyncio
                
                result = asyncio.run(get_chat_history(12345, "test_secret"))
                assert "history" in result
                assert len(result["history"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
