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

    async def install(context: ApplicationContext):
        service = SimpleNamespace()
        context.telegram_salescoach = service
        return service

    installer = AsyncMock(side_effect=install)
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
    assert context.telegram_salescoach is not None

    context.client = SimpleNamespace()
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    installer.assert_awaited_once()
