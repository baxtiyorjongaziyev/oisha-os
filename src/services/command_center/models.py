"""Evidence-first command planning for Oisha's business control center."""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any
import logging
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IntegrationCapability:
    key: str
    name: str
    configured: bool
    operations: tuple[str, ...]


@dataclass(frozen=True)
class CommandPlan:
    intent: str
    mutation: bool
    approval_required: bool
    confidence: float
    entities: dict[str, Any]
    required_sources: tuple[str, ...]
    next_action: str
    idempotency_key: str

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BrandingERPPhase:
    phase: int
    title: str
    outcome: str
    source_of_truth: tuple[str, ...]
    must_run_24_7: tuple[str, ...]
    acceptance_checks: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TelegramMigrationCheck:
    key: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class TelegramMigrationStatus:
    stage: str
    userbot_runtime: str
    bot_runtime_backend: str
    aiogram_dispatcher_enabled: bool
    rollback_backend: str
    checks: tuple[TelegramMigrationCheck, ...]
    next_actions: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ready_count"] = sum(1 for item in self.checks if item.ok)
        payload["total_count"] = len(self.checks)
        return payload


@dataclass(frozen=True)
class SalesPriorityLead:
    lead_id: int
    name: str
    priority_score: int
    priority: str
    action: str
    reasons: tuple[str, ...]
    evidence: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectRiskItem:
    project_id: str
    name: str
    risk_score: int
    risk: str
    action: str
    reasons: tuple[str, ...]
    evidence: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinanceRiskItem:
    project_id: str
    name: str
    risk_score: int
    risk: str
    action: str
    reasons: tuple[str, ...]
    evidence: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TeamCapacityItem:
    owner_key: str
    owner_name: str
    load_score: int
    load: str
    action: str
    reasons: tuple[str, ...]
    evidence: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


_PHONE_RE = re.compile(r"\+?998\d{9}")
_LEAD_ID_RE = re.compile(r"(?:lead|lid|bitim)[ \t]{0,16}#?[ \t]{0,16}(\d{5,})", re.IGNORECASE)
_TIME_RE = re.compile(r"\b(?:soat\s*)?(\d{1,2})(?::(\d{2}))?\b", re.IGNORECASE)
CLOSED_LEAD_STATUS_IDS = frozenset({142, 143})
CLOSED_PROJECT_STAGE_MARKERS = ("done", "completed", "yakunlangan", "topshirildi", "arxiv", "bekor", "cancel")
PROJECT_FIELD_ALIASES = {
    "name": ("Loyihani nomi?", "Project Name", "Name", "name", "title"),
    "stage": ("Loyiha bosqichi", "Stage", "Status", "Holati", "stage", "status"),
    "deadline": ("END sana", "Deadline", "Muddati", "deadline", "due_date"),
    "manager": ("PM", "Manager", "Mas'ul", "owner", "manager"),
    "summary": ("Xulosa", "Summary", "Chat Summary", "notes", "summary"),
    "budget": ("Kelishgan narx", "Jami loyiha narxi (UZS)", "Budget", "budget"),
    "paid": ("To'langan", "Jami to'langan", "paid_amount", "Jami to'langan USD", "paid"),
    "remaining": ("Qoldiq to'lov $", "Qoldiq", "remaining", "remaining_amount"),
    "payment_status": ("To'lov statusi", "To'lovlar holati", "payment_status"),
}


def _configured(*keys: str) -> bool:
    return all(bool((os.getenv(key) or "").strip()) for key in keys)


def _env_bool(key: str) -> bool:
    return (os.getenv(key) or "").strip().lower() in {"1", "true", "yes", "on"}

def _lead_contacts(lead: dict[str, Any]) -> list[dict[str, Any]]:
    return lead.get("_embedded", {}).get("contacts", []) or lead.get("contacts", []) or []


def _field_text(fields: dict[str, Any], key: str) -> str:
    for name in PROJECT_FIELD_ALIASES.get(key, (key,)):
        if name not in fields:
            continue
        value = fields.get(name)
        if isinstance(value, list):
            return ", ".join(str(item) for item in value if item).strip()
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except (TypeError, ValueError):
        return None


def _money_value(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value)
    digits = re.sub(r"[^\d-]", "", text)
    if digits in ("", "-"):
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _age_hours(timestamp: int, now: datetime) -> int | None:
    if timestamp <= 0:
        return None
    return max(0, int((now.timestamp() - timestamp) // 3600))


def _age_days(timestamp: int, now: datetime) -> int | None:
    if timestamp <= 0:
        return None
    return max(0, int((now.timestamp() - timestamp) // 86400))


def _has_overdue_task(tasks: list[dict[str, Any]], now: datetime) -> bool:
    current_ts = int(now.timestamp())
    for task in tasks:
        complete_till = _int_or_zero(task.get("complete_till"))
        if complete_till and complete_till < current_ts:
            return True
    return False


