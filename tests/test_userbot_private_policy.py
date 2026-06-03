from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import src.main as main
from src.services.core.safe_responder import SafeResponder


@pytest.mark.asyncio
async def test_safe_responder_blocks_private_dm_even_for_team_member():
    responder = SafeResponder()
    event = SimpleNamespace(
        out=False,
        is_private=True,
        is_group=False,
        chat_id=150074828,
        sender_id=150074828,
        raw_text="salom",
        message=SimpleNamespace(text="salom"),
        get_sender=AsyncMock(return_value=SimpleNamespace(username="baxtiyorjongaziyev")),
    )

    assert await responder.should_respond(event) is False


def test_private_userbot_reply_policy_defaults_to_block(monkeypatch):
    monkeypatch.delenv("USERBOT_DISABLE_PRIVATE_REPLIES", raising=False)
    event = SimpleNamespace(is_private=True, out=False)

    assert main._should_block_private_userbot_reply(event) is True


def test_private_userbot_reply_policy_allows_groups(monkeypatch):
    monkeypatch.delenv("USERBOT_DISABLE_PRIVATE_REPLIES", raising=False)
    event = SimpleNamespace(is_private=False, out=False)

    assert main._should_block_private_userbot_reply(event) is False


@pytest.mark.asyncio
async def test_negotiation_handler_ignores_private_dm_by_policy(monkeypatch):
    monkeypatch.setenv("ENABLE_AI_NEGOTIATION", "1")
    monkeypatch.delenv("USERBOT_DISABLE_PRIVATE_REPLIES", raising=False)
    event = SimpleNamespace(
        out=False,
        is_private=True,
        chat_id=77,
        message=SimpleNamespace(text="branding kerak"),
    )
    monkeypatch.setattr(main, "auto_lead_agent", SimpleNamespace(extract_lead_info=AsyncMock()))

    await main.negotiation_agent_handler(event)

    main.auto_lead_agent.extract_lead_info.assert_not_awaited()


@pytest.mark.asyncio
async def test_shadow_advisor_ignores_private_dm_by_policy(monkeypatch):
    monkeypatch.setenv("ENABLE_SHADOW_ADVISOR", "1")
    monkeypatch.delenv("USERBOT_DISABLE_PRIVATE_REPLIES", raising=False)
    event = SimpleNamespace(
        out=False,
        is_private=True,
        chat_id=77,
        message=SimpleNamespace(text="salom"),
    )
    advice = AsyncMock()
    monkeypatch.setattr(main, "run_autonomous_advice", advice)

    await main.shadow_advisor_handler(event)

    advice.assert_not_awaited()
