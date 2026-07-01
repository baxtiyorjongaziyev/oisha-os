import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, List, Optional

try:
    import libsql  # type: ignore[import]
except ImportError:
    import libsql_experimental as libsql  # type: ignore[import,no-redef]

from src.settings import settings

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
        "hrana",
    )
    return any(marker in message for marker in markers)


def _setting_text(value: Any) -> str:
    if value is None:
        return ""
    getter = getattr(value, "get_secret_value", None)
    if callable(getter):
        try:
            value = getter()
        except Exception as exc:
            logger.debug("[DB POOL] Secret getter failed, using str: %s", exc)
            value = str(value)

    # Remove BOM and all invisible/whitespace characters
    text = str(value).replace("\ufeff", "").strip()
    # Remove any other potential control characters
    return "".join(char for char in text if ord(char) >= 32)


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
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):
            self.url = _setting_text(settings.TURSO_DATABASE_URL).replace(
                "libsql://", "https://"
            )
            self.auth_token = _setting_text(settings.TURSO_AUTH_TOKEN)
            self.initialized = True
            logger.info(f"[DB POOL] Initialized for Turso: {self.url}")

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
        for attempt in range(3):
            try:
                return await asyncio.wait_for(asyncio.to_thread(_run), timeout=45.0)
            except Exception as e:
                if attempt < 2 and _is_resettable_connection_error(e):
                    logger.warning(f"[DB POOL] Connection dropped. Retrying ({attempt+1}/3)...")
                    self.close()  # Reset connection
                    conn = self.get_connection()  # Get new one
                    continue
                raise
            except BaseException as e:
                if isinstance(e, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
                    raise
                # libsql can surface Rust panics as BaseException subclasses
                # (pyo3_runtime.PanicException). Reset the connection so a
                # transient bad handle does not turn /healthz into ASGI 500.
                self.close()
                if attempt < 2:
                    logger.warning(
                        f"[DB POOL] Non-standard database error. Retrying ({attempt+1}/3): {type(e).__name__}"
                    )
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
