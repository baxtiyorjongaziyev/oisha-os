"""
Unit tests for AmoCRM retry logic.
Tests: Exponential backoff, retry limits, exception handling.
"""
import pytest
import time
from unittest.mock import patch, MagicMock
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestRetryDecorator:
    """Test the retry_with_backoff decorator."""

    def test_retry_success_after_failure(self):
        """Test that retry succeeds after initial failures."""
        from src.services.core.amocrm_sync import retry_with_backoff
        
        call_count = 0
        
        @retry_with_backoff(max_retries=3, initial_delay=0.1, exceptions=(Exception,))
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = flaky_function()
        assert result == "success"
        assert call_count == 3

    def test_retry_exhaustion_raises(self):
        """Test that exception is raised after max retries."""
        from src.services.core.amocrm_sync import retry_with_backoff
        
        @retry_with_backoff(max_retries=3, initial_delay=0.1, exceptions=(Exception,))
        def always_fails():
            raise Exception("Always fails")
        
        with pytest.raises(Exception):
            always_fails()

    def test_retry_backoff_timing(self):
        """Test that backoff delays increase exponentially."""
        from src.services.core.amocrm_sync import retry_with_backoff
        
        delays = []
        original_sleep = time.sleep
        
        def mock_sleep(duration):
            delays.append(duration)
            # Don't actually sleep in tests
        
        @retry_with_backoff(max_retries=3, initial_delay=1, backoff_factor=2, exceptions=(Exception,))
        def flaky_with_timing():
            raise Exception("fail")
        
        with patch('time.sleep', mock_sleep):
            try:
                flaky_with_timing()
            except Exception:
                pass
        
        # Should have delays: 1, 2 (before each retry attempt after first)
        assert len(delays) == 2
        assert delays[0] == 1
        assert delays[1] == 2


class TestAmoCRMSyncMethods:
    """Test AmoCRM sync methods with retry."""

    @pytest.fixture
    def mock_amocrm(self):
        """Create a mock AmoCRM instance."""
        from src.services.core.amocrm_sync import AmoCRMSync
        
        with patch.dict(os.environ, {}, clear=True):
            amocrm = AmoCRMSync(
                subdomain="test",
                client_id="test_id",
                client_secret="test_secret",
                redirect_url="http://test/callback",
                token_file="/tmp/test_token.json"
            )
            return amocrm

    def test_create_lead_has_retry_decorator(self, mock_amocrm):
        """Verify create_lead_for_contact has retry decorator."""
        import inspect
        from src.services.core.amocrm_sync import retry_with_backoff
        
        # Check if method has retry decorator
        method = mock_amocrm.create_lead_for_contact
        # The decorator wraps the function
        assert hasattr(method, '__wrapped__') or 'retry' in str(method)

    def test_get_contact_has_retry_decorator(self, mock_amocrm):
        """Verify get_contact_by_phone has retry decorator."""
        method = mock_amocrm.get_contact_by_phone
        assert hasattr(method, '__wrapped__') or 'retry' in str(method)


class TestAmoCRMErrorHandling:
    """Test AmoCRM specific error handling."""

    def test_401_token_refresh(self):
        """Test that 401 triggers token refresh."""
        from src.services.core.amocrm_sync import AmoCRMSync
        
        with patch.dict(os.environ, {}, clear=True):
            amocrm = AmoCRMSync(
                subdomain="test",
                client_id="test_id",
                client_secret="test_secret",
                redirect_url="http://test/callback",
                token_file="/tmp/test_token.json"
            )
            
            # Mock refresh_token to return True
            amocrm.refresh_token = MagicMock(return_value=True)
            amocrm._load_token = MagicMock()
            amocrm.access_token = "test_token"
            
            # Mock requests.post to return 401 then 200
            with patch('requests.post') as mock_post:
                mock_post.side_effect = [
                    MagicMock(status_code=401, json=lambda: {}),
                    MagicMock(
                        status_code=200,
                        json=lambda: {"_embedded": {"leads": [{"id": 123}]}}
                    )
                ]
                
                # Should retry with token refresh
                result = amocrm.create_lead_for_contact(1, "Test Lead")
                
                # Token refresh should be called
                amocrm.refresh_token.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
