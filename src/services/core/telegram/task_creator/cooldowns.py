"""
Cooldown management, persistence, and throttle state tracking mixin.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Dict, Optional
import structlog

from src.services.core.telegram.task_creator.dialogs import _maybe_await

logger = structlog.get_logger()


class CooldownManagerMixin:
    """Tracks and persists Gemini and Telegram resolution cooldowns."""

    _gemini_blocked_until = 0.0
    _telegram_blocked_until = 0.0
    _GEMINI_COOLDOWN_KEY = "telegram_task:gemini_blocked_until"
    _TELEGRAM_COOLDOWN_KEY = "telegram_task:telegram_blocked_until"

    @classmethod
    def _gemini_cooldown_remaining(cls) -> int:
        return max(0, int(cls._gemini_blocked_until - time.time()))

    @classmethod
    def _telegram_cooldown_remaining(cls) -> int:
        return max(0, int(cls._telegram_blocked_until - time.time()))

    def cooldown_seconds_remaining(self) -> int:
        """Return the longest active dependency cooldown for the task pipeline."""
        return max(
            self._gemini_cooldown_remaining(),
            self._telegram_cooldown_remaining(),
        )

    def cooldown_reason(self) -> Optional[str]:
        """Return the dependency currently imposing the longest cooldown."""
        gemini_remaining = self._gemini_cooldown_remaining()
        telegram_remaining = self._telegram_cooldown_remaining()
        if gemini_remaining >= telegram_remaining and gemini_remaining:
            return "gemini_quota"
        if telegram_remaining:
            return "telegram_entity_lookup"
        return None

    def is_cooling_down(self) -> bool:
        return self.cooldown_seconds_remaining() > 0

    def blocks_dialogue_analysis(self) -> bool:
        """Per-lead resolution handles flood-waits without blocking the whole scan."""
        return False

    def _pause_gemini(self) -> None:
        type(self)._gemini_blocked_until = (
            time.time() + self.gemini_cooldown_seconds
        )

    def _pause_telegram_resolution(self, error: Exception) -> int:
        match = re.search(r"wait of (\d+) seconds", str(error), flags=re.IGNORECASE)
        requested_seconds = int(match.group(1)) if match else 0
        cooldown_seconds = max(
            requested_seconds,
            self.telegram_flood_cooldown_seconds,
        )
        type(self)._telegram_blocked_until = time.time() + cooldown_seconds
        return cooldown_seconds

    async def _load_persisted_cooldowns(self) -> None:
        if self._cooldowns_loaded:
            return
        self._cooldowns_loaded = True
        get_state = getattr(self.db, "get_state", None)
        if not callable(get_state):
            return
        try:
            gemini_until = float(
                await _maybe_await(get_state(self._GEMINI_COOLDOWN_KEY, "0")) or 0
            )
            telegram_until = float(
                await _maybe_await(get_state(self._TELEGRAM_COOLDOWN_KEY, "0")) or 0
            )
            type(self)._gemini_blocked_until = max(
                type(self)._gemini_blocked_until,
                gemini_until,
            )
            type(self)._telegram_blocked_until = max(
                type(self)._telegram_blocked_until,
                telegram_until,
            )
        except Exception as exc:
            logger.debug("[TELEGRAM_TASK] Cooldown state load skipped: %s", exc)

    async def _persist_cooldowns(self) -> None:
        set_state = getattr(self.db, "set_state", None)
        if not callable(set_state):
            return
        try:
            await _maybe_await(
                set_state(
                    self._GEMINI_COOLDOWN_KEY,
                    str(type(self)._gemini_blocked_until),
                )
            )
            await _maybe_await(
                set_state(
                    self._TELEGRAM_COOLDOWN_KEY,
                    str(type(self)._telegram_blocked_until),
                )
            )
        except Exception as exc:
            logger.debug("[TELEGRAM_TASK] Cooldown state write skipped: %s", exc)
