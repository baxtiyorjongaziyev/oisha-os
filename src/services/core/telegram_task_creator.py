"""
telegram_task_creator.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Core service to analyze Telegram messaging logs and voice notes using Gemini,
extract concrete follow-up action items (vazifalar), and automatically insert
them into AmoCRM deals as tasks.
"""

import os
import time
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from google import genai
    from google.genai import types as genai_types
except Exception:
    genai = None
    genai_types = None

logger = logging.getLogger(__name__)


class TelegramTaskCreator:
    """
    Scans Telegram dialogues (text + voice), transcribes audios inline,
    analyzes the overall conversation logic for promises, commitments, and deadlines,
    and registers them automatically in AmoCRM as active Tasks.
    """

    def __init__(
        self,
        amocrm: Any,
        db: Any,
        user_client: Optional[Any] = None,
        voice_processor: Optional[Any] = None,
        gemini_api_key: Optional[str] = None,
    ):
        self.amocrm = amocrm
        self.db = db
        self.user_client = user_client
        self.voice_processor = voice_processor
        self.gemini_api_key = gemini_api_key

        self.genai_client = None
        if gemini_api_key and genai is not None:
            try:
                self.genai_client = genai.Client(api_key=gemini_api_key)
            except Exception as e:
                logger.error(f"[TELEGRAM_TASK] Gemini Client failed to init: {e}")

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
                    pass

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
            f"Ushbu suhbatni diqqat bilan tahlil qiling va menejer tomonidan mijozga va'da qilingan, "
            f"kelishilgan yoki dushanba, ertaga kabi nisbiy muddatlari ko'rsatilgan har qanday aniq "
            f"keyingi harakatlarni (Action Items / Vazifalarni) aniqlang.\n\n"
            f"Qoidalarga rioya qiling:\n"
            f"1. Faqat real bajarilishi lozim bo'lgan ishlarni oling (masalan, narxlarni jo'natish, logotip namunalarini ko'rsatish, telefon qilish).\n"
            f"2. Nisbiy muddatlarni aniqlang va ularni hozirgi vaqtdan boshlab necha soatdan keyin bajarilishi kerakligiga o'giring (due_in_hours).\n"
            f"   - Agar vaqt aniq aytilmagan bo'lsa (masalan, 'narxlarni tashlayman' yoki 'tekshirib aytaman'), 24 soat bering.\n"
            f"   - 'Ertaga 18:00' bo'lsa va hozirgi vaqt kungi tahlil bo'lsa, taxminiy soatlarni hisoblang (e.g. 24-30 soat).\n\n"
            f"Javobni FAQAT quyidagi JSON formatida qaytaring, hech qanday qo'shimcha matn yoki izohsiz:\n"
            f"[\n"
            f"  {{\n"
            f"    \"text\": \"Mijozga ekspert tekshiruvi xizmati narxi va karta raqamini yuborish\",\n"
            f"    \"due_in_hours\": 24\n"
            f"  }}\n"
            f"]"
        )

        if not self.genai_client:
            logger.warning("[TELEGRAM_TASK] Gemini client not initialized. Cannot extract tasks.")
            return []

        try:
            config = genai_types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            )
            response = await self.genai_client.aio.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=config,
            )
            raw_json = (response.text or "").strip()
            if raw_json:
                data = json.loads(raw_json)
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.error(f"[TELEGRAM_TASK] Gemini task extraction failed: {e}")

        return []

    async def create_amocrm_tasks_from_chat(
        self, phone_or_username: str, lead_id: int, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Main pipeline: Fetches recent Telegram dialogue, handles voice transcriptions,
        runs Gemini task tahlili, and inserts the tasks into AmoCRM deal.
        """
        logger.info(f"[TELEGRAM_TASK] Starting dialogue analysis for {phone_or_username} (lead {lead_id})...")
        if not self.user_client:
            logger.warning("[TELEGRAM_TASK] Telegram client not set. Cannot pull chat history.")
            return []

        try:
            entity = await self.user_client.get_input_entity(phone_or_username)
            messages = await self.user_client.get_messages(entity, limit=limit)
        except Exception as e:
            logger.error(f"[TELEGRAM_TASK] Failed to fetch messages for {phone_or_username}: {e}")
            return []

        if not messages:
            logger.warning("[TELEGRAM_TASK] No messages retrieved.")
            return []

        # Parse and build chat logs backwards (newest last)
        messages = list(reversed(messages))
        chat_lines = []

        for msg in messages:
            sender = "Menejer" if msg.out else "Mijoz"
            
            # 1. Handle Voice / Audio Notes
            if msg.voice or msg.audio:
                voice_text = await self.download_and_transcribe_voice(msg)
                if voice_text:
                    chat_lines.append(f"{sender} (Ovozli xabar): {voice_text}")
            # 2. Handle standard text
            elif msg.message:
                chat_lines.append(f"{sender}: {msg.message.strip()}")

        full_chat_text = "\n".join(chat_lines)
        if not full_chat_text.strip():
            logger.info("[TELEGRAM_TASK] Conversation is empty (no text/voice parsed).")
            return []

        logger.info(f"[TELEGRAM_TASK] Building chat context ({len(chat_lines)} lines). Extracting tasks...")
        extracted_tasks = await self.analyze_text_for_tasks(full_chat_text)

        if not extracted_tasks:
            logger.info("[TELEGRAM_TASK] No actionable tasks found in conversation.")
            return []

        logger.info(f"[TELEGRAM_TASK] Found {len(extracted_tasks)} task(s). Creating in AmoCRM...")
        created_tasks = []
        now_ts = int(time.time())

        for t in extracted_tasks:
            task_text = t.get("text", "").strip()
            due_hours = t.get("due_in_hours", 24)
            if not task_text:
                continue

            # Compute complete_till timestamp (unix timestamp)
            complete_till = now_ts + (due_hours * 3600)

            try:
                # Add task to AmoCRM
                res = await self.amocrm.create_task(
                    element_id=lead_id,
                    text=task_text,
                    complete_till=complete_till,
                )
                if res:
                    logger.info(f"✅ [TELEGRAM_TASK] AmoCRM Task created: '{task_text}' (Due in {due_hours}h).")
                    created_tasks.append({"text": task_text, "due_in_hours": due_hours})
            except Exception as exc:
                logger.error(f"[TELEGRAM_TASK] Failed to create AmoCRM task for '{task_text}': {exc}")

        return created_tasks
