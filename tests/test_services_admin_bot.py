"""
Unit tests for AdminBot in src/services/core/admin_bot.py.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from src.services.core.admin_bot import AdminBot


@pytest.mark.asyncio
async def test_send_kpi_report(monkeypatch):
    # Arrange
    admin_bot = AdminBot.__new__(AdminBot)
    admin_bot.db = MagicMock()
    mock_event = AsyncMock()
    
    # Mock EnterpriseReporter
    mock_reporter = MagicMock()
    mock_reporter.get_team_efficiency_report = AsyncMock(return_value="KPI SUCCESS")
    
    mock_crm = MagicMock()
    mock_airtable = MagicMock()
    
    # Monkeypatch the classes in their original import modules
    monkeypatch.setattr("src.services.core.crm.crm_service.CRMService", MagicMock(return_value=mock_crm))
    monkeypatch.setattr("src.services.core.airtable_sync.AirtableSync", MagicMock(return_value=mock_airtable))
    monkeypatch.setattr("src.services.core.enterprise_reporter.EnterpriseReporter", MagicMock(return_value=mock_reporter))
    
    # Act
    await admin_bot.send_kpi_report(mock_event)
    
    # Assert
    mock_event.respond.assert_any_call("📊 **Jamoa KPI va samaradorlik hisoboti shakllantirilmoqda...**")
    mock_event.respond.assert_any_call("KPI SUCCESS", parse_mode="html", link_preview=False)


@pytest.mark.asyncio
async def test_send_deadline_report(monkeypatch):
    # Arrange
    admin_bot = AdminBot.__new__(AdminBot)
    admin_bot.db = MagicMock()
    mock_event = AsyncMock()
    
    # Mock EnterpriseReporter & Airtable
    mock_reporter = MagicMock()
    mock_reporter.get_accountability_segment = AsyncMock(return_value="ACCOUNTABILITY SUCCESS")
    
    # Haqiqiy Airtable ustun nomlari ishlatiladi (alias kalitlar emas) —
    # AirtableSync.FIELD_MAP orqali _get_field/resolve_pm_handle hal qiladi.
    mock_airtable = MagicMock()
    mock_airtable.get_overdue_projects = MagicMock(return_value=[
        {"fields": {"Loyihani nomi?": "Project A", "PM": "Inomjon aka"}}
    ])
    mock_airtable.get_projects = MagicMock(return_value=[])

    import src.services.core.airtable_sync as airtable_sync_module
    monkeypatch.setattr("src.services.core.crm.crm_service.CRMService", MagicMock())
    # Konstruktorni almashtiramiz, lekin _get_field/resolve_pm_handle haqiqiy
    # statik metodlar bo'lib qoladi — shu bilan alias-resolution mantiqi ham sinaladi.
    monkeypatch.setattr(
        airtable_sync_module.AirtableSync, "__init__", lambda self, *a, **kw: None
    )
    monkeypatch.setattr(
        airtable_sync_module.AirtableSync, "get_overdue_projects",
        lambda self: mock_airtable.get_overdue_projects(),
    )
    monkeypatch.setattr(
        airtable_sync_module.AirtableSync, "get_projects",
        lambda self: mock_airtable.get_projects(),
    )
    monkeypatch.setattr("src.services.core.enterprise_reporter.EnterpriseReporter", MagicMock(return_value=mock_reporter))

    # Act
    await admin_bot.send_deadline_report(mock_event)

    # Assert
    mock_event.respond.assert_any_call("⏰ **Muddati o'tgan vazifalar va loyihalar tahlil qilinmoqda...**")
    final_call_args = mock_event.respond.call_args_list[-1][0][0]
    assert "ACCOUNTABILITY SUCCESS" in final_call_args
    assert "Project A" in final_call_args
    assert "@Inomjon_JonBranding" in final_call_args
