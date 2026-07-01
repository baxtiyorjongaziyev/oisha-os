"""Turso/libsql adapter classes — extracted from database.py for separation of concerns."""
from __future__ import annotations

import structlog
from typing import Any, List

from src.database_pool import db_pool

logger = structlog.get_logger()


def _normalize_cursor_description(result_set: Any) -> List[Any]:
    description = getattr(result_set, "description", None)
    if description:
        return list(description)
    columns = getattr(result_set, "columns", None) or []
    return [(str(col), None, None, None, None, None, None) for col in columns]


def _extract_prefetched_rows(result_set: Any) -> List[Any]:
    if result_set is None:
        return []
    rows = getattr(result_set, "rows", None)
    if rows is not None:
        try:
            return list(rows)
        except TypeError:
            return []
    try:
        return list(result_set)
    except TypeError:
        return []


class _TursoCursor:
    """aiosqlite.Cursor-compatible cursor for Turso."""

    def __init__(self, rows=None, description=None):
        self._rows = _extract_prefetched_rows(rows)
        self._description = description or _normalize_cursor_description(rows)
        self._ptr = 0
        self.rowcount = len(self._rows)
        self.description = self._description

    async def fetchone(self):
        if self._ptr < len(self._rows):
            row = self._rows[self._ptr]
            self._ptr += 1
            return row
        return None

    async def fetchall(self):
        remaining = self._rows[self._ptr:]
        self._ptr = len(self._rows)
        return remaining

    async def fetchmany(self, size=1):
        end = min(self._ptr + size, len(self._rows))
        chunk = self._rows[self._ptr:end]
        self._ptr = end
        return chunk

    async def close(self):
        self._rows = []
        self._ptr = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        row = await self.fetchone()
        if row is None:
            raise StopAsyncIteration
        return row

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class _EmptyResultSet:
    """Placeholder for no-op PRAGMA responses."""

    columns = []
    description = []
    rows_affected = 0
    rowcount = 0

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def fetchmany(self, size=1):
        return []

    def close(self):
        return None

    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0


class _ExecuteProxy:
    """Dual-mode result of TursoAdapter.execute(sql, ...)."""

    def __init__(self, sql, parameters):
        self._sql = sql
        self._params = parameters
        self._cursor = None

    async def _run(self):
        sql = self._sql or ""
        if sql.lstrip().upper().startswith("PRAGMA"):
            return _TursoCursor(_EmptyResultSet())
        rows = await db_pool.execute(sql, self._params)
        desc = None
        if rows:
            desc = [(k, None, None, None, None, None, None) for k in rows[0].keys()]
        return _TursoCursor(rows, desc)

    def __await__(self):
        return self._run().__await__()

    async def __aenter__(self):
        self._cursor = await self._run()
        return self._cursor

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class _CursorContext:
    def __init__(self, conn):
        self._conn = conn
        self._cursor = _TursoCursor(_EmptyResultSet())

    async def __aenter__(self):
        return self._cursor

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._cursor.close()

    async def execute(self, sql, parameters=None):
        proxy = self._conn.execute(sql, parameters)
        self._cursor = await proxy
        return self._cursor

    async def executemany(self, sql, parameter_list):
        return await self._conn.executemany(sql, parameter_list)

    async def fetchone(self):
        return await self._cursor.fetchone()


class TursoAdapter:
    """aiosqlite-compatible adapter for Turso/libsql."""

    def __init__(self):
        self.row_factory = None

    def execute(self, sql, parameters=None):
        return _ExecuteProxy(sql, parameters)

    async def executemany(self, sql, parameter_list):
        affected = 0
        for params in parameter_list or []:
            await db_pool.execute(sql, params)
            affected += 1
        cursor = _TursoCursor()
        cursor.rowcount = affected
        return cursor

    async def executescript(self, script):
        statements = [
            stmt.strip() for stmt in (script or "").split(";") if stmt.strip()
        ]
        for statement in statements:
            await db_pool.execute(statement, None)
        return _TursoCursor(_EmptyResultSet())

    async def commit(self):
        await db_pool.commit()

    async def rollback(self):
        await db_pool.rollback()

    async def close(self):
        try:
            db_pool.close()
        except Exception as exc:
            logger.debug("[DB] Turso pool close warning: %s", exc)

    def cursor(self):
        return _CursorContext(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
