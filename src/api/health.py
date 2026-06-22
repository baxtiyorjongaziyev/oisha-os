"""
Health check API server — Cloud Run compatibility.

Usage:
    from src.api.health import run_health_check_api, stop_health_check_api
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_health_api_server: Optional[object] = None


async def run_health_check_api() -> None:
    """Run the FastAPI health check server for Cloud Run compatibility.

    Handles port conflicts gracefully by logging warnings instead of crashing.
    """
    global _health_api_server

    try:
        from src.api_server import app as api_app
    except ImportError:
        logger.error(
            "[API] Could not import api_app. Health check server will not start."
        )
        return

    try:
        import uvicorn
    except ImportError:
        logger.error("[API] uvicorn not installed. Health check server will not start.")
        return

    config_uvicorn = uvicorn.Config(
        api_app,
        host="0.0.0.0",  # nosec
        port=int(os.environ.get("PORT", 8080)),
        log_level="info",
    )
    server = uvicorn.Server(config_uvicorn)
    _health_api_server = server
    try:
        await server.serve()
    except SystemExit:
        logger.warning(
            "[API] Uvicorn port band (yoki server conflict). API server skip qilindi, bot davom etadi."
        )
    except OSError as exc:
        logger.warning("[API] API server ishga tushmadi: %s. Bot davom etadi.", exc)
    finally:
        if _health_api_server is server:
            _health_api_server = None


async def stop_health_check_api(
    api_task: Optional[asyncio.Task], timeout_seconds: float = 5.0
) -> None:
    """Ask Uvicorn to finish its lifespan before the event loop is closed."""
    global _health_api_server
    server = _health_api_server
    if server is not None:
        server.should_exit = True

    if api_task is not None and not api_task.done():
        try:
            await asyncio.wait_for(
                asyncio.shield(api_task),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning("[SHUTDOWN] API server exceeded shutdown deadline; forcing.")
            api_task.cancel()
            await asyncio.gather(api_task, return_exceptions=True)

    _health_api_server = None
