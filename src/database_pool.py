"""
Database connection pooling for Oisha-OS.
Supports both SQLite (with aiosqlite pool) and PostgreSQL (with asyncpg).
This enables better performance under high concurrent load.
"""
import os
import asyncio
import logging
from typing import Optional, List, Any, Dict
from contextlib import asynccontextmanager
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import database drivers
try:
    import aiosqlite
    HAS_SQLITE = True
except ImportError:
    HAS_SQLITE = False

try:
    import asyncpg
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False


@dataclass
class PoolConfig:
    """Configuration for connection pool."""
    min_size: int = 2
    max_size: int = 10
    command_timeout: float = 60.0
    max_inactive_time: float = 300.0  # Close connections after 5 min idle


class ConnectionPool:
    """
    Async database connection pool.
    
    Supports SQLite (via aiosqlite connection pool) and PostgreSQL.
    SQLite is used for local/single-instance deployments.
    PostgreSQL is used for production/scaled deployments.
    """
    
    def __init__(
        self,
        database_url: Optional[str] = None,
        config: Optional[PoolConfig] = None,
        sqlite_path: Optional[str] = None
    ):
        self.config = config or PoolConfig()
        self._pool: Optional[Any] = None
        self._sqlite_path = sqlite_path or "bot_database.db"
        self._database_url = database_url or os.environ.get("DATABASE_URL")
        self._lock = asyncio.Lock()
        self._is_postgres = False
        
        # Determine database type
        if self._database_url and self._database_url.startswith("postgresql://"):
            self._is_postgres = True
            if not HAS_POSTGRES:
                raise ImportError(
                    "PostgreSQL support requires asyncpg. "
                    "Install with: pip install asyncpg"
                )
        else:
            if not HAS_SQLITE:
                raise ImportError("SQLite support requires aiosqlite")
    
    async def initialize(self):
        """Initialize the connection pool."""
        async with self._lock:
            if self._pool is not None:
                return
            
            if self._is_postgres:
                await self._init_postgres_pool()
            else:
                await self._init_sqlite_pool()
            
            logger.info(f"[DB POOL] Initialized ({'PostgreSQL' if self._is_postgres else 'SQLite'})")
    
    async def _init_postgres_pool(self):
        """Initialize PostgreSQL connection pool."""
        if not HAS_POSTGRES:
            raise RuntimeError("asyncpg not installed")
        
        self._pool = await asyncpg.create_pool(
            self._database_url,
            min_size=self.config.min_size,
            max_size=self.config.max_size,
            command_timeout=self.config.command_timeout,
            max_inactive_time=self.config.max_inactive_time
        )
    
    async def _init_sqlite_pool(self):
        """
        Initialize SQLite 'pool' (connection manager).
        
        SQLite doesn't support true connection pooling like PostgreSQL,
        but we simulate it with connection reuse and WAL mode.
        """
        # For SQLite, we maintain persistent connections
        # that are checked out and returned
        self._pool = SQLiteConnectionPool(
            db_path=self._sqlite_path,
            max_connections=self.config.max_size
        )
        await self._pool.initialize()
    
    @asynccontextmanager
    async def acquire(self):
        """
        Acquire a connection from the pool.
        
        Usage:
            async with pool.acquire() as conn:
                await conn.execute("SELECT 1")
        """
        if self._pool is None:
            await self.initialize()
        
        if self._is_postgres:
            async with self._pool.acquire() as conn:
                yield conn
        else:
            conn = await self._pool.acquire()
            try:
                yield conn
            finally:
                await self._pool.release(conn)
    
    async def execute(self, query: str, *args) -> str:
        """
        Execute a query without returning results.
        
        Args:
            query: SQL query string
            *args: Query parameters
            
        Returns:
            Status message
        """
        async with self.acquire() as conn:
            if self._is_postgres:
                await conn.execute(query, *args)
            else:
                await conn.execute(query, args)
            return "OK"
    
    async def fetchone(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """
        Fetch a single row.
        
        Args:
            query: SQL query string
            *args: Query parameters
            
        Returns:
            Dict representing the row, or None
        """
        async with self.acquire() as conn:
            if self._is_postgres:
                row = await conn.fetchrow(query, *args)
                return dict(row) if row else None
            else:
                async with conn.execute(query, args) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        columns = [desc[0] for desc in cursor.description]
                        return dict(zip(columns, row))
                    return None
    
    async def fetchall(self, query: str, *args) -> List[Dict[str, Any]]:
        """
        Fetch all rows.
        
        Args:
            query: SQL query string
            *args: Query parameters
            
        Returns:
            List of dicts representing rows
        """
        async with self.acquire() as conn:
            if self._is_postgres:
                rows = await conn.fetch(query, *args)
                return [dict(row) for row in rows]
            else:
                async with conn.execute(query, args) as cursor:
                    rows = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    return [dict(zip(columns, row)) for row in rows]
    
    async def close(self):
        """Close the connection pool."""
        if self._pool:
            if self._is_postgres:
                await self._pool.close()
            else:
                await self._pool.close()
            self._pool = None
            logger.info("[DB POOL] Closed")


class SQLiteConnectionPool:
    """
    SQLite connection pool implementation.
    
    Manages multiple persistent connections with WAL mode.
    """
    
    def __init__(self, db_path: str, max_connections: int = 10):
        self.db_path = db_path
        self.max_connections = max_connections
        self._available: asyncio.Queue = asyncio.Queue()
        self._in_use: set = set()
        self._lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self):
        """Initialize the pool with connections."""
        if self._initialized:
            return
        
        async with self._lock:
            # Create initial connections
            for _ in range(min(2, self.max_connections)):
                conn = await self._create_connection()
                await self._available.put(conn)
            
            self._initialized = True
    
    async def _create_connection(self) -> aiosqlite.Connection:
        """Create a new SQLite connection with optimizations."""
        conn = await aiosqlite.connect(self.db_path, timeout=30)
        
        # Performance optimizations
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        await conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        await conn.execute("PRAGMA temp_store=MEMORY")
        await conn.execute("PRAGMA mmap_size=268435456")  # 256MB mmap
        
        # Enable foreign keys
        await conn.execute("PRAGMA foreign_keys=ON")
        
        return conn
    
    async def acquire(self) -> aiosqlite.Connection:
        """Acquire a connection from the pool."""
        # Fast path: try to get from available queue
        try:
            conn = self._available.get_nowait()
            async with self._lock:
                self._in_use.add(id(conn))
            return conn
        except asyncio.QueueEmpty:
            pass
        
        # Slow path: create new connection or wait
        async with self._lock:
            if len(self._in_use) < self.max_connections:
                conn = await self._create_connection()
                self._in_use.add(id(conn))
                return conn
        
        # Wait for a connection to become available
        conn = await self._available.get()
        async with self._lock:
            self._in_use.add(id(conn))
        return conn
    
    async def release(self, conn: aiosqlite.Connection):
        """Release a connection back to the pool."""
        async with self._lock:
            self._in_use.discard(id(conn))
        
        # Test connection is still alive
        try:
            await conn.execute("SELECT 1")
            await self._available.put(conn)
        except Exception:
            # Connection is dead, close it
            try:
                await conn.close()
            except Exception:
                pass
    
    async def close(self):
        """Close all connections."""
        # Close in-use connections
        async with self._lock:
            while not self._available.empty():
                try:
                    conn = self._available.get_nowait()
                    await conn.close()
                except Exception:
                    pass
        
        self._initialized = False


# Global pool instance
_pool_instance: Optional[ConnectionPool] = None


async def get_pool(
    database_url: Optional[str] = None,
    sqlite_path: Optional[str] = None,
    force_new: bool = False
) -> ConnectionPool:
    """
    Get or create the global connection pool.
    
    Args:
        database_url: PostgreSQL connection string (optional)
        sqlite_path: Path to SQLite database (optional)
        force_new: Force creation of new pool instance
        
    Returns:
        ConnectionPool instance
    """
    global _pool_instance
    
    if _pool_instance is None or force_new:
        _pool_instance = ConnectionPool(
            database_url=database_url,
            sqlite_path=sqlite_path
        )
        await _pool_instance.initialize()
    
    return _pool_instance


def get_pool_sync() -> Optional[ConnectionPool]:
    """Get the global pool instance (non-async)."""
    return _pool_instance


async def close_pool():
    """Close the global connection pool."""
    global _pool_instance
    if _pool_instance:
        await _pool_instance.close()
        _pool_instance = None
