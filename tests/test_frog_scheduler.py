from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.schedulers.frog_scheduler as frog_scheduler
from src.services.core.telegram.bot_runtime import AiogramBotRuntime


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def fetchall(self):
        return self._rows

    async def fetchone(self):
        return self._rows[0] if self._rows else None


class _Conn:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []

    async def execute(self, query, params=None):
        self.executed.append((query, params))
        return _Cursor(self.rows)

    async def commit(self):
        return None


class _Db:
    def __init__(self, rows):
        self.conn = _Conn(rows)

    async def get_connection(self):
        return self.conn


class _BotClient:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text, kwargs))
        return SimpleNamespace(id=99)


class _Frog:
    most_important_task_id = 7
    profit_estimate = 1500
    motivation_message = "Bugun shu qurbaqani yeymiz!"


@pytest.mark.asyncio
async def test_frog_brief_uses_bot_client(monkeypatch):
    db = _Db([(7, "Task", "Desc", 1, 1500)])
    bot_client = _BotClient()

    monkeypatch.setattr(frog_scheduler, "get_db", lambda: db)
    monkeypatch.setattr(
        frog_scheduler,
        "FrogAgent",
        lambda: SimpleNamespace(identify_frog=lambda tasks: _async_value(_Frog())),
    )

    await frog_scheduler.send_daily_frog_brief(bot_client=bot_client, team_group_id=-100123)

    assert len(bot_client.sent) == 1
    assert bot_client.sent[0][0] == -100123
    assert "Qurbaqani yeymiz!" in bot_client.sent[0][1]
    assert bot_client.sent[0][2]["parse_mode"] == "html"


class _AiogramBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, **kwargs):
        self.sent.append(kwargs)
        return SimpleNamespace(message_id=100)


@pytest.mark.asyncio
async def test_frog_brief_accepts_aiogram_runtime(monkeypatch):
    db = _Db([(7, "Task", "Desc", 1, 1500)])
    aiogram_bot = _AiogramBot()

    monkeypatch.setattr(frog_scheduler, "get_db", lambda: db)
    monkeypatch.setattr(
        frog_scheduler,
        "FrogAgent",
        lambda: SimpleNamespace(identify_frog=lambda tasks: _async_value(_Frog())),
    )

    await frog_scheduler.send_daily_frog_brief(
        bot_client=AiogramBotRuntime(aiogram_bot),
        team_group_id=-100123,
    )

    assert len(aiogram_bot.sent) == 1
    assert aiogram_bot.sent[0]["chat_id"] == -100123
    assert aiogram_bot.sent[0]["parse_mode"] == "HTML"


class _MockComposioService:
    async def fetch_tasks(self):
        return [
            {
                "title": "Uchrashuv Buyurtmachi A $1500",
                "description": "Important call",
                "priority": "High",
                "profit_estimate": 1500,
                "external_task_id": "trello_123",
                "source_manager": "trello",
            }
        ]


@pytest.mark.asyncio
async def test_frog_brief_with_composio(monkeypatch):
    db = _Db([])
    bot_client = _BotClient()

    class MockSettings:
        FROG_SOURCE = "composio"
        COMPOSIO_API_KEY = "test_key"
        COMPOSIO_GOOGLE_TASKLIST_ID = None
        COMPOSIO_TRELLO_BOARD_ID = None

    import src.settings as src_settings
    monkeypatch.setattr(src_settings, "settings", MockSettings())
    monkeypatch.setattr(frog_scheduler, "get_db", lambda: db)
    import src.services.core.composio_tasks as composio_tasks
    monkeypatch.setattr(
        composio_tasks,
        "ComposioTaskService",
        _MockComposioService,
    )
    monkeypatch.setattr(
        frog_scheduler,
        "FrogAgent",
        lambda: SimpleNamespace(identify_frog=lambda tasks: _async_value(_Frog())),
    )

    await frog_scheduler.send_daily_frog_brief(bot_client=bot_client, team_group_id=-100123)

    assert len(db.conn.executed) > 0
    queries = [q[0] for q in db.conn.executed]
    assert any("INSERT INTO tasks" in q for q in queries)


async def _async_value(value):
    return value
