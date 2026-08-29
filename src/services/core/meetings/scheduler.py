"""
TelegramMeetingScheduler main orchestrator for message events and dialog scans.
"""
from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional
from zoneinfo import ZoneInfo
import structlog

from src.settings import settings
from src.services.core.meetings.models import (
    CONFIRMATION_TERMS,
    LEAD_TERMS,
    LOCATION_HINTS,
    MEETING_TERMS,
    TZ,
    ContextMessage,
    MeetingCandidate,
    _clean_text,
    extract_meeting_candidate,
)
from src.services.core.meetings.crm_sync import MeetingCrmSyncMixin

logger = structlog.get_logger()


class TelegramMeetingScheduler(MeetingCrmSyncMixin):
    """
    Telegram suhbatlaridagi uchrashuvlarni avtomatik aniqlab kalendarga kiritadi.
    """

    def __init__(
        self,
        db: Any,
        gcalendar: Any,
        admin_notifier: Any = None,
        amocrm: Any = None,
        lead_detector: Any = None,
    ):
        self.db = db
        self.gcalendar = gcalendar
        self.admin_notifier = admin_notifier
        self.amocrm = amocrm
        self.lead_detector = lead_detector

    async def process_event(self, event: Any, client: Any) -> Optional[MeetingCandidate]:
        if os.getenv("ENABLE_CALENDAR_AUTOSCHEDULE", "1").strip().lower() in {
            "0",
            "false",
            "no",
            "off",
        }:
            return None
        if not getattr(event, "is_private", False):
            return None
        message = getattr(event, "message", None)
        if not message or not getattr(message, "text", None):
            return None

        chat_id = getattr(event, "chat_id", None)
        if chat_id is None:
            return None

        peer = await self._get_peer(event)
        participant_name = self._peer_name(peer)
        messages = await self._recent_context(client, chat_id, participant_name)
        reference = self._event_reference(message)
        candidate = extract_meeting_candidate(messages, reference, participant_name)
        if not candidate:
            return None

        return await self._create_calendar_and_sync(
            chat_id=chat_id,
            peer=peer,
            participant_name=participant_name,
            messages=messages,
            candidate=candidate,
        )

    async def scan_recent_dialogs(
        self,
        client: Any,
        dialog_limit: int = 80,
        message_limit: int = 12,
        max_age_hours: int = 72,
    ) -> Dict[str, Any]:
        """Scan recent private chats and schedule clear meeting agreements."""
        if os.getenv("ENABLE_CALENDAR_AUTOSCAN", "1").strip().lower() in {
            "0",
            "false",
            "no",
            "off",
        }:
            return {"enabled": False, "scanned": 0, "created": 0}

        scanned = 0
        created = 0
        skipped_old = 0
        errors = 0
        now = datetime.now(TZ)
        newest_allowed = now - timedelta(hours=max_age_hours)

        async for dialog in client.iter_dialogs(limit=max(1, int(dialog_limit))):
            entity = getattr(dialog, "entity", None)
            if not getattr(dialog, "is_user", False) or getattr(entity, "bot", False):
                continue
            chat_id = getattr(dialog, "id", None)
            if chat_id is None:
                continue
            scanned += 1
            participant_name = self._peer_name(entity)

            try:
                messages = await self._recent_context(
                    client, chat_id, participant_name, limit=message_limit
                )
                if not messages:
                    continue
                latest_at = max(
                    (msg.created_at for msg in messages if msg.created_at),
                    default=None,
                )
                if latest_at and latest_at < newest_allowed:
                    skipped_old += 1
                    continue

                reference = latest_at or now
                candidate = extract_meeting_candidate(
                    messages, reference, participant_name
                )
                if not candidate:
                    continue
                if candidate.start_time < now - timedelta(hours=2):
                    skipped_old += 1
                    continue

                result = await self._create_calendar_and_sync(
                    chat_id=chat_id,
                    peer=entity,
                    participant_name=participant_name,
                    messages=messages,
                    candidate=candidate,
                )
                if result:
                    created += 1
            except Exception as exc:
                errors += 1
                logger.warning(
                    f"[MEETING SCAN] Dialog skipped chat={chat_id}: {type(exc).__name__}: {exc}"
                )

        return {
            "enabled": True,
            "scanned": scanned,
            "created": created,
            "skipped_old": skipped_old,
            "errors": errors,
        }

    async def _create_calendar_and_sync(
        self,
        chat_id: int,
        peer: Any,
        participant_name: str,
        messages: List[ContextMessage],
        candidate: MeetingCandidate,
    ) -> Optional[MeetingCandidate]:
        dedupe_key = f"calendar:auto:{chat_id}:{candidate.start_time.isoformat()}"
        if self.db and str(await self.db.get_state(dedupe_key, "")):
            logger.info(f"[MEETING] Duplicate calendar event skipped chat={chat_id}")
            return candidate

        created = False
        if self.gcalendar:
            created = bool(
                self.gcalendar.create_event(
                    summary=candidate.summary,
                    start_time=candidate.start_time.isoformat(),
                    end_time=candidate.end_time.isoformat(),
                    description=candidate.description,
                    location=candidate.location,
                )
            )
        if not created:
            logger.warning("[MEETING] Google Calendar event was not created.")
            return None

        if self.db:
            await self.db.set_state(dedupe_key, "created")
            await self._save_meeting_state(peer, participant_name, candidate)

        await self._sync_crm_lead_if_needed(peer, participant_name, messages, candidate)
        await self._notify_admin(candidate, participant_name)
        logger.info(
            "[MEETING] Calendar event created chat=%s start=%s",
            chat_id,
            candidate.start_time.isoformat(),
        )
        return candidate

    async def _recent_context(
        self, client: Any, chat_id: int, participant_name: str, limit: int = 10
    ) -> List[ContextMessage]:
        raw_messages = await client.get_messages(chat_id, limit=max(1, int(limit)))
        items: List[ContextMessage] = []
        for msg in reversed(raw_messages or []):
            text = getattr(msg, "text", None) or getattr(msg, "message", None) or ""
            geo_text = self._geo_text(msg)
            if geo_text:
                text = f"{text}\n{geo_text}".strip()
            if not text:
                continue
            created_at = self._event_reference(msg)
            items.append(
                ContextMessage(
                    text=text,
                    is_outgoing=bool(getattr(msg, "out", False)),
                    sender_name="Baxtiyorjon" if getattr(msg, "out", False) else participant_name,
                    created_at=created_at,
                )
            )
        return items

    def _event_reference(self, message: Any) -> datetime:
        value = getattr(message, "date", None)
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=ZoneInfo("UTC"))
            return value.astimezone(TZ)
        return datetime.now(TZ)

    async def _get_peer(self, event: Any) -> Any:
        try:
            return await event.get_chat()
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            try:
                return await event.get_sender()
            except Exception:
                logger.error("Exception handled in %s", __name__, exc_info=True)
                return None

    def _peer_name(self, peer: Any) -> str:
        first = getattr(peer, "first_name", "") or ""
        last = getattr(peer, "last_name", "") or ""
        title = getattr(peer, "title", "") or ""
        username = getattr(peer, "username", "") or ""
        return _clean_text(f"{first} {last}") or title or username or "Mijoz"

    def _geo_text(self, msg: Any) -> str:
        media = getattr(msg, "media", None)
        geo = getattr(media, "geo", None) or getattr(msg, "geo", None)
        lat = getattr(geo, "lat", None)
        lon = getattr(geo, "long", None) or getattr(geo, "lon", None)
        if lat is None or lon is None:
            return ""
        return f"Geo: https://maps.google.com/maps?q={lat},{lon}"
