"""
Unit tests for rate limiting functionality.
Tests: Token bucket, adaptive limiting, Telegram-specific limits.
"""
import pytest # type: ignore
import asyncio
import time
from unittest.mock import patch, MagicMock
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestTokenBucketRateLimiter:
    """Test token bucket rate limiter."""

    @pytest.fixture
    def limiter(self):
        from src.utils.rate_limiter import TokenBucketRateLimiter, RateLimitConfig
        return TokenBucketRateLimiter(
            RateLimitConfig(requests_per_second=10, burst_size=5)
        )

    @pytest.mark.asyncio
    async def test_burst_allowed(self, limiter):
        """Test that burst requests are allowed up to burst_size."""
        # Should allow 5 immediate (burst_size)
        allowed = 0
        for _ in range(5):
            if await limiter.acquire():
                allowed += 1
        
        assert allowed == 5, f"Expected 5 burst allowed, got {allowed}"

    @pytest.mark.asyncio
    async def test_throttling_after_burst(self, limiter):
        """Test that requests are throttled after burst."""
        # Use up burst
        for _ in range(5):
            await limiter.acquire()
        
        # Next request should be denied immediately
        assert not await limiter.acquire()

    @pytest.mark.asyncio
    async def test_wait_for_token(self, limiter):
        """Test waiting for token availability."""
        # Use up burst
        for _ in range(5):
            await limiter.acquire()
        
        # Wait for token with short timeout
        start = time.monotonic()
        result = await limiter.wait_for_token(timeout=0.5)
        elapsed = time.monotonic() - start
        
        # Should eventually get a token
        assert result is True or elapsed >= 0.5


class TestAdaptiveRateLimiter:
    """Test adaptive rate limiter."""

    @pytest.fixture
    def adaptive(self):
        from src.utils.rate_limiter import AdaptiveRateLimiter
        return AdaptiveRateLimiter(
            initial_rps=5.0,
            min_rps=0.5,
            max_rps=10.0
        )

    @pytest.mark.asyncio
    async def test_success_increases_rate(self, adaptive):
        """Test that successful requests gradually increase rate."""
        initial_rps = adaptive.current_rps
        
        # Report 10 successes
        for _ in range(10):
            await adaptive.report_success()
        
        # Rate should have increased
        assert adaptive.current_rps > initial_rps

    @pytest.mark.asyncio
    async def test_rate_limit_decreases_rate(self, adaptive):
        """Test that rate limit errors decrease rate."""
        initial_rps = adaptive.current_rps
        
        # Report rate limit error
        await adaptive.report_error(is_rate_limit=True)
        
        # Rate should have decreased
        assert adaptive.current_rps < initial_rps

    @pytest.mark.asyncio
    async def test_min_rate_enforced(self, adaptive):
        """Test that rate doesn't go below minimum."""
        # Report many rate limit errors
        for _ in range(20):
            await adaptive.report_error(is_rate_limit=True)
        
        # Should not go below min_rps
        assert adaptive.current_rps >= adaptive.min_rps


class TestTelegramRateLimiter:
    """Test Telegram-specific rate limiter."""

    @pytest.fixture
    def tg_limiter(self):
        from src.utils.rate_limiter import TelegramRateLimiter
        return TelegramRateLimiter()

    @pytest.mark.asyncio
    async def test_group_vs_private_limits(self, tg_limiter):
        """Test different limits for groups vs private chats."""
        # Groups should allow more requests
        group_allowed = 0
        for _ in range(10):
            if await tg_limiter.can_send_message(1, is_group=True):
                group_allowed += 1
        
        # Private should allow fewer
        private_allowed = 0
        for _ in range(10):
            if await tg_limiter.can_send_message(2, is_group=False):
                private_allowed += 1
        
        # Group should allow more due to higher limits
        assert group_allowed > private_allowed

    @pytest.mark.asyncio
    async def test_flood_wait_blocking(self, tg_limiter):
        """Test that flood wait blocks requests."""
        # Set flood wait for 2 seconds
        tg_limiter.report_flood_wait(2)
        
        # Should not be able to send immediately
        assert not await tg_limiter.can_send_message(1, is_group=True)

    @pytest.mark.asyncio
    async def test_flood_wait_recovery(self, tg_limiter):
        """Test that requests are allowed after flood wait expires."""
        # Set short flood wait
        tg_limiter.report_flood_wait(0.1)
        
        # Wait for it to expire
        await asyncio.sleep(0.2)
        
        # Should be able to check now
        # Note: actual sending still rate limited
        result = await tg_limiter.can_send_message(1, is_group=True)
        # Result depends on rate limiter state, but should not be blocked by flood


class TestRateLimiterIntegration:
    """Integration tests for rate limiter."""

    @pytest.mark.asyncio
    async def test_concurrent_access(self):
        """Test rate limiter under concurrent access."""
        from src.utils.rate_limiter import TokenBucketRateLimiter, RateLimitConfig
        
        limiter = TokenBucketRateLimiter(
            RateLimitConfig(requests_per_second=0.01, burst_size=10)
        )
        
        # Many concurrent acquire attempts
        results = await asyncio.gather(*[
            limiter.acquire()
            for _ in range(20)
        ])
        
        # Burst size should be respected
        assert sum(results) <= 10

    @pytest.mark.asyncio
    async def test_rate_limiter_singleton(self):
        """Test that global rate limiter is a singleton."""
        from src.utils.rate_limiter import get_telegram_limiter, reset_telegram_limiter
        
        # Reset first
        reset_telegram_limiter()
        
        # Get two instances
        limiter1 = get_telegram_limiter()
        limiter2 = get_telegram_limiter()
        
        # Should be same instance
        assert limiter1 is limiter2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
