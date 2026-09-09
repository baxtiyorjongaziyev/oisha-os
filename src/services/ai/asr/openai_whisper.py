"""Async OpenAI Whisper adapter with fail-closed input validation."""
from __future__ import annotations

import io
import os
from typing import Any, Optional

import structlog

logger = structlog.get_logger()

_EXTENSIONS = {
    "audio/mpeg": "mp3",
    "audio/mp4": "mp4",
    "audio/ogg": "ogg",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/flac": "flac",
    "audio/aac": "aac",
    "audio/webm": "webm",
}
MAX_AUDIO_BYTES = 25 * 1024 * 1024


class OpenAIWhisperASR:
    """Small async wrapper around OpenAI audio transcription."""

    def __init__(self, *, api_key: Optional[str] = None, client: Any = None) -> None:
        key = (api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")).strip()
        self._client = client
        if self._client is None and key:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(api_key=key)
            except (ImportError, TypeError, ValueError):
                logger.warning("OpenAI ASR client is unavailable", exc_info=True)

    async def transcribe(self, audio_bytes: bytes, mime_type: str) -> Optional[str]:
        """Return Uzbek transcript, or ``None`` when unavailable/invalid."""
        if self._client is None:
            return None
        if not audio_bytes or len(audio_bytes) > MAX_AUDIO_BYTES:
            return None
        normalized_mime = mime_type.split(";", 1)[0].strip().lower()
        extension = _EXTENSIONS.get(normalized_mime)
        if extension is None:
            return None

        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = f"audio.{extension}"
        try:
            response = await self._client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="uz",
                response_format="text",
                prompt="Telefon qo'ng'irog'ini o'zbek lotin yozuvida transkripsiya qiling.",
            )
        except Exception:
            logger.warning("OpenAI ASR transcription failed", exc_info=True)
            return None
        transcript = str(response).strip()
        return transcript or None
