from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.ai.asr.openai_whisper import MAX_AUDIO_BYTES, OpenAIWhisperASR


def _client(response=" salom "):
    create = AsyncMock(return_value=response)
    return SimpleNamespace(
        audio=SimpleNamespace(transcriptions=SimpleNamespace(create=create))
    ), create


@pytest.mark.asyncio
async def test_transcribe_uses_async_client_and_normalizes_mime_type():
    client, create = _client()
    adapter = OpenAIWhisperASR(client=client)

    assert await adapter.transcribe(b"audio", "audio/ogg; codecs=opus") == "salom"
    kwargs = create.await_args.kwargs
    assert kwargs["file"].name == "audio.ogg"
    assert kwargs["language"] == "uz"


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["empty", "mime", "oversize"])
async def test_transcribe_rejects_invalid_input_without_api_call(case):
    client, create = _client()
    adapter = OpenAIWhisperASR(client=client)
    audio = b"x" * (MAX_AUDIO_BYTES + 1) if case == "oversize" else b"x"
    mime_type = "application/octet-stream" if case == "mime" else "audio/mpeg"
    if case == "empty":
        audio = b""

    assert await adapter.transcribe(audio, mime_type) is None
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_transcribe_fails_closed_on_provider_error():
    client, create = _client()
    create.side_effect = RuntimeError("provider unavailable")

    assert await OpenAIWhisperASR(client=client).transcribe(b"audio", "audio/wav") is None
