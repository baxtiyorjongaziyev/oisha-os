"""Tests for Meta Lead Optimizer service and scheduler."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.core.marketing.meta_lead_optimizer import (
    fetch_active_lead_adsets,
    get_meta_config,
    notify_optimization_success,
    run_lead_optimization_sweep,
    upgrade_adset_to_quality_lead,
)
from src.schedulers.meta_lead_optimizer_scheduler import (
    _get_interval,
    _is_enabled,
    meta_lead_optimizer_loop,
)


def test_get_meta_config():
    cfg = get_meta_config()
    assert isinstance(cfg, dict)
    assert "access_token" in cfg
    assert "ad_account_id" in cfg
    assert "dataset_id" in cfg


@patch("requests.get")
def test_fetch_active_lead_adsets(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "data": [
            {"id": "123", "name": "Test AdSet", "optimization_goal": "LEAD_GENERATION", "status": "ACTIVE"}
        ]
    }
    cfg = {"access_token": "token", "ad_account_id": "370591433710957", "version": "v21.0"}
    adsets = fetch_active_lead_adsets(cfg)
    assert len(adsets) == 1
    assert adsets[0]["id"] == "123"


@patch("requests.post")
def test_upgrade_adset_to_quality_lead_success(mock_post):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"success": True}

    adset = {"id": "123", "name": "Ad Set 1", "promoted_object": {"page_id": "999"}}
    cfg = {"access_token": "token", "dataset_id": "1134785364752294", "version": "v21.0"}
    ok, msg = upgrade_adset_to_quality_lead(adset, cfg)
    assert ok is True
    assert "Muvaffaqiyatli" in msg


@patch("requests.post")
def test_upgrade_adset_to_quality_lead_failure(mock_post):
    mock_post.return_value.status_code = 400
    mock_post.return_value.json.return_value = {"error": {"message": "Permissions error"}}

    adset = {"id": "123", "name": "Ad Set 1"}
    cfg = {"access_token": "token", "dataset_id": "1134785364752294", "version": "v21.0"}
    ok, msg = upgrade_adset_to_quality_lead(adset, cfg)
    assert ok is False
    assert "Permissions error" in msg


@patch("src.services.core.marketing.meta_lead_optimizer.fetch_active_lead_adsets")
@patch("src.services.core.marketing.meta_lead_optimizer.upgrade_adset_to_quality_lead")
def test_run_lead_optimization_sweep(mock_upgrade, mock_fetch):
    mock_fetch.return_value = [
        {"id": "1", "name": "AdSet 1", "optimization_goal": "LEAD_GENERATION"},
        {"id": "2", "name": "AdSet 2", "optimization_goal": "QUALITY_LEAD"},
    ]
    mock_upgrade.return_value = (True, "OK")

    res = run_lead_optimization_sweep({"access_token": "token"})
    assert res["scanned"] == 2
    assert res["already_quality"] == 1
    assert len(res["converted"]) == 1
    assert res["converted"][0] == "AdSet 1"


@pytest.mark.asyncio
async def test_notify_optimization_success():
    bot = MagicMock()
    bot.send_message = AsyncMock()

    with patch("src.settings.settings.TEAM_GROUP_ID", -10012345):
        await notify_optimization_success("Target 1", "123", bot)
        assert bot.send_message.called


def test_scheduler_helpers():
    assert _is_enabled() is True
    assert _get_interval() > 0


@pytest.mark.asyncio
async def test_meta_lead_optimizer_loop_cancelled():
    with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
        # Should exit gracefully on CancelledError
        await meta_lead_optimizer_loop()
