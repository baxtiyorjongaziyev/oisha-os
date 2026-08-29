"""Telegram business-dialog orchestration for SalesCoach analysis."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Literal, Mapping, Optional

from src.services.core.telegram_salescoach_store import ConversationAnalysisRecord


logger = logging.getLogger("TelegramSalesCoach")
_VALID_MODES = {"shadow", "approval", "auto"}


@dataclass(frozen=True)
class TelegramConversationMessage:
    id: int
    role: Literal["manager", "customer"]
    text: str
    sent_at: datetime


@dataclass(frozen=True)
class CrmMatch:
    lead_id: int
    contact_id: int | None
    responsible_user_id: int
    confidence: float
    crm_status: str = ""


def _hash_value(value: Any) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def conversation_fingerprint(
    lead_id: int,
    messages: Iterable[TelegramConversationMessage],
) -> str:
    """Stable fingerprint that stores only hashes of message text."""
    parts = [f"lead={int(lead_id)}"]
    for message in messages:
        sent_at = message.sent_at
        if sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=timezone.utc)
        timestamp = sent_at.astimezone(timezone.utc).replace(microsecond=0).isoformat()
        text_hash = hashlib.sha256(message.text.encode("utf-8")).hexdigest()
        parts.append(
            f"{int(message.id)}|{message.role}|{timestamp}|{text_hash}"
        )
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _normalize_message(value: Any) -> Optional[TelegramConversationMessage]:
    if isinstance(value, TelegramConversationMessage):
        text = value.text.strip()
        if not text:
            return None
        return TelegramConversationMessage(
            id=int(value.id),
            role=value.role,
            text=text,
            sent_at=value.sent_at,
        )
    if not isinstance(value, Mapping):
        return None

    role = value.get("role")
    text = str(value.get("text") or "").strip()
    sent_at = _parse_datetime(value.get("sent_at") or value.get("sentAt"))
    try:
        message_id = int(value.get("id"))
    except (TypeError, ValueError):
        return None
    if role not in {"manager", "customer"} or not text or sent_at is None:
        return None
    return TelegramConversationMessage(
        id=message_id,
        role=role,
        text=text,
        sent_at=sent_at,
    )

