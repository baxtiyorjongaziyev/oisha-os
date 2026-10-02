import asyncio
import os
import socket
import subprocess  # nosec B404 - test spawns a short-lived local process
import sys
import types

import aiosqlite
import pytest

from src.services.core.telegram import session_store as ss


class _FakeOAuth:
    def __init__(self, conn):
        self._conn = conn

    async def _init_tables(self):
        await self._conn.execute(
            "CREATE TABLE IF NOT EXISTS oauth_tokens (service_name TEXT PRIMARY KEY, "
            "access_token TEXT, refresh_token TEXT, expires_at TEXT, updated_at TEXT, extra_data TEXT)"
        )

    async def _get_conn(self):
        return self._conn

    async def get_tokens(self, name):
        cur = await self._conn.execute(
            "SELECT access_token, expires_at FROM oauth_tokens WHERE service_name = ?", (name,)
        )
        row = await cur.fetchone()
        return {"access_token": row[0], "expires_at": row[1]} if row else None


def _dead_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])  # nosec B603
    proc.wait()
    return proc.pid


async def _acquire_with_holder(monkeypatch, holder: str) -> bool:
    conn = await aiosqlite.connect(":memory:")
    oauth = _FakeOAuth(conn)
    await oauth._init_tables()
    await conn.execute(
        "INSERT INTO oauth_tokens VALUES (?, ?, 'n/a', ?, ?, NULL)",
        (ss.OWNER_SERVICE_NAME, holder, ss._deadline_iso(ss.OWNER_TTL_SECS), ss._now_iso()),
    )
    await conn.commit()
    monkeypatch.setitem(sys.modules, "src.db", types.SimpleNamespace(get_db=lambda: types.SimpleNamespace(oauth=oauth)))
    try:
        return await ss._try_acquire_owner_async(force=False)
    finally:
        await conn.close()


def test_dead_local_holder_is_taken_over(monkeypatch):
    holder = f"{socket.gethostname()}:{_dead_pid()}"
    assert asyncio.run(_acquire_with_holder(monkeypatch, holder)) is True


@pytest.mark.parametrize(
    "holder",
    [
        f"{socket.gethostname()}:{os.getppid()}",  # shu hostda tirik jarayon
        "other-host:12345",  # boshqa mashina — TTL kutiladi
    ],
)
def test_live_or_remote_holder_is_respected(monkeypatch, holder):
    assert asyncio.run(_acquire_with_holder(monkeypatch, holder)) is False
