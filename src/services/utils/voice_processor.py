import os
import asyncio
import logging
from google import genai
from typing import Optional

logger = logging.getLogger(__name__)


class VoiceProcessor:
    """
    Processes audio files (call recordings, voice messages) using Gemini for
    Uzbek transcription and summarization.
    """

    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.0-flash"

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
            logger.info(f"[VOICE] Uploading {file_path} ({file_size} bytes) to Gemini...")
            audio_file = await self.client.aio.files.upload(path=file_path)

            if mode == "call":
                prompt = self._call_recording_prompt()
            else:
                prompt = self._voice_message_prompt()

            response = await self.client.aio.models.generate_content(
                model=self.model_name, contents=[audio_file, prompt]
            )

            if response.text:
                text = response.text.strip()
                logger.info(f"[VOICE] Transcription successful: {text[:80]}...")
                return text

        except Exception as e:
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
