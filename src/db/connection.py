"""Database connection management."""
from __future__ import annotations

import aiosqlite
import sqlite3
import asyncio
import structlog
import os
from contextlib import asynccontextmanager
from typing import Any, Optional

try:
    import libsql
    HAS_LIBSQL = True
except ImportError:
    HAS_LIBSQL = False

from src.settings import settings
from src.database_pool import db_pool
from src.db.turso import TursoAdapter  # noqa: F811 — override stub

logger = structlog.get_logger()


def _normalize_turso_url(url: str) -> str:
    if url.startswith("libsql://"):
        return "https://" + url[len("libsql://"):]
    return url


def _setting_text(value: Any) -> str:
    if value is None:
        return ""
    getter = getattr(value, "get_secret_value", None)
    if callable(getter):
        try:
            value = getter()
        except Exception as exc:
            logger.debug("[DB] Secret getter failed, using str: %s", exc)
            value = str(value)
    return str(value).lstrip("\ufeff").strip()


class ConnectionManager:
    """Manages database connections (Turso or SQLite)."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.path.join(os.getcwd(), "data", "bot.db")
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._conn: Optional[Any] = None
        self._state_backend = "sqlite"
        logger.info("[DB] ConnectionManager initialized: %s", self.db_path)

    async def get_connection(self) -> Any:
        """Get database connection (Turso or SQLite)."""
        turso_url = _normalize_turso_url(_setting_text(settings.TURSO_DATABASE_URL))
        turso_token = _setting_text(settings.TURSO_AUTH_TOKEN)

        if turso_url and turso_token and HAS_LIBSQL:
            if self._conn and isinstance(self._conn, TursoAdapter):
                self._state_backend = "turso"
                return self._conn

            try:
                db_pool.url = turso_url
                db_pool.auth_token = turso_token
                db_pool.close()

                def _probe_turso():
                    if turso_url == ":memory:":
                        conn = libsql.connect(turso_url)
                    else:
                        conn = libsql.connect(turso_url, auth_token=turso_token)
                    res = conn.execute("SELECT 1")
                    if hasattr(res, "fetchone"):
                        res.fetchone()
                    else:
                        list(res)
                    return conn

                probe_conn = await asyncio.wait_for(
                    asyncio.to_thread(_probe_turso), timeout=15.0
                )
                try:
                    pass
                finally:
                    try:
                        probe_conn.close()
                    except Exception as exc:
                        logger.debug("[DB] Probe conn close failed: %s", exc)

                self._conn = TursoAdapter()
                self._state_backend = "turso"
                return self._conn
            except Exception as exc:
                logger.warning("[DB] Turso probe failed, using SQLite: %s", exc)
                try:
                    db_pool.close()
                except Exception as exc:
                    logger.debug("[DB] Pool close failed: %s", exc)
                self._conn = None

        if (
            self._conn
            and not isinstance(self._conn, TursoAdapter)
        ):
            try:
                await self._conn.execute("SELECT 1")
                self._state_backend = "sqlite"
                return self._conn
            except (aiosqlite.Error, asyncio.TimeoutError, Exception):
                self._conn = None

        self._conn = await aiosqlite.connect(self.db_path, timeout=30)
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        self._state_backend = "sqlite"
        return self._conn

    @asynccontextmanager
    async def get_conn(self):
        """Async context manager for database connection."""
        conn = await self.get_connection()
        yield conn

    async def close(self):
        """Close database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    def get_backend_name(self) -> str:
        return self._state_backend
