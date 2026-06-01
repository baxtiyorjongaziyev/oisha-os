import pytest
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.core.telegram_task_creator import TelegramTaskCreator
from src.services.utils.gemini_fallback import model_candidates


@pytest.fixture(autouse=True)
def reset_task_creator_cooldowns():
    TelegramTaskCreator._gemini_blocked_until = 0.0
    TelegramTaskCreator._telegram_blocked_until = 0.0
    yield
    TelegramTaskCreator._gemini_blocked_until = 0.0
    TelegramTaskCreator._telegram_blocked_until = 0.0


@pytest.mark.asyncio
async def test_transcribe_voice_message_success():
    amocrm_mock = MagicMock()
    db_mock = MagicMock()
    userbot_mock = MagicMock()
    voice_proc_mock = MagicMock()

    # Mock telethon message downloading
    mock_msg = MagicMock()
    mock_msg.id = 123
    mock_msg.download_media = AsyncMock()

    # Mock voice processor STT result
    voice_proc_mock.transcribe = AsyncMock(return_value="Matn: Menga logotip va patent kerak | Maqsad: Patent so'rovi")

    creator = TelegramTaskCreator(
        amocrm=amocrm_mock,
        db=db_mock,
        user_client=userbot_mock,
        voice_processor=voice_proc_mock,
        gemini_api_key="mock_key",
    )

    with patch("os.path.exists", return_value=True), \
         patch("os.remove", MagicMock()):
        
        text = await creator.download_and_transcribe_voice(mock_msg)
        assert text == "Menga logotip va patent kerak"
        mock_msg.download_media.assert_called_once()
        voice_proc_mock.transcribe.assert_called_once()


@pytest.mark.asyncio
async def test_analyze_text_for_tasks_gemini_success():
    amocrm_mock = MagicMock()
    db_mock = MagicMock()

    creator = TelegramTaskCreator(
        amocrm=amocrm_mock,
        db=db_mock,
        gemini_api_key="mock_key",
    )

    # Mock Gemini AI JSON response
    mock_response = MagicMock()
    mock_response.text = (
        '[\n'
        '  {\n'
        '    "text": "Jasurga logotip tekshiruvi narxini yuborish",\n'
        '    "due_in_hours": 24\n'
        '  }\n'
        ']'
    )
    
    creator.genai_client = MagicMock()
    creator.genai_client.aio = MagicMock()
    creator.genai_client.aio.models = MagicMock()
    creator.genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    tasks = await creator.analyze_text_for_tasks("Manager: Assalomu alaykum Jasur. Client: Oysha shop uchun logotip qilmoqchimiz.")
    
    assert len(tasks) == 1
    assert tasks[0]["text"] == "Jasurga logotip tekshiruvi narxini yuborish"
    assert tasks[0]["due_in_hours"] == 24
    creator.genai_client.aio.models.generate_content.assert_awaited_once()
    assert (
        creator.genai_client.aio.models.generate_content.await_args.kwargs["model"]
        == creator.gemini_model
    )


@pytest.mark.asyncio
async def test_analyze_text_for_tasks_pauses_after_gemini_quota_error():
    creator = TelegramTaskCreator(
        amocrm=MagicMock(),
        db=MagicMock(),
        gemini_api_key="mock_key",
    )
    creator.genai_client = MagicMock()
    creator.genai_client.aio.models.generate_content = AsyncMock(
        side_effect=RuntimeError("429 RESOURCE_EXHAUSTED")
    )

    assert await creator.analyze_text_for_tasks("Suhbat") == []
    assert await creator.analyze_text_for_tasks("Takror suhbat") == []
    assert creator.genai_client.aio.models.generate_content.await_count == len(
        model_candidates(creator.gemini_model)
    )
    assert creator.is_cooling_down()
    assert creator.cooldown_reason() == "gemini_quota"


