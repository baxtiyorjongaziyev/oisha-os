import os
import asyncio
import logging
import mimetypes
from google import genai
from typing import Optional

from src.settings import settings
from src.services.utils.gemini_fallback import (
    generate_content_with_fallback,
    is_quota_error,
    is_transient_error,
)

logger = logging.getLogger(__name__)


class VoiceProcessor:
    """
    Processes audio files through free-first STT, with Gemini as a fallback.
    """

    _quota_blocked_until = 0.0

    def __init__(self, api_key: str, model_name: Optional[str] = None):
        self.client = genai.Client(api_key=api_key)
        self.model_name = (
            model_name
            or os.getenv("GEMINI_VOICE_MODEL")
            or settings.GEMINI_CALL_MODEL
        )
        self.quota_cooldown_seconds = int(
            os.getenv("GEMINI_VOICE_COOLDOWN_SECONDS", "21600")
        )
        self.transient_cooldown_seconds = int(
            os.getenv("GEMINI_TRANSIENT_COOLDOWN_SECONDS", "120")
        )
        from src.services.utils.free_ai_router import get_free_ai_router

        self.free_ai_router = get_free_ai_router()

    @classmethod
    def _quota_cooling_down(cls) -> bool:
        return cls._quota_blocked_until > asyncio.get_running_loop().time()

    def _pause_for(self, seconds: int) -> None:
        type(self)._quota_blocked_until = (
            asyncio.get_running_loop().time() + seconds
        )

    async def _upload_with_retry(self, file_path: str):
        last_error = None
        for attempt in range(2):
            try:
                return await self.client.aio.files.upload(file=file_path)
            except Exception as exc:
                last_error = exc
                if is_quota_error(exc) or not is_transient_error(exc) or attempt:
                    raise
                logger.warning(
                    "[VOICE] Gemini upload unavailable (%s); retrying.",
                    type(exc).__name__,
                )
                await asyncio.sleep(0.5)
        raise last_error or RuntimeError("Gemini upload failed")

    async def transcribe(self, file_path: str, mode: str = "voice") -> Optional[str]:
        """
        Uploads an audio file to Gemini and returns the transcription.

        Args:
            file_path: Path to the audio file (mp3, ogg, wav, mp4, m4a).
            mode: 'voice' for Telegram voice messages, 'call' for phone call recordings.
        """
        if not os.path.exists(file_path):
            logger.error(f"[VOICE] File not found: {file_path}")
            return None

        file_size = os.path.getsize(file_path)
        if file_size == 0:
            logger.error(f"[VOICE] Empty file: {file_path}")
            return None

        try:
            with open(file_path, "rb") as audio_file:
                audio_bytes = audio_file.read()
            mime_type = mimetypes.guess_type(file_path)[0] or "audio/ogg"
            routed = await self.free_ai_router.transcribe_audio(audio_bytes, mime_type)
            if routed and routed.text:
                logger.info(
                    "[VOICE] Free-first transcription provider=%s model=%s",
                    routed.provider,
                    routed.model,
                )
                return routed.text
        except Exception as exc:
            logger.warning(
                "[VOICE] Free-first transcription unavailable: %s",
                type(exc).__name__,
            )

        if self._quota_cooling_down():
            logger.info("[VOICE] Gemini quota cooldown active; skipping transcription.")
            return None

        try:
            logger.info(f"[VOICE] Uploading {file_path} ({file_size} bytes) to Gemini...")
            audio_file = await self._upload_with_retry(file_path)

            if mode == "call":
                prompt = self._call_recording_prompt()
            else:
                prompt = self._voice_message_prompt()

            response, _ = await generate_content_with_fallback(
                self.client,
                primary_model=self.model_name,
                contents=[audio_file, prompt],
                env_name="GEMINI_VOICE_FALLBACK_MODELS",
                log_prefix="[VOICE]",
            )

            if response.text:
                text = response.text.strip()
                logger.info(f"[VOICE] Transcription successful: {text[:80]}...")
                return text

        except Exception as e:
            if is_quota_error(e):
                self._pause_for(self.quota_cooldown_seconds)
                logger.warning(
                    "[VOICE] Gemini quota exhausted; pausing transcription for %ss.",
                    self.quota_cooldown_seconds,
                )
            elif is_transient_error(e):
                self._pause_for(self.transient_cooldown_seconds)
                logger.warning(
                    "[VOICE] Gemini temporarily unavailable; retrying after %ss.",
                    self.transient_cooldown_seconds,
                )
            else:
                logger.error(f"[VOICE] Processing error: {e}")

        return None

    def _call_recording_prompt(self) -> str:
        """Prompt optimized for Uzbek phone call recordings with two speakers."""
        return (
            "Siz O'zbek tili mutaxassisi va qo'ng'iroq tahlilchisisiz. "
            "Ushbu telefon qo'ng'irog'ini diqqat bilan eshiting va quyidagilarni bajaring:\n\n"
            "1. **TO'LIQ TRANSKRIPSIYA**: Har ikki tomonning so'zlarini aniq yozing.\n"
            "   Format:\n"
            "   A: [birinchi shaxs so'zlari]\n"
            "   B: [ikkinchi shaxs so'zlari]\n"
            "   (Agar tilni aniqlay olmasangiz, eng yaqin ma'noni yozing)\n\n"
            "2. **AGAR SUS ESHITILSA**: To'liq eshita olmasangiz ham, eshitgan so'zlaringizni yozing.\n\n"
            "Faqat transkripsiyani yozing. Boshqa izohlar shart emas.\n"
            "Muhim: O'zbek tilida bo'lsa O'zbekcha, Ruscha bo'lsa Ruscha yozing."
        )

    def _voice_message_prompt(self) -> str:
        """Prompt for Telegram voice messages."""
        return (
            "Siz Oisha-OS ovozli yordamchisisiz. Ushbu ovozli xabarni diqqat bilan eshiting va:\n"
            "1. Matnga o'giring (Full Transcription).\n"
            "2. Asosiy maqsadni (Summary) 1 ta gapda yozing.\n"
            "3. Agar xabarda bizga tegishli (Jon.Branding xizmatlari) ehtiyoj bo'lsa, uni belgilang.\n\n"
            "Format: Matn: [matn] | Maqsad: [maqsad]"
        )

    async def transcribe_call(self, file_path: str) -> Optional[str]:
        """Shortcut for call recording transcription."""
        return await self.transcribe(file_path, mode="call")

    async def cleanup(self, file_path: str):
        """Deletes the temporary audio file."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"[VOICE] Cleaned up temp file: {file_path}")
        except Exception as e:
            logger.warning(f"[VOICE] Failed to delete temp file {file_path}: {e}")
