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
import structlog
import re
import inspect
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.settings import settings
from src.services.utils.gemini_fallback import (
    generate_content_with_fallback,
    is_quota_error,
)

try:
    from google import genai
    from google.genai import types as genai_types
except Exception:
    genai = None
    genai_types = None

logger = structlog.get_logger()


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class TelegramTaskCreator:
    """
    Scans Telegram dialogues (text + voice), transcribes audios inline,
    analyzes the overall conversation logic for promises, commitments, and deadlines,
    and registers them automatically in AmoCRM as active Tasks.
    """

    _gemini_blocked_until = 0.0
    _telegram_blocked_until = 0.0
    _GEMINI_COOLDOWN_KEY = "telegram_task:gemini_blocked_until"
    _TELEGRAM_COOLDOWN_KEY = "telegram_task:telegram_blocked_until"

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
        self.gemini_model = (
            os.getenv("GEMINI_TELEGRAM_TASK_MODEL") or settings.GEMINI_CALL_MODEL
        )
        self.gemini_cooldown_seconds = int(
            os.getenv("GEMINI_TASK_COOLDOWN_SECONDS", "21600")
        )
        self.telegram_flood_cooldown_seconds = int(
            os.getenv("TELEGRAM_ENTITY_COOLDOWN_SECONDS", "10800")
        )
        self._cooldowns_loaded = False

        self.genai_client = None
        if gemini_api_key and genai is not None:
            try:
                self.genai_client = genai.Client(api_key=gemini_api_key)
            except Exception as e:
                logger.error(f"[TELEGRAM_TASK] Gemini Client failed to init: {e}")

    @classmethod
    def _gemini_cooldown_remaining(cls) -> int:
        return max(0, int(cls._gemini_blocked_until - time.time()))

    @classmethod
    def _telegram_cooldown_remaining(cls) -> int:
        return max(0, int(cls._telegram_blocked_until - time.time()))

    def cooldown_seconds_remaining(self) -> int:
        """Return the longest active dependency cooldown for the task pipeline."""
        return max(
            self._gemini_cooldown_remaining(),
            self._telegram_cooldown_remaining(),
        )

    def cooldown_reason(self) -> Optional[str]:
        """Return the dependency currently imposing the longest cooldown."""
        gemini_remaining = self._gemini_cooldown_remaining()
        telegram_remaining = self._telegram_cooldown_remaining()
        if gemini_remaining >= telegram_remaining and gemini_remaining:
            return "gemini_quota"
        if telegram_remaining:
            return "telegram_entity_lookup"
        return None

    def is_cooling_down(self) -> bool:
        return self.cooldown_seconds_remaining() > 0

    def blocks_dialogue_analysis(self) -> bool:
        """Per-lead resolution handles flood-waits without blocking the whole scan."""
        return False

    def _pause_gemini(self) -> None:
        type(self)._gemini_blocked_until = (
            time.time() + self.gemini_cooldown_seconds
        )

    def _pause_telegram_resolution(self, error: Exception) -> int:
        match = re.search(r"wait of (\d+) seconds", str(error), flags=re.IGNORECASE)
        requested_seconds = int(match.group(1)) if match else 0
        cooldown_seconds = max(
            requested_seconds,
            self.telegram_flood_cooldown_seconds,
        )
        type(self)._telegram_blocked_until = time.time() + cooldown_seconds
        return cooldown_seconds

    async def _load_persisted_cooldowns(self) -> None:
        if self._cooldowns_loaded:
            return
        self._cooldowns_loaded = True
        get_state = getattr(self.db, "get_state", None)
        if not callable(get_state):
            return
        try:
            gemini_until = float(
                await _maybe_await(get_state(self._GEMINI_COOLDOWN_KEY, "0")) or 0
            )
            telegram_until = float(
                await _maybe_await(get_state(self._TELEGRAM_COOLDOWN_KEY, "0")) or 0
            )
            type(self)._gemini_blocked_until = max(
                type(self)._gemini_blocked_until,
                gemini_until,
            )
            type(self)._telegram_blocked_until = max(
                type(self)._telegram_blocked_until,
                telegram_until,
            )
        except Exception as exc:
            logger.debug("[TELEGRAM_TASK] Cooldown state load skipped: %s", exc)

    async def _persist_cooldowns(self) -> None:
        set_state = getattr(self.db, "set_state", None)
        if not callable(set_state):
            return
        try:
            await _maybe_await(
                set_state(
                    self._GEMINI_COOLDOWN_KEY,
                    str(type(self)._gemini_blocked_until),
                )
            )
            await _maybe_await(
                set_state(
                    self._TELEGRAM_COOLDOWN_KEY,
                    str(type(self)._telegram_blocked_until),
                )
            )
        except Exception as exc:
            logger.debug("[TELEGRAM_TASK] Cooldown state write skipped: %s", exc)

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

    @staticmethod
    def _normalise_phone(value: str) -> str:
        digits = re.sub(r"\D", "", str(value or ""))
        if len(digits) == 9:
            digits = "998" + digits
        return digits

    async def _resolve_dialog_entity(self, phone_or_username: str) -> tuple[Any, Optional[int]]:
        """Resolve cached peers first, then temporarily import a phone contact."""
        clean_phone = self._normalise_phone(phone_or_username)
        is_phone_lookup = bool(clean_phone) and len(clean_phone) >= 9
        if is_phone_lookup and self._telegram_cooldown_remaining():
            return None, None
        try:
            return await self.user_client.get_input_entity(phone_or_username), None
        except Exception as first_error:
            error_text = str(first_error).lower()
            if (
                "flood" in error_text
                or "getcontactsrequest" in error_text
                or "wait of" in error_text
            ):
                raise first_error
            if not clean_phone:
                raise first_error

        from telethon.tl import functions, types

        contact = types.InputPhoneContact(
            client_id=random.randrange(-(2**63), 2**63),
            phone=clean_phone,
            first_name="Oisha Lookup",
            last_name="",
        )
        imported = await self.user_client(
            functions.contacts.ImportContactsRequest(contacts=[contact])
        )
        users = list(getattr(imported, "users", None) or [])
        if not users:
            return None, None
        user = users[0]
        return await self.user_client.get_input_entity(user), int(user.id)

    async def _delete_temporary_contact(self, user_id: Optional[int]) -> None:
        if not user_id:
            return
        try:
            from telethon.tl import functions

            await self.user_client(
                functions.contacts.DeleteContactsRequest(id=[int(user_id)])
            )
        except Exception as exc:
            logger.debug("[TELEGRAM_TASK] Temporary contact cleanup skipped: %s", exc)

    async def _fetch_shared_group_messages(self, client_user_id: int, limit: int = 20) -> list:
        """Recent messages from groups where the client actively participates."""
        collected = []
        try:
            async for dialog in self.user_client.iter_dialogs(limit=35):
                if not dialog.is_group:
                    continue
                recent = await self.user_client.get_messages(dialog.entity, limit=20)
                # Check if the client sent any of the recent messages
                client_present = any(
                    getattr(getattr(m, "from_id", None), "user_id", None) == client_user_id
                    for m in recent
                )
                if client_present:
                    title = getattr(dialog.entity, "title", str(dialog.entity))
                    logger.info(
                        "[TELEGRAM_TASK] Found shared group '%s' with client %d",
                        title,
                        client_user_id,
                    )
                    collected.extend(recent[:limit])
        except Exception as exc:
            logger.debug("[TELEGRAM_TASK] Group scan error: %s", exc)
        return collected

    async def create_amocrm_tasks_from_chat(
        self, phone_or_username: str, lead_id: int, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Main pipeline: Fetches recent Telegram dialogue, handles voice transcriptions,
        runs Gemini task tahlili, and inserts the tasks into AmoCRM deal.
        """
        logger.info(f"[TELEGRAM_TASK] Starting dialogue analysis for {phone_or_username} (lead {lead_id})...")
        await self._load_persisted_cooldowns()
        if not self.user_client:
            logger.warning("[TELEGRAM_TASK] Telegram client not set. Cannot pull chat history.")
            return []
        temporary_contact_id = None
        try:
            entity, temporary_contact_id = await self._resolve_dialog_entity(
                phone_or_username
            )
            if entity is None:
                logger.info(
                    "[TELEGRAM_TASK] Telegram account not resolved for lead %s.",
                    lead_id,
                )
                return []
            messages = await self.user_client.get_messages(entity, limit=limit)
        except Exception as e:
            error_text = str(e)
            if "flood" in error_text.lower() or "GetContactsRequest" in error_text:
                cooldown_seconds = self._pause_telegram_resolution(e)
                await self._persist_cooldowns()
                logger.error(
                    "[TELEGRAM_TASK] Telegram entity lookup flood wait; pausing lookup for %ss.",
                    cooldown_seconds,
                )
            else:
                logger.info(
                    "[TELEGRAM_TASK] Telegram dialogue unavailable for lead %s: %s",
                    lead_id,
                    type(e).__name__,
                )
            return []
        finally:
            await self._delete_temporary_contact(temporary_contact_id)

        if not messages:
            logger.warning("[TELEGRAM_TASK] No messages retrieved.")
            return []

        # Detect client's user_id from private chat messages for group scan
        client_user_id: Optional[int] = None
        for m in messages:
            if not m.out:
                fid = getattr(m, "from_id", None)
                uid = getattr(fid, "user_id", None)
                if uid:
                    client_user_id = uid
                    break

        # Also collect messages from shared group chats
        if client_user_id:
            group_messages = await self._fetch_shared_group_messages(client_user_id, limit=limit)
            if group_messages:
                logger.info(
                    "[TELEGRAM_TASK] Adding %d group message(s) to analysis context.",
                    len(group_messages),
                )
                messages = list(messages) + group_messages

        # Parse and build chat logs (oldest first)
        import datetime as _dt
        def _msg_date(m: Any) -> Any:
            d = getattr(m, "date", None)
            return d if isinstance(d, (_dt.datetime, _dt.date)) else _dt.datetime.min
        messages = sorted(messages, key=_msg_date)
        chat_lines = []

        for msg in messages:
            if msg.out:
                sender = "Menejer"
            else:
                sender_name = None
                sender_obj = getattr(msg, "sender", None)
                if sender_obj:
                    first = getattr(sender_obj, "first_name", None) or ""
                    last = getattr(sender_obj, "last_name", None) or ""
                    sender_name = (first + " " + last).strip() or None
                sender = sender_name or "Mijoz"

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

        # Fetch existing open tasks for this lead to avoid duplicates
        existing_task_texts: set[str] = set()
        try:
            open_tasks = await self.amocrm.get_lead_open_tasks(lead_id)
            for ot in open_tasks:
                raw = (ot.get("text") or "").strip().lower()
                # Strip common prefix added by this pipeline
                normalized = raw.removeprefix("telegram suhbatidan: ")
                if normalized:
                    existing_task_texts.add(normalized)
            if existing_task_texts:
                logger.info(
                    "[TELEGRAM_TASK] Lead %s already has %d open task(s); will skip duplicates.",
                    lead_id,
                    len(existing_task_texts),
                )
        except Exception as exc:
            logger.warning("[TELEGRAM_TASK] Could not fetch existing tasks for dedup: %s", exc)

        for t in extracted_tasks:
            task_text = t.get("text", "").strip()
            due_hours = t.get("due_in_hours", 24)
            if not task_text:
                continue

            # Dedup: skip if a very similar task already exists (80%+ word overlap)
            task_lower = task_text.lower().removeprefix("telegram suhbatidan: ")
            task_words = set(task_lower.split())
            is_duplicate = False
            for existing in existing_task_texts:
                existing_words = set(existing.split())
                if not existing_words:
                    continue
                overlap = len(task_words & existing_words) / max(len(task_words), len(existing_words))
                if overlap >= 0.8:
                    logger.info(
                        "[TELEGRAM_TASK] Skipping duplicate task (%.0f%% overlap with existing): '%s'",
                        overlap * 100,
                        task_text[:80],
                    )
                    is_duplicate = True
                    break
            if is_duplicate:
                continue

            complete_till = now_ts + (due_hours * 3600)
            try:
                res = await self.amocrm.create_task(
                    element_id=lead_id,
                    text=task_text,
                    complete_till=complete_till,
                )
                if res:
                    logger.info(f"✅ [TELEGRAM_TASK] AmoCRM Task created: '{task_text}' (Due in {due_hours}h).")
                    created_tasks.append({"text": task_text, "due_in_hours": due_hours})
                    existing_task_texts.add(task_lower)
            except Exception as exc:
                logger.error(f"[TELEGRAM_TASK] Failed to create AmoCRM task for '{task_text}': {exc}")

        return created_tasks
