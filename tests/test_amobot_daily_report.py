import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.core.crm.amobot_daily_report import (
    is_amobot_daily_report,
    extract_report_date,
    translate_amobot_daily_report,
    process_amobot_message,
    check_and_relay_amobot_report,
)

SAMPLE_AMOBOT_REPORT = """Отчет за сегодня (02.11.2026)

Активных сделок на конец периода: [479](https://jonbranding.amocrm.ru/gtd/leads/list/?filter%5Bstatus%5D=opened&filter_date_from=02.11.2026&filter_date_to=02.11.2026)
Активных сделок на конец периода на сумму: [181,490,600 soʻm](https://jonbranding.amocrm.ru/gtd/leads/list/?filter%5Bstatus%5D=opened&filter_date_from=02.11.2026&filter_date_to=02.11.2026)
Успешно завершено сделок: [2](https://jonbranding.amocrm.ru/gtd/leads/list/?useFilter=y&filter_date_switch=closed&filter_date_from=02.11.2026&filter_date_to=02.11.2026&filter%5Bpipe%5D%5B11162698%5D%5B0%5D=142)
Успешно завершено сделок на сумму: [700,000 soʻm](https://jonbranding.amocrm.ru/gtd/leads/list/?useFilter=y&filter_date_switch=closed&filter_date_from=02.11.2026&filter_date_to=02.11.2026&filter%5Bpipe%5D%5B11162698%5D%5B0%5D=142)
Нереализовано сделок : [4](https://jonbranding.amocrm.ru/gtd/leads/list/?useFilter=y&filter_date_switch=closed&filter_date_from=02.11.2026&filter_date_to=02.11.2026&filter%5Bpipe%5D%5B11162698%5D%5B0%5D=143)
Нереализовано сделок на сумму: [0 soʻm](https://jonbranding.amocrm.ru/gtd/leads/list/?useFilter=y&filter_date_switch=closed&filter_date_from=02.11.2026&filter_date_to=02.11.2026&filter%5Bpipe%5D%5B11162698%5D%5B0%5D=143)
Новых сделок за период создано: [11](https://jonbranding.amocrm.ru/gtd/leads/list/?useFilter=y&show_all_leads=y&filter_date_switch=created&filter_date_from=02.11.2026&filter_date_to=02.11.2026)
Новых компаний за период создано: [0](https://jonbranding.amocrm.ru/gtd/contacts/list/companies/?useFilter=y&filter_date_switch=created&filter_date_from=02.11.2026&filter_date_to=02.11.2026)
Новых контактов за период создано: [11](https://jonbranding.amocrm.ru/gtd/contacts/list/contacts/?useFilter=y&filter_date_switch=created&filter_date_from=02.11.2026&filter_date_to=02.11.2026)"""


def test_is_amobot_daily_report():
    assert is_amobot_daily_report(SAMPLE_AMOBOT_REPORT) is True
    assert is_amobot_daily_report("Отчет за (01.11.2026)\nАктивных сделок: 10") is True
    assert is_amobot_daily_report("Oddiy xabar") is False
    assert is_amobot_daily_report("** Просроченная задача **\nJavoxir") is False
    assert is_amobot_daily_report("") is False


def test_extract_report_date():
    assert extract_report_date(SAMPLE_AMOBOT_REPORT) == "02.11.2026"
    assert extract_report_date("Отчет за (15.05.2026)") == "15.05.2026"


def test_translate_amobot_daily_report():
    uz_text = translate_amobot_daily_report(SAMPLE_AMOBOT_REPORT)

    # Check Uzbek headers and emojis
    assert "📊 **Kunlik AmoCRM hisoboti (02.11.2026)**" in uz_text
    assert "🔹 **Davr oxiridagi faol bitimlar:** [479](" in uz_text
    assert "🔹 **Faol bitimlar umumiy summasi:** [181,490,600 soʻm](" in uz_text
    assert "✅ **Muvaffaqiyatli yakunlangan bitimlar:** [2](" in uz_text
    assert "💰 **Muvaffaqiyatli yakunlangan summa:** [700,000 soʻm](" in uz_text
    assert "❌ **Amalga oshmagan (yopilgan) bitimlar:** [4](" in uz_text
    assert "🔻 **Amalga oshmagan bitimlar summasi:** [0 soʻm](" in uz_text
    assert "🆕 **Davr ichida yangi bitimlar:** [11](" in uz_text
    assert "🏢 **Yangi yaratilgan kompaniyalar:** [0](" in uz_text
    assert "👤 **Yangi yaratilgan kontaktlar:** [11](" in uz_text

    # Verify URLs are not broken or altered
    assert "https://jonbranding.amocrm.ru/gtd/leads/list/?filter%5Bstatus%5D=opened" in uz_text
    assert "filter%5Bpipe%5D%5B11162698%5D%5B0%5D=142" in uz_text
    assert "filter%5Bpipe%5D%5B11162698%5D%5B0%5D=143" in uz_text


@pytest.mark.asyncio
async def test_process_amobot_message_success():
    bot_runtime = AsyncMock()
    user_client = AsyncMock()
    db = AsyncMock()
    db.get_state.return_value = []

    with patch("src.services.core.crm.amobot_daily_report.settings") as mock_settings:
        mock_settings.CRM_SALES_REPORT_GROUP_ID = -1003854308552
        mock_settings.CRM_SALES_REPORT_TOPIC_ID = 115
        mock_settings.OWNER_ID = 150074828

        handled = await process_amobot_message(
            SAMPLE_AMOBOT_REPORT,
            bot_runtime=bot_runtime,
            user_client=user_client,
            db=db,
        )

        assert handled is True
        assert bot_runtime.send_message.call_count >= 1
        db.set_state.assert_called_once()
        saved_key, saved_dates = db.set_state.call_args[0]
        assert "02.11.2026" in saved_dates


@pytest.mark.asyncio
async def test_process_amobot_message_dedup():
    bot_runtime = AsyncMock()
    db = AsyncMock()
    db.get_state.return_value = ["02.11.2026"]

    handled = await process_amobot_message(
        SAMPLE_AMOBOT_REPORT,
        bot_runtime=bot_runtime,
        db=db,
    )

    assert handled is False
    bot_runtime.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_check_and_relay_amobot_report():
    bot_runtime = AsyncMock()
    user_client = AsyncMock()
    db = AsyncMock()
    db.get_state.return_value = []

    mock_msg = MagicMock()
    mock_msg.text = SAMPLE_AMOBOT_REPORT
    user_client.get_messages.return_value = [mock_msg]

    with patch("src.services.core.crm.amobot_daily_report.settings") as mock_settings:
        mock_settings.CRM_SALES_REPORT_GROUP_ID = -1003854308552
        mock_settings.CRM_SALES_REPORT_TOPIC_ID = 115
        mock_settings.OWNER_ID = 150074828

        handled = await check_and_relay_amobot_report(
            user_client=user_client,
            bot_runtime=bot_runtime,
            db=db,
        )

        assert handled is True
        user_client.get_messages.assert_called_once_with("amocrm_amobot", limit=5)
