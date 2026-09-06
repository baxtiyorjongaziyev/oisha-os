from unittest.mock import AsyncMock

import pytest

from src.services.core.notification_quality import notification_is_publishable
from src.services.proactive.reminders import _execute_telegram_notification


@pytest.mark.parametrize("text", [
    "Noma'lum", "Noma’lum", "Mas'ul aniqlansin", "['recoKLD3kbbVnDW2s']",
    "Uchrashuv Buyurtmachi A $1500", "Loyiha #123456", "ðŸ test", "",
])
def test_unresolved_notification_is_rejected(text):
    assert not notification_is_publishable(text)


def test_named_project_link_is_allowed():
    assert notification_is_publishable(
        "🏗 Atlas — @Inomjon <a href='https://airtable.com/recoKLD3kbbVnDW2s'>Kartasi</a>"
    )


@pytest.mark.asyncio
async def test_bad_report_never_reaches_group_or_dm():
    client = AsyncMock()
    result = await _execute_telegram_notification(
        client, -100123, "PM Stage Push: Noma'lum",
        direct_messages=[{"user_id": 123, "text": "PM push"}],
    )
    assert result["suppressed"]
    assert not result["success"]
    client.send_message.assert_not_called()
    client.get.assert_not_called()
