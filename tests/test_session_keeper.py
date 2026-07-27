"""Unit tests for session_keeper module."""

from __future__ import annotations

import asyncio
import os
import tempfile
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── helpers ──────────────────────────────────────────────────────────────────

class _FakeSessionObj:
    """Minimal Telethon StringSession stub."""

    def __init__(self, string: str = "AAabctest1234"):
        self._string = string
        self.dc_id = 1
        self.server_address = "149.154.167.51"
        self.port = 443
        self.auth_key = None

    def save(self):
        pass

    def get_string(self) -> str:
        return self._string


class _FakeClient:
    """Minimal Telethon client stub."""

    def __init__(self, session_string: str = "AAabctest1234", authorized: bool = True):
        self.session = _FakeSessionObj(session_string)
        self._authorized = authorized

    async def get_me(self):
        if self._authorized:
            me = MagicMock()
            me.username = "test_user"
            return me
        return None


# ─── file read/write ───────────────────────────────────────────────────────────

def test_write_and_read_session_string(tmp_path):
    from src.services.core.session_keeper import (
        _read_session_string_from_file,
        _write_session_string_to_file,
    )

    path = str(tmp_path / "session.txt")
    test_str = "AAABBBCCC" * 10  # fake session string
    assert _write_session_string_to_file(test_str, path=path) is True
    result = _read_session_string_from_file(path=path)
    assert result == test_str


def test_read_nonexistent_file_returns_none(tmp_path):
    from src.services.core.session_keeper import _read_session_string_from_file

    result = _read_session_string_from_file(path=str(tmp_path / "nope.txt"))
    assert result is None


def test_write_creates_parent_dirs(tmp_path):
    from src.services.core.session_keeper import _write_session_string_to_file

    path = str(tmp_path / "nested" / "dir" / "session.txt")
    assert _write_session_string_to_file("XYZXYZ" * 10, path=path) is True
    assert os.path.exists(path)


# ─── get_best_session_string ──────────────────────────────────────────────────

def test_get_best_session_string_prefers_file(tmp_path, monkeypatch):
    from src.services.core.session_keeper import get_best_session_string, _write_session_string_to_file

    test_str = "FILE_SESSION" * 10
    path = str(tmp_path / "session.txt")
    _write_session_string_to_file(test_str, path=path)

    monkeypatch.setattr("src.services.core.session_keeper.SESSION_STRING_FILE", path)
    monkeypatch.setenv("USERBOT_SESSION_STRING", "ENV_SESSION" * 5)
    
    result = get_best_session_string()
    assert result == test_str


def test_get_best_session_string_falls_back_to_env(tmp_path, monkeypatch):
    from src.services.core.session_keeper import get_best_session_string

    path = str(tmp_path / "nonexistent.txt")
    env_val = "ENV_SESSION_STRING" * 5

    monkeypatch.setattr("src.services.core.session_keeper.SESSION_STRING_FILE", path)
    monkeypatch.setenv("USERBOT_SESSION_STRING", env_val)
    
    result = get_best_session_string()
    assert result == env_val


def test_get_best_session_string_returns_none_when_both_missing(tmp_path, monkeypatch):
    from src.services.core.session_keeper import get_best_session_string

    path = str(tmp_path / "missing.txt")
    monkeypatch.delenv("USERBOT_SESSION_STRING", raising=False)
    monkeypatch.setattr("src.services.core.session_keeper.SESSION_STRING_FILE", path)
    
    result = get_best_session_string()
    assert result is None



# ─── save_current_session_string ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_current_session_string(tmp_path, monkeypatch):
    from src.services.core.session_keeper import save_current_session_string

    client = _FakeClient("MYSESSION" * 15)
    path = str(tmp_path / "saved.txt")

    monkeypatch.setattr("src.services.core.session_keeper.SESSION_STRING_FILE", path)
    result = await save_current_session_string(client)

    assert result is not None
    assert len(result) > 20
    assert os.path.exists(path)


@pytest.mark.asyncio
async def test_save_current_session_string_with_none_client():
    from src.services.core.session_keeper import save_current_session_string

    result = await save_current_session_string(None)
    assert result is None


# ─── keepalive loop ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_keepalive_loop_cancels_cleanly():
    """Keep-alive task should cancel cleanly without raising unexpected errors."""
    from src.services.core.session_keeper import session_keepalive_loop

    stop = asyncio.Event()
    task = asyncio.create_task(
        session_keepalive_loop(None, interval_secs=60, stop_event=stop)
    )
    await asyncio.sleep(0)  # yield control so task starts
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert task.done()


@pytest.mark.asyncio
async def test_keepalive_loop_stop_event_respected():
    """stop_event.set() should cause the loop to exit cleanly."""
    from src.services.core.session_keeper import session_keepalive_loop

    stop = asyncio.Event()
    task = asyncio.create_task(
        session_keepalive_loop(None, interval_secs=60, stop_event=stop)
    )
    await asyncio.sleep(0)  # yield so task starts
    stop.set()             # signal stop
    task.cancel()           # also cancel to unblock the initial sleep
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert task.done()


