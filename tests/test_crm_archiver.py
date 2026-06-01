import json
import pytest
import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.core.crm_archiver import CRMArchiver

@pytest.mark.asyncio
async def test_init_tables():
    db = MagicMock()
    conn = AsyncMock()
    conn.__aenter__.return_value = conn
    db.get_connection = AsyncMock(return_value=conn)

    archiver = CRMArchiver(amocrm=MagicMock(), db=db)
    await archiver.init_tables()

    assert db.get_connection.called
    assert conn.execute.call_count == 2
    assert conn.commit.called

@pytest.mark.asyncio
async def test_fetch_all_active_leads_filtering():
    amocrm = MagicMock()
    amocrm.base_url = "https://test.amocrm.ru"
    amocrm.access_token = "mock_token"
    amocrm._get_headers = MagicMock(return_value={})

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value={
        "_embedded": {
            "leads": [
                {"id": 1, "name": "Active Lead 1", "status_id": 100, "pipeline_id": 123},
                {"id": 2, "name": "Closed Won Lead", "status_id": 142, "pipeline_id": 123},
                {"id": 3, "name": "Closed Lost Lead", "status_id": 143, "pipeline_id": 123},
                {"id": 4, "name": "Active Lead 2", "status_id": 101, "pipeline_id": 123},
            ]
        }
    })

    archiver = CRMArchiver(amocrm=amocrm, db=MagicMock())

    with patch("requests.get", return_value=mock_response):
        active_leads = await archiver.fetch_all_active_leads()

    assert len(active_leads) == 2
    assert active_leads[0]["id"] == 1
    assert active_leads[1]["id"] == 4

@pytest.mark.asyncio
async def test_fetch_open_task_lead_ids():
    amocrm = MagicMock()
    amocrm.base_url = "https://test.amocrm.ru"
    amocrm.access_token = "mock_token"
    amocrm._get_headers = MagicMock(return_value={})

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value={
        "_embedded": {
            "tasks": [
                {"id": 10, "entity_type": "leads", "entity_id": 1},
                {"id": 11, "entity_type": "contacts", "entity_id": 2},
                {"id": 12, "entity_type": "leads", "entity_id": 4},
            ]
        }
    })

    archiver = CRMArchiver(amocrm=amocrm, db=MagicMock())

    with patch("requests.get", return_value=mock_response):
        open_lead_ids = await archiver.fetch_open_task_lead_ids()

    assert open_lead_ids == {1, 4}

@pytest.mark.asyncio
async def test_get_stagnant_leads():
    archiver = CRMArchiver(amocrm=MagicMock(), db=MagicMock())

    # 21 days ago in seconds: threshold is ~ 1814400 seconds ago
    now = int(datetime.datetime.now().timestamp())
    older_than_21 = now - (25 * 24 * 3600)
    newer_than_21 = now - (5 * 24 * 3600)

    archiver.fetch_all_active_leads = AsyncMock(return_value=[
        {"id": 101, "name": "Stagnant 1", "updated_at": older_than_21},
        {"id": 102, "name": "Active/Recent", "updated_at": newer_than_21},
        {"id": 103, "name": "Stagnant with task", "updated_at": older_than_21},
    ])

    archiver.fetch_open_task_lead_ids = AsyncMock(return_value={103})

    stagnant_leads = await archiver.get_stagnant_leads(max_stagnant_days=21)

    assert len(stagnant_leads) == 1
    assert stagnant_leads[0]["id"] == 101

@pytest.mark.asyncio
async def test_archive_lead_dry_run():
    amocrm = MagicMock()
    amocrm.get_lead_notes = AsyncMock(return_value=[{"id": 1, "text": "Call details"}])
    amocrm.update_lead_status = AsyncMock(return_value=True)

    archiver = CRMArchiver(amocrm=amocrm, db=MagicMock())
    archiver.fetch_contact_details = AsyncMock(return_value={"name": "Alisher", "phone": "998901234567"})
    archiver.generate_outreach_campaign = AsyncMock(return_value={
        "step1": "Xabar 1", "step2": "Xabar 2", "step3": "Xabar 3"
    })

    lead = {
        "id": 555,
        "name": "Branding for Alisher",
        "price": 10000000,
        "status_id": 12,
        "pipeline_id": 99,
        "responsible_user_id": 1,
        "created_at": 1234567,
        "updated_at": 1234567,
        "_embedded": {"contacts": [{"id": 999}]}
    }

    res = await archiver.archive_lead(lead, dry_run=True)

    assert res["success"] is True
    assert res["lead_id"] == 555
    assert res["contact_name"] == "Alisher"
    assert res["phone"] == "998901234567"
    assert res["campaign"]["step1"] == "Xabar 1"

    # In dry_run, no status update or db insert should happen
    assert amocrm.update_lead_status.called is False
