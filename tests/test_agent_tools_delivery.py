from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.tools import AgentToolExecutor
from src.services.core.tool_adapters import configure_userbot_group_fallback


@pytest.fixture(autouse=True)
def reset_userbot_fallback():
    configure_userbot_group_fallback(None)
    yield
    configure_userbot_group_fallback(None)


@pytest.mark.asyncio
async def test_forward_to_crm_group_uses_running_userbot_fallback():
    executor = AgentToolExecutor.__new__(AgentToolExecutor)
    executor.config = SimpleNamespace(CRM_GROUP_ID=-100123, CRM_TOPIC_ID=52)
    executor.bot_app = SimpleNamespace(bot=MagicMock())
    executor.bot_app.bot.send_message = AsyncMock(
        side_effect=RuntimeError("chat not found")
    )
    executor.db = SimpleNamespace()
    executor._db_call = AsyncMock(
        return_value={
            "first_name": "Mijoz",
            "phone": "+998000000000",
            "service_type": "Branding",
        }
    )
    executor._log_action = AsyncMock()
    userbot = MagicMock()
    userbot.send_message = AsyncMock()
    configure_userbot_group_fallback(userbot)

    result = await executor._forward_to_crm_group(123, "Sifatli", "Qisqa xulosa")

    assert result["success"] is True
    assert userbot.send_message.await_count == 1
    args, kwargs = userbot.send_message.await_args
    assert args[0] == -100123
    assert "SIFATLI LEAD" in args[1]
    assert kwargs["reply_to"] == 52
    assert kwargs["parse_mode"] == "html"
