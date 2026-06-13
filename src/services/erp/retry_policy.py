from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


RETRY_DELAYS_SECONDS = (30, 120, 600, 1800, 7200)
MAX_ATTEMPTS = 5


@dataclass(frozen=True)
class RetryPolicy:
    delays_seconds: tuple[int, ...] = RETRY_DELAYS_SECONDS
    max_attempts: int = MAX_ATTEMPTS

    def delay_for_attempt(self, attempt_number: int) -> int:
        if not self.delays_seconds:
            return 0
        index = max(0, min(int(attempt_number) - 1, len(self.delays_seconds) - 1))
        return int(self.delays_seconds[index])

    def is_permanent(self, error: BaseException) -> bool:
        status_code = self._status_code(error)
        if status_code is None:
            return False
        return 400 <= status_code < 500 and status_code not in {408, 429}

    def should_retry(self, error: BaseException, attempt_number: int) -> bool:
        return (
            int(attempt_number) < int(self.max_attempts)
            and not self.is_permanent(error)
        )

    @staticmethod
    def _status_code(error: BaseException) -> Optional[int]:
        value = getattr(error, "status_code", None)
        if value is None:
            response = getattr(error, "response", None)
            value = getattr(response, "status_code", None)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
