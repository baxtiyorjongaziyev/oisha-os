
import os
import logging
import asyncio
from google import genai
from google.genai import types
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

class VoiceProcessor:
    """
    Processes Telegram voice messages using Gemini 2.0 Flash for transcription and summarization.
    """

    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.0-flash"

    async def transcribe(self, file_path: str) -> Optional[str]:
        """
        Uploads an audio file to Gemini and returns the transcription/summary asynchronously.
        """
        try:
            # 1. Upload to Gemini Files API (Async)
            logger.info(f"[VOICE] Uploading {file_path} to Gemini...")
            audio_file = await self.client.aio.files.upload(path=file_path)
            
            # 2. Wait for processing (Status check if needed)
            # For small voice notes (<1min), upload is usually sufficient for generation
            
            # 3. Generate Transcription and Business Insight (Async)
            prompt = (
                "Siz Oisha-OS ovozli yordamchisisiz. Ushbu ovozli xabarni diqqat bilan eshiting va: "
                "1. Matnga o'giring (Full Transcription). "
                "2. Asosiy maqsadni (Summary) 1 ta gapda yozing. "
                "3. Agar xabarda bizga tegishli (Jon.Branding xizmatlari) ehtiyoj bo'lsa, uni belgilang. "
                "\n\nFormat: Matn: [matn] | Maqsad: [maqsad]"
            )
            
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=[audio_file, prompt]
            )
            
            if response.text:
                logger.info(f"[VOICE] Transcription successful: {response.text[:50]}...")
                return response.text
                
        except Exception as e:
            logger.error(f"[VOICE] Processing error: {e}")
        
        return None

    async def cleanup(self, file_path: str):
        """Deletes the temporary audio file."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.warning(f"[VOICE] Failed to delete temp file {file_path}: {e}")
