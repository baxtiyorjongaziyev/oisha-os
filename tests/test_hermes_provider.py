"""Tests for Hermes Agent integration with Oisha-OS."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from src.services.core.ai.hermes_provider import (
    HermesAgentProvider,
    clean_hermes_output,
    get_hermes_provider,
    strip_ansi,
)
from src.services.utils.free_ai_router import FreeAIProviderRouter


def test_strip_ansi():
    raw = "\x1b[38;2;255;248;220mSalom Dunyo\x1b[0m"
    assert strip_ansi(raw) == "Salom Dunyo"


def test_clean_hermes_output_box_format():
    box_text = (
        "Query: Salom\n"
        "Initializing agent...\n"
        "────────────────────────────────────────\n\n"
        "╭─ ⚕ Hermes ───────────────────────────────────────────────────────────────────╮\n"
        "    Assalomu alaykum! Men Hermes Agentman.\n"
        "    Sizga qanday yordam bera olaman?\n"
        "╰──────────────────────────────────────────────────────────────────────────────╯\n\n"
        "Resume this session with:\n"
        "  hermes --resume 20261027_104829_338b8c\n"
    )
    cleaned = clean_hermes_output(box_text)
    assert "Assalomu alaykum! Men Hermes Agentman." in cleaned
    assert "Sizga qanday yordam bera olaman?" in cleaned
    assert "Resume this session" not in cleaned
    assert "Initializing agent" not in cleaned


def test_clean_hermes_output_fallback():
    fallback_text = (
        "Query: Hello\n"
        "Initializing agent...\n"
        "────────────────────────────────────────\n"
        "Here is the simple answer.\n"
        "Resume this session with: hermes --resume 12345"
    )
    cleaned = clean_hermes_output(fallback_text)
    assert cleaned == "Here is the simple answer."


def test_hermes_provider_availability():
    provider = get_hermes_provider()
    # It should detect hermes installed on this system
    assert provider.is_available() is True
    assert provider.find_executable() is not None


@pytest.mark.asyncio
async def test_free_ai_router_with_hermes():
    router = FreeAIProviderRouter()
    assert router.available("hermes") is True

    # Test mock generation
    with patch.object(
        HermesAgentProvider,
        "generate_response",
        new_callable=AsyncMock,
        return_value="Salom, men Hermes!",
    ):
        res = await router.generate_text("Salom", providers=("hermes",))
        assert res.provider == "hermes"
        assert res.text == "Salom, men Hermes!"
