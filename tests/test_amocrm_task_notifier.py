import pytest
from unittest.mock import AsyncMock, MagicMock
from src.services.core.amocrm_task_notifier import (
    AmoCrmTaskNotifier,
    format_task_notification,
    parse_amocrm_task_webhook_data,
    DEFAULT_FORWARD_GROUP_ID,
    DEFAULT_FORWARD_TOPIC_ID,
)


def test_format_task_notification_due():
    task = {
        "id": 12345,
        "entity_id": 36654487,
        "entity_type": "leads",
        "task_type_id": 1,
        "text": "Aloqaga chiqib uchrashuv belgilash",
        "complete_till": 1758617300,
    }
    lead = {
        "name": "Azamat Aka Admiral",
        "pipeline_id": 11162698,
        "status_id": 87609518,
        "price": 15000000,
        "custom_fields_values": [
            {"field_id": 1034671, "values": [{"value": "Brending"}]},
            {"field_id": 1034663, "values": [{"value": "Tez Natija (TN5)"}]},
            {"field_id": 1037937, "values": [{"value": "@azamat_admiral"}]},
        ]
    }
    contact = {"name": "Azamat Aka", "phone": "+998901234567"}

    msg, buttons = format_task_notification(
        task=task,
        lead_or_contact=lead,
        contact_details=contact,
        phone="+998901234567",
        responsible_name="Baxtiyorjon Gaziyev",
        alert_type="due",
        subdomain="jonbrandingagency",
    )
    assert "Пора выполнить задачу" in msg
    assert "Azamat Aka Admiral" in msg
    assert "+998901234567" in msg
    assert "Baxtiyorjon Gaziyev" in msg
    assert "Aloqaga chiqib uchrashuv belgilash" in msg
    assert "1. PRESALES ➔ Aloqaga chiqildi" in msg
    assert "Brending" in msg
    assert "Tez Natija (TN5)" in msg
    assert "15 000 000" in msg
    assert "@azamat_admiral" in msg
    assert buttons is not None
    assert buttons[0][0]["url"] == "https://jonbrandingagency.amocrm.ru/leads/detail/36654487"


def test_format_task_notification_overdue():
    task = {
        "id": 12346,
        "entity_id": 112233,
        "entity_type": "contacts",
        "task_type_id": 4061818,
        "text": "Qayta aloqa",
        "complete_till": 1758610000,
    }
    contact = {"name": "Nilufar opa", "phone": "+998775073030"}
    msg, buttons = format_task_notification(
        task=task,
        lead_or_contact=contact,
        responsible_name="Oydin",
        alert_type="overdue",
    )
    assert "Просроченная задача" in msg
    assert "Nilufar opa" in msg
    assert "Oydin" in msg
    assert "+998775073030" in msg
    assert buttons[0][0]["url"] == "https://jonbrandingagency.amocrm.ru/contacts/detail/112233"


def test_parse_amocrm_task_webhook_data():
    # Test form-data parsing
    form_data = {
        "tasks[add][0][id]": "998877",
        "tasks[add][0][element_id]": "554433",
        "tasks[add][0][element_type]": "2",
        "tasks[add][0][text]": "Test task from webhook",
        "tasks[add][0][complete_till]": "1758620000",
        "tasks[add][0][responsible_user_id]": "13021974",
    }
    parsed = parse_amocrm_task_webhook_data(form_data)
    assert len(parsed) == 1
    assert parsed[0]["id"] == 998877
    assert parsed[0]["element_id"] == "554433"
    assert parsed[0]["text"] == "Test task from webhook"
    assert parsed[0]["complete_till"] == 1758620000

    # Test direct JSON parsing
    json_data = {
        "tasks": [
            {"id": 111, "text": "Json task"}
        ]
    }
    parsed_json = parse_amocrm_task_webhook_data(json_data)
    assert len(parsed_json) == 1
    assert parsed_json[0]["id"] == 111


@pytest.mark.asyncio
async def test_send_task_alert_and_deduplication():
    mock_bot = AsyncMock()
    mock_amocrm = MagicMock()
    mock_amocrm.get_user_name.return_value = "Baxtiyorjon Gaziyev"
    mock_amocrm.get_lead = AsyncMock(return_value={"name": "Test Lead"})
    mock_amocrm.get_lead_phone.return_value = "+998901112233"
    mock_amocrm.get_contact_details_async = AsyncMock(return_value=None)

    notifier = AmoCrmTaskNotifier(amocrm=mock_amocrm, bot_runtime=mock_bot)

    task = {
        "id": 5555,
        "entity_id": 9999,
        "entity_type": "leads",
        "text": "Eslatma matni",
        "complete_till": 1758617300,
        "responsible_user_id": 13021974,
    }

    # 1. First send -> should succeed
    sent = await notifier.send_task_alert(task, alert_type="due")
    assert sent is True
    assert mock_bot.send_message.call_count == 1

    # 2. Second send (same task & type) -> deduplicated, should skip
    sent_dup = await notifier.send_task_alert(task, alert_type="due")
    assert sent_dup is False
    assert mock_bot.send_message.call_count == 1  # Not called again


@pytest.mark.asyncio
async def test_check_and_notify_due_tasks():
    import time
    now = time.time()

    mock_bot = AsyncMock()
    mock_amocrm = MagicMock()
    mock_amocrm.get_user_name.return_value = "Baxtiyorjon"
    mock_amocrm.get_lead = AsyncMock(return_value={"name": "Due Lead"})
    mock_amocrm.get_lead_phone.return_value = None
    mock_amocrm.get_contact_details_async = AsyncMock(return_value=None)

    # Return 1 due task, 1 overdue task, 1 future task
    mock_amocrm.get_tasks = AsyncMock(return_value=[
        {"id": 101, "complete_till": now - 300, "text": "Due now", "entity_id": 1, "entity_type": "leads"},
        {"id": 102, "complete_till": now - 3600, "text": "Overdue 1h", "entity_id": 2, "entity_type": "leads"},
        {"id": 103, "complete_till": now + 7200, "text": "Future 2h", "entity_id": 3, "entity_type": "leads"},
    ])

    notifier = AmoCrmTaskNotifier(amocrm=mock_amocrm, bot_runtime=mock_bot)
    stats = await notifier.check_and_notify_due_tasks()

    assert stats["total_open"] == 3
    assert stats["due_sent"] == 1
    assert stats["overdue_sent"] == 1
    assert stats["skipped"] == 1
    assert mock_bot.send_message.call_count == 2
