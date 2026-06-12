from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.utils.voice_processor import VoiceProcessor


@pytest.fixture(autouse=True)
def reset_voice_processor_cooldown():
    VoiceProcessor._quota_blocked_until = 0.0
    yield
    VoiceProcessor._quota_blocked_until = 0.0


@pytest.mark.asyncio
async def test_transcribe_uploads_audio_with_google_sdk_file_argument(tmp_path):
    audio_path = tmp_path / "voice.ogg"
    audio_path.write_bytes(b"audio")
    processor = VoiceProcessor(api_key="mock_key")
    processor.free_ai_router.transcribe_audio = AsyncMock(return_value=None)
    processor.client = MagicMock()
    processor.client.aio.files.upload = AsyncMock(return_value="uploaded-audio")
    processor.client.aio.models.generate_content = AsyncMock(
        return_value=SimpleNamespace(text="Matn: Assalomu alaykum")
    )

    result = await processor.transcribe(str(audio_path))

    assert result == "Matn: Assalomu alaykum"
    processor.client.aio.files.upload.assert_awaited_once_with(file=str(audio_path))
    assert (
        processor.client.aio.models.generate_content.await_args.kwargs["model"]
        == processor.model_name
    )


@pytest.mark.asyncio
async def test_transcribe_pauses_after_gemini_quota_error(tmp_path):
    audio_path = tmp_path / "voice.ogg"
    audio_path.write_bytes(b"audio")
    processor = VoiceProcessor(api_key="mock_key")
    processor.free_ai_router.transcribe_audio = AsyncMock(return_value=None)
    processor.client = MagicMock()
    processor.client.aio.files.upload = AsyncMock(
        side_effect=RuntimeError("429 RESOURCE_EXHAUSTED")
    )

    assert await processor.transcribe(str(audio_path)) is None
    assert await processor.transcribe(str(audio_path)) is None
    processor.client.aio.files.upload.assert_awaited_once()


@pytest.mark.asyncio
async def test_transcribe_uses_free_first_stt_before_gemini(tmp_path):
    audio_path = tmp_path / "voice.ogg"
    audio_path.write_bytes(b"audio")
    processor = VoiceProcessor(api_key="mock_key")
    processor.free_ai_router.transcribe_audio = AsyncMock(
        return_value=SimpleNamespace(
            text="Groq matni",
            provider="groq",
            model="whisper-large-v3-turbo",
        )
    )
    processor.client = MagicMock()
    processor.client.aio.files.upload = AsyncMock()

    result = await processor.transcribe(str(audio_path))

    assert result == "Groq matni"
    processor.free_ai_router.transcribe_audio.assert_awaited_once_with(
        b"audio", "audio/ogg"
    )
    processor.client.aio.files.upload.assert_not_awaited()
