import asyncio
import logging
from typing import Any, List, Optional

import libsql

from src.settings import settings

logger = logging.getLogger(__name__)


class SmartRow(dict):
    """
    Dict ko'rinishida ishlaydi, lekin int index bilan ham eski tuple kabi o'qiladi.
    """

    def __init__(self, values, columns):
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
            self.url = str(settings.TURSO_DATABASE_URL or "")
            self.auth_token = settings.TURSO_AUTH_TOKEN.get_secret_value() if settings.TURSO_AUTH_TOKEN else ""
            self.initialized = True
            logger.info("[DB POOL] Initialized for Turso backend.")

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
                logger.info("[DB POOL] New connection established.")
            except Exception as exc:
                logger.error(f"[DB POOL] Connection failed: {exc}")
                raise
        return self._connection

    async def execute(self, query: str, params: Optional[List[Any]] = None) -> List[SmartRow]:
        params = params or []
        conn = self.get_connection()

        def _run():
            result = conn.execute(query, params)
            description = getattr(result, "description", None)
            columns = getattr(result, "columns", None)

            normalized_columns: List[str] = []
            if description:
                for column in description:
                    if isinstance(column, (list, tuple)) and column:
                        normalized_columns.append(str(column[0]))
                    else:
                        normalized_columns.append(str(getattr(column, "name", column)))
            elif columns:
                normalized_columns = [str(column) for column in columns]

            if hasattr(result, "fetchall"):
                raw_rows = result.fetchall() or []
            else:
                raw_rows = getattr(result, "rows", None)
                if raw_rows is None:
                    try:
                        raw_rows = list(result)
                    except TypeError:
                        raw_rows = []

            if not normalized_columns:
                return []

            rows: List[SmartRow] = []
            for item in raw_rows or []:
                if isinstance(item, SmartRow):
                    rows.append(item)
                    continue

                if isinstance(item, dict):
                    values = [item.get(column) for column in normalized_columns]
                else:
                    try:
                        values = list(item)
                    except TypeError:
                        if len(normalized_columns) == 1:
                            values = [item]
                        else:
                            values = [getattr(item, column, None) for column in normalized_columns]
                rows.append(SmartRow(values, normalized_columns))
            return rows

        try:
            return await asyncio.to_thread(_run)
        except Exception as exc:
            logger.error(f"[DB POOL] Execution error: {exc} | Query: {query}")
            raise

    async def execute_one(self, query: str, params: Optional[List[Any]] = None) -> Optional[SmartRow]:
        rows = await self.execute(query, params)
        return rows[0] if rows else None

    def close(self):
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = None
            logger.info("[DB POOL] Connection released.")


db_pool = DatabasePool()
