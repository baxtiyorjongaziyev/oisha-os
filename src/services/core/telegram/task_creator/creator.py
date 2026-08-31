"""Telegram Task Creator pipeline and AmoCRM bridge."""
from __future__ import annotations

import datetime as _dt
import os
from typing import Any, Dict, List, Optional
import structlog

from src.settings import settings
from src.services.core.telegram.task_creator.analyzer import (
    TaskAnalyzerMixin,
    genai,
)
from src.services.core.telegram.task_creator.cooldowns import CooldownManagerMixin
from src.services.core.telegram.task_creator.dialogs import DialogResolverMixin

logger = structlog.get_logger()


class TelegramTaskCreator(
    CooldownManagerMixin,
    TaskAnalyzerMixin,
    DialogResolverMixin,
):
    """Telegram chat tahlili orqali AmoCRM da avtomatik vazifalar yaratish."""

    def __init__(
        self,
        amocrm: Any,
        db: Any,
        user_client: Optional[Any] = None,
        voice_processor: Optional[Any] = None,
        gemini_api_key: Optional[str] = None,
    ) -> None:
        self.user_client = user_client
        self.amocrm = amocrm
        self.db = db
        self.voice_processor = voice_processor
        self.gemini_api_key = gemini_api_key
        self.gemini_model = (
            os.getenv("GEMINI_TELEGRAM_TASK_MODEL") or settings.GEMINI_CALL_MODEL
        )
        self.gemini_cooldown_seconds = int(
            os.getenv("GEMINI_TASK_COOLDOWN_SECONDS", "21600")
        )
        self.cooldowns: Dict[str, float] = {}
        self.telegram_cooldown_file = os.getenv("TELEGRAM_ENTITY_COOLDOWNS_PATH", "data/telegram_entity_cooldowns.json")
        self.telegram_flood_cooldown_seconds = int(os.getenv("TELEGRAM_ENTITY_COOLDOWN_SECONDS", "10800"))
        self._cooldowns_loaded = False

        self.genai_client = None
        if gemini_api_key and genai is not None:
            try:
                self.genai_client = genai.Client(api_key=gemini_api_key)
            except Exception as e:
                logger.error(f"[TELEGRAM_TASK] Gemini Client failed to init: {e}")

    async def _pull_dialog_messages(self, phone_or_username: str, lead_id: int, limit: int) -> List[Any]:
        await self._load_persisted_cooldowns()
        if not self.user_client:
            return []
        temp_contact_id = None
        try:
            entity, temp_contact_id = await self._resolve_dialog_entity(phone_or_username)
            if entity is None:
                return []
            messages = await self.user_client.get_messages(entity, limit=limit)
        except Exception as e:
            if "flood" in str(e).lower() or "GetContactsRequest" in str(e):
                self._pause_telegram_resolution(e)
                await self._persist_cooldowns()
            return []
        finally:
            await self._delete_temporary_contact(temp_contact_id)

        if not messages:
            return []

        client_uid = next((getattr(getattr(m, "from_id", None), "user_id", None) for m in messages if not m.out), None)
        if client_uid:
            grp_msgs = await self._fetch_shared_group_messages(client_uid, limit=limit)
            if grp_msgs:
                messages = list(messages) + grp_msgs
        return messages

    async def _build_chat_transcript(self, messages: List[Any]) -> str:
        def _msg_date(m: Any) -> Any:
            d = getattr(m, "date", None)
            return d if isinstance(d, (_dt.datetime, _dt.date)) else _dt.datetime.min

        lines = []
        for msg in sorted(messages, key=_msg_date):
            sender = "Menejer" if msg.out else ((getattr(getattr(msg, "sender", None), "first_name", "") + " " + getattr(getattr(msg, "sender", None), "last_name", "")).strip() or "Mijoz")
            if msg.voice or msg.audio:
                voice_text = await self.download_and_transcribe_voice(msg)
                if voice_text:
                    lines.append(f"{sender} (Ovozli xabar): {voice_text}")
            elif msg.message:
                lines.append(f"{sender}: {msg.message.strip()}")
        return "\n".join(lines)

    async def _insert_deduped_tasks(self, lead_id: int, extracted_tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        existing: set[str] = set()
        try:
            for ot in await self.amocrm.get_lead_open_tasks(lead_id):
                norm = (ot.get("text") or "").strip().lower().removeprefix("telegram suhbatidan: ")
                if norm:
                    existing.add(norm)
        except Exception as exc:
            logger.warning("[TELEGRAM_TASK] Could not fetch existing tasks for dedup: %s", exc)

        from src.utils.task_scheduler import task_deadline
        created = []
        for t in extracted_tasks:
            task_text = t.get("text", "").strip()
            due_hours = t.get("due_in_hours", 24)
            if not task_text:
                continue
            task_words = set(task_text.lower().removeprefix("telegram suhbatidan: ").split())
            if any(len(task_words & set(e.split())) / max(len(task_words), len(e.split())) >= 0.8 for e in existing if e.split()):
                continue
            try:
                res = await self.amocrm.create_task(element_id=lead_id, text=task_text, complete_till=task_deadline(due_in_hours=due_hours))
                if res:
                    created.append({"text": task_text, "due_in_hours": due_hours})
                    existing.add(task_text.lower().removeprefix("telegram suhbatidan: "))
            except Exception as exc:
                logger.error(f"[TELEGRAM_TASK] Failed to create AmoCRM task for '{task_text}': {exc}")
        return created

    async def create_amocrm_tasks_from_chat(self, phone_or_username: str, lead_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Main pipeline: Fetches recent Telegram dialogue, runs AI task analyzer and creates AmoCRM tasks."""
        logger.info(f"[TELEGRAM_TASK] Starting dialogue analysis for {phone_or_username} (lead {lead_id})...")
        messages = await self._pull_dialog_messages(phone_or_username, lead_id, limit)
        if not messages:
            return []
        chat_text = await self._build_chat_transcript(messages)
        if not chat_text.strip():
            return []
        extracted = await self.analyze_text_for_tasks(chat_text)
        if not extracted:
            return []
        return await self._insert_deduped_tasks(lead_id, extracted)
