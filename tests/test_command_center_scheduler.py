from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.schedulers.command_center_scheduler import send_command_center_digest
from src.services.core.telegram.bot_runtime import AiogramBotRuntime


class _TelethonLikeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text, kwargs))
        return SimpleNamespace(id=77)


class _AiogramBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, **kwargs):
        self.sent.append(kwargs)
        return SimpleNamespace(message_id=88)


async def _snapshot():
    return {
        "status": "attention_required",
        "summary": {
            "attention_items": 1,
            "ready_sections": 1,
            "total_sections": 4,
            "unavailable_sections": [],
        },
        "sections": {
            "sales": {
                "status": "ready",
                "items": [
                    {
                        "name": "Hot lead",
                        "priority": "high",
                        "priority_score": 80,
                    }
                ],
            }
        },
    }


@pytest.mark.asyncio
async def test_command_center_digest_sends_via_telethon_compatible_bot():
    bot = _TelethonLikeBot()

    sent = await send_command_center_digest(
        bot_client=bot,
        target_chat_id=-100123,
        snapshot_provider=_snapshot,
        topic_id=55,
    )

    assert sent is True
    assert bot.sent[0][0] == -100123
    assert "Oisha Command Center" in bot.sent[0][1]
    assert bot.sent[0][2]["reply_to"] == 55
    assert bot.sent[0][2]["link_preview"] is False


@pytest.mark.asyncio
async def test_command_center_digest_accepts_aiogram_runtime():
    bot = _AiogramBot()

    sent = await send_command_center_digest(
        bot_client=AiogramBotRuntime(bot),
        target_chat_id=-100123,
        snapshot_provider=_snapshot,
        topic_id=55,
    )

    assert sent is True
    assert bot.sent[0]["chat_id"] == -100123
    assert bot.sent[0]["message_thread_id"] == 55
    assert "Oisha Command Center" in bot.sent[0]["text"]


@pytest.mark.asyncio
async def test_command_center_digest_skips_without_target():
    bot = _TelethonLikeBot()

    sent = await send_command_center_digest(
        bot_client=bot,
        target_chat_id=None,
        snapshot_provider=_snapshot,
    )

    assert sent is False
    assert bot.sent == []


def test_boot_wires_command_center_digest_flag_without_userbot():
    text = open("src/boot.py", encoding="utf-8").read()

    assert "OISHA_COMMAND_CENTER_DIGEST_ENABLED" in text
    assert "command_center_digest_loop" in text
    assert "bot_client=bot_runtime" in text
