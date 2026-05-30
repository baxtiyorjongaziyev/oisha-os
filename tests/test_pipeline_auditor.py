import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.core.pipeline_auditor import PipelineAuditor


class MockCursor:
    """
    A unified mock helper that behaves exactly like an aiosqlite Cursor:
    1. Can be awaited directly: `cursor = await conn.execute(...)`
    2. Can be used as an async context manager: `async with conn.execute(...) as cursor:`
    """
    def __init__(self, fetch_val=None, fetchall_val=None):
        self.fetch_val = fetch_val
        self.fetchall_val = fetchall_val

    def __await__(self):
        async def _async_self():
            return self
        return _async_self().__await__()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def fetchone(self):
        return self.fetch_val

    async def fetchall(self):
        return self.fetchall_val


@pytest.mark.asyncio
async def test_generate_intelligence_profile_success():
    amocrm_mock = MagicMock()
    airtable_mock = MagicMock()
    db_mock = MagicMock()

    auditor = PipelineAuditor(amocrm=amocrm_mock, airtable=airtable_mock, db=db_mock)
    auditor.genai_client = MagicMock()

    mock_response = MagicMock()
    mock_response.text = (
        '{"psychotype": "Analytical", "pain_points": "Narx baland", '
        '"objections": "Chegirma so\'radi", "buying_drivers": "Status", '
        '"close_probability": 90, "next_task_text": "Mijoz bilan bog\'lanish", '
        '"negotiation_strategy": "1. Chegirma berish"}'
    )

    with patch.object(
        auditor.genai_client.models, "generate_content", return_value=mock_response
    ):
        result = await auditor.generate_intelligence_profile(
            deal_info={"name": "Test Deal", "price": 50000},
            dm_history=[],
            call_history=[],
            airtable_project=None
        )
        assert result["psychotype"] == "Analytical"
        assert result["close_probability"] == 90
        assert result["pain_points"] == "Narx baland"


@pytest.mark.asyncio
async def test_audit_all_deals_blocked_by_auth():
    amocrm_mock = MagicMock()
    airtable_mock = MagicMock()
    db_mock = MagicMock()

    # Mock get_leads_detailed to return empty (simulating auth expired)
    amocrm_mock.get_leads_detailed = AsyncMock(return_value=[])

    auditor = PipelineAuditor(amocrm=amocrm_mock, airtable=airtable_mock, db=db_mock)
    report = await auditor.audit_all_deals(limit=10)
    
    assert report["success"] is False
    assert report["reason"] == "amocrm_auth_expired"


@pytest.mark.asyncio
async def test_audit_all_deals_success():
    amocrm_mock = MagicMock()
    airtable_mock = MagicMock()
    db_mock = MagicMock()

    # Mock detailed deals
    mock_deal = {"id": 12345, "name": "Mock Project Deal", "price": 10000000, "responsible_user_id": 777}
    amocrm_mock.get_leads_detailed = AsyncMock(return_value=[mock_deal])
    amocrm_mock.get_lead_phone = MagicMock(return_value="+998901234567")
    amocrm_mock.add_lead_note = MagicMock()
    amocrm_mock.add_lead_tag = AsyncMock()
    amocrm_mock.create_task = AsyncMock(return_value={"id": 888})

    # Mock Airtable projects
    mock_project = {"project_name": "Mock Project Deal", "stage": "Design", "pm": "Ali"}
    airtable_mock.get_projects = MagicMock(return_value=[mock_project])

    # Mock Database using our custom MockCursor
    db_mock.get_user_id_by_phone = AsyncMock(return_value=42)
    db_mock.get_recent_messages = AsyncMock(return_value=[])
    
    cursor = MockCursor(
        fetch_val=None, 
        fetchall_val=[("Qo'ng'iroq yozuvi matni", "Xulosa", "Keyingi qadamlar", "Positive")]
    )
    
    mock_conn = MagicMock()
    mock_conn.execute = MagicMock(return_value=cursor)
    mock_conn.commit = AsyncMock()
    db_mock.get_connection = AsyncMock(return_value=mock_conn)

    auditor = PipelineAuditor(amocrm=amocrm_mock, airtable=airtable_mock, db=db_mock)

    # Mock CallAnalyzer process recordings call
    auditor.call_analyzer.process_call_recordings_for_lead = AsyncMock(return_value=1)

    # Mock intelligence profile
    profile_result = {
        "psychotype": "Expressive",
        "pain_points": "N/A",
        "objections": "N/A",
        "buying_drivers": "Quality",
        "close_probability": 85,
        "next_task_text": "Mijozga shartnoma taqdim etish",
        "negotiation_strategy": "1. Aloqa\n2. Reja\n3. Shartnoma"
    }

    with patch("builtins.open", MagicMock()), \
         patch.object(auditor, "generate_intelligence_profile", return_value=profile_result):
         
        report = await auditor.audit_all_deals(limit=1)
        assert report["success"] is True
        assert report["scanned"] == 1
        amocrm_mock.get_leads_detailed.assert_called_once()
        amocrm_mock.add_lead_tag.assert_called_once_with(12345, "High_Win_Prob")
        amocrm_mock.create_task.assert_called_once()
        task_kwargs = amocrm_mock.create_task.call_args.kwargs
        assert task_kwargs["element_id"] == 12345
        assert "Mijozga shartnoma taqdim etish" in task_kwargs["text"]
