"""Task and Note writer service for SalesCoach recommendations."""
from __future__ import annotations

import datetime
import inspect
from typing import Any, Callable, Mapping, Literal, Optional

from src.services.core.crm.salescoach_writer.models import (
    TASHKENT,
    TASK_RULES,
    TaskRule,
    TaskWriteResult,
    _analysis_value,
    _extract_id,
    _next_business_day,
    _normalized_text,
    task_idempotency_key,
)
from src.services.core.salescoach_store.models import TaskWriteAudit


class SalesCoachTaskWriter:
    """SalesCoach tavsiyalarini AmoCRM ga xavfsiz yozish."""

    def __init__(
        self,
        amocrm: Any,
        store: Any,
        admin_notifier: Any = None,
        now_provider: Optional[Callable[[], datetime.datetime]] = None,
    ) -> None:
        self.amocrm = amocrm
        self.store = store
        self.admin_notifier = admin_notifier
        self.now_provider = now_provider or (lambda: datetime.datetime.now(TASHKENT))

    def _now(self) -> datetime.datetime:
        value = self.now_provider()
        if value.tzinfo is None:
            return value.replace(tzinfo=TASHKENT)
        return value.astimezone(TASHKENT)

    def _deadline(self, rule: TaskRule) -> int:
        now = self._now()
        if isinstance(rule.delay, datetime.timedelta):
            return int((now + rule.delay).timestamp())

        today_at_18 = now.replace(hour=18, minute=0, second=0, microsecond=0)
        if now < today_at_18 and today_at_18.weekday() < 5:
            return int(today_at_18.timestamp())

        next_day = _next_business_day(
            (now + datetime.timedelta(days=1)).replace(
                hour=10,
                minute=0,
                second=0,
                microsecond=0,
            )
        )
        return int(next_day.timestamp())

    async def _notify_failure(self, **payload: Any) -> None:
        notifier = getattr(self.admin_notifier, "notify_write_failure", None)
        if callable(notifier):
            result = notifier(**payload)
            if inspect.isawaitable(result):
                await result

    async def _ensure_note(self, *, lead_id: int, conversation_fingerprint: str, analysis: Mapping[str, Any]) -> tuple[int | None, bool]:
        key = task_idempotency_key(lead_id, "note", conversation_fingerprint)
        note_text = str(_analysis_value(analysis, "coachingNote", "coaching_note", "") or "").strip()
        if not note_text:
            return None, True
        if await self.store.note_key_exists(key):
            return await self.store.get_note_id(key), True

        created = await self.amocrm.add_lead_note(int(lead_id), note_text)
        note_id = _extract_id(created)
        if not note_id:
            return None, False
        verified = bool(await self.amocrm.get_lead_note(int(lead_id), int(note_id)))
        await self.store.record_note_write(key=key, lead_id=lead_id, note_id=note_id, verified=verified)
        return note_id, verified

    def _verification_failure(self, task: Mapping[str, Any], *, lead_id: int, responsible_user_id: int, expected_text: str, expected_deadline: int) -> str:
        if int(task.get("element_id") or task.get("entity_id") or 0) != int(lead_id):
            return "lead_id_mismatch"
        if int(task.get("responsible_user_id") or 0) != int(responsible_user_id):
            return "responsible_user_mismatch"
        if _normalized_text(task.get("text")) != _normalized_text(expected_text):
            return "text_mismatch"
        if abs(int(task.get("complete_till") or 0) - int(expected_deadline)) > 60:
            return "deadline_mismatch"
        return ""

    async def _validate_preconditions(self, mode: str, approval_actor: Optional[str], analysis_id: int, lead_id: int) -> tuple[int, Optional[TaskWriteResult]]:
        if mode not in {"approval", "auto"}:
            return 0, None
        if mode == "approval" and not str(approval_actor or "").strip():
            return 0, TaskWriteResult(task_type="", skipped=True, failure_code="approval_actor_required")
        now = self._now()
        if now.hour >= 23 or now.hour < 7:
            return 0, TaskWriteResult(task_type="", skipped=True, failure_code="quiet_hours_deferred")
        lead = await self.amocrm.get_lead(int(lead_id))
        resp = int((lead or {}).get("responsible_user_id") or 0)
        if resp <= 0:
            await self._notify_failure(analysis_id=analysis_id, lead_id=lead_id, failure_code="responsible_user_missing")
            return 0, TaskWriteResult(task_type="", verified=False, failure_code="responsible_user_missing")
        return resp, None

    async def _write_and_verify_task(self, *, lead_id: int, resp: int, rule: TaskRule, key: str, task_type: str, fingerprint: str, note_id: Optional[int], analysis_id: int, approval_actor: Optional[str]) -> TaskWriteResult:
        deadline = self._deadline(rule)
        payload = {"text": rule.text, "entity_id": int(lead_id), "entity_type": "leads", "complete_till": deadline, "responsible_user_id": resp, "params": {"type": rule.task_kind}}
        created = await self.amocrm.create_task(payload)
        task_id = _extract_id(created)
        if not task_id:
            failure_code, verified = "task_id_missing", False
        else:
            fetched = await self.amocrm.get_task(int(task_id))
            if not isinstance(fetched, Mapping):
                failure_code, verified = "task_not_found", False
            else:
                failure_code = self._verification_failure(fetched, lead_id=lead_id, responsible_user_id=resp, expected_text=rule.text, expected_deadline=deadline)
                verified = not failure_code

        await self.store.record_task_write(TaskWriteAudit(idempotency_key=key, lead_id=lead_id, task_type=task_type, conversation_fingerprint=fingerprint, amocrm_task_id=task_id, amocrm_note_id=note_id, verification_status="verified" if verified else "failed", failure_code=failure_code))
        if not verified:
            await self._notify_failure(analysis_id=analysis_id, lead_id=lead_id, task_type=task_type, task_id=task_id, failure_code=failure_code, approval_actor=approval_actor)
        return TaskWriteResult(task_type=task_type, task_id=task_id, note_id=note_id, verified=verified, failure_code=failure_code)

    async def _process_recommendation(self, rec: Mapping[str, Any], *, lead_id: int, resp: int, fingerprint: str, note_id: Optional[int], open_texts: set[str], analysis_id: int, approval_actor: Optional[str]) -> Optional[TaskWriteResult]:
        task_type = str(rec.get("type") or "")
        rule = TASK_RULES.get(task_type)
        if rule is None:
            return None
        key = task_idempotency_key(lead_id, task_type, fingerprint)
        claim = getattr(self.store, "claim_task_write", None)
        claimed = await claim(TaskWriteAudit(idempotency_key=key, lead_id=lead_id, task_type=task_type, conversation_fingerprint=fingerprint, amocrm_note_id=note_id, verification_status="claimed")) if callable(claim) else not await self.store.task_key_exists(key)
        if not claimed:
            return TaskWriteResult(task_type=task_type, note_id=note_id, skipped=True, failure_code="idempotency_key_exists")
        if _normalized_text(rule.text) in open_texts:
            return TaskWriteResult(task_type=task_type, note_id=note_id, skipped=True, failure_code="open_task_exists")
        return await self._write_and_verify_task(lead_id=lead_id, resp=resp, rule=rule, key=key, task_type=task_type, fingerprint=fingerprint, note_id=note_id, analysis_id=analysis_id, approval_actor=approval_actor)

    async def apply_analysis(self, *, analysis_id: int, lead_id: int, responsible_user_id: int, conversation_fingerprint: str, analysis: Mapping[str, Any], mode: Literal["approval", "auto"], approval_actor: str | None = None) -> list[TaskWriteResult]:
        resp, early_err = await self._validate_preconditions(mode, approval_actor, analysis_id, lead_id)
        if early_err:
            return [early_err]
        if resp == 0:
            return []

        note_id, note_verified = await self._ensure_note(lead_id=lead_id, conversation_fingerprint=conversation_fingerprint, analysis=analysis)
        if not note_verified:
            await self._notify_failure(analysis_id=analysis_id, lead_id=lead_id, failure_code="note_verification_failed")
            return [TaskWriteResult(task_type="", note_id=note_id, verified=False, failure_code="note_verification_failed")]

        recs = _analysis_value(analysis, "recommendedTasks", "recommended_tasks", [])
        if not isinstance(recs, list):
            return []

        open_tasks = await self.amocrm.list_open_tasks(int(lead_id))
        open_texts = {_normalized_text(t.get("text")) for t in (open_tasks or []) if not bool(t.get("is_completed", False))}
        results: list[TaskWriteResult] = []
        for r in recs:
            if isinstance(r, Mapping):
                res = await self._process_recommendation(r, lead_id=lead_id, resp=resp, fingerprint=conversation_fingerprint, note_id=note_id, open_texts=open_texts, analysis_id=analysis_id, approval_actor=approval_actor)
                if res:
                    results.append(res)
        return results
