import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

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
    return str(value).lstrip("\ufeff").strip()


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


@dataclass
class PoolConfig:
    min_size: int = 2
    max_size: int = 10
    command_timeout: float = 60.0


class SQLiteConnectionPool:
    def __init__(self, db_path: str, max_connections: int = 10):
        self.db_path = db_path
        self.max_connections = max_connections
        self._queue: asyncio.Queue[aiosqlite.Connection] = asyncio.Queue(maxsize=max_connections)
        self._connections: List[aiosqlite.Connection] = []
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        for _ in range(self.max_connections):
            conn = await aiosqlite.connect(self.db_path, timeout=30)
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA foreign_keys=ON")
            await conn.execute("PRAGMA synchronous=NORMAL")
            await conn.commit()
            self._connections.append(conn)
            await self._queue.put(conn)
        self._initialized = True

    async def acquire(self) -> aiosqlite.Connection:
        if not self._initialized:
            await self.initialize()
        return await self._queue.get()

    async def release(self, conn: aiosqlite.Connection) -> None:
        if conn in self._connections:
            await self._queue.put(conn)

    async def close(self) -> None:
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        for conn in list(self._connections):
            await conn.close()
        self._connections.clear()
        self._initialized = False


class ConnectionPool:
    def __init__(
        self,
        database_url: Optional[str] = None,
        sqlite_path: str = "bot_database.db",
        config: Optional[PoolConfig] = None,
    ):
        self.database_url = database_url or ""
        self.sqlite_path = sqlite_path
        self.config = config or PoolConfig()
        self._is_postgres = self.database_url.startswith(("postgres://", "postgresql://"))
        self._pool: Optional[Any] = None

    async def initialize(self) -> None:
        if self._is_postgres:
            raise RuntimeError("PostgreSQL pool is not configured in this runtime")
        self._pool = SQLiteConnectionPool(self.sqlite_path, max_connections=self.config.max_size)
        await self._pool.initialize()

    @asynccontextmanager
    async def acquire(self):
        if self._pool is None:
            await self.initialize()
        conn = await self._pool.acquire()
        try:
            yield conn
        finally:
            await self._pool.release(conn)

    def _normalize_params(self, params: tuple[Any, ...]) -> tuple[Any, ...]:
        if len(params) == 1 and isinstance(params[0], (tuple, list)):
            return tuple(params[0])
        return params

    async def execute(self, query: str, *params: Any) -> None:
        async with self.acquire() as conn:
            await conn.execute(query, self._normalize_params(params))
            await conn.commit()

    async def fetchone(self, query: str, *params: Any) -> Optional[Dict[str, Any]]:
        async with self.acquire() as conn:
            async with conn.execute(query, self._normalize_params(params)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row is not None else None

    async def fetchall(self, query: str, *params: Any) -> List[Dict[str, Any]]:
        async with self.acquire() as conn:
            async with conn.execute(query, self._normalize_params(params)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None


_pool_instance: Optional[ConnectionPool] = None


async def get_pool(
    database_url: Optional[str] = None,
    sqlite_path: str = "bot_database.db",
    config: Optional[PoolConfig] = None,
) -> ConnectionPool:
    global _pool_instance
    if _pool_instance is None:
        _pool_instance = ConnectionPool(database_url=database_url, sqlite_path=sqlite_path, config=config)
        await _pool_instance.initialize()
    return _pool_instance


async def close_pool() -> None:
    global _pool_instance
    if _pool_instance is not None:
        await _pool_instance.close()
        _pool_instance = None


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
