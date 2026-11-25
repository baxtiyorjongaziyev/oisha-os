"""Userbot single-host guard: prod session faqat prod hostda, bitta jarayonda."""
import os
import sys

import pytest
from telethon.crypto import AuthKey
from telethon.sessions import StringSession

from src.services.core.telegram import userbot_host_guard as guard


def _session_string(seed: int) -> str:
    s = StringSession()
    s.set_dc(2, "149.154.167.51", 443)
    s.auth_key = AuthKey(bytes([seed]) * 256)
    return s.save()


PROD = _session_string(1)
DEV = _session_string(2)


class _FakeClient:
    def __init__(self, session_string: str):
        self.session = StringSession(session_string)


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    monkeypatch.setenv("USERBOT_SESSION_STRING", PROD)
    monkeypatch.delenv("TELEGRAM_MCP_SESSION_STRING", raising=False)
    monkeypatch.setenv("ALLOW_LOCAL_RUN", "1")
    monkeypatch.setenv("OISHA_USERBOT_LOCK_FILE", str(tmp_path / "userbot.lock"))
    monkeypatch.setattr(guard, "_lock_fd", None)
    yield
    if guard._lock_fd is not None:
        os.close(guard._lock_fd)
        guard._lock_fd = None


def test_prod_session_blocked_on_non_prod_host_even_with_allow_local(monkeypatch):
    monkeypatch.setattr(guard, "is_prod_host", lambda *a, **k: False)
    with pytest.raises(guard.UserbotHostGuardError):
        guard.check_client(_FakeClient(PROD))


def test_dev_session_allowed_on_non_prod_host(monkeypatch):
    monkeypatch.setattr(guard, "is_prod_host", lambda *a, **k: False)
    guard.check_client(_FakeClient(DEV))  # raise yoʼq
    assert guard._lock_fd is None


def test_mcp_equal_to_prod_rejected(monkeypatch):
    monkeypatch.setenv("TELEGRAM_MCP_SESSION_STRING", PROD)
    with pytest.raises(guard.UserbotHostGuardError):
        guard.assert_mcp_session_distinct()
    monkeypatch.setenv("TELEGRAM_MCP_SESSION_STRING", DEV)
    guard.assert_mcp_session_distinct()


def test_is_prod_host_requires_marker_and_hostname(tmp_path):
    marker = tmp_path / "oisha-prod-host"
    assert not guard.is_prod_host(str(marker), hostname="jon-ai-prod-01")
    marker.write_text("1")
    assert guard.is_prod_host(str(marker), hostname="jon-ai-prod-01")
    assert not guard.is_prod_host(str(marker), hostname="laptop")


@pytest.mark.skipif(sys.platform == "win32", reason="fcntl faqat POSIX")
def test_second_instance_on_prod_host_refused(monkeypatch, tmp_path):
    import fcntl

    monkeypatch.setattr(guard, "is_prod_host", lambda *a, **k: True)
    lock = str(tmp_path / "userbot.lock")
    other = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)  # "birinchi jarayon"
    try:
        with pytest.raises(guard.UserbotHostGuardError, match="allaqachon"):
            guard.check_client(_FakeClient(PROD))
    finally:
        os.close(other)
    guard.check_client(_FakeClient(PROD))  # lock boʼshagach ruxsat
    assert guard._lock_fd is not None


@pytest.mark.asyncio
async def test_installed_connect_blocks_before_network(monkeypatch):
    from telethon import TelegramClient

    import src  # noqa: F401 — install() src import da chaqiriladi

    monkeypatch.setattr(guard, "is_prod_host", lambda *a, **k: False)
    client = TelegramClient(StringSession(PROD), 1, "x")
    with pytest.raises(guard.UserbotHostGuardError):
        await client.connect()


def test_error_messages_never_contain_session():
    try:
        guard.check_client(_FakeClient(PROD))
    except guard.UserbotHostGuardError as exc:
        assert PROD not in str(exc)
