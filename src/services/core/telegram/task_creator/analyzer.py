"""
Voice transcription, Gemini task analysis, and keyword fallback extraction mixin.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tempfile
import time
from typing import Any, Dict, List, Optional
import structlog

from src.settings import settings
from src.services.utils.gemini_fallback import (
    generate_content_with_fallback,
    is_quota_error,
)

logger = structlog.get_logger()

try:
    from google import genai
    from google.genai import types as genai_types
except Exception:
    logger.error("Google Generative AI imports failed in %s", __name__, exc_info=True)
    genai = None
    genai_types = None


class TaskAnalyzerMixin:
    """Handles audio transcription and text analysis to extract action items."""

    async def download_and_transcribe_voice(self, message: Any) -> str:
        """Downloads a Telegram voice note and transcribes it using VoiceProcessor."""
        if not self.voice_processor or not self.user_client:
            logger.warning("[TELEGRAM_TASK] Voice processor or Telegram client missing.")
            return ""

        temp_path = f"temp_voice_{message.id}.ogg"
        try:
            logger.info(f"[TELEGRAM_TASK] Downloading Telegram voice note message {message.id}...")
            # Telethon message download
            await message.download_media(file=temp_path)
            
            if not os.path.exists(temp_path):
                logger.warning(f"[TELEGRAM_TASK] Download failed for message {message.id}.")
                return ""

            # Transcribe via Gemini
            logger.info(f"[TELEGRAM_TASK] Transcribing downloaded Telegram voice note...")
            transcript = await self.voice_processor.transcribe(temp_path, mode="voice")
            
            # Transcription format cleanup (Matn: ... | Maqsad: ...)
            if transcript:
                # Remove Gemini prompt metadata if returned
                if "Matn:" in transcript:
                    parts = transcript.split("|")
                    text_part = parts[0].replace("Matn:", "").strip()
                    return text_part
                return transcript
        except Exception as e:
            logger.error(f"[TELEGRAM_TASK] Error transcribing voice message {message.id}: {e}")
        finally:
            # Always delete temp file
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    logger.debug("[TELEGRAM_TASK] Failed to remove temp voice file %s", temp_path, exc_info=True)

        return ""

    async def analyze_text_for_tasks(self, full_chat_text: str) -> List[Dict[str, Any]]:
        """
        Uses Gemini to extract a list of structured action items and relative deadlines.
        Returns a list of dicts: [{'text': 'vazifa matni', 'due_in_hours': 24}]
        """
        prompt = (
            f"Siz Jon Branding agency AI operatsion tizimi - Oishasiz. "
            f"Quyida menejer va mijoz o'rtasidagi Telegram suhbatining (matn va transkripsiya) tarixi taqdim etilgan:\n\n"
            f"--- SUHBAT BOSHLANISHI ---\n"
            f"{full_chat_text}\n"
            f"--- SUHBAT YAKUNI ---\n\n"
            f"Ushbu suhbatni diqqat bilan tahlil qiling va HALI BAJARILMAGAN, kutilayotgan harakatlarni aniqlang.\n\n"
            f"MUHIM QOIDALAR:\n"
            f"1. Agar suhbatda biror ish ALLAQACHON bajarilganligini ko'rsatuvchi belgilar bo'lsa — bu ish uchun VAZIFA YARATMANG.\n"
            f"   Bajarilganlik belgilari:\n"
            f"   - Menejer 'yubordik', 'jo'natdik', 'tayyorladik', 'qildik', 'yuborib qo'ydik', 'tashlab qo'ydik' deb yozgan\n"
            f"   - Menejer shu so'rovga javob bergan (masalan, rekvizit so'raldi → menejer rekvizit yubordi)\n"
            f"   - Mijoz 'rahmat', 'oldim', 'ko'rdim', 'yaxshi', 'tushunarli' deb tasdiqlagan\n"
            f"   - Shartnoma, hujjat, fayl, link yuborilganligi ko'rinib turibdi\n"
            f"2. Faqat hali javob berilmagan, bajarilmagan, kutilayotgan ishlarni oling.\n"
            f"3. Nisbiy muddatlarni aniqlang (due_in_hours):\n"
            f"   - Vaqt aytilmagan bo'lsa: 24 soat\n"
            f"   - 'bugun': 6 soat\n"
            f"   - 'ertaga': 24 soat\n"
            f"   - 'dushanba': 72 soat\n"
            f"4. Agar suhbatda bajarilishi kerak bo'lgan hech narsa qolmagan bo'lsa — bo'sh massiv [] qaytaring.\n\n"
            f"Javobni FAQAT quyidagi JSON formatida qaytaring, hech qanday qo'shimcha matn yoki izohsiz:\n"
            f"[\n"
            f"  {{\n"
            f"    \"text\": \"Mijozga ekspert tekshiruvi xizmati narxi va karta raqamini yuborish\",\n"
            f"    \"due_in_hours\": 24\n"
            f"  }}\n"
            f"]"
        )

        await self._load_persisted_cooldowns()
        if not self.genai_client:
            logger.warning("[TELEGRAM_TASK] Gemini client missing; using local extraction.")
            return self._fallback_extract_tasks(full_chat_text)
        if self._gemini_cooldown_remaining():
            logger.info("[TELEGRAM_TASK] Gemini cooldown active; using local extraction.")
            return self._fallback_extract_tasks(full_chat_text)

        try:
            config = genai_types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            )
            response, _ = await generate_content_with_fallback(
                self.genai_client,
                primary_model=self.gemini_model,
                contents=prompt,
                config=config,
                env_name="GEMINI_TELEGRAM_TASK_FALLBACK_MODELS",
                log_prefix="[TELEGRAM_TASK]",
            )
            raw_json = (response.text or "").strip()
            if raw_json:
                data = json.loads(raw_json)
                if isinstance(data, list):
                    return data
        except Exception as e:
            if is_quota_error(e):
                self._pause_gemini()
                await self._persist_cooldowns()
                logger.warning(
                    "[TELEGRAM_TASK] Gemini quota exhausted; local extraction active for %ss.",
                    self.gemini_cooldown_seconds,
                )
            else:
                logger.warning(
                    "[TELEGRAM_TASK] Gemini task extraction unavailable; using local extraction: %s",
                    type(e).__name__,
                )

        return self._fallback_extract_tasks(full_chat_text)

    @staticmethod
    def _fallback_extract_tasks(full_chat_text: str) -> List[Dict[str, Any]]:
        """Conservative Uzbek/Russian promise parser used during AI outages."""
        action_markers = (
            "yubor",
            "jo'nat",
            "jonat",
            "tashla",
            "qo'ng'iroq",
            "qong'iroq",
            "bog'lan",
            "tekshir",
            "aytaman",
            "beraman",
            "tayyorla",
            "ko'rsat",
            "uchrash",
            "yozaman",
            "otprav",
            "скин",
            "позвон",
            "провер",
        )
        manager_prefixes = ("menejer:", "manager:", "oisha:")
        tasks: List[Dict[str, Any]] = []
        seen = set()
        for raw_line in full_chat_text.splitlines():
            line = raw_line.strip()
            lowered = line.lower()
            if not lowered.startswith(manager_prefixes):
                continue
            if not any(marker in lowered for marker in action_markers):
                continue
            task_text = line.split(":", 1)[-1].strip()
            if not task_text or task_text.lower() in seen:
                continue
            due_hours = 24
            if "bugun" in lowered or "сегодня" in lowered:
                due_hours = 6
            elif "ertaga" in lowered or "завтра" in lowered:
                due_hours = 24
            elif "dushanba" in lowered or "понедельник" in lowered:
                due_hours = 72
            seen.add(task_text.lower())
            tasks.append(
                {
                    "text": f"Telegram suhbatidan: {task_text}"[:500],
                    "due_in_hours": due_hours,
                }
            )
        return tasks[:5]
