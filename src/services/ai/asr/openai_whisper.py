import os
import io
from typing import Optional

import structlog

logger = structlog.get_logger()

class OpenAIWhisperASR:
    """Thin async wrapper around OpenAI Whisper transcription API.
    Uses the free‑tier key from environment variable ``OPENAI_API_KEY``.
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not self.api_key:
            logger.warning("[ASR] OPENAI_API_KEY not set – ASR will be unavailable.")
        self._client = None
        if self.api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except Exception as exc:
                logger.error("[ASR] Failed to init OpenAI client: %s", exc)
                self._client = None

    async def transcribe(self, audio_bytes: bytes, mime_type: str) -> Optional[str]:
        """Transcribe ``audio_bytes`` (any supported mime) to Uzbek latin text.
        Returns ``None`` on failure.
        """
        if not self._client:
            logger.error("[ASR] OpenAI client not available for transcription.")
            return None
        ext = {
            "audio/mpeg": "mp3",
            "audio/mp4": "mp4",
            "audio/ogg": "ogg",
            "audio/wav": "wav",
            "audio/flac": "flac",
            "audio/aac": "aac",
            "audio/webm": "webm",
            "audio/amr": "amr",
        }.get(mime_type, "mp3")
        file_obj = io.BytesIO(audio_bytes)
        file_obj.name = f"call.{ext}"
        try:
            response = await self._client.audio.transcriptions.create(
                model="whisper-1",
                file=file_obj,
                language="uz",
                response_format="text",
                prompt="Telefon qo'ng'irog'ini O'zbek lotinida transkripsiya qiling.",
            )
            return str(response).strip()
        except Exception as exc:
            logger.error("[ASR] Whisper transcription failed: %s", exc)
            return None
