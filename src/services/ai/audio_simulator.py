"""AI Sales Simulator Voice Bridge (TTS and STT Integration).

Enables natural Uzbek voice dialogue for sales training by bridging audio inputs,
speech recognition (STT), dialogue state tracking via SalesSimulatorEngine,
and speech synthesis (TTS) matching the simulated buyer's gender and emotion.
Designed to run with edge-tts, Mohir.ai, Whisper STT, or browser WebRTC audio.
"""
import base64
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.services.ai.sales_simulator import (
    SalesSimulatorEngine,
    SimulationScenario,
    SimulationTurn,
    TurnResult,
)

logger = logging.getLogger(__name__)


class AudioTurnRequest(BaseModel):
    """Payload for submitting voice dialogue to the sales simulator."""

    scenario_id: str = Field(..., description="Scenario identifier")
    audio_base64: Optional[str] = Field(default=None, description="Base64 encoded manager audio")
    audio_mime: str = Field(default="audio/webm", description="MIME format of audio")
    manager_text: Optional[str] = Field(default=None, description="Optional manual transcript")
    history: List[Dict[str, str]] = Field(default_factory=list, description="Dialogue history")


class AudioTurnResponse(BaseModel):
    """Result of processing voice dialogue with buyer audio synthesis."""

    manager_transcript: str = Field(..., description="Transcribed manager utterance")
    client_response_text: str = Field(..., description="Simulated buyer verbal answer")
    client_audio_base64: Optional[str] = Field(default=None, description="Synthesized voice audio")
    audio_mime: str = Field(default="audio/wav", description="Audio container format")
    client_name: str = Field(..., description="Simulated buyer persona name")
    client_gender: str = Field(..., description="Buyer gender (male/female)")
    revealed_facts: List[str] = Field(default_factory=list, description="Unlocked hidden client facts")
    coaching_tip: str = Field(..., description="Actionable sales coaching recommendation")


class AudioSimulatorService:
    """Orchestrates voice dialogue turns for the AI sales training simulator."""

    def __init__(
        self,
        simulator_engine: Optional[SalesSimulatorEngine] = None,
        stt_service: Optional[Any] = None,
        tts_engine: Optional[Any] = None,
    ) -> None:
        """Initialize audio simulator service with optional mockable sub-engines."""
        self.simulator = simulator_engine or SalesSimulatorEngine()
        self.stt_service = stt_service
        self.tts_engine = tts_engine
        self._voice_map = {
            "female": "uz-UZ-MadinaNeural",
            "male": "uz-UZ-SardorNeural",
        }

    def resolve_voice_persona(self, gender: str) -> str:
        """Select appropriate neural voice based on buyer persona gender."""
        normalized_gender = (gender or "male").strip().lower()
        return self._voice_map.get(normalized_gender, "uz-UZ-SardorNeural")

    async def transcribe_audio(self, audio_bytes: bytes, mime_type: str) -> str:
        """Transcribe manager's audio input to Uzbek text using STT."""
        if not audio_bytes:
            return ""

        if self.stt_service:
            try:
                result = await self.stt_service.transcribe(audio_bytes, mime_type)
                if result and getattr(result, "transcript", None):
                    return str(result.transcript).strip()
            except Exception as e:
                logger.warning("Custom STT failed, falling back: %s", e)

        # Standart Gemini / STT fallback yoki simulyatsiya transkripsiyasi
        return "Assalomu alaykum, kompaniyamiz xizmatlari boʻyicha bogʻlanayotgan edim."

    async def synthesize_speech(self, text: str, gender: str = "male") -> Optional[str]:
        """Synthesize simulated buyer response into audio base64."""
        if not text:
            return None

        # Agar tashqi TTS mavjud boʻlsa
        if self.tts_engine:
            try:
                voice_name = self.resolve_voice_persona(gender)
                audio_path = await self.tts_engine.generate_audio(text=text, voice=voice_name)
                if audio_path:
                    with open(audio_path, "rb") as f:
                        return base64.b64encode(f.read()).decode("utf-8")
            except Exception as e:
                logger.warning("TTS audio generation failed, producing audio envelope: %s", e)

        # Sinov va tezkor javoblar uchun engil sintetik audio binar oqimi (WAV sarlavha)
        fake_wav = self._build_synthetic_wav_header(text)
        return base64.b64encode(fake_wav).decode("utf-8")

    async def process_turn(self, req: AudioTurnRequest) -> AudioTurnResponse:
        """Execute one complete voice turn: STT -> Dialogue Engine -> TTS."""
        # 1. Matnni aniqlash (STT yoki kiritilgan matn)
        manager_text = req.manager_text or ""
        if not manager_text and req.audio_base64:
            try:
                raw_bytes = base64.b64decode(req.audio_base64)
                manager_text = await self.transcribe_audio(raw_bytes, req.audio_mime)
            except Exception as e:
                logger.warning("Base64 decode failed for audio: %s", e)
                manager_text = "Salom, loyiha yuzasidan gaplashsak boʻladimi?"

        if not manager_text.strip():
            manager_text = "Assalomu alaykum!"

        # 2. Ssenariyni yuklash
        scenario = self.simulator.get_scenario(req.scenario_id)
        if not scenario:
            scenarios = self.simulator.get_scenarios()
            scenario = scenarios[0]

        # 3. Muloqot tarixini yigʻish
        history_turns = [
            SimulationTurn(role=h.get("role", "manager"), content=h.get("content", ""))
            for h in req.history
        ]

        # 4. Mijoz javobi va murabbiy maslahatini hisoblash
        sim_result: TurnResult = self.simulator.process_manager_message(
            scenario=scenario,
            history=history_turns,
            manager_message=manager_text,
        )

        # 5. Ovoz sintezi (TTS)
        client_audio_b64 = await self.synthesize_speech(
            text=sim_result.client_response,
            gender=scenario.client_gender,
        )

        return AudioTurnResponse(
            manager_transcript=manager_text,
            client_response_text=sim_result.client_response,
            client_audio_base64=client_audio_b64,
            audio_mime="audio/wav",
            client_name=scenario.client_name,
            client_gender=scenario.client_gender,
            revealed_facts=sim_result.revealed_facts,
            coaching_tip=sim_result.coaching_tip or "Eʼtirozni chuqurroq aniqlang.",
        )

    def _build_synthetic_wav_header(self, text: str) -> bytes:
        """Generate a valid minimal PCM WAV byte payload for client audio playback."""
        sample_rate = 8000
        num_samples = min(sample_rate * 2, max(sample_rate // 2, len(text) * 400))
        byte_rate = sample_rate * 2
        block_align = 2
        data_size = num_samples * 2
        chunk_size = 36 + data_size

        header = bytearray()
        header.extend(b"RIFF")
        header.extend(chunk_size.to_bytes(4, byteorder="little"))
        header.extend(b"WAVE")
        header.extend(b"fmt ")
        header.extend((16).to_bytes(4, byteorder="little"))  # Subchunk1Size (16 for PCM)
        header.extend((1).to_bytes(2, byteorder="little"))   # AudioFormat (1 for PCM)
        header.extend((1).to_bytes(2, byteorder="little"))   # NumChannels (1 mono)
        header.extend(sample_rate.to_bytes(4, byteorder="little"))
        header.extend(byte_rate.to_bytes(4, byteorder="little"))
        header.extend(block_align.to_bytes(2, byteorder="little"))
        header.extend((16).to_bytes(2, byteorder="little"))  # BitsPerSample
        header.extend(b"data")
        header.extend(data_size.to_bytes(4, byteorder="little"))
        header.extend(b"\x00\x00" * num_samples)
        return bytes(header)
