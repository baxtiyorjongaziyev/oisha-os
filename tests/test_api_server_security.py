"""
Unit tests for API Server security and endpoints.
"""
import pytest
import os
from unittest.mock import patch, MagicMock, AsyncMock
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.api.routes.state import api_state


class TestAPISecurity:
    def test_api_secret_required_from_env(self):
        with patch.dict(os.environ, {"OISHA_API_SECRET": ""}):
            from src.api_server import lookup_user_by_phone
            from fastapi import HTTPException
            import asyncio
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(lookup_user_by_phone("+1234567890", "any_secret"))
            assert exc_info.value.status_code == 401

    def test_api_secret_mismatch_blocks_access(self):
        with patch.dict(os.environ, {"OISHA_API_SECRET": "correct_secret"}):
            from src.api_server import lookup_user_by_phone
            from fastapi import HTTPException
            import asyncio
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(lookup_user_by_phone("+1234567890", "wrong_secret"))
            assert exc_info.value.status_code == 401

    def test_api_secret_match_allows_access(self):
        with patch.dict(os.environ, {"OISHA_API_SECRET": "correct_secret"}):
            from src.api_server import lookup_user_by_phone
            import asyncio
            result = asyncio.run(lookup_user_by_phone("+998901234567", "correct_secret"))
            assert result == {"error": "Database not connected"}

    def test_no_hardcoded_secret_default(self):
        api_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'api_server.py')
        with open(api_file, 'r', encoding='utf-8') as f:
            content = f.read()
        assert 'oisha_safe_123' not in content
        assert 'os.environ.get("OISHA_API_SECRET", "")' not in content

        widget_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'static', 'widget.html')
        with open(widget_file, 'r', encoding='utf-8') as f:
            widget_content = f.read()
        assert 'oisha_safe_123' not in widget_content
        assert '?secret_key=' not in widget_content
        assert "'X-Secret-Key': SECRET" in widget_content

        amocrm_widget = os.path.join(
            os.path.dirname(__file__), '..', 'src', 'widgets', 'amocrm', 'script.js'
        )
        with open(amocrm_widget, 'r', encoding='utf-8') as f:
            amocrm_widget_content = f.read()
        assert '?secret_key=' not in amocrm_widget_content
        assert "headers: {'X-Secret-Key': secret}" in amocrm_widget_content

    def test_health_check_is_not_force_green(self):
        api_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'api_server.py')
        with open(api_file, 'r', encoding='utf-8') as f:
            api_content = f.read()
        health_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'api', 'routes', 'health.py')
        with open(health_file, 'r', encoding='utf-8') as f:
            health_content = f.read()
        combined = api_content + health_content

        assert "async def liveness_probe" in combined
        assert "db_ok" in combined

    def test_http_transport_logs_do_not_expose_bot_api_tokens(self):
        for relative_path in ('main.py', 'api_server.py'):
            source_file = os.path.join(os.path.dirname(__file__), '..', 'src', relative_path)
            with open(source_file, 'r', encoding='utf-8') as f:
                content = f.read()
            assert 'logging.getLogger("httpx").setLevel(logging.WARNING)' in content
            assert 'logging.getLogger("httpcore").setLevel(logging.WARNING)' in content

    def test_database_pool_has_no_hardcoded_turso_token(self):
        pool_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'database_pool.py')
        with open(pool_file, 'r', encoding='utf-8') as f:
            content = f.read()
        assert "settings.TURSO_AUTH_TOKEN" in content
        assert "eyJhbGci" not in content

    def test_oracle_is_the_only_oisha_production_deploy_workflow(self):
        workflow_dir = os.path.join(os.path.dirname(__file__), '..', '.github', 'workflows')
        cloud_run_workflow = os.path.join(workflow_dir, 'deploy.yml')
        oracle_workflow = os.path.join(workflow_dir, 'oracle-deploy.yml')
        assert not os.path.exists(cloud_run_workflow)
        with open(oracle_workflow, 'r', encoding='utf-8') as f:
            content = f.read()
        assert "CLOUD_RUN_CONTROL_PLANE_ONLY=false" in content
        assert "ENABLE_CLOUD_USERBOT=true" in content
        assert "USERBOT_DISABLE_PRIVATE_REPLIES=true" in content
        assert "TELEGRAM_BOT_TO_BOT_ENABLED=false" in content
        assert "USERBOT_SESSION_STRING=${USERBOT_SESSION_STRING}" in content
        assert "sudo systemctl restart oisha-os" in content
        assert "http://127.0.0.1:8080/readyz/" in content

    def test_cloud_run_control_plane_skips_userbot_session_parsing(self):
        boot_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'boot.py')
        with open(boot_file, 'r', encoding='utf-8') as f:
            content = f.read()
        assert "if cloud_control_plane_only:" in content
        assert "[CLOUD] Control-plane mode active." in content
        assert "StringSession()" in content.split("if cloud_control_plane_only:")[1].split("else:")[0]

    def test_oracle_deploy_runs_for_every_main_push(self):
        """Deploy har qanday push'da emas — CI xarajatini tejash uchun
        `paths:` filtri ataylab qo'shilgan (ce261ce, 2026-07-09). Muhim
        kafolat endi shu: ilova kodi (`src/**`) o'zgarsa, deploy albatta
        ishga tushishi kerak — bu haqiqiy xavfsizlik invarianti."""
        workflow_file = os.path.join(
            os.path.dirname(__file__), '..', '.github', 'workflows', 'oracle-deploy.yml'
        )
        with open(workflow_file, 'r', encoding='utf-8') as f:
            content = f.read()
        push_block = content.split("workflow_dispatch:", 1)[0]
        assert "branches: [main]" in push_block
        assert "'src/**'" in push_block, "src/** o'zgarishlari doim deploy qilinishi shart"


