"""Morning Task Triage and Secure Daily Review Engine.

Supports morning triage workflows (today vs overdue tasks, bulk done/reschedule)
and generates signed ephemeral tokens for protected audio review in Telegram.
Ensures strict cryptographic integrity and role-based action accountability.
"""
import base64
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
import secrets
from typing import Any, Dict, List, Optional, Tuple

from src.settings import settings


@dataclass
class MorningTaskItem:
    """Individual task item for morning triage in Telegram or Web UI."""

    task_id: str
    lead_id: str
    lead_name: str
    text: str
    due_date: date
    manager_id: str
    status: str = "pending"
    is_overdue: bool = False
    priority_level: str = "normal"  # "high", "normal", "low"


@dataclass
class MorningOverview:
    """Aggregated morning task overview split into today and overdue queues."""

    today_count: int
    overdue_count: int
    today_tasks: List[MorningTaskItem] = field(default_factory=list)
    overdue_tasks: List[MorningTaskItem] = field(default_factory=list)


@dataclass
class TriageActionResult:
    """Result of executing a triage operation on a batch of tasks."""

    success: bool
    updated_count: int
    action: str
    message: str


class MorningTriageService:
    """Handles morning task classification, bulk triage actions, and token signing."""

    def __init__(
        self,
        current_date: Optional[date] = None,
        secret_salt: Optional[str] = None,
    ) -> None:
        """Initialize triage service with target date and cryptographic salt."""
        self.current_date = current_date or datetime.now(timezone.utc).date()
        salt_val = (
            secret_salt
            or os.getenv("TRIAGE_SECRET_SALT")
            or os.getenv("OISHA_API_SECRET")
            or getattr(settings, "OISHA_API_SECRET", None)
            or getattr(settings, "JWT_SECRET", None)
        )
        if not salt_val:
            salt_val = secrets.token_hex(32)
        self.secret_salt = salt_val.encode("utf-8")

    def is_task_due_today(self, task: MorningTaskItem) -> bool:
        """Check whether task deadline is strictly today."""
        return task.due_date == self.current_date and task.status != "done"

    def get_overview(self, tasks: List[MorningTaskItem]) -> MorningOverview:
        """Categorize tasks into today and overdue groups."""
        today_list: List[MorningTaskItem] = []
        overdue_list: List[MorningTaskItem] = []

        for task in tasks:
            if task.status == "done":
                continue

            if task.due_date < self.current_date:
                task.is_overdue = True
                overdue_list.append(task)
            else:
                task.is_overdue = False
                today_list.append(task)

        return MorningOverview(
            today_count=len(today_list),
            overdue_count=len(overdue_list),
            today_tasks=today_list,
            overdue_tasks=overdue_list,
        )

    def execute_bulk_action(
        self,
        tasks: List[MorningTaskItem],
        task_ids: List[str],
        action: str,  # "done" or "reschedule_tomorrow"
    ) -> Tuple[List[MorningTaskItem], TriageActionResult]:
        """Perform bulk operation across multiple tasks."""
        target_set = set(task_ids)
        updated_count = 0
        tomorrow = self.current_date + timedelta(days=1)

        for task in tasks:
            if task.task_id in target_set:
                if action == "done":
                    task.status = "done"
                    updated_count += 1
                elif action == "reschedule_tomorrow":
                    task.due_date = tomorrow
                    task.is_overdue = False
                    updated_count += 1

        msg = f"{updated_count} ta vazifa muvaffaqiyatli yangilandi"
        return tasks, TriageActionResult(
            success=True,
            updated_count=updated_count,
            action=action,
            message=msg,
        )

    def reschedule_tasks_by_days(
        self,
        tasks: List[MorningTaskItem],
        task_ids: List[str],
        days_ahead: int = 2,
    ) -> Tuple[List[MorningTaskItem], TriageActionResult]:
        """Postpone a subset of tasks by a custom number of calendar days."""
        target_set = set(task_ids)
        updated_count = 0
        target_date = self.current_date + timedelta(days=max(1, days_ahead))

        for task in tasks:
            if task.task_id in target_set:
                task.due_date = target_date
                task.is_overdue = False
                updated_count += 1

        return tasks, TriageActionResult(
            success=True,
            updated_count=updated_count,
            action=f"reschedule_{days_ahead}_days",
            message=f"{updated_count} ta vazifa {target_date} sanasiga surildi",
        )

    def apply_action(
        self,
        tasks: List[MorningTaskItem],
        action: str,
        task_ids: List[str],
        reschedule_days: int = 1,
    ) -> TriageActionResult:
        """Apply done or reschedule action across selected tasks."""
        if action == "done":
            _, res = self.execute_bulk_action(tasks, task_ids, action="done")
            return res
        if action == "reschedule":
            _, res = self.reschedule_tasks_by_days(tasks, task_ids, days_ahead=reschedule_days)
            return res
        return TriageActionResult(
            success=False,
            updated_count=0,
            action=action,
            message="Nomaʼlum amal koʻrsatildi",
        )

    def generate_signed_audio_token(
        self, call_id: str, manager_id: str, ttl_minutes: int = 60
    ) -> str:
        """Generate tamper-proof signed URL token for listening to call recording."""
        now_ts = int(datetime.now(timezone.utc).timestamp())
        expires_at = now_ts + (ttl_minutes * 60)

        payload_dict = {
            "call_id": call_id,
            "manager_id": manager_id,
            "cid": call_id,
            "mid": manager_id,
            "exp": expires_at,
        }
        raw_json = json.dumps(payload_dict, separators=(",", ":"))
        b64_payload = base64.urlsafe_b64encode(raw_json.encode("utf-8")).decode("utf-8")

        sig = hmac.new(
            self.secret_salt, b64_payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()[:24]

        return f"{b64_payload}.{sig}"

    def create_secure_review_token(
        self, call_id: str, manager_id: str, ttl_minutes: int = 15
    ) -> str:
        """Generate secure token for call audio review."""
        return self.generate_signed_audio_token(call_id, manager_id, ttl_minutes)

    def verify_signed_audio_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify token authenticity and expiration."""
        if not token or "." not in token:
            return None

        parts = token.split(".")
        if len(parts) != 2:
            return None

        b64_payload, provided_sig = parts
        expected_sig = hmac.new(
            self.secret_salt, b64_payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()[:24]

        if not hmac.compare_digest(provided_sig, expected_sig):
            return None

        try:
            raw_bytes = base64.urlsafe_b64decode(b64_payload.encode("utf-8"))
            data = json.loads(raw_bytes.decode("utf-8"))
            now_ts = int(datetime.now(timezone.utc).timestamp())
            if data.get("exp", 0) < now_ts:
                return None  # Expired
            return data
        except Exception:
            return None

    def validate_review_token(self, token: str) -> Tuple[bool, Dict[str, Any]]:
        """Validate token and return (is_valid, payload) tuple."""
        data = self.verify_signed_audio_token(token)
        if not data:
            return False, {}
        return True, data
