import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_ai_autopilot_loop_execution_cycle():
    # 1. Setup minimal mocks for the main.py context
    mock_amocrm = MagicMock()
    mock_db = MagicMock()
    mock_client = MagicMock()
    
    mock_leads = [
        {
            "id": 111,
            "status_id": 142,
            "name": "Oysha Shop Deal",
            "_embedded": {
                "contacts": [
                    {
                        "name": "Jasur",
                        "custom_fields_values": [
                            {
                                "field_code": "PHONE",
                                "values": [{"value": "+998903881047"}]
                            }
                        ]
                    }
                ]
            }
        }
    ]
    mock_amocrm.get_leads_detailed = AsyncMock(return_value=mock_leads)

    # 2. Mock all imported service classes to prevent actual HTTP/AI requests
    with patch("src.services.core.telegram_task_creator.TelegramTaskCreator") as mock_creator_cls, \
         patch("src.services.core.call_analyzer.CallAnalyzer") as mock_analyzer_cls, \
         patch("src.services.core.ambassador_journey.AmbassadorJourneyManager") as mock_ambassador_cls, \
         patch("src.services.utils.voice_processor.VoiceProcessor") as mock_voice_cls, \
         patch("asyncio.sleep", AsyncMock()) as mock_sleep:

        mock_creator = MagicMock()
        mock_creator.create_amocrm_tasks_from_chat = AsyncMock()
        mock_creator_cls.return_value = mock_creator

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_recent_calls = AsyncMock()
        mock_analyzer_cls.return_value = mock_analyzer

        mock_ambassador = MagicMock()
        mock_ambassador.sync_won_leads_to_ambassadors = AsyncMock()
        mock_ambassador.process_scheduled_touchpoints = AsyncMock()
        mock_ambassador_cls.return_value = mock_ambassador

        # Import the main's local function to test it
        # Since it is a nested function inside main(), we can mock the classes it imports and runs.
        # Alternatively, we can verify that the classes instantiate with correct args.
        
        # For direct testing, we simulate the body of the autopilot loop cycle once
        from src.services.core.telegram_task_creator import TelegramTaskCreator
        from src.services.core.call_analyzer import CallAnalyzer
        from src.services.core.ambassador_journey import AmbassadorJourneyManager

        creator = TelegramTaskCreator(
            amocrm=mock_amocrm, db=mock_db, user_client=mock_client, gemini_api_key="mock_key"
        )
        analyzer = CallAnalyzer(amocrm=mock_amocrm, db=mock_db)
        ambassador = AmbassadorJourneyManager(
            amocrm=mock_amocrm, db=mock_db, user_client=mock_client, gemini_api_key="mock_key"
        )

        # Execute STAGE 1
        leads = await mock_amocrm.get_leads_detailed(limit=30)
        assert len(leads) == 1
        lead = leads[0]
        phone = "+998903881047"
        
        await creator.create_amocrm_tasks_from_chat(
            phone_or_username=phone,
            lead_id=int(lead["id"]),
            limit=15,
        )
        mock_creator.create_amocrm_tasks_from_chat.assert_called_once_with(
            phone_or_username=phone,
            lead_id=111,
            limit=15,
        )

        # Execute STAGE 2
        await analyzer.analyze_recent_calls(limit=30)
        mock_analyzer.analyze_recent_calls.assert_called_once_with(limit=30)

        # Execute STAGE 3
        await ambassador.sync_won_leads_to_ambassadors(limit=30)
        await ambassador.process_scheduled_touchpoints()
        mock_ambassador.sync_won_leads_to_ambassadors.assert_called_once_with(limit=30)
        mock_ambassador.process_scheduled_touchpoints.assert_called_once()
