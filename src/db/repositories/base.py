"""Base repository class for database operations."""
from __future__ import annotations

import structlog
from typing import Any, Dict, List, Optional

logger = structlog.get_logger()


def _is_benign_schema_error(exc: Exception) -> bool:
    message = str(exc).lower()
    if not message:
        return False
    markers = (
        "duplicate column name",
        "already exists",
        "duplicate key name",
        "column already exists",
    )
    return any(marker in message for marker in markers)


class BaseRepository:
    """Base class for all repositories."""

    def __init__(self, conn_manager):
        self.conn_manager = conn_manager
        self._get_conn_fn = None

    def set_connection_factory(self, get_conn_fn):
        """Set a connection factory (used by Database to allow monkeypatching)."""
        self._get_conn_fn = get_conn_fn

    async def _get_conn(self):
        """Get connection — uses factory if set, else conn_manager."""
        if self._get_conn_fn:
            return await self._get_conn_fn()
        return await self.conn_manager.get_connection()

    async def _execute(self, sql: str, params: tuple = ()) -> Any:
        """Execute a query and return the cursor."""
        conn = await self._get_conn()
        return await conn.execute(sql, params)

    async def _fetch_one(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Fetch a single row."""
        cursor = await self._execute(sql, params)
        row = await cursor.fetchone()
        if row is None:
            return None
        if isinstance(row, dict):
            # Turso/libsql rows (SmartRow) are already {column: value} dicts.
            # zip(columns, row) would iterate dict keys, not values.
            return dict(row)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        return dict(zip(columns, row)) if columns else row

    async def _fetch_all(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Fetch all rows."""
        cursor = await self._execute(sql, params)
        rows = await cursor.fetchall()
        if rows and isinstance(rows[0], dict):
            return [dict(row) for row in rows]
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        return [dict(zip(columns, row)) for row in rows] if columns else rows

    async def _fetch_all_flat(self, sql: str, params: tuple = ()) -> List[Any]:
        """Fetch all rows as flat list (for single-column results)."""
        cursor = await self._execute(sql, params)
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def _execute_many(self, sql: str, params_list: List[tuple]) -> None:
        """Execute many queries."""
        conn = await self._get_conn()
        await conn.executemany(sql, params_list)

    @staticmethod
    def _is_safe_identifier(name: str) -> bool:
        return (
            bool(name)
            and all(ch.isascii() and (ch.isalnum() or ch == "_") for ch in name)
            and not name[0].isdigit()
        )

    async def _get_table_column_types(self, table_name: str) -> dict[str, str]:
        """Get mapping of column names to SQLite declared types (Turso-safe)."""
        if not self._is_safe_identifier(table_name):
            raise ValueError(f"Invalid SQLite identifier: {table_name!r}")
        conn = await self._get_conn()
        rows: list = []
        from_pragma_stmt = False
        try:
            cursor = await conn.execute(
                "SELECT name, type FROM pragma_table_info(?)",
                (table_name,),
            )
            rows = list(await cursor.fetchall())
        except Exception:
            rows = []
        if not rows:
            try:
                cursor = await conn.execute(f"PRAGMA table_info({table_name})")
                rows = list(await cursor.fetchall())
                from_pragma_stmt = True
            except Exception:
                rows = []
        result: dict[str, str] = {}
        for row in rows:
            if hasattr(row, "keys"):
                name = str(row["name"])
                col_type = str(row["type"] or "")
            elif from_pragma_stmt:
                name = str(row[1])
                col_type = str(row[2] or "")
            else:
                name = str(row[0])
                col_type = str((row[1] if len(row) > 1 else "") or "")
            if name:
                result[name] = col_type
        return result

    async def _get_table_columns(self, table_name: str) -> set[str]:
        """Get column names for a table."""
        return set(await self._get_table_column_types(table_name))

    async def _add_column_if_missing(self, table: str, column: str, col_type: str) -> None:
        """Add a column if it doesn't exist."""
        existing = await self._get_table_columns(table)
        if column in existing:
            return
        try:
            await self._execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        except Exception as exc:
            # "duplicate column" / "already exists" — ustun aslida bor,
            # ``_get_table_columns`` (PRAGMA) uni ba'zi backendlarda
            # ko'rmagan. Bu kutilgan holat: jimgina qaytamiz, aks holda
            # har boot'da har mavjud ustun uchun to'liq traceback spam
            # bo'ladi va /healthz probe'ini bo'g'adi.
            if _is_benign_schema_error(exc):
                logger.debug(
                    "[DB] ADD COLUMN %s.%s allaqachon mavjud — o'tkazib yuborildi",
                    table, column,
                )
                return
            logger.error(
                "[DB] ADD COLUMN %s.%s muvaffaqiyatsiz: %s",
                table, column, type(exc).__name__, exc_info=True,
            )
            raise
