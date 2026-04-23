import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, List, Optional

import aiosqlite
import libsql

from src.settings import settings

logger = logging.getLogger(__name__)
HAS_SQLITE = True


def _setting_text(value: Any) -> str:
    if value is None:
        return ""
    getter = getattr(value, "get_secret_value", None)
    if callable(getter):
        try:
            value = getter()
        except Exception:
            value = str(value)
    return str(value).strip()


class SmartRow(dict):
    """
    Dict ko'rinishida ishlaydi, lekin int index bilan ham eski tuple kabi o'qiladi.
    """

    def __init__(self, values, columns):
        # Initialize as a dict: {col_name: value}
        data = dict(zip(columns, values))
        super().__init__(data)
        self._values = tuple(values)
        self._columns = list(columns)

    def __getitem__(self, key):
        if isinstance(key, int):
            try:
                return self._values[key]
            except IndexError:
                return None
        return super().get(key)

    def __iter__(self):
        return iter(self._values)

    def keys(self):
        return self._columns


class DatabasePool:
    """
    Turso/LibSQL uchun bitta ulanishni boshqaradi.
    """

    _instance = None
    _connection = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabasePool, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):
            # [ROOT CAUSE FIX] Explicitly strip all secrets to remove trailing newlines (\n) from Secret Manager
            self.url = _setting_text(settings.TURSO_DATABASE_URL).strip().replace("libsql://", "https://")
            self.auth_token = _setting_text(settings.TURSO_AUTH_TOKEN).strip()
            self.initialized = True
            logger.info(f"[DB POOL] Initialized for Turso backend (Cleaned Secrets). Protocol: {'https' if 'https' in self.url else 'libsql'}")

    def get_connection(self):
        if self._connection is None:
            try:
                url = self.url
                if url.startswith("libsql://"):
                    url = url.replace("libsql://", "https://")

                if self.auth_token:
                    self._connection = libsql.connect(url, auth_token=self.auth_token)
                else:
                    self._connection = libsql.connect(url)
                logger.debug("[DB POOL] New connection established.")
            except Exception as exc:
                logger.error(f"[DB POOL] Connection failed: {exc}")
                raise
        return self._connection

    async def execute(self, query: str, params: Optional[List[Any]] = None) -> List[SmartRow]:
        """Executes a SQL query asynchronously and returns SmartRows."""
        params = params or []
        conn = self.get_connection()

        def _run():
            res = conn.execute(query, params)
            
            # Extract column names - handle both libsql ResultSet and sqlite3 Cursor
            cols = []
            if hasattr(res, "columns"):
                cols = res.columns
            elif hasattr(res, "description") and res.description:
                cols = [d[0] for d in res.description]
            
            # If no columns and no description, it might be a DML (CREATE/INSERT/UPDATE)
            if not cols:
                return []
            
            # Convert results to SmartRow
            rows = []
            raw_rows = []
            try:
                # Try iterating directly
                raw_rows = list(res)
            except TypeError:
                # If not iterable, try fetchall()
                if hasattr(res, "fetchall"):
                    raw_rows = res.fetchall()
            
            for item in raw_rows:
                rows.append(SmartRow(item, cols))
            return rows

        try:
            return await asyncio.to_thread(_run)
        except Exception as exc:
            logger.error(f"❌ [DB POOL] Execution error: {exc} | Query: {query}")
            raise

    async def execute_one(self, query: str, params: Optional[List[Any]] = None) -> Optional[SmartRow]:
        """Convenience method to get a single row."""
        rows = await self.execute(query, params)
        return rows[0] if rows else None

    def close(self):
        if self._connection:
            try:
                self._connection.close()
                logger.info("[DB POOL] Connection released. 🛡️")
            except Exception as e:
                logger.warning(f"[DB POOL] Close error: {e}")
            finally:
                self._connection = None

# Legacy/Simple helper for direct access (optional)
@asynccontextmanager
async def get_db_connection():
    pool = DatabasePool()
    conn = pool.get_connection()
    try:
        yield conn
    finally:
        pass # Pool handles persistence
db_pool = DatabasePool()
