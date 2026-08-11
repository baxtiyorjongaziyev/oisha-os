import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.core.wow_service_engine import WowServiceEngine


@pytest.mark.asyncio
async def test_wow_service_lead_first_hour_wow():
    # Arrange
    mock_db = AsyncMock()
    mock_bot = AsyncMock()

    # Stub get_checkpoint to return None first (which schedules/marks notifed)
    # and then return a value with created_at old enough to trigger nudge
    checkpoint_state = {"val": None}
    async def mock_get_checkpoint(ext_id, key):
        return checkpoint_state["val"]

    mock_db.get_checkpoint = mock_get_checkpoint
    mock_db.mark_checkpoint_notified = AsyncMock()

    engine = WowServiceEngine(db=mock_db, bot_client=mock_bot)

    lead = {
        "id": "lead_99",
        "name": "Acme Brand",
        "status_id": 143, # Yangi lid
        "responsible_user_id": 777,
    }

    # Act 1: Initial call (schedules checkpoint)
    await engine._audit_lead_journey(lead)
    mock_db.mark_checkpoint_notified.assert_any_call("lead_99", "lead_first_hour_wow")

    # Act 2: Nudge call (simulate time passed)
    import datetime
    checkpoint_state["val"] = {
        "created_at": (datetime.datetime.now() - datetime.timedelta(hours=1)).isoformat(),
        "status": "Pending",
        "last_notified_at": None,
    }
    await engine._audit_lead_journey(lead)

    # Assert
    mock_bot.send_message.assert_any_call(
        777,
        "🚀 <b>First 1-Hour WOW Nudge: Acme Brand</b>\nYangi bitim yaratilganiga 30 daqiqa bo'ldi. Mijozga birinchi master-klass yoki bonus yuborildimi?\n\n💡 <b>WOW MOMENT:</b>\nMijozga Jon Branding agentligi master-klass va mini-loyihalar to'plamini yuboring.",
        parse_mode="html"
    )


@pytest.mark.asyncio
async def test_wow_service_does_not_message_client_group_on_stage_change():
    # Arrange
    mock_db = AsyncMock()
    mock_bot = AsyncMock()

    mock_db.get_checkpoint = AsyncMock(return_value=None) # No previous stage recorded
    mock_db.mark_checkpoint_notified = AsyncMock()

    engine = WowServiceEngine(db=mock_db, bot_client=mock_bot)

    project = {
        "id": "proj_11",
        "fields": {
            "Loyihani nomi?": "Diyor Web Design",
            "Stage": "Design", # Key capitalized to match FIELD_MAP
            "manager": "@pm_dilshod",
            "Telegram Group ID": -1009999,
        }
    }

    # Mock user lookup
    mock_db.get_user_by_username = AsyncMock(return_value={"user_id": 888})

    # Act
    with patch("src.services.core.wow_service_engine.AirtableSync.resolve_pm_handle", return_value="@pm_dilshod"):
        await engine._audit_project_journey(project)

        # Customer-facing project groups are never messaged automatically.
        for call in mock_bot.send_message.call_args_list:
            assert call.args[0] != -1009999
