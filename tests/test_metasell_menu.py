"""Unit tests for Telegram Bot Metasell Console Mini App menu."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from telegram import Update, Message, User, CallbackQuery
from telegram.ext import ContextTypes

from src.handlers.metasell_menu import (
    build_metasell_menu_keyboard,
    build_aiogram_metasell_keyboard,
    format_executive_digest,
    console_command,
    cockpit_command,
    simulator_command,
    morning_triage_command,
    handle_metasell_callback,
)


def test_build_metasell_menu_keyboard():
    markup = build_metasell_menu_keyboard(
        base_url="https://app.metasell.uz",
        is_owner=True,
        include_simulator=True,
    )
    assert len(markup.inline_keyboard) == 3

    # Row 1: Cockpit Mini App button
    btn_console = markup.inline_keyboard[0][0]
    assert "Boshqaruv" in btn_console.text
    assert btn_console.web_app.url == "https://app.metasell.uz/metasell-console"

    # Row 2: Simulator & Triage
    row2 = markup.inline_keyboard[1]
    assert len(row2) == 2
    assert "Simulyator" in row2[0].text
    assert row2[0].web_app.url == "https://app.metasell.uz/metasell-console#simulator"
    assert "Trijaj" in row2[1].text

    # Row 3: Owner extras
    row3 = markup.inline_keyboard[2]
    assert any(b.callback_data == "metasell:summary" for b in row3)


def test_format_executive_digest():
    metrics = {
        "hero": {"sales_won_amount": 50_000_000.0, "conversion_rate_pct": 32.5},
        "speed_to_lead": {"sla_rate_pct": 88.0, "unanswered_leads": 1},
        "stuck_deals": {"total_stuck_deals": 4, "total_stuck_value": 80_000_000.0},
    }
    text = format_executive_digest(metrics)
    assert "50.0 mln" in text
    assert "32.5%" in text
    assert "88.0%" in text
    assert "4 ta" in text
    assert "80.0 mln" in text


@pytest.mark.asyncio
async def test_console_command():
    update = MagicMock(spec=Update)
    message = MagicMock(spec=Message)
    message.reply_text = AsyncMock()
    user = MagicMock(spec=User)
    user.id = 1234567

    update.message = message
    update.effective_user = user
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    await console_command(update, context)
    message.reply_text.assert_awaited_once()
    args, kwargs = message.reply_text.call_args
    assert "Boshqaruv" in args[0]
    assert kwargs.get("reply_markup") is not None


@pytest.mark.asyncio
async def test_callback_query_summary():
    update = MagicMock(spec=Update)
    query = MagicMock(spec=CallbackQuery)
    query.data = "metasell:summary"
    query.answer = AsyncMock()
    msg = MagicMock(spec=Message)
    msg.reply_text = AsyncMock()
    query.message = msg
    update.callback_query = query
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    await handle_metasell_callback(update, context)
    query.answer.assert_awaited_once()
    msg.reply_text.assert_awaited_once()
    args, kwargs = msg.reply_text.call_args
    assert "ROP Boshqaruv Xulosasi" in args[0]
