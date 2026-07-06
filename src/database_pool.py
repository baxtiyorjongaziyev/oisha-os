import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, List, Optional

try:
    import libsql  # type: ignore[import]
except ImportError:
    import libsql_experimental as libsql  # type: ignore[import,no-redef]

from src.settings import settings
from src.db._helpers import normalize_turso_url, setting_text as _setting_text

logger = logging.getLogger(__name__)


def _is_resettable_connection_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    markers = (
        "10054",
        "forcibly closed",
        "connection error",
        "connection reset",
        "broken pipe",
        "stream not found",
        "hrana: stream not found",
        "hrana: connection",
    )
    return any(marker in message for marker in markers)


class SmartRow(dict):
    """
    Dict-like row that also supports index access.
    """

    def __init__(self, values, columns):
        data = dict(zip(columns, values))
        super().__init__(data)
        self._values = tuple(values)
        self._columns = list(columns)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().get(key)

    def keys(self):
        return self._columns


class DatabasePool:
    """
    Simple and robust Turso/LibSQL connection manager.
    """

    _instance = None
    _connection = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabasePool, cls).__new__(cls)
            cls._instance._circuit_open_until = 0
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):
            self.url = normalize_turso_url(_setting_text(settings.TURSO_DATABASE_URL))
            self.auth_token = _setting_text(settings.TURSO_AUTH_TOKEN)
            self.initialized = True
            self._circuit_open_until = 0
            logger.info(f"[DB POOL] Initialized for Turso: {self.url}")

    def configure(self, url: str, auth_token: str) -> None:
        """Point the pool at a new Turso endpoint and drop any live connection.

        Preferred over mutating ``url``/``auth_token`` directly so callers
        (e.g. ``ConnectionManager``) do not reach into pool internals.
        """
        new_url = normalize_turso_url(_setting_text(url))
        new_token = _setting_text(auth_token)
        if new_url == self.url and new_token == self.auth_token:
            return
        self.url = new_url
        self.auth_token = new_token
        self.close()

    def get_connection(self):
        if self._connection is None:
            try:
                if self.auth_token:
                    self._connection = libsql.connect(
                        self.url, auth_token=self.auth_token
                    )
                else:
                    self._connection = libsql.connect(self.url)
            except Exception as e:
                logger.error(f"[DB POOL] Connection failed: {e}")
                raise
        return self._connection

    async def execute(
        self, query: str, params: Optional[List[Any]] = None
    ) -> List[SmartRow]:
        params = params or []
        conn = self.get_connection()

        def _run():
            res = conn.execute(query, params)
            columns = getattr(res, "columns", None)
            if columns is None and getattr(res, "description", None):
                columns = [desc[0] for desc in res.description]
            columns = columns or []
            rows = res.fetchall()
            if rows is None:
                rows = []
            return [SmartRow(row, columns) for row in rows]

        # Use wait_for with retries to handle intermittent Turso connection drops
        import time
        for attempt in range(5):
            try:
                return await asyncio.wait_for(asyncio.to_thread(_run), timeout=45.0)
            except Exception as e:
                if attempt < 4 and _is_resettable_connection_error(e):
                    delay = min(2 ** attempt, 30)  # 1, 2, 4, 8, max 30 seconds
                    logger.warning(f"[DB POOL] Connection dropped ({str(e)}). Retrying ({attempt+1}/5) in {delay}s...")
                    self.close()
                    await asyncio.sleep(delay)
                    conn = self.get_connection()
                    continue
                raise
            except BaseException as e:
                if isinstance(e, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
                    raise
                # libsql can surface Rust panics as BaseException subclasses
                # (pyo3_runtime.PanicException). Reset the connection so a
                # transient bad handle does not turn /healthz into ASGI 500.
                self.close()
                if attempt < 4:
                    delay = min(2 ** attempt, 30)
                    logger.warning(
                        f"[DB POOL] Non-standard database error. Retrying ({attempt+1}/5) in {delay}s: {type(e).__name__}"
                    )
                    await asyncio.sleep(delay)
                    conn = self.get_connection()
                    continue
                raise RuntimeError(f"database_pool_failed:{type(e).__name__}") from e

    async def _run_connection_control(self, action: str) -> None:
        for attempt in range(3):
            conn = self.get_connection()
            method = getattr(conn, action, None)
            if not callable(method):
                return
            try:
                await asyncio.wait_for(asyncio.to_thread(method), timeout=45.0)
                return
            except Exception as exc:
                if attempt < 2 and _is_resettable_connection_error(exc):
                    logger.warning(
                        f"[DB POOL] {action} connection dropped. Retrying ({attempt+1}/3)..."
                    )
                    self.close()
                    continue
                raise

    async def commit(self) -> None:
        await self._run_connection_control("commit")

    async def rollback(self) -> None:
        await self._run_connection_control("rollback")

    def get_backend_name(self) -> str:
        return "turso"

    def close(self) -> None:
        conn = self._connection
        self._connection = None
        if conn is None:
            return
        close = getattr(conn, "close", None)
        if callable(close):
            close()


# Singleton instance
db_pool = DatabasePool()


@asynccontextmanager
async def get_db_connection():
    """Legacy helper for code compatibility."""
    yield db_pool.get_connection()
