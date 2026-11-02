"""Morning Task Triage and Secure Daily Review Engine.

Supports morning triage workflows (today vs overdue tasks, bulk done/reschedule)
and generates signed ephemeral tokens for protected audio review in Telegram.
"""
import base64
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import hashlib
import hmac
import json
from typing import Any, Dict, List, Optional, Tuple


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
        secret_salt: str = "oisha_default_triage_salt_2026",
    ) -> None:
        """Initialize triage service with target date and cryptographic salt."""
        self.current_date = current_date or datetime.now(timezone.utc).date()
        self.secret_salt = secret_salt.encode("utf-8")

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
            elif task.due_date == self.current_date:
                task.is_overdue = False
                today_list.append(task)

        return MorningOverview(
            today_count=len(today_list),
            overdue_count=len(overdue_list),
            today_tasks=today_list,
            overdue_tasks=overdue_list,
        )

    def apply_action(
        self,
        tasks: List[MorningTaskItem],
        action: str,
        task_ids: List[str],
        reschedule_days: int = 1,
    ) -> TriageActionResult:
        """Apply bulk action (done, dismiss_today, reschedule) to targeted tasks."""
        target_set = set(task_ids)
        updated = 0

        for task in tasks:
            if task.task_id not in target_set:
                continue

            if action == "done":
                task.status = "done"
                updated += 1
            elif action == "dismiss_today":
                task.due_date = self.current_date + timedelta(days=1)
                task.is_overdue = False
                updated += 1
            elif action == "reschedule":
                task.due_date = self.current_date + timedelta(days=reschedule_days)
                task.is_overdue = False
                updated += 1

        msg = f"{updated} ta vazifa muvaffaqiyatli yangilandi."
        return TriageActionResult(
            success=True,
            updated_count=updated,
            action=action,
            message=msg,
        )

    def create_secure_review_token(
        self, call_id: str, manager_id: str, ttl_minutes: int = 15
    ) -> str:
        """Generate a cryptographically signed ephemeral audio review token."""
        expires_at = int(
            (datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)).timestamp()
        )
        payload = {
            "call_id": call_id,
            "manager_id": manager_id,
            "exp": expires_at,
        }
        encoded_data = base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
        ).decode("utf-8")

        sig = hmac.new(
            self.secret_salt, encoded_data.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return f"{encoded_data}.{sig}"

    def validate_review_token(self, token: str) -> Tuple[bool, Dict[str, Any]]:
        """Validate signature and expiration of an ephemeral audio review token."""
        if "." not in token:
            return False, {}

        data_part, sig_part = token.split(".", 1)
        expected_sig = hmac.new(
            self.secret_salt, data_part.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(sig_part, expected_sig):
            return False, {}

        try:
            raw_json = base64.urlsafe_b64decode(data_part.encode("utf-8")).decode("utf-8")
            payload = json.loads(raw_json)
        except Exception:
            return False, {}

        now_ts = int(datetime.now(timezone.utc).timestamp())
        if payload.get("exp", 0) < now_ts:
            return False, {}

        return True, payload
