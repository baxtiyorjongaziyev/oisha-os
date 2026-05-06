"""Alembic env.py — raw-SQL migration environment (no ORM models).

Because Oisha-OS uses aiosqlite / libsql directly (not SQLAlchemy ORM),
autogenerate is disabled.  Write every migration as explicit `op.execute(sql)`.

Usage:
  alembic revision -m "describe change"   # create new migration script
  alembic upgrade head                    # apply all pending migrations
  alembic downgrade -1                    # roll back one step
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Allow DATABASE_URL env var to override alembic.ini sqlalchemy.url.
# Use the SQLite URL only — Turso migrations are applied via CLI separately.
database_url = os.environ.get("DATABASE_URL")
if database_url and database_url.startswith("sqlite"):
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_url}")
elif not database_url:
    pass  # use alembic.ini default

# No SQLAlchemy metadata — autogenerate is intentionally disabled.
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (for SQL script generation)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live SQLite connection."""
    url = config.get_main_option("sqlalchemy.url")
    connectable = create_engine(url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
