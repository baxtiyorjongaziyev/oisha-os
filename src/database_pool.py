import logging
import asyncio
from typing import Optional, List, Any, Dict, Union
import libsql
from src.settings import settings

logger = logging.getLogger(__name__)

class SmartRow(dict):
    """
    A dictionary that also supports integer indexing for backward compatibility.
    Behaves like a sqlite3.Row or a tuple when subscripted with an int.
    """
    def __init__(self, values, columns):
        # Initialize as a dict: {col_name: value}
        # Filter out None values from zip if columns/values lengths differ
        data = dict(zip(columns, values))
        super().__init__(data)
        self._values = tuple(values)
        self._columns = columns

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
    Managed database pool for Turso/LibSQL.
    Optimized for resource conservation and Cloud Run connection management.
    """
    _instance = None
    _connection = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabasePool, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.url = str(settings.TURSO_DATABASE_URL)
            self.auth_token = settings.TURSO_AUTH_TOKEN.get_secret_value() if settings.TURSO_AUTH_TOKEN else ""
            self.initialized = True
            logger.info(f"👸 [DB POOL] Initialized for Cloud Core: {self.url[:15]}...🌩️")

    def get_connection(self):
        """Returns a synchronized connection."""
        if self._connection is None:
            try:
                # libsql native package is best used with https/libsql urls
                url = self.url
                if url.startswith("libsql://"):
                    url = url.replace("libsql://", "https://")
                
                self._connection = libsql.connect(url, auth_token=self.auth_token)
                logger.info("[DB POOL] 🚀 New secure connection established.")
            except Exception as e:
                logger.error(f"❌ [DB POOL] Connection failed: {e}")
                raise
        return self._connection

    async def execute(self, query: str, params: List[Any] = None) -> List[SmartRow]:
        """Executes a SQL query asynchronously and returns SmartRows."""
        params = params or []
        conn = self.get_connection()
        
        def _run():
            res = conn.execute(query, params)
            if not hasattr(res, 'columns'):
                return []
            
            cols = res.columns
            # In modern libsql, res is iterable and yields Row objects
            # We convert each row (which might not be subscriptable) to a list first
            rows = []
            for item in res:
                try:
                    # Try to convert to list/tuple to ensure subscriptability
                    val_list = list(item)
                except TypeError:
                    # Fallback for weird objects
                    val_list = [item[i] for i in range(len(cols))]
                rows.append(SmartRow(val_list, cols))
            return rows
            
        try:
            return await asyncio.to_thread(_run)
        except Exception as e:
            logger.error(f"❌ [DB POOL] Execution error: {e} | Query: {query}")
            raise

    async def execute_one(self, query: str, params: List[Any] = None) -> Optional[SmartRow]:
        """Helper to get a single row."""
        rows = await self.execute(query, params)
        return rows[0] if rows else None

    def close(self):
        """Closes the connection."""
        if self._connection:
            try:
                self._connection.close()
            except:
                pass
            self._connection = None
            logger.info("[DB POOL] Connection released. 🛡️")

# Global instance for easy access
db_pool = DatabasePool()
