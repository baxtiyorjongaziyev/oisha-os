"""Tests for Farmer Transition Engine."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.core.crm.amocrm_pipeline_config import (
    FARMER_PIPELINE_ID,
    SALES_PIPELINE_ID,
    STATUS_WON,
)
from src.services.core.crm.farmer_transition import FarmerTransitionService


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch):
    monkeypatch.delenv("AMOCRM_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("AMOCRM_TOKEN_SOURCE", raising=False)


@pytest.mark.asyncio
async def test_hand_off_rejects_empty_id():
    service = FarmerTransitionService(amocrm=MagicMock())
    result = await service.hand_off_to_farmer(0)
    assert result["success"] is False
    assert result["reason"] == "empty_sales_lead_id"


@pytest.mark.asyncio
async def test_hand_off_rejects_non_won_lead():
    amocrm = MagicMock()
    service = FarmerTransitionService(amocrm=amocrm)
    lead_data = {
        "id": 100,
        "name": "Test deal",
        "status_id": 87609518,  # Not Won
        "pipeline_id": SALES_PIPELINE_ID,
    }
    result = await service.hand_off_to_farmer(100, lead_data=lead_data)
    assert result["success"] is False
    assert result["reason"] == "lead_not_eligible_for_farmer"


@pytest.mark.asyncio
async def test_hand_off_rejects_foreign_pipeline():
    amocrm = MagicMock()
    service = FarmerTransitionService(amocrm=amocrm)
    lead_data = {
        "id": 101,
        "name": "HR deal",
        "status_id": STATUS_WON,
        "pipeline_id": 10963570,  # HR Pipeline
    }
    result = await service.hand_off_to_farmer(101, lead_data=lead_data)
    assert result["success"] is False
    assert result["reason"] == "lead_not_eligible_for_farmer"


@pytest.mark.asyncio
async def test_hand_off_idempotency_via_db():
    db = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = ("99999:1700000000",)
    conn = MagicMock()
    conn.execute = MagicMock(return_value=cursor)
    db.get_connection = AsyncMock(return_value=conn)

    service = FarmerTransitionService(amocrm=MagicMock(), db=db)
    result = await service.hand_off_to_farmer(102)
    assert result["success"] is False
    assert result["reason"] == "already_transitioned"


@pytest.mark.asyncio
async def test_hand_off_successful_execution():
    amocrm = MagicMock()
    amocrm.base_url = "https://jonbranding.amocrm.ru"
    amocrm._get_headers.return_value = {"Authorization": "Bearer test"}
    amocrm.create_task = AsyncMock(return_value={"id": 888})
    amocrm.add_lead_note = AsyncMock(return_value=True)

    bot_runtime = MagicMock()
    bot_runtime.send_message = AsyncMock(return_value=True)

    lead_data = {
        "id": 500,
        "name": "Asl Oila MChJ",
        "price": 15000000,
        "status_id": STATUS_WON,
        "pipeline_id": SALES_PIPELINE_ID,
        "responsible_user_id": 13021974,
        "custom_fields_values": [
            {"field_id": 1551701, "values": [{"value": "Asl Oila"}]},
            {"field_id": 1034673, "values": [{"value": "Ishlab chiqarish"}]},
        ],
        "_embedded": {"contacts": [{"id": 333}]},
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"_embedded": {"leads": [{"id": 7777}]}}

    with patch("requests.post", return_value=mock_resp):
        service = FarmerTransitionService(amocrm=amocrm, bot_runtime=bot_runtime)
        result = await service.hand_off_to_farmer(500, lead_data=lead_data)

    assert result["success"] is True
    assert result["sales_lead_id"] == 500
    assert result["farmer_lead_id"] == 7777

    # Verified onboarding task created
    amocrm.create_task.assert_awaited_once()
    task_call_kwargs = amocrm.create_task.await_args.kwargs
    assert task_call_kwargs["element_id"] == 7777
    assert "onboarding" in task_call_kwargs["text"]

    # Verified sales lead note added
    amocrm.add_lead_note.assert_awaited_once()
    note_args = amocrm.add_lead_note.await_args.args
    assert note_args[0] == 500
    assert "7777" in note_args[1]
