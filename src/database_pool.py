import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import aiosqlite
import libsql

from src.settings import settings

logger = logging.getLogger(__name__)

def _setting_text(value: Any) -> str:
    if value is None:
        return ""
    getter = getattr(value, "get_secret_value", None)
    if callable(getter):
        try:
            value = getter()
        except Exception:
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
            self.url = _setting_text(settings.TURSO_DATABASE_URL).replace("libsql://", "https://")
            self.auth_token = _setting_text(settings.TURSO_AUTH_TOKEN)
            self.initialized = True
            logger.info(f"[DB POOL] Initialized for Turso: {self.url}")

    def get_connection(self):
        if self._connection is None:
            try:
                if self.auth_token:
                    self._connection = libsql.connect(self.url, auth_token=self.auth_token)
                else:
                    self._connection = libsql.connect(self.url)
            except Exception as e:
                logger.error(f"[DB POOL] Connection failed: {e}")
                raise
        return self._connection

    async def execute(self, query: str, params: Optional[List[Any]] = None) -> List[SmartRow]:
        params = params or []
        conn = self.get_connection()
        
        def _run():
            res = conn.execute(query, params)
            columns = res.columns
            return [SmartRow(row, columns) for row in res.fetchall()]

        return await asyncio.get_event_loop().run_in_executor(None, _run)

    def get_backend_name(self) -> str:
        return "turso"


# Singleton instance
db_pool = DatabasePool()

@asynccontextmanager
async def get_db_connection():
    """Legacy helper for code compatibility."""
    yield db_pool.get_connection()
