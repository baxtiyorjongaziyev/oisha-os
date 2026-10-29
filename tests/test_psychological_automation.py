import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from src.services.core.psychological_automation import PsychologicalAutomationService
from src.schedulers.background_monitor import BackgroundMonitor


def test_generate_morning_boost():
    service = PsychologicalAutomationService()
    day1 = datetime(2026, 10, 15, 9, 15)
    day2 = datetime(2026, 10, 16, 9, 15)
    boost1 = service.generate_morning_boost(now=day1)
    boost2 = service.generate_morning_boost(now=day2)

    assert "OISHA KUNLIK PSIXOLOGIK IMPULS" in boost1
    assert "Jon Branding" in boost1
    assert "Bugungi oltin qoida:" in boost1
    assert "Bugungi 3 ta vazifangiz:" in boost1
    # Har kuni bir xil motivatsiya ketmasligi shart
    assert boost1 != boost2


def test_generate_morning_boost_adapts_to_situational_metrics():
    service = PsychologicalAutomationService()
    now = datetime(2026, 10, 17, 9, 15)

    stagnation_boost = service.generate_morning_boost(
        context={
            "stagnated_count": 6,
            "top_stagnated_lead": "Akfa Medline",
            "top_stagnated_value": "$4,500",
            "active_leads_count": 18,
            "pipeline_value": 45000,
        },
        now=now,
    )
    assert "Bugungi vaziyat va ko'rsatkichlar:" in stagnation_boost
    assert "6 ta" in stagnation_boost
    assert "Akfa Medline" in stagnation_boost
    assert "Call Reluctance Breaker" in stagnation_boost

    deadline_boost = service.generate_morning_boost(
        context={
            "overdue_projects_count": 2,
            "top_overdue_project": "Payme Rebranding",
            "overdue_tasks_count": 4,
        },
        now=now,
    )
    assert "Payme Rebranding" in deadline_boost
    assert "PM & SLA Shield" in deadline_boost
    assert deadline_boost != stagnation_boost

    quality_boost = service.generate_morning_boost(
        context={
            "recent_calls_count": 15,
            "solid_calls_count": 3,
            "avg_call_score": 54.0,
        },
        now=now,
    )
    assert "54/100" in quality_boost
    assert "3+ Daqiqa Standarti" in quality_boost
    assert quality_boost != stagnation_boost


@pytest.mark.asyncio
async def test_build_morning_boost_collects_live_sources():
    amocrm_mock = MagicMock()
    amocrm_mock.get_stagnated_leads = MagicMock(
        return_value=[
            {"id": 501, "name": "Korzinka Branding", "price": 5000},
            {"id": 502, "name": "Texnomart Pack", "price": 3000},
            {"id": 503, "name": "Uzum Seller", "price": 1500},
        ]
    )
    amocrm_mock.get_all_leads = MagicMock(
        return_value=[
            {"id": 501, "status_id": 100, "price": 5000},
            {"id": 504, "status_id": 142, "price": 4000},
        ]
    )
    airtable_mock = MagicMock()
    airtable_mock.get_overdue_projects = MagicMock(return_value=[])

    service = PsychologicalAutomationService(
        amocrm=amocrm_mock, airtable=airtable_mock
    )
    boost = await service.build_morning_boost(now=datetime(2026, 10, 17, 9, 15))
    assert "Korzinka Branding" in boost
    assert "3 ta" in boost
    assert "Yangi yopilgan bitimlar (Won): **1 ta**" in boost


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
    sent_boost_text = bot_client.send_message.await_args_list[0].args[1]
    assert "Test Lead" in sent_boost_text

    # Idempotent
    await monitor._job_psychological_mindset_boost(now)
    assert bot_client.send_message.await_count == 1

    # Sales reluctance job
    sales_now = datetime(2026, 8, 23, 11, 30)
    await monitor._job_sales_reluctance_automation(sales_now)
    # PM conflict job
    pm_now = datetime(2026, 8, 23, 11, 45)
    await monitor._job_pm_conflict_automation(pm_now)
