"""
TelegramTaskCreator main class composing cooldown, analyzer, and dialog mixins.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
import structlog

from src.settings import settings
from src.services.core.telegram.task_creator.cooldowns import CooldownManagerMixin
from src.services.core.telegram.task_creator.analyzer import TaskAnalyzerMixin, genai, genai_types
from src.services.core.telegram.task_creator.dialogs import (
    DialogResolverMixin,
    _maybe_await,
)

logger = structlog.get_logger()


class TelegramTaskCreator(CooldownManagerMixin, TaskAnalyzerMixin, DialogResolverMixin):
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

            # Ish vaqtini hisobga olgan holda deadline
            from src.utils.task_scheduler import task_deadline
            complete_till = task_deadline(due_in_hours=due_hours)
            try:
                res = await self.amocrm.create_task(
                    element_id=lead_id,
                    text=task_text,
                    complete_till=complete_till,
                )
                if res:
                    logger.info(f"✅ [TELEGRAM_TASK] AmoCRM Task created: '{task_text}' (Due in {due_hours}h, working hours).")
                    created_tasks.append({"text": task_text, "due_in_hours": due_hours})
                    existing_task_texts.add(task_lower)
            except Exception as exc:
                logger.error(f"[TELEGRAM_TASK] Failed to create AmoCRM task for '{task_text}': {exc}")

        return created_tasks
