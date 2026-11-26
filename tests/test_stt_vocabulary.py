"""Tests for STT proper-noun prompt hints and spelling normalization."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.call_analytics.stt_vocabulary import (
    STT_PROPER_NOUNS_PROMPT,
    build_caller_stt_context,
    is_mumtozmaxal_phone,
    normalize_name_spellings,
)


def test_is_mumtozmaxal_phone_matches_formats():
    assert is_mumtozmaxal_phone("+998773220098") is True
    assert is_mumtozmaxal_phone("998773220098") is True
    assert is_mumtozmaxal_phone("+998 77 322-00-98") is True
    assert is_mumtozmaxal_phone("773220098") is True
    assert is_mumtozmaxal_phone("+998901234567") is False
    assert is_mumtozmaxal_phone("") is False


def test_build_caller_stt_context_triggers_for_mumtozmaxal():
    ctx_phone = build_caller_stt_context(caller_phone="+998773220098")
    assert "Mumtozmaxal" in ctx_phone
    assert "+998773220098" in ctx_phone

    ctx_mgr = build_caller_stt_context(manager_name="Mumtozmaxal Normurodova")
    assert "Mumtozmaxal" in ctx_mgr

    assert build_caller_stt_context(caller_phone="+998901112233", manager_name="Rayxon") == ""


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Assalomu alaykum, men Mumtoz mahalman", "Assalomu alaykum, men Mumtozmaxalman"),
        ("Mumtozmahal qoʻngʻiroq qildi", "Mumtozmaxal qoʻngʻiroq qildi"),
        ("Мумтоз махал bilan gaplashdik", "Mumtozmaxal bilan gaplashdik"),
        ("Telegram: @MumtozmaxalJonbranding", "Telegram: @MumtozmaxalJonbranding"),
        ("John Branding Agency dan qoʻngʻiroq", "Jon Branding Agentligi dan qoʻngʻiroq"),
        ("Djon Branding Agentligidan salom", "Jon Branding Agentligidan salom"),
        ("Джон Брендинг Агентлиги xizmati", "Jon Branding Agentligi xizmati"),
        ("Baxtiyor Gaziev bilan uchrashuv", "Baxtiyorjon Gaziyev bilan uchrashuv"),
        ("Bakhtiyorjon Gaziev rahbar", "Baxtiyorjon Gaziyev rahbar"),
        ("Бахтиёржон Газиев asoschi", "Baxtiyorjon Gaziyev asoschi"),
        ("Rayhonajon mijozga yozdi", "Rayxon mijozga yozdi"),
    ],
)
def test_normalize_name_spellings(raw: str, expected: str):
    assert normalize_name_spellings(raw) == expected


@pytest.mark.asyncio
async def test_transcribe_inline_includes_mumtozmaxal_context_and_normalizes():
    from src.services.call_analytics import CallAnalyzer

    analyzer = CallAnalyzer(amocrm=MagicMock(), db=None, gemini_client=MagicMock())
    captured_contents = []

    async def fake_generate(*, contents, config=None):
        captured_contents.append(contents)
        return SimpleNamespace(
            text=(
                "[00:02] Menejer: Assalomu alaykum, John Branding Agency dan "
                "Mumtoz mahalman, Baxtiyor Gaziev jamoasidan."
            )
        )

    with patch.object(analyzer, "_gemini_generate_content", side_effect=fake_generate):
        transcript = await analyzer._transcribe_inline(
            b"FAKE_AUDIO",
            "audio/mpeg",
            caller_phone="+998773220098",
        )

    assert transcript is not None
    assert "Jon Branding Agentligi" in transcript
    assert "Mumtozmaxalman" in transcript
    assert "Baxtiyorjon Gaziyev" in transcript

    prompt_sent = captured_contents[0][0]
    assert STT_PROPER_NOUNS_PROMPT in prompt_sent
    assert "+998773220098" in prompt_sent
