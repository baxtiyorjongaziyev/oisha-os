"""
Data models and decoding helpers for Telegram SalesCoach storage.
"""
from __future__ import annotations

import inspect
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

logger = logging.getLogger("TelegramSalesCoachStore")

_SENSITIVE_ANALYSIS_KEYS = {
    "conversation",
    "message_text",
    "messages",
    "raw_messages",
    "transcript",
}
_ANALYSIS_COLUMNS = [
    "id",
    "conversation_hash",
    "telegram_user_hash",
    "contact_id",
    "lead_id",
    "manager_id",
    "fingerprint",
    "overall_score",
    "confidence",
    "source_message_ids_json",
    "rollout_mode",
    "analysis_json",
    "status",
    "created_at",
    "updated_at",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _privacy_safe_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _privacy_safe_value(item)
            for key, item in value.items()
            if str(key).strip().lower() not in _SENSITIVE_ANALYSIS_KEYS
        }
    if isinstance(value, list):
        return [_privacy_safe_value(item) for item in value]
    if isinstance(value, tuple):
        return [_privacy_safe_value(item) for item in value]
    return value


def _privacy_safe_analysis(value: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively drop raw conversation fields before persistence."""
    return _privacy_safe_value(value)


def _row_to_dict(row: Any, columns: list[str]) -> dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, Mapping):
        return dict(row)
    try:
        return dict(row)
    except (TypeError, ValueError):
        return dict(zip(columns, row, strict=True))


def _decode_analysis_row(row: Any, columns: list[str]) -> dict[str, Any]:
    item = _row_to_dict(row, columns)
    if not item:
        return {}
    try:
        item["source_message_ids"] = json.loads(
            item.pop("source_message_ids_json", "[]")
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        item["source_message_ids"] = []
    try:
        item["analysis"] = json.loads(item.pop("analysis_json", "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        item["analysis"] = {}
    return item


@dataclass(frozen=True)
class ConversationAnalysisRecord:
    conversation_hash: str
    telegram_user_hash: str
    lead_id: int
    manager_id: str
    fingerprint: str
    overall_score: int
    confidence: float
    source_message_ids: list[int]
    rollout_mode: str
    analysis: Mapping[str, Any]
    contact_id: int | None = None
    status: str = "analyzed"


@dataclass(frozen=True)
class TaskWriteAudit:
    idempotency_key: str
    lead_id: int
    task_type: str
    conversation_fingerprint: str
    amocrm_task_id: str = ""
    amocrm_note_id: str = ""
    verification_status: str = "pending"
    failure_code: str = ""
    created_at: str = field(default_factory=_now_iso)
