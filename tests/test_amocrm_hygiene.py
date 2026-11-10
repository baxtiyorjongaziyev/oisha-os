"""Tests for AmoCRM Hygiene & Capacity Engine."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.core.crm.amocrm_hygiene import AmoCRMHygieneService
from src.services.core.crm.amocrm_pipeline_config import SALES_PIPELINE_ID


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch):
    monkeypatch.delenv("AMOCRM_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("AMOCRM_TOKEN_SOURCE", raising=False)


@pytest.mark.asyncio
async def test_fetch_all_active_leads_filters_closed_leads():
    amocrm = MagicMock()
    amocrm.base_url = "https://jonbranding.amocrm.ru"
    amocrm._get_headers.return_value = {"Authorization": "Bearer test"}

    batch1 = {
        "_embedded": {
            "leads": [
                {"id": 1, "status_id": 89067962},  # Active
                {"id": 2, "status_id": 142},       # Won (closed)
                {"id": 3, "status_id": 143},       # Lost (closed)
                {"id": 4, "status_id": 87609518},  # Active
            ]
        }
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = batch1

    with patch("requests.get", return_value=mock_resp):
        service = AmoCRMHygieneService(amocrm=amocrm)
        leads = await service.fetch_all_active_leads()

    assert len(leads) == 2
    assert [ld["id"] for ld in leads] == [1, 4]


@pytest.mark.asyncio
async def test_enforce_tasks_creates_tasks_for_leads_without_tasks():
    amocrm = MagicMock()
    amocrm.base_url = "https://jonbranding.amocrm.ru"
    amocrm._get_headers.return_value = {"Authorization": "Bearer test"}

    active_leads = [
        {"id": 10, "responsible_user_id": 13021974},
        {"id": 20, "responsible_user_id": 13021974},
        {"id": 30, "responsible_user_id": 13021974},
    ]
    open_task_ids = {20}  # Lead 20 already has a task

    mock_post = MagicMock()
    mock_post.status_code = 201
    mock_post.json.return_value = {"_embedded": {"tasks": [{"id": 101}, {"id": 102}]}}

    with patch("requests.post", return_value=mock_post) as mock_requests_post:
        service = AmoCRMHygieneService(amocrm=amocrm)
        created = await service.enforce_tasks_on_active_deals(
            active_leads=active_leads,
            open_task_ids=open_task_ids,
            dry_run=False,
        )

    assert created == 2
    mock_requests_post.assert_called_once()
    payload = mock_requests_post.call_args.kwargs["json"]
    assert len(payload) == 2
    assert payload[0]["entity_id"] == 10
    assert payload[1]["entity_id"] == 30


@pytest.mark.asyncio
async def test_inspect_capacity_does_not_archive_by_default(tmp_path):
    amocrm = MagicMock()
    now_ts = 1780000000
    active_leads = [
        {
            "id": 101,
            "name": "Muddati oʻtgan lid",
            "pipeline_id": SALES_PIPELINE_ID,
            "status_id": 87609518,
            "created_at": now_ts - (35 * 86400),
            "_embedded": {"contacts": []},
        },
    ]

    with patch("time.time", return_value=now_ts), patch("requests.patch") as mock_patch:
        service = AmoCRMHygieneService(amocrm=amocrm, reports_dir=tmp_path)
        candidates, backup_file, archived = await service.inspect_and_handle_capacity(
            active_leads=active_leads,
            max_stagnant_days=30,
            auto_archive=False,
        )

    assert len(candidates) == 1
    assert archived == 0  # Hech qanday bitim arxivlanmadi
    mock_patch.assert_not_called()
    assert (tmp_path / f"amocrm_backup_{now_ts}.json").exists()


@pytest.mark.asyncio
async def test_inspect_capacity_archives_when_explicitly_authorized(tmp_path):
    amocrm = MagicMock()
    amocrm.base_url = "https://jonbranding.amocrm.ru"
    amocrm._get_headers.return_value = {"Authorization": "Bearer test"}

    now_ts = 1780000000
    active_leads = [
        {
            "id": 101,
            "name": "Muddati oʻtgan lid",
            "pipeline_id": SALES_PIPELINE_ID,
            "status_id": 87609518,
            "created_at": now_ts - (35 * 86400),
            "_embedded": {"contacts": []},
        },
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("time.time", return_value=now_ts), patch("requests.patch", return_value=mock_resp) as mock_patch:
        service = AmoCRMHygieneService(amocrm=amocrm, reports_dir=tmp_path)
        candidates, backup_file, archived = await service.inspect_and_handle_capacity(
            active_leads=active_leads,
            max_stagnant_days=30,
            auto_archive=True,
        )

    assert len(candidates) == 1
    assert archived == 1
    mock_patch.assert_called_once()


@pytest.mark.asyncio
async def test_run_hygiene_cycle_safe_mode(tmp_path):
    amocrm = MagicMock()
    service = AmoCRMHygieneService(amocrm=amocrm, reports_dir=tmp_path)

    service.fetch_all_active_leads = AsyncMock(return_value=[{"id": 1, "responsible_user_id": 100}])
    service.fetch_open_task_lead_ids = AsyncMock(return_value={1})
    service.enforce_tasks_on_active_deals = AsyncMock(return_value=0)

    report = await service.run_hygiene_cycle(dry_run=False, capacity_threshold=480)

    assert report["total_active_before"] == 1
    assert report["total_active_after"] == 1
    assert report["tasks_created"] == 0
    assert report["archived_leads"] == 0
    assert report["status"] == "safe"
