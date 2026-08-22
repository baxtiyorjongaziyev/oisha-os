import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from src.services.core.psychological_automation import PsychologicalAutomationService
from src.schedulers.background_monitor import BackgroundMonitor


def test_generate_morning_boost():
    service = PsychologicalAutomationService()
    boost = service.generate_morning_boost()
    assert "OISHA KUNLIK PSIXOLOGIK IMPULS" in boost
    assert "Mijozning rad javobi" in boost
    assert "Jon Branding" in boost


@pytest.mark.asyncio
async def test_scan_and_generate_sales_reluctance_interventions():
    amocrm_mock = MagicMock()
    amocrm_mock.get_stagnated_leads = MagicMock(return_value=[
        {"id": 12345, "name": "Akbar aka Mebel", "price": 3500, "responsible_user_id": 999}
    ])
    service = PsychologicalAutomationService(amocrm=amocrm_mock)
    interventions = await service.scan_and_generate_sales_reluctance_interventions(limit=2)

    assert len(interventions) == 1
    assert interventions[0]["lead_id"] == 12345
    assert interventions[0]["client_name"] == "Akbar aka Mebel"
    assert "$3,500" in interventions[0]["deal_value"]
    assert "AVTOMATIK SOTUV PUSH" in interventions[0]["message"]
    assert "Hozir qilsang nima bo'ladi?" in interventions[0]["message"]


@pytest.mark.asyncio
async def test_scan_and_generate_pm_interventions():
    airtable_mock = MagicMock()
    airtable_mock.get_overdue_projects = MagicMock(return_value=[
        {"name": "Payme Rebranding", "manager": "Sardor PM", "deadline": "2026-08-25"}
    ])
    service = PsychologicalAutomationService(airtable=airtable_mock)
    interventions = await service.scan_and_generate_pm_interventions(limit=2)

    assert len(interventions) == 1
    assert interventions[0]["project_name"] == "Payme Rebranding"
    assert interventions[0]["manager"] == "Sardor PM"
    assert "AVTOMATIK PM LOYIHA HIMOYASI" in interventions[0]["message"]


@pytest.mark.asyncio
async def test_deliver_interventions():
    bot_client = MagicMock()
    bot_client.send_message = AsyncMock()
    service = PsychologicalAutomationService(bot_client=bot_client)

    interventions = [
        {"message": "Test push 1"},
        {"message": "Test push 2"},
    ]
    sent = await service.deliver_interventions(interventions, target_chat_id=-100123456, topic_id=77)
    assert sent == 2
    assert bot_client.send_message.await_count == 2


@pytest.mark.asyncio
async def test_background_monitor_psychological_jobs():
    bot_client = MagicMock()
    bot_client.send_message = AsyncMock()
    settings = MagicMock()
    settings.CRM_GROUP_ID = -100111
    settings.TEAM_GROUP_ID = -100222
    settings.TOPIC_REPORTS_ID = 55
    settings.TOPIC_CRM_ID = 66

    amocrm_mock = MagicMock()
    amocrm_mock.get_stagnated_leads = MagicMock(return_value=[
        {"id": 991, "name": "Test Lead", "price": 2000, "responsible_user_id": 12}
    ])

    monitor = BackgroundMonitor(
        msg_controller=None,
        client=None,
        bot_client=bot_client,
        settings=settings,
    )
    monitor.amocrm = amocrm_mock

    now = datetime(2026, 8, 23, 9, 15)
    await monitor._job_psychological_mindset_boost(now)
    assert bot_client.send_message.await_count == 1

    # Idempotent
    await monitor._job_psychological_mindset_boost(now)
    assert bot_client.send_message.await_count == 1

    # Sales reluctance job
    sales_now = datetime(2026, 8, 23, 11, 30)
    await monitor._job_sales_reluctance_automation(sales_now)
    # PM conflict job
    pm_now = datetime(2026, 8, 23, 11, 45)
    await monitor._job_pm_conflict_automation(pm_now)
