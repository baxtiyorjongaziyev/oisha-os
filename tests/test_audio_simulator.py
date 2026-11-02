"""Unit tests for AI Sales Simulator Voice Bridge."""
import base64
import pytest

from src.services.ai.audio_simulator import (
    AudioSimulatorService,
    AudioTurnRequest,
    AudioTurnResponse,
)


@pytest.mark.asyncio
async def test_audio_simulator_text_turn():
    """Verify processing text turn produces simulated buyer voice."""
    service = AudioSimulatorService()
    req = AudioTurnRequest(
        scenario_id="ask_before_selling",
        manager_text="Assalomu alaykum Aziz aka! Narxdan oldin sizga qanday natija kerakligini bilmoqchiman.",
    )
    res: AudioTurnResponse = await service.process_turn(req)

    assert res.manager_transcript.startswith("Assalomu alaykum")
    assert len(res.client_response_text) > 0
    assert res.client_name == "Aziz"
    assert res.client_gender == "male"
    assert res.client_audio_base64 is not None
    assert len(res.client_audio_base64) > 10
    assert res.audio_mime == "audio/wav"
    assert len(res.coaching_tip) > 0


@pytest.mark.asyncio
async def test_audio_simulator_with_audio_base64():
    """Verify processing base64 audio executes STT and returns synthesized voice."""
    service = AudioSimulatorService()
    dummy_audio_b64 = base64.b64encode(b"dummy_pcm_audio_bytes").decode("utf-8")
    req = AudioTurnRequest(
        scenario_id="first_30_seconds",
        audio_base64=dummy_audio_b64,
        audio_mime="audio/webm",
    )
    res: AudioTurnResponse = await service.process_turn(req)

    assert res.manager_transcript != ""
    assert res.client_audio_base64 is not None
    assert res.client_name == "Kamola"
    assert res.client_gender == "female"


@pytest.mark.asyncio
async def test_audio_simulator_with_mock_stt_and_tts(tmp_path):
    """Verify custom STT service and TTS engine are called when provided."""
    class FakeSTTResult:
        transcript = "Biz sizning kompaniyangizga maxsus taklif beramiz."

    class FakeSTTService:
        async def transcribe(self, audio_bytes: bytes, mime_type: str):
            return FakeSTTResult()

    class FakeTTSEngine:
        async def generate_audio(self, text: str, voice: str):
            temp_file = tmp_path / "tts_out.mp3"
            temp_file.write_bytes(b"ID3_FAKE_MP3_CONTENT")
            return str(temp_file)

    service = AudioSimulatorService(
        stt_service=FakeSTTService(),
        tts_engine=FakeTTSEngine(),
    )
    req = AudioTurnRequest(
        scenario_id="ask_before_selling",
        audio_base64=base64.b64encode(b"some_audio").decode("utf-8"),
    )
    res = await service.process_turn(req)

    assert "taklif" in res.manager_transcript
    decoded_audio = base64.b64decode(res.client_audio_base64)
    assert decoded_audio == b"ID3_FAKE_MP3_CONTENT"