@pytest.mark.asyncio
async def test_analyze_text_for_tasks_uses_local_parser_during_gemini_cooldown():
    creator = TelegramTaskCreator(
        amocrm=MagicMock(),
        db=MagicMock(),
        gemini_api_key="mock_key",
    )
    creator.genai_client = MagicMock()
    creator.genai_client.aio.models.generate_content = AsyncMock()
    TelegramTaskCreator._gemini_blocked_until = time.time() + 600

    tasks = await creator.analyze_text_for_tasks(
        "Mijoz: Narxini ayting.\nMenejer: Bugun tijorat taklifini yuboraman."
    )

    assert tasks == [
        {
            "text": "Telegram suhbatidan: Bugun tijorat taklifini yuboraman.",
            "due_in_hours": 6,
        }
    ]
    creator.genai_client.aio.models.generate_content.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_tasks_pauses_after_telegram_flood_wait():
    userbot_mock = MagicMock()
    userbot_mock.get_input_entity = AsyncMock(
        side_effect=RuntimeError(
            "A wait of 9924 seconds is required (caused by GetContactsRequest)"
        )
    )
    creator = TelegramTaskCreator(
        amocrm=MagicMock(),
        db=MagicMock(),
        user_client=userbot_mock,
    )

    assert await creator.create_amocrm_tasks_from_chat("+998000000000", 1) == []
    assert await creator.create_amocrm_tasks_from_chat("+998000000001", 2) == []
    userbot_mock.get_input_entity.assert_awaited_once()
    assert creator.cooldown_seconds_remaining() >= 9923
    assert creator.cooldown_reason() == "telegram_entity_lookup"


@pytest.mark.asyncio
async def test_resolve_dialog_entity_imports_and_cleans_up_temporary_contact():
    userbot_mock = AsyncMock()
    userbot_mock.get_input_entity = AsyncMock(
        side_effect=[ValueError("Could not find the input entity"), "peer"]
    )
    userbot_mock.return_value = SimpleNamespace(users=[SimpleNamespace(id=77)])
    creator = TelegramTaskCreator(
        amocrm=MagicMock(),
        db=MagicMock(),
        user_client=userbot_mock,
    )

    entity, temporary_contact_id = await creator._resolve_dialog_entity(
        "+998 90 123 45 67"
    )
    await creator._delete_temporary_contact(temporary_contact_id)

    assert entity == "peer"
    assert temporary_contact_id == 77
    assert userbot_mock.await_count == 2


@pytest.mark.asyncio
async def test_persisted_telegram_cooldown_skips_lookup_after_restart():
    db_mock = MagicMock()
    db_mock.get_state = AsyncMock(
        side_effect=["0", str(time.time() + 600)]
    )
    userbot_mock = MagicMock()
    userbot_mock.get_input_entity = AsyncMock(return_value="peer")
    creator = TelegramTaskCreator(
        amocrm=MagicMock(),
        db=db_mock,
        user_client=userbot_mock,
    )

    assert await creator.create_amocrm_tasks_from_chat("+998000000000", 1) == []
    userbot_mock.get_input_entity.assert_not_awaited()
    assert creator.cooldown_seconds_remaining() >= 598


@pytest.mark.asyncio
async def test_create_amocrm_tasks_from_chat_success():
    amocrm_mock = MagicMock()
    db_mock = MagicMock()
    userbot_mock = MagicMock()
    voice_proc_mock = MagicMock()

    # 1 text message, 1 voice note message
    msg_text = MagicMock()
    msg_text.id = 1
    msg_text.out = False
    msg_text.voice = None
    msg_text.audio = None
    msg_text.message = "Assalomu alaykum Baxtiyor. Oysha shopga patent kerak."

    msg_voice = MagicMock()
    msg_voice.id = 2
    msg_voice.out = True
    msg_voice.voice = MagicMock()
    msg_voice.audio = None
    msg_voice.message = None

    userbot_mock.get_input_entity = AsyncMock(return_value="peer_id")
    userbot_mock.get_messages = AsyncMock(return_value=[msg_text, msg_voice])

    creator = TelegramTaskCreator(
        amocrm=amocrm_mock,
        db=db_mock,
        user_client=userbot_mock,
        voice_processor=voice_proc_mock,
        gemini_api_key="mock_key",
    )

    # Mock tasks list from Gemini
    gemini_tasks = [
        {"text": "Jasurga ekspert tekshiruvi narxini jo'natish", "due_in_hours": 6}
    ]

    amocrm_mock.create_task = AsyncMock(return_value=True)

    with patch.object(creator, "download_and_transcribe_voice", return_value="Tekshirish pullikmi bepulmi?") as mock_transcribe, \
         patch.object(creator, "analyze_text_for_tasks", return_value=gemini_tasks) as mock_analyze:

        results = await creator.create_amocrm_tasks_from_chat(
            phone_or_username="+998903881047",
            lead_id=45118637,
            limit=10,
        )

        assert len(results) == 1
        assert results[0]["text"] == "Jasurga ekspert tekshiruvi narxini jo'natish"
        assert results[0]["due_in_hours"] == 6

        # Check AmoCRM create_task called
        amocrm_mock.create_task.assert_called_once()
        mock_transcribe.assert_called_once_with(msg_voice)
        mock_analyze.assert_called_once()
