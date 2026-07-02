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
    
    mock_airtable = MagicMock()
    mock_airtable.get_overdue_projects = MagicMock(return_value=[
        {"fields": {"project_name": "Project A", "manager": "PM A"}}
    ])
    
    monkeypatch.setattr("src.services.core.crm.crm_service.CRMService", MagicMock())
    monkeypatch.setattr("src.services.core.airtable_sync.AirtableSync", MagicMock(return_value=mock_airtable))
    monkeypatch.setattr("src.services.core.enterprise_reporter.EnterpriseReporter", MagicMock(return_value=mock_reporter))
    
    # Act
    await admin_bot.send_deadline_report(mock_event)
    
    # Assert
    mock_event.respond.assert_any_call("⏰ **Muddati o'tgan vazifalar va loyihalar tahlil qilinmoqda...**")
    final_call_args = mock_event.respond.call_args_list[-1][0][0]
    assert "ACCOUNTABILITY SUCCESS" in final_call_args
    assert "Project A" in final_call_args
    assert "PM A" in final_call_args
