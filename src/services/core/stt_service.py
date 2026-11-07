"""Speech-to-text wrapper. Gemini only (best Uzbek accuracy; Whisper/free STT disabled)."""
import asyncio
import os
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger()


class STTResult:
    def __init__(
        self,
        transcript: str,
        segments: Optional[List[Dict[str, Any]]] = None,
        source: Optional[str] = None,
    ):
        self.transcript = transcript
        self.segments = segments or []
        self.source = source


_PROMPT = (
    "Audio yozuvni diqqat bilan eshiting va aynan eshitilganidek, toʼliq oʼzbek tilida "
    "(lotin alifbosida) yozing. Hech narsa oʼylab topmang. Tushunarli nutq boʼlmasa "
    "boʼsh javob qaytaring."
)


class STTService:
    """Gemini-only STT."""

    def __init__(self) -> None:
        self.provider = "gemini"

    async def transcribe(self, audio_bytes: bytes, mime_type: str) -> Optional[STTResult]:
        """Return ``STTResult`` or ``None`` on failure."""
        try:
            from google import genai
            from google.genai import types

            from src.settings import settings

            api_key = settings.GEMINI_API_KEY.get_secret_value().strip()
            if not api_key:
                logger.warning("[STT] GEMINI_API_KEY is not configured")
                return None
            model = os.getenv("GEMINI_CALL_MODEL") or settings.GEMINI_CALL_MODEL
            client = genai.Client(api_key=api_key)
            part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
            resp = await asyncio.to_thread(
                client.models.generate_content,
                model=model,
                contents=[_PROMPT, part],
                config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=8192),
            )
            text = (getattr(resp, "text", "") or "").strip()
            if text:
                return STTResult(transcript=text, source=f"gemini/{model}")
        except Exception as exc:
            logger.warning("[STT] Gemini failed: %s", type(exc).__name__)
        return None

    async def transcribe_url(self, audio_url: str) -> str:
        """Download audio and transcribe it with Gemini. Returns ``""`` on failure."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as http:
                resp = await http.get(audio_url)
                resp.raise_for_status()
            mime = resp.headers.get("content-type", "audio/mpeg").split(";")[0] or "audio/mpeg"
            result = await self.transcribe(resp.content, mime)
            return result.transcript if result else ""
        except Exception as exc:
            logger.warning("[STT] transcribe_url failed: %s", type(exc).__name__)
            return ""
