"""Telegram context to Google Calendar scheduler.

The scheduler watches private Telegram conversations and turns clear meeting
agreements into Google Calendar events. It is intentionally rule-based first:
no hallucinated dates, no scheduling without a meeting intent and a concrete
time.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable, List, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

TZ = ZoneInfo("Asia/Tashkent")

MEETING_TERMS = (
    "uchrashuv",
    "suhbat",
    "intervyu",
    "konsultatsiya",
    "zoom",
    "google meet",
    "ofis",
    "kelolasiz",
    "kelasiz",
    "kelaman",
    "keladi",
)

CONFIRMATION_TERMS = (
    "yozib qo'ydim",
    "yozib quydim",
    "belgiladim",
    "calendar",
    "kalendar",
    "ok",
    "hop",
    "bo'ladi",
    "boladi",
    "kelaman",
    "tasdiq",
)

LOCATION_HINTS = ("ofis", "manzil", "geopozitsiya", "геопозиция", "maps.google")
LEAD_TERMS = (
    "branding",
    "brending",
    "logo",
    "logotip",
    "naming",
    "nomlash",
    "brandbook",
    "brendbuk",
    "qadoq",
    "dizayn",
    "patent",
    "narx",
    "tijoriy taklif",
    "brief",
    "brif",
    "loyiha",
    "xizmat",
    "konsultatsiya",
)


@dataclass
class ContextMessage:
    text: str
    is_outgoing: bool
    sender_name: str = ""
    created_at: Optional[datetime] = None


@dataclass
class MeetingCandidate:
    summary: str
    start_time: datetime
    end_time: datetime
    description: str
    location: str = ""
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _parse_explicit_date(text: str, reference: datetime) -> Optional[datetime]:
    date_match = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b", text)
    if date_match:
        day, month, year = map(int, date_match.groups())
        if year < 100:
            year += 2000
        try:
            return datetime(year, month, day, tzinfo=TZ)
        except ValueError:
            return None

    iso_match = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text)
    if iso_match:
        year, month, day = map(int, iso_match.groups())
        try:
            return datetime(year, month, day, tzinfo=TZ)
        except ValueError:
            return None

    lowered = text.lower()
    if "indinga" in lowered:
        return (reference + timedelta(days=2)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    if "ertaga" in lowered:
        return (reference + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    if "bugun" in lowered:
        return reference.replace(hour=0, minute=0, second=0, microsecond=0)
    return None


def _parse_time(text: str) -> Optional[tuple[int, int]]:
    lowered = text.lower()
    candidates = [
        r"\bsoat\s+(\d{1,2})[:.\s](\d{2})\b",
        r"\b(\d{1,2}):(\d{2})\b",
        r"(?<![./-])\b(\d{1,2})\.(\d{2})\b(?![./-]\d)",
        r"\b(\d{1,2})\s+(\d{2})\b",
        r"\bsoat\s+(\d{1,2})\b",
    ]
    for pattern in candidates:
        match = re.search(pattern, lowered)
        if not match:
            continue
        hour = int(match.group(1))
        minute = int(match.group(2)) if len(match.groups()) > 1 else 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute
    return None


def _extract_location(messages: Iterable[ContextMessage]) -> str:
    location_parts: List[str] = []
    for msg in messages:
        text = msg.text or ""
        lowered = text.lower()
        if any(hint in lowered for hint in LOCATION_HINTS):
            location_parts.append(_clean_text(text))
        maps_match = re.search(r"https?://\S*maps\.google\S+", text)
        if maps_match:
            location_parts.append(maps_match.group(0))
        coord_match = re.search(r"q=(-?\d+\.\d+),(-?\d+\.\d+)", text)
        if coord_match:
            location_parts.append(f"{coord_match.group(1)},{coord_match.group(2)}")
    return "\n".join(dict.fromkeys(location_parts))[:500]


def extract_meeting_candidate(
    messages: List[ContextMessage],
    reference: Optional[datetime] = None,
    participant_name: str = "Mijoz",
) -> Optional[MeetingCandidate]:
    """Extract a concrete meeting from recent chat context."""
    if not messages:
        return None

    reference = (reference or datetime.now(TZ)).astimezone(TZ)
    ordered = [msg for msg in messages if _clean_text(msg.text)]
    if not ordered:
        return None

    combined = "\n".join(msg.text for msg in ordered)
    lowered = combined.lower()
    if not any(term in lowered for term in MEETING_TERMS):
        return None

    date_base: Optional[datetime] = None
    date_evidence = ""
    for msg in ordered:
        parsed_date = _parse_explicit_date(msg.text, msg.created_at or reference)
        if parsed_date:
            date_base = parsed_date
            date_evidence = msg.text

    time_value: Optional[tuple[int, int]] = None
    time_evidence = ""
    for msg in ordered:
        parsed_time = _parse_time(msg.text)
        if parsed_time:
            time_value = parsed_time
            time_evidence = msg.text

    if not date_base or not time_value:
        return None

    has_confirmation = any(term in lowered for term in CONFIRMATION_TERMS)
    has_owner_question = any(
        msg.is_outgoing and ("kelolasiz" in msg.text.lower() or "nech" in msg.text.lower())
        for msg in ordered
    )
    has_client_time_reply = any(
        (not msg.is_outgoing) and _parse_time(msg.text) for msg in ordered
    )
    if not (has_confirmation or (has_owner_question and has_client_time_reply)):
        return None

    hour, minute = time_value
    start = date_base.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if start < reference - timedelta(hours=2):
        return None
    end = start + timedelta(hours=1)

    location = _extract_location(ordered)
    evidence = [
        f"Sana: {_clean_text(date_evidence)}",
        f"Vaqt: {_clean_text(time_evidence)}",
    ]
    if location:
        evidence.append("Manzil: Telegram kontekstdan olindi")

    return MeetingCandidate(
        summary=f"Suhbat: {participant_name}",
        start_time=start,
        end_time=end,
        location=location,
        description=(
            "Oisha Telegram suhbatidan avtomatik yaratdi.\n\n"
            + "\n".join(f"{'Baxtiyorjon' if m.is_outgoing else participant_name}: {m.text}" for m in ordered[-8:])
        )[:2000],
        confidence=0.9 if has_confirmation else 0.82,
        evidence=evidence,
    )


class TelegramMeetingScheduler:
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
            try:
                return await event.get_sender()
            except Exception:
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

    async def _save_meeting_state(
        self, peer: Any, participant_name: str, candidate: MeetingCandidate
    ) -> None:
        user_id = getattr(peer, "id", None)
        if not user_id:
            return
        username = getattr(peer, "username", None)
        try:
            await self.db.upsert_user(
                user_id,
                participant_name,
                username=username,
                meeting_time=candidate.start_time.isoformat(),
                meeting_status="scheduled",
            )
        except Exception as exc:
            logger.debug(f"[MEETING] DB meeting state skipped: {exc}")

    async def _sync_crm_lead_if_needed(
        self,
        peer: Any,
        participant_name: str,
        messages: List[ContextMessage],
        candidate: MeetingCandidate,
    ) -> Optional[int]:
        if os.getenv("ENABLE_CALENDAR_CRM_SYNC", "1").strip().lower() in {
            "0",
            "false",
            "no",
            "off",
        }:
            return None
        if not self.amocrm:
            return None
        is_auth_blocked = getattr(self.amocrm, "is_auth_blocked", None)
        if callable(is_auth_blocked) and is_auth_blocked():
            logger.info("[MEETING] AmoCRM sync skipped: OAuth reauthorization required.")
            return None

        user_id = getattr(peer, "id", None)
        username = getattr(peer, "username", None)
        context_text = "\n".join(msg.text for msg in messages[-10:])
        lead_data = await self._detect_lead(context_text, peer, participant_name)
        if not lead_data.get("is_lead"):
            return None

        crm_key = f"calendar:crm_synced:{user_id or participant_name}:{candidate.start_time.isoformat()}"
        if self.db and str(await self.db.get_state(crm_key, "")):
            return None

        phone = (
            lead_data.get("phone")
            or getattr(peer, "phone", None)
            or ""
        )
        note = self._build_crm_note(
            participant_name=participant_name,
            username=username,
            candidate=candidate,
            context_text=context_text,
            lead_data=lead_data,
        )
        lead_name = f"Telegram Meeting Lead: {participant_name}"

        lead_id: Optional[int] = None
        try:
            if phone:
                task_result = await self._create_existing_lead_meeting_task(
                    phone=str(phone),
                    candidate=candidate,
                    participant_name=participant_name,
                    note=note,
                )
                lead_id = task_result
                if not lead_id:
                    lead_id = await self.amocrm.ensure_lead(
                        name=lead_name,
                        phone=str(phone),
                        note=note,
                    )
            if not lead_id and hasattr(self.amocrm, "create_standalone_lead"):
                lead_id = await self.amocrm.create_standalone_lead(
                    name=lead_name,
                    note=note,
                    tags=["TELEGRAM_MEETING_LEAD"],
                )
        except Exception as exc:
            logger.warning(f"[MEETING] AmoCRM lead sync failed: {exc}")
            return None

        if lead_id and self.db:
            await self.db.set_state(crm_key, str(lead_id))
            if user_id:
                try:
                    await self.db.set_state(f"crm:lead:{user_id}", str(lead_id))
                except Exception:
                    pass

        if lead_id:
            logger.info(f"[MEETING] AmoCRM meeting lead synced: {lead_id}")
        return lead_id

    async def _create_existing_lead_meeting_task(
        self,
        phone: str,
        candidate: MeetingCandidate,
        participant_name: str,
        note: str,
    ) -> Optional[int]:
        """Mavjud ochiq AmoCRM sdelka bo'lsa, yangi lead emas task yaratish."""
        task_text = self._build_meeting_task_text(candidate, participant_name)
        complete_till = int(candidate.start_time.timestamp())

        if hasattr(self.amocrm, "create_meeting_task_for_phone"):
            result = await self.amocrm.create_meeting_task_for_phone(
                phone=phone,
                task_text=task_text,
                complete_till=complete_till,
                note=note,
            )
            if isinstance(result, dict) and result.get("success"):
                return int(result["lead_id"])
            if (
                isinstance(result, dict)
                and result.get("reason") != "active_lead_not_found"
            ):
                raise RuntimeError(
                    f"existing_lead_task_failed:{result.get('reason') or 'unknown'}"
                )
            return None

        if not hasattr(self.amocrm, "find_active_lead_by_phone"):
            return None

        lead = self.amocrm.find_active_lead_by_phone(phone)
        if not lead:
            return None

        lead_id = int(lead["id"])
        if hasattr(self.amocrm, "create_task"):
            task = await self.amocrm.create_task(
                element_id=lead_id,
                text=task_text,
                complete_till=complete_till,
                responsible_user_id=lead.get("responsible_user_id"),
            )
            if not task:
                raise RuntimeError("existing_lead_task_failed")
        if hasattr(self.amocrm, "add_lead_note"):
            self.amocrm.add_lead_note(lead_id, note)
        return lead_id

    async def _detect_lead(
        self,
        context_text: str,
        peer: Any,
        participant_name: str,
    ) -> dict:
        profile = {
            "id": getattr(peer, "id", None),
            "first_name": participant_name,
            "username": getattr(peer, "username", None),
        }
        if self.lead_detector:
            try:
                lead_data = await self.lead_detector.extract_lead_info(
                    context_text, profile
                )
                if isinstance(lead_data, dict):
                    return lead_data
            except Exception as exc:
                logger.debug(f"[MEETING] Lead detector fallback: {exc}")

        lowered = context_text.lower()
        is_lead = any(term in lowered for term in LEAD_TERMS)
        return {
            "is_lead": is_lead,
            "intent_category": "MEETING_LEAD" if is_lead else "MEETING_ONLY",
            "needs": "Telegram suhbatida uchrashuv belgilandi",
        }

    def _build_crm_note(
        self,
        participant_name: str,
        username: Optional[str],
        candidate: MeetingCandidate,
        context_text: str,
        lead_data: dict,
    ) -> str:
        return (
            "Oisha: Telegram suhbatidan avtomatik uchrashuv/lead signali.\n"
            f"Mijoz: {participant_name}\n"
            f"Telegram: @{username or 'yoq'}\n"
            f"Uchrashuv vaqti: {candidate.start_time.strftime('%d.%m.%Y %H:%M')}\n"
            f"Manzil: {candidate.location or 'korsatilmagan'}\n"
            f"Lead turi: {lead_data.get('intent_category', 'meeting_lead')}\n"
            f"Ehtiyoj: {lead_data.get('needs') or 'Uchrashuv belgilandi'}\n\n"
            f"Suhbat konteksti:\n{context_text[-1800:]}"
        )

    def _build_meeting_task_text(
        self, candidate: MeetingCandidate, participant_name: str
    ) -> str:
        location = candidate.location or "manzil ko'rsatilmagan"
        return (
            f"Uchrashuv: {participant_name} bilan "
            f"{candidate.start_time.strftime('%d.%m.%Y %H:%M')} da. "
            f"Manzil: {location}. Oisha Telegram suhbatidan avtomatik qo'ydi."
        )

    async def _notify_admin(
        self, candidate: MeetingCandidate, participant_name: str
    ) -> None:
        if not self.admin_notifier:
            return
        try:
            location_label = candidate.location or "Manzil ko'rsatilmagan"
            text = (
                "Oisha Google Calendar'ga uchrashuv qo'shdi\n"
                f"Mijoz: {participant_name}\n"
                f"Vaqt: {candidate.start_time.strftime('%d.%m.%Y %H:%M')}\n"
                f"Manzil: {location_label}"
            )
            await self.admin_notifier.notify_lead(text)
        except Exception as exc:
            logger.debug(f"[MEETING] Admin notify skipped: {exc}")