class TestAPIEndpoints:
    @pytest.fixture
    def mock_db(self):
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
        with patch.dict(os.environ, {"OISHA_API_SECRET": "test_secret"}):
            with patch.object(api_state, 'db_instance', mock_db):
                from src.api_server import lookup_user_by_phone
                import asyncio
                result = asyncio.run(lookup_user_by_phone("+998901234567", "test_secret"))
                assert result["status"] == "found"
                assert result["user_id"] == 12345

    def test_lookup_user_not_found(self, mock_db):
        async def mock_none(phone): return None
        mock_db.get_user_id_by_phone = mock_none
        with patch.dict(os.environ, {"OISHA_API_SECRET": "test_secret"}):
            with patch.object(api_state, 'db_instance', mock_db):
                from src.api_server import lookup_user_by_phone
                import asyncio
                result = asyncio.run(lookup_user_by_phone("+99999999999", "test_secret"))
                assert result["status"] == "not_found"

    def test_chat_history_endpoint(self, mock_db):
        with patch.dict(os.environ, {"OISHA_API_SECRET": "test_secret"}):
            with patch.object(api_state, 'db_instance', mock_db):
                from src.api_server import get_chat_history
                import asyncio
                result = asyncio.run(get_chat_history("12345", "test_secret"))
                assert "history" in result
                assert len(result["history"]) == 2

    def test_chat_history_with_string_and_web_user_id(self, mock_db):
        recorded_ids = []
        async def mock_get_recent(user_id, limit=30):
            recorded_ids.append(user_id)
            return []
        mock_db.get_recent_messages = mock_get_recent
        with patch.dict(os.environ, {"OISHA_API_SECRET": "test_secret"}):
            with patch.object(api_state, 'db_instance', mock_db):
                from src.api_server import get_chat_history
                import asyncio
                asyncio.run(get_chat_history("98765", "test_secret"))
                assert recorded_ids[-1] == 98765
                asyncio.run(get_chat_history("web_user123", "test_secret"))
                assert recorded_ids[-1] == "web_user123"

    def test_send_chat_message_sync_for_web_user(self, mock_db):
        from src.api_server import send_chat_message, SendMessageRequest
        import asyncio

        mock_db.log_message = AsyncMock()

        mock_agent_instance = MagicMock()
        async def mock_handle(user_id, message, autonomy_level="full"):
            return {"response": "Mocked AI Response"}
        mock_agent_instance.handle_incoming = mock_handle

        with patch.dict(os.environ, {"OISHA_API_SECRET": "test_secret"}):
            with patch.object(api_state, 'db_instance', mock_db):
                with patch('src.agents.autonomous_sales_agent.AutonomousSalesAgent', return_value=mock_agent_instance):
                    with patch.object(api_state, 'command_queue') as mock_queue:
                        req = SendMessageRequest(
                            user_id="web_session_999",
                            text="Salom Oisha",
                            secret_key="test_secret"
                        )
                        result = asyncio.run(send_chat_message(req))
                        assert result["status"] == "success"
                        assert result["response"] == "Mocked AI Response"
                        assert mock_db.log_message.call_count == 2
                        mock_db.log_message.assert_any_call("web_session_999", "Salom Oisha", is_ai=False)
                        mock_db.log_message.assert_any_call("web_session_999", "Mocked AI Response", is_ai=True)
                        mock_queue.put_nowait.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
