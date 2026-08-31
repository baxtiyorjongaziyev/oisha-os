"""
Data models and helpers for SalesCoach task writer.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal, Mapping
from zoneinfo import ZoneInfo

TASHKENT = ZoneInfo("Asia/Tashkent")


@dataclass(frozen=True)
class TaskRule:
    text: str
    delay: timedelta | Literal["today_18_00"]
    task_kind: str


TASK_RULES: dict[str, TaskRule] = {
    "reply_customer": TaskRule(
        "Mijozga javob bering", timedelta(minutes=30), "call"
    ),
    "schedule_meeting": TaskRule(
        "Uchrashuv vaqtini belgilang", "today_18_00", "call"
    ),
    "send_proposal": TaskRule(
        "Moslashtirilgan taklif/KP yuboring", timedelta(hours=2), "follow_up"
    ),
    "follow_up": TaskRule("Follow-up qiling", timedelta(hours=24), "follow_up"),
    "send_material": TaskRule(
        "Va'da qilingan materialni yuboring", timedelta(hours=1), "follow_up"
    ),
    "manager_review": TaskRule(
        "Rahbar bilan suhbatni ko'rib chiqing", "today_18_00", "follow_up"
    ),
}


@dataclass(frozen=True)
class TaskWriteResult:
    task_type: str
    task_id: str = ""
    note_id: str = ""
    verified: bool = False
    skipped: bool = False
    failure_code: str = ""


def task_idempotency_key(
    lead_id: int,
    task_type: str,
    conversation_fingerprint: str,
) -> str:
    raw = f"{int(lead_id)}:{task_type}:{conversation_fingerprint}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _normalized_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _note_text(note: Mapping[str, Any]) -> str:
    direct = note.get("text")
    if direct:
        return str(direct)
    params = note.get("params")
    if isinstance(params, Mapping):
        return str(params.get("text") or "")
    return ""


def _extract_id(value: Any) -> str:
    if isinstance(value, Mapping):
        direct = value.get("id")
        if direct is not None:
            return str(direct)
        embedded = value.get("_embedded")
        if isinstance(embedded, Mapping):
            for key in ("tasks", "notes"):
                items = embedded.get(key)
                if isinstance(items, list) and items and isinstance(items[0], Mapping):
                    item_id = items[0].get("id")
                    if item_id is not None:
                        return str(item_id)
    item_id = getattr(value, "id", None)
    return str(item_id) if item_id is not None else ""


def _analysis_value(
    analysis: Mapping[str, Any],
    camel: str,
    snake: str,
    default: Any,
) -> Any:
    if camel in analysis:
        return analysis[camel]
    if snake in analysis:
        return analysis[snake]
    return default


def _next_business_day(value: datetime) -> datetime:
    candidate = value
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate
