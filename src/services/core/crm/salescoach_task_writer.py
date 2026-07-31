"""Verified, idempotent AmoCRM writes for Telegram SalesCoach analyses."""

from __future__ import annotations

import hashlib
import inspect
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Literal, Mapping, Optional
from zoneinfo import ZoneInfo

from src.services.core.telegram_salescoach_store import TaskWriteAudit


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


def _analysis_value(analysis: Mapping[str, Any], camel: str, snake: str, default: Any) -> Any:
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


class SalesCoachTaskWriter:
    """Writes allowlisted AmoCRM notes/tasks and verifies every mutation."""

    def __init__(
        self,
        *,
        amocrm: Any,
        store: Any,
        admin_notifier: Any = None,
        now_provider: Optional[Callable[[], datetime]] = None,
    ):
        self.amocrm = amocrm
        self.store = store
        self.admin_notifier = admin_notifier
        self.now_provider = now_provider or (lambda: datetime.now(TASHKENT))

    def _now(self) -> datetime:
        value = self.now_provider()
        if value.tzinfo is None:
            return value.replace(tzinfo=TASHKENT)
        return value.astimezone(TASHKENT)

    def _deadline(self, rule: TaskRule) -> int:
        now = self._now()
        if isinstance(rule.delay, timedelta):
            return int((now + rule.delay).timestamp())

        today_at_18 = now.replace(hour=18, minute=0, second=0, microsecond=0)
        if now < today_at_18 and today_at_18.weekday() < 5:
            return int(today_at_18.timestamp())

        next_day = _next_business_day(
            (now + timedelta(days=1)).replace(
                hour=10, minute=0, second=0, microsecond=0
            )
        )
        return int(next_day.timestamp())

    async def _notify_failure(self, **payload: Any) -> None:
        notifier = getattr(self.admin_notifier, "notify_write_failure", None)
        if callable(notifier):
            result = notifier(**payload)
            if inspect.isawaitable(result):
                await result

    async def _ensure_note(
        self,
        *,
        lead_id: int,
        conversation_fingerprint: str,
        analysis: Mapping[str, Any],
    ) -> tuple[str, bool]:
        notes = await self.amocrm.list_notes(lead_id)
        for note in notes or []:
            if conversation_fingerprint in str(note.get("text", "")):
                return _extract_id(note), True

        score = int(_analysis_value(analysis, "overallScore", "overall_score", 0) or 0)
        intent = str(_analysis_value(analysis, "clientIntent", "client_intent", "cold"))
        risk = str(_analysis_value(analysis, "dealRisk", "deal_risk", "medium"))
        next_action = str(
            _analysis_value(analysis, "nextBestAction", "next_best_action", "")
        )
        objections = _analysis_value(analysis, "objections", "objections", [])
        evidence = _analysis_value(
            analysis, "evidenceMessageIds", "evidence_message_ids", []
        )
        objection_text = ", ".join(str(item) for item in objections or []) or "yo'q"
        evidence_text = ",".join(str(int(item)) for item in evidence or [] if str(item).isdigit())
        note_text = (
            "[OISHA_SALESCOACH]\n"
            f"Score: {max(0, min(score, 100))}/100\n"
            f"Intent: {intent}\n"
            f"Risk: {risk}\n"
            f"Objections: {objection_text}\n"
            f"Next: {next_action}\n"
            f"Evidence: {evidence_text}\n"
            f"Fingerprint: {conversation_fingerprint}"
        )
        created = await self.amocrm.create_note(lead_id, note_text)
        note_id = _extract_id(created)

        refreshed = await self.amocrm.list_notes(lead_id)
        verified = any(
            conversation_fingerprint in str(note.get("text", ""))
            for note in (refreshed or [])
        )
        return note_id, verified

    @staticmethod
    def _verification_failure(
        task: Mapping[str, Any],
        *,
        lead_id: int,
        responsible_user_id: int,
        expected_text: str,
        expected_deadline: int,
    ) -> str:
        if int(task.get("entity_id") or 0) != int(lead_id):
            return "entity_id_mismatch"
        if int(task.get("responsible_user_id") or 0) != int(responsible_user_id):
            return "responsible_user_mismatch"
        if _normalized_text(task.get("text")) != _normalized_text(expected_text):
            return "task_text_mismatch"
        actual_deadline = int(task.get("complete_till") or 0)
        if abs(actual_deadline - int(expected_deadline)) > 60:
            return "deadline_mismatch"
        return ""

    async def apply_analysis(
        self,
        *,
        analysis_id: int,
        lead_id: int,
        responsible_user_id: int,
        conversation_fingerprint: str,
        analysis: Mapping[str, Any],
        mode: Literal["approval", "auto"],
        approval_actor: str | None = None,
    ) -> list[TaskWriteResult]:
        if mode not in {"approval", "auto"}:
            return []

        lead = await self.amocrm.get_lead(int(lead_id))
        current_responsible = int((lead or {}).get("responsible_user_id") or 0)
        if current_responsible <= 0:
            await self._notify_failure(
                analysis_id=analysis_id,
                lead_id=lead_id,
                failure_code="responsible_user_missing",
            )
            return [
                TaskWriteResult(
                    task_type="",
                    verified=False,
                    failure_code="responsible_user_missing",
                )
            ]

        # The passed value is a CRM-match hint only. The current lead owner wins.
        _ = responsible_user_id
        note_id, note_verified = await self._ensure_note(
            lead_id=lead_id,
            conversation_fingerprint=conversation_fingerprint,
            analysis=analysis,
        )
        if not note_verified:
            await self._notify_failure(
                analysis_id=analysis_id,
                lead_id=lead_id,
                failure_code="note_verification_failed",
            )
            return [
                TaskWriteResult(
                    task_type="",
                    note_id=note_id,
                    verified=False,
                    failure_code="note_verification_failed",
                )
            ]

        recommendations = _analysis_value(
            analysis, "recommendedTasks", "recommended_tasks", []
        )
        if not isinstance(recommendations, list):
            return []

        open_tasks = await self.amocrm.list_open_tasks(int(lead_id))
        open_texts = {
            _normalized_text(task.get("text"))
            for task in (open_tasks or [])
            if not bool(task.get("is_completed", False))
        }

        results: list[TaskWriteResult] = []
        for recommendation in recommendations:
            if not isinstance(recommendation, Mapping):
                continue
            task_type = str(recommendation.get("type") or "")
            rule = TASK_RULES.get(task_type)
            if rule is None:
                continue

            key = task_idempotency_key(
                lead_id, task_type, conversation_fingerprint
            )
            if await self.store.task_key_exists(key):
                results.append(
                    TaskWriteResult(
                        task_type=task_type,
                        note_id=note_id,
                        skipped=True,
                        failure_code="idempotency_key_exists",
                    )
                )
                continue

            if _normalized_text(rule.text) in open_texts:
                results.append(
                    TaskWriteResult(
                        task_type=task_type,
                        note_id=note_id,
                        skipped=True,
                        failure_code="open_task_exists",
                    )
                )
                continue

            deadline = self._deadline(rule)
            payload = {
                "text": rule.text,
                "entity_id": int(lead_id),
                "entity_type": "leads",
                "complete_till": deadline,
                "responsible_user_id": current_responsible,
                "params": {"type": rule.task_kind},
            }
            created = await self.amocrm.create_task(payload)
            task_id = _extract_id(created)
            if not task_id:
                failure_code = "task_id_missing"
                verified = False
            else:
                fetched = await self.amocrm.get_task(int(task_id))
                if not isinstance(fetched, Mapping):
                    failure_code = "task_not_found"
                else:
                    failure_code = self._verification_failure(
                        fetched,
                        lead_id=lead_id,
                        responsible_user_id=current_responsible,
                        expected_text=rule.text,
                        expected_deadline=deadline,
                    )
                verified = not failure_code

            await self.store.record_task_write(
                TaskWriteAudit(
                    idempotency_key=key,
                    lead_id=lead_id,
                    task_type=task_type,
                    conversation_fingerprint=conversation_fingerprint,
                    amocrm_task_id=task_id,
                    amocrm_note_id=note_id,
                    verification_status="verified" if verified else "failed",
                    failure_code=failure_code,
                )
            )

            if not verified:
                await self._notify_failure(
                    analysis_id=analysis_id,
                    lead_id=lead_id,
                    task_type=task_type,
                    task_id=task_id,
                    failure_code=failure_code,
                    approval_actor=approval_actor,
                )

            results.append(
                TaskWriteResult(
                    task_type=task_type,
                    task_id=task_id,
                    note_id=note_id,
                    verified=verified,
                    failure_code=failure_code,
                )
            )

        return results
