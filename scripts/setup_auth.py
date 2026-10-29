#!/usr/bin/env python3
"""Run auth migration and create initial API keys."""

import asyncio
import sys
from pathlib import Path

# Fix root path when running from command line
_ROOT = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path.cwd()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from src.database import Database
from src.api.auth import APIKeyManager


async def run_migration():
    """Run the auth tables migration."""
    db = Database()
    await db.init_instance()

    migration_path = _ROOT / "src" / "database" / "migrations" / "001_auth_tables.sql"
    sql = migration_path.read_text(encoding="utf-8")

    conn = await db.get_connection()
    for statement in sql.split(";"):
        stmt = statement.strip()
        if stmt:
            try:
                await conn.execute(stmt)
                print(f"[Migration] Executed: {stmt[:60]}...")
            except Exception as e:
                print(f"[Migration] Error: {e}")

    print("[Migration] Completed")


async def create_initial_keys():
    """Create initial API keys for existing integrations."""
    db = Database()
    await db.init_instance()
    manager = APIKeyManager(db)

    # Create key for JonOS Dashboard
    key, model = await manager.create_key(
        org_id="legacy",
        name="JonOS Dashboard",
        scopes=["read", "write", "admin"],
        rate_limit=10000,
        rate_window_seconds=60
    )
    print(f"[Auth] JonOS Dashboard API Key: {key}")

    # Create key for AmoCRM Webhook
    key, model = await manager.create_key(
        org_id="legacy",
        name="AmoCRM Webhook",
        scopes=["read", "write", "webhook"],
        rate_limit=5000,
        rate_window_seconds=60
    )
    print(f"[Auth] AmoCRM Webhook API Key: {key}")

    # Create key for External Integrations
    key, model = await manager.create_key(
        org_id="legacy",
        name="External Integrations",
        scopes=["read", "write"],
        rate_limit=2000,
        rate_window_seconds=60
    )
    print(f"[Auth] External Integrations API Key: {key}")


async def main():
    await run_migration()
    await create_initial_keys()


if __name__ == "__main__":
    asyncio.run(main())