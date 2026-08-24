"""Unit test for CallAnalyzer proactive Telegram alerts."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.core.call_analyzer import CallAnalyzer


@pytest.mark.asyncio
async def test_notify_telegram_call_analysis_triggers_bot():
    mock_amocrm = MagicMock()
    mock_amocrm.subdomain = "testbrand"
    mock_db = MagicMock()

    analyzer = CallAnalyzer(amocrm=mock_amocrm, db=mock_db)

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(return_value=True)

    with patch("src.context.app_ctx.bot_runtime", mock_bot), \
         patch("src.settings.settings.AMOCRM_ALERT_FORWARD_GROUP_ID", -100123456789), \
         patch("src.settings.settings.AMOCRM_ALERT_FORWARD_TOPIC_ID", 443):

        await analyzer._notify_telegram_call_analysis(
            lead_id=98765,
            call_id="call-999",
            category="Mijoz",
            summary="Mijoz yangi qadoq dizayni so'radi",
            client_mood="Ijobiy",
            next_steps="Ertaga 11:00 da smeta yuborish",
            duration_seconds=145,
            manager_name="Baxtiyorjon",
            caller_phone="+998901234567",
            analysis={
                "natija": "Kelishuv",
                "sifat_bahosi": 92,
                "etirozlar": ["Narx biroz qimmat tuyuldi, ammo qiymat tushuntirildi"],
            },
            task_id="task-777",
        )

        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert call_kwargs["chat_id"] == -100123456789
        assert call_kwargs["reply_to_message_id"] == 443
        assert "Call Intelligence" in call_kwargs["text"]
        assert "AmoCRM Lead #98765" in call_kwargs["text"]
        assert "92/100" in call_kwargs["text"]
        assert "Task #task-777" in call_kwargs["text"]
