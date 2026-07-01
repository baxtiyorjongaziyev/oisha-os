"""Schema versioning and migration system for Oisha-OS database.

Usage:
    from src.db.migrations import MigrationRunner
    runner = MigrationRunner(conn)
    await runner.run_pending()
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class Migration:
    """Represents a single database migration."""

    def __init__(
        self,
        version: str,
        name: str,
        up_sql: str,
        down_sql: str = "",
    ):
        self.version = version
        self.name = name
        self.up_sql = up_sql
        self.down_sql = down_sql

    def __repr__(self) -> str:
        return f"Migration({self.version}, {self.name})"


class MigrationRunner:
    """Runs database migrations in order."""

    def __init__(self, conn_manager):
        self.conn_manager = conn_manager
        self._migrations: List[Migration] = []

    async def ensure_table(self) -> None:
        """Create schema_version table if not exists."""
        conn = await self.conn_manager.get_connection()
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version TEXT PRIMARY KEY,
                name TEXT,
                applied_at DATETIME
            )
        """)
        await conn.commit()

    async def get_applied_versions(self) -> set[str]:
        """Get set of already applied migration versions."""
        await self.ensure_table()
        conn = await self.conn_manager.get_connection()
        async with conn.execute(
            "SELECT version FROM schema_version"
        ) as cursor:
            rows = await cursor.fetchall()
            return {row[0] for row in rows}

    async def apply(self, migration: Migration) -> bool:
        """Apply a single migration if not already applied."""
        applied = await self.get_applied_versions()
        if migration.version in applied:
            return False

        conn = await self.conn_manager.get_connection()
        try:
            for statement in migration.up_sql.split(";"):
                statement = statement.strip()
                if statement:
                    await conn.execute(statement)
            now = datetime.now(timezone.utc).isoformat()
            await conn.execute(
                "INSERT INTO schema_version (version, name, applied_at) VALUES (?, ?, ?)",
                (migration.version, migration.name, now),
            )
            await conn.commit()
            logger.info("[Migration] Applied: %s - %s", migration.version, migration.name)
            return True
        except Exception as exc:
            await conn.rollback()
            logger.error(
                "[Migration] Failed: %s - %s: %s",
                migration.version, migration.name, exc,
            )
            raise

    async def rollback(self, migration: Migration) -> bool:
        """Rollback a migration."""
        applied = await self.get_applied_versions()
        if migration.version not in applied:
            return False

        if not migration.down_sql:
            raise ValueError(
                f"Migration {migration.version} has no down SQL for rollback"
            )

        conn = await self.conn_manager.get_connection()
        try:
            for statement in migration.down_sql.split(";"):
                statement = statement.strip()
                if statement:
                    await conn.execute(statement)
            await conn.execute(
                "DELETE FROM schema_version WHERE version = ?",
                (migration.version,),
            )
            await conn.commit()
            logger.info("[Migration] Rolled back: %s - %s", migration.version, migration.name)
            return True
        except Exception as exc:
            await conn.rollback()
            logger.error(
                "[Migration] Rollback failed: %s - %s: %s",
                migration.version, migration.name, exc,
            )
            raise

    def register(self, migration: Migration) -> None:
        """Register a migration."""
        self._migrations.append(migration)
        self._migrations.sort(key=lambda m: m.version)

    async def run_pending(self) -> int:
        """Run all pending migrations. Returns count of applied."""
        await self.ensure_table()
        applied = await self.get_applied_versions()
        count = 0
        for migration in self._migrations:
            if migration.version not in applied:
                await self.apply(migration)
                count += 1
        return count

    async def current_version(self) -> Optional[str]:
        """Get current schema version."""
        await self.ensure_table()
        conn = await self.conn_manager.get_connection()
        async with conn.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None
