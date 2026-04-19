"""
Shared pytest fixtures for Oisha-OS.

Most tests assume a throw-away local SQLite DB. The local .env file may set
TURSO_DATABASE_URL + TURSO_AUTH_TOKEN (often a placeholder), which would make
Database.get_connection() try to connect to Turso and fail in CI / local dev.

This conftest isolates every test from that env by forcing aiosqlite fallback.
Tests that specifically exercise Turso paths must opt in via the
`use_turso_env` fixture (to be added when needed).
"""

import os
import pytest


@pytest.fixture(autouse=True)
def _force_local_sqlite(monkeypatch):
    """Strip Turso env for every test so Database falls back to aiosqlite."""
    # Clear env (covers subprocess + re-read paths)
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)
    # Settings object is already instantiated on import — patch attributes too
    try:
        from src.settings import settings
        monkeypatch.setattr(settings, "TURSO_DATABASE_URL", None, raising=False)
        monkeypatch.setattr(settings, "TURSO_AUTH_TOKEN", None, raising=False)
    except Exception:
        pass
    yield
