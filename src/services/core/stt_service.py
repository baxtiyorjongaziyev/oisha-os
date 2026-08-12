import os
import structlog
from typing import Optional, List, Dict, Any

logger = structlog.get_logger()

class STTResult:
    def __init__(self, transcript: str, segments: Optional[List[Dict[str, Any]]] = None):
        self.transcript = transcript
        self.segments = segments or []

class STTService:
    """Simple wrapper around available STT providers.
    Currently uses the free_ai_router (Gemini/Free) as default.
    Future providers (Google, Azure) can be added via env `SALESCOACH_STT_PROVIDER`.
    """

    def __init__(self):
        self.provider = os.getenv("SALESCOACH_STT_PROVIDER", "free").lower()
        self._router = None

    async def _ensure_router(self):
        if self._router is None:
            from src.services.utils.free_ai_router import get_free_ai_router
            self._router = get_free_ai_router()

    async def transcribe(self, audio_bytes: bytes, mime_type: str) -> Optional[STTResult]:
        """Transcribe audio and (optionally) return speaker diarization segments.
        Returns ``STTResult`` or ``None`` on failure.
        """
        await self._ensure_router()
        try:
            routed = await self._router.transcribe_audio(audio_bytes, mime_type)
            if routed and getattr(routed, "text", None):
                return STTResult(transcript=routed.text, segments=getattr(routed, "segments", []))
        except Exception as exc:
            logger.warning("[STT] Provider %s failed: %s", self.provider, type(exc).__name__)
        return None
