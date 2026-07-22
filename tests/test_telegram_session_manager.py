import pytest

from src.services.core.telegram_session_manager import TelegramSessionManager


class FakeTelegramClient:
    def __init__(self):
        self.connected = False
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.session = object()

    async def connect(self):
        self.connect_calls += 1
        self.connected = True

    async def disconnect(self):
        self.disconnect_calls += 1
        self.connected = False

    async def is_user_authorized(self):
        return True

    def is_connected(self):
        return self.connected


@pytest.mark.asyncio
async def test_reconnect_reuses_existing_client(monkeypatch):
    monkeypatch.setenv("USERBOT_RECONNECT_MAX_ATTEMPTS", "1")
    manager = TelegramSessionManager(api_id=1, api_hash="hash", session_string="secret")
    fake_client = FakeTelegramClient()
    manager.client = fake_client

    assert await manager.connect() is True

    assert manager.client is fake_client
    assert fake_client.connect_calls == 1


@pytest.mark.asyncio
async def test_reconnect_monitor_defaults_to_forever(monkeypatch):
    monkeypatch.delenv("USERBOT_RECONNECT_MAX_ATTEMPTS", raising=False)
    manager = TelegramSessionManager(api_id=1, api_hash="hash", session_string="secret")

    assert manager.status["max_reconnect"] == 0
    assert manager.status["reconnect_forever"] is True


@pytest.mark.asyncio
async def test_auth_key_duplicated_stops_future_reconnects(monkeypatch):
    messages = []

    async def notify(message: str):
        messages.append(message)

    manager = TelegramSessionManager(
        api_id=1,
        api_hash="hash",
        session_string="secret",
        admin_notifier=notify,
    )
    fake_client = FakeTelegramClient()
    manager.client = fake_client

    await manager._handle_auth_key_duplicated()

    assert manager.status["fatal_auth_error"] is True
    assert manager._stop_event.is_set()
    assert fake_client.disconnect_calls == 1
    assert messages
