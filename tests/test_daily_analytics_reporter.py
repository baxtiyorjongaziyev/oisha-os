import importlib

import pytest


@pytest.mark.asyncio
async def test_daily_analytics_reporter_imports_and_skips_without_config():
    module = importlib.import_module("src.schedulers.daily_analytics_reporter")

    await module.run_daily_analytics_report(bot_client=None)
