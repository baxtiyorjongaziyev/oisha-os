from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.context import ApplicationContext


@pytest.mark.asyncio
async def test_salescoach_bootstrap_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("TELEGRAM_SALESCOACH_ENABLED", raising=False)
    installer = AsyncMock()
    monkeypatch.setattr(
        "src.services.core.telegram_salescoach_runtime.install_telegram_salescoach",
        installer,
    )
    context = ApplicationContext()

    context.client = SimpleNamespace()
    context.bot_runtime = SimpleNamespace()
    context.msg_controller = SimpleNamespace()
    await asyncio.sleep(0)

    installer.assert_not_awaited()


@pytest.mark.asyncio
async def test_salescoach_bootstrap_runs_once_when_dependencies_are_ready(monkeypatch):
    monkeypatch.setenv("TELEGRAM_SALESCOACH_ENABLED", "1")
    installer = AsyncMock(return_value=SimpleNamespace())
    monkeypatch.setattr(
        "src.services.core.telegram_salescoach_runtime.install_telegram_salescoach",
        installer,
    )
    context = ApplicationContext()

    context.client = SimpleNamespace()
    context.bot_runtime = SimpleNamespace()
    context.msg_controller = SimpleNamespace()
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    installer.assert_awaited_once_with(context)
    assert context.telegram_salescoach_install_task is None

    context.client = SimpleNamespace()
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    # The fake installer does not set telegram_salescoach, so a later canonical
    # dependency reassignment is allowed to retry. Production installer sets it.
    assert installer.await_count == 2
