"""
Brain evolution loop — OishaBrain.evolve() ni muntazam ishga tushirish.

Usage:
    from src.schedulers.brain_evolution import brain_evolution_loop
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


async def brain_evolution_loop(oisha_brain: Optional[Any] = None) -> None:
    """Runs OishaBrain.evolve() every 6 hours to self-diagnose agent failures."""
    await asyncio.sleep(300)  # 5-minute boot delay
    while True:
        try:
            if oisha_brain:
                result = await oisha_brain.evolve(task="routine_health_check")
                logger.info(
                    "[BRAIN] Evolution cycle done: priority=%s component=%s",
                    result.get("priority"),
                    result.get("affected_component"),
                )
        except Exception as exc:
            logger.error("[BRAIN] Evolution loop error: %s", exc)
        await asyncio.sleep(21600)  # 6 hours
