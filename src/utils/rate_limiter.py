"""
Rate limiting utilities for Telegram API and other external services.
Implements token bucket algorithm for smooth request distribution.
"""
import asyncio
import time
from typing import Optional, Dict
from dataclasses import dataclass, field
from collections import deque
import logging

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_second: float = 1.0
    burst_size: int = 5
    retry_after: float = 1.0


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter for API calls.
    
    Allows bursts up to burst_size, then throttles to requests_per_second.
    """
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.tokens: float = config.burst_size
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> bool:
        """
        Acquire a token to make a request.
        
        Returns:
            bool: True if token acquired, False if should wait
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            
            # Add tokens based on elapsed time
            self.tokens = min(
                self.config.burst_size,
                self.tokens + elapsed * self.config.requests_per_second
            )
            self.last_update = now
            
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            
            return False
    
    async def wait_for_token(self, timeout: Optional[float] = None) -> bool:
        """
        Wait until a token is available.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            bool: True if token acquired, False if timeout
        """
        start_time = time.monotonic()
        
        while True:
            if await self.acquire():
                return True
            
            if timeout and (time.monotonic() - start_time) > timeout:
                return False
            
            # Calculate wait time for next token
            wait_time = (1 - self.tokens) / self.config.requests_per_second
            await asyncio.sleep(max(0.1, wait_time))


class AdaptiveRateLimiter:
    """
    Adaptive rate limiter that adjusts based on API responses.
    
    Automatically slows down when receiving 429 (Too Many Requests) errors.
    """
    
    def __init__(
        self,
        initial_rps: float = 1.0,
        min_rps: float = 0.1,
        max_rps: float = 10.0,
        backoff_factor: float = 0.5,
        recovery_factor: float = 1.1
    ):
        self.current_rps = initial_rps
        self.min_rps = min_rps
        self.max_rps = max_rps
        self.backoff_factor = backoff_factor
        self.recovery_factor = recovery_factor
        
        self.success_count = 0
        self.error_count = 0
        self.last_error_time: Optional[float] = None
        
        self._lock = asyncio.Lock()
        self._limiter = TokenBucketRateLimiter(
            RateLimitConfig(
                requests_per_second=initial_rps,
                burst_size=max(1, int(initial_rps * 2))
            )
        )
    
    async def acquire(self) -> bool:
        """Acquire permission to make a request."""
        return await self._limiter.wait_for_token(timeout=30)
    
    async def report_success(self):
        """Report a successful API call."""
        async with self._lock:
            self.success_count += 1
            
            # Gradually increase rate after consistent success
            if self.success_count >= 10:
                self.current_rps = min(
                    self.max_rps,
                    self.current_rps * self.recovery_factor
                )
                self._update_limiter()
                self.success_count = 0
    
    async def report_error(self, is_rate_limit: bool = False):
        """
        Report an API error.
        
        Args:
            is_rate_limit: True if error was 429 Too Many Requests
        """
        async with self._lock:
            self.error_count += 1
            self.last_error_time = time.monotonic()
            
            if is_rate_limit:
                # Aggressive backoff for rate limit errors
                self.current_rps = max(
                    self.min_rps,
                    self.current_rps * self.backoff_factor
                )
                self._update_limiter()
                self.success_count = 0
                
                logger.warning(
                    f"[RATE LIMIT] Backing off to {self.current_rps:.2f} req/s"
                )
    
    def _update_limiter(self):
        """Update the underlying limiter with new rate."""
        self._limiter = TokenBucketRateLimiter(
            RateLimitConfig(
                requests_per_second=self.current_rps,
                burst_size=max(1, int(self.current_rps * 2))
            )
        )


class TelegramRateLimiter:
    """
    Rate limiter specifically optimized for Telegram API.
    
    Handles:
    - Message sending limits (30 msgs/sec in groups, 1 msg/sec in private)
    - Flood wait errors (retry-after handling)
    - Different limits for different chat types
    """
    
    def __init__(self):
        # Per-chat rate limiters
        self._group_limiter = TokenBucketRateLimiter(
            RateLimitConfig(requests_per_second=20, burst_size=10)
        )
        self._private_limiter = TokenBucketRateLimiter(
            RateLimitConfig(requests_per_second=1, burst_size=1)
        )
        
        # Global flood protection
        self._flood_wait_until: Optional[float] = None
        self._adaptive = AdaptiveRateLimiter(
            initial_rps=1.0,
            min_rps=0.1,
            max_rps=5.0
        )
    
    async def can_send_message(
        self,
        chat_id: int,
        is_group: bool = False
    ) -> bool:
        """
        Check if a message can be sent to the given chat.
        
        Args:
            chat_id: The target chat ID
            is_group: True if chat is a group/channel
            
        Returns:
            bool: True if allowed to send
        """
        # Check global flood wait
        if self._flood_wait_until and time.monotonic() < self._flood_wait_until:
            return False
        
        # Use appropriate limiter
        limiter = self._group_limiter if is_group else self._private_limiter
        
        return await limiter.acquire()
    
    async def wait_to_send(
        self,
        chat_id: int,
        is_group: bool = False,
        timeout: float = 60.0
    ) -> bool:
        """
        Wait until allowed to send a message.
        
        Args:
            chat_id: Target chat ID
            is_group: True if chat is a group/channel
            timeout: Maximum wait time
            
        Returns:
            bool: True if allowed, False if timeout
        """
        start = time.monotonic()
        
        while time.monotonic() - start < timeout:
            if await self.can_send_message(chat_id, is_group):
                return True
            await asyncio.sleep(0.5)
        
        return False
    
    def report_flood_wait(self, retry_after: int):
        """
        Report a flood wait error from Telegram.
        
        Args:
            retry_after: Seconds to wait (from Telegram API)
        """
        wait_until = time.monotonic() + retry_after
        
        if self._flood_wait_until is None or wait_until > self._flood_wait_until:
            self._flood_wait_until = wait_until
            logger.warning(
                f"[TELEGRAM RATE LIMIT] Flood wait: {retry_after}s"
            )
        
        # Also notify adaptive limiter
        asyncio.create_task(self._adaptive.report_error(is_rate_limit=True))
    
    async def execute_with_limit(
        self,
        chat_id: int,
        is_group: bool,
        coro
    ):
        """
        Execute a coroutine with rate limiting.
        
        Args:
            chat_id: Target chat ID
            is_group: True if chat is a group
            coro: The coroutine to execute
            
        Returns:
            Result of the coroutine
        """
        if not await self.wait_to_send(chat_id, is_group):
            raise TimeoutError("Rate limit timeout")
        
        try:
            result = await coro
            await self._adaptive.report_success()
            return result
        except Exception as e:
            # Check if it's a flood wait error
            if "FLOOD_WAIT" in str(e) or "Too Many Requests" in str(e):
                # Extract retry_after if available
                retry_after = 60  # Default
                await self._adaptive.report_error(is_rate_limit=True)
            raise


# Global rate limiter instance
_telegram_limiter: Optional[TelegramRateLimiter] = None


def get_telegram_limiter() -> TelegramRateLimiter:
    """Get the global Telegram rate limiter instance."""
    global _telegram_limiter
    if _telegram_limiter is None:
        _telegram_limiter = TelegramRateLimiter()
    return _telegram_limiter


def reset_telegram_limiter():
    """Reset the global rate limiter (useful for testing)."""
    global _telegram_limiter
    _telegram_limiter = None
