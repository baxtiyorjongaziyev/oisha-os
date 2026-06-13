from __future__ import annotations

import asyncio
import inspect
from typing import Any

from src.services.erp.models import VerificationResult


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _call(obj: Any, method_name: str, *args: Any, **kwargs: Any) -> Any:
    method = getattr(obj, method_name, None)
    if not callable(method):
        raise RuntimeError(f"live_readback_method_missing:{method_name}")
    if inspect.iscoroutinefunction(method):
        return await method(*args, **kwargs)
    return await asyncio.to_thread(method, *args, **kwargs)


def _message_id(execution: dict[str, Any]) -> Any:
    return (
        execution.get("message_id")
        or execution.get("group_message_id")
        or (execution.get("direct_message_ids") or [None])[0]
        or execution.get("metadata", {}).get("message_id")
    )


class AmoCRMTaskLiveVerifier:
    def __init__(self, amocrm: Any):
        self.amocrm = amocrm

    async def verify(
        self,
        action: dict[str, Any],
        execution: dict[str, Any],
    ) -> VerificationResult:
        payload = dict(action.get("payload") or {})
        expected = dict(action.get("expected_result") or {})
        lead_id = int(payload.get("lead_id") or expected.get("lead_id") or 0)
        task_id = (
            execution.get("task_id")
            or execution.get("metadata", {}).get("task_id")
            or expected.get("task_id")
        )
        if not lead_id:
            return VerificationResult(
                False,
                "amocrm",
                expected,
                {"task_exists": False},
                "amocrm_lead_id_missing",
            )
        try:
            tasks = await _call(self.amocrm, "get_lead_open_tasks", lead_id)
        except Exception as exc:
            return VerificationResult(
                False,
                "amocrm",
                expected,
                {"task_exists": False, "error": str(exc)},
                "amocrm_task_readback_failed",
            )
        task_exists = any(
            (task_id and str(item.get("id")) == str(task_id))
            or (
                not task_id
                and str(item.get("text") or "").strip()
                == str(payload.get("text") or "").strip()
            )
            for item in (tasks or [])
        )
        return VerificationResult(
            task_exists,
            "amocrm",
            expected,
            {
                "lead_id": lead_id,
                "task_id": task_id,
                "task_exists": task_exists,
                "open_task_count": len(tasks or []),
            },
            "amocrm_task_confirmed"
            if task_exists
            else "amocrm_task_missing_after_write",
        )


class AmoCRMNoteLiveVerifier:
    def __init__(self, amocrm: Any):
        self.amocrm = amocrm

    async def verify(
        self,
        action: dict[str, Any],
        execution: dict[str, Any],
    ) -> VerificationResult:
        payload = dict(action.get("payload") or {})
        expected = dict(action.get("expected_result") or {})
        lead_id = int(payload.get("lead_id") or expected.get("lead_id") or 0)
        expected_text = str(payload.get("text") or expected.get("text") or "").strip()
        note_id = (
            execution.get("note_id")
            or execution.get("metadata", {}).get("note_id")
            or expected.get("note_id")
        )
        try:
            notes = await _call(self.amocrm, "get_lead_notes", lead_id)
        except Exception as exc:
            return VerificationResult(
                False,
                "amocrm",
                expected,
                {"note_exists": False, "error": str(exc)},
                "amocrm_note_readback_failed",
            )
        note = next(
            (
                item
                for item in (notes or [])
                if (note_id and str(item.get("id")) == str(note_id))
                or (
                    not note_id
                    and str(
                        item.get("text")
                        or (item.get("params") or {}).get("text")
                        or ""
                    ).strip()
                    == expected_text
                )
            ),
            None,
        )
        success = note is not None
        return VerificationResult(
            success,
            "amocrm",
            expected,
            {
                "lead_id": lead_id,
                "note_id": (note or {}).get("id") or note_id,
                "note_exists": success,
            },
            "amocrm_note_confirmed" if success else "amocrm_note_missing_after_write",
        )


class AirtableRecordLiveVerifier:
    def __init__(self, airtable: Any):
        self.airtable = airtable

    async def verify(
        self,
        action: dict[str, Any],
        execution: dict[str, Any],
    ) -> VerificationResult:
        payload = dict(action.get("payload") or {})
        expected = dict(action.get("expected_result") or {})
        record_id = str(payload.get("record_id") or expected.get("record_id") or "")
        expected_fields = dict(payload.get("fields") or expected.get("fields") or {})
        if not record_id:
            return VerificationResult(
                False,
                "airtable",
                expected,
                {"record_exists": False},
                "airtable_record_id_missing",
            )
        try:
            records = await _call(self.airtable, "get_projects", force_refresh=True)
        except TypeError:
            records = await _call(self.airtable, "get_projects")
        except Exception as exc:
            return VerificationResult(
                False,
                "airtable",
                expected,
                {"record_exists": False, "error": str(exc)},
                "airtable_record_readback_failed",
            )
        record = next(
            (item for item in (records or []) if str(item.get("id")) == record_id),
            None,
        )
        actual_fields = dict((record or {}).get("fields") or {})
        mismatches = {
            key: {"expected": value, "actual": actual_fields.get(key)}
            for key, value in expected_fields.items()
            if actual_fields.get(key) != value
        }
        success = record is not None and not mismatches
        return VerificationResult(
            success,
            "airtable",
            {**expected, "record_id": record_id, "fields": expected_fields},
            {
                "record_exists": record is not None,
                "record_id": record_id,
                "fields": actual_fields,
                "mismatches": mismatches,
            },
            "airtable_record_confirmed"
            if success
            else (
                "airtable_record_missing"
                if record is None
                else "airtable_fields_mismatch"
            ),
        )


class AirtableIncomeLiveVerifier:
    def __init__(self, airtable: Any):
        self.airtable = airtable

    async def verify(
        self,
        action: dict[str, Any],
        execution: dict[str, Any],
    ) -> VerificationResult:
        payload = dict(action.get("payload") or {})
        expected = dict(action.get("expected_result") or {})
        source_event_id = str(
            payload.get("source_event_id") or expected.get("source_event_id") or ""
        )
        record_id = (
            execution.get("record_id")
            or execution.get("metadata", {}).get("record_id")
            or expected.get("record_id")
        )
        try:
            records = await _call(self.airtable, "get_finance_records")
        except Exception as exc:
            return VerificationResult(
                False,
                "airtable",
                expected,
                {"record_exists": False, "error": str(exc)},
                "airtable_income_readback_failed",
            )
        record = next(
            (
                item
                for item in (records or [])
                if (
                    str(item.get("_record_type") or "income") == "income"
                    and (
                        (record_id and str(item.get("id")) == str(record_id))
                        or str((item.get("fields") or {}).get("Oisha Source Event") or "")
                        == source_event_id
                    )
                )
            ),
            None,
        )
        success = record is not None
        return VerificationResult(
            success,
            "airtable",
            expected,
            {
                "record_exists": success,
                "record_id": (record or {}).get("id") or record_id,
                "source_event_id": source_event_id,
            },
            "airtable_income_confirmed"
            if success
            else "airtable_income_missing_after_write",
        )


class TelegramMessageLiveVerifier:
    def __init__(self, telegram_reader: Any):
        self.telegram_reader = telegram_reader

    async def verify(
        self,
        action: dict[str, Any],
        execution: dict[str, Any],
    ) -> VerificationResult:
        payload = dict(action.get("payload") or {})
        expected = dict(action.get("expected_result") or {})
        chat_id = payload.get("chat_id") or expected.get("chat_id")
        message_id = _message_id(execution)
        if not message_id:
            return VerificationResult(
                False,
                "telegram",
                expected,
                {"message_exists": False, "chat_id": chat_id},
                "telegram_message_id_missing",
            )
        try:
            message = await _call(
                self.telegram_reader,
                "get_messages",
                chat_id,
                ids=int(message_id),
            )
        except Exception as exc:
            return VerificationResult(
                False,
                "telegram",
                expected,
                {
                    "message_exists": False,
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "error": str(exc),
                },
                "telegram_message_readback_failed",
            )
        exists = bool(message and getattr(message, "id", None))
        return VerificationResult(
            exists,
            "telegram",
            expected,
            {
                "message_exists": exists,
                "chat_id": chat_id,
                "message_id": message_id,
            },
            "telegram_message_confirmed"
            if exists
            else "telegram_message_missing_after_send",
        )


class MeetingLiveVerifier:
    def __init__(self, calendar: Any, amocrm: Any):
        self.calendar = calendar
        self.amocrm = amocrm

    async def verify(
        self,
        action: dict[str, Any],
        execution: dict[str, Any],
    ) -> VerificationResult:
        payload = dict(action.get("payload") or {})
        expected = dict(action.get("expected_result") or {})
        event_id = execution.get("event_id") or expected.get("event_id")
        summary = str(payload.get("summary") or "")
        start_time = str(payload.get("start_time") or "")
        lead_id = int(payload.get("lead_id") or 0)
        try:
            events = await _call(self.calendar, "get_upcoming_events")
        except Exception:
            events = []
        calendar_event = next(
            (
                event
                for event in (events or [])
                if (event_id and str(event.get("id")) == str(event_id))
                or (
                    not event_id
                    and str(event.get("summary") or "") == summary
                    and str((event.get("start") or {}).get("dateTime") or "") == start_time
                )
            ),
            None,
        )
        try:
            tasks = await _call(self.amocrm, "get_lead_open_tasks", lead_id)
        except Exception:
            tasks = []
        amocrm_task = next(
            (
                task
                for task in (tasks or [])
                if "uchrashuv" in str(task.get("text") or "").casefold()
            ),
            None,
        )
        calendar_exists = calendar_event is not None
        amocrm_task_exists = amocrm_task is not None
        success = calendar_exists and amocrm_task_exists
        if success:
            reason = "meeting_confirmed_in_calendar_and_amocrm"
        elif calendar_exists and not amocrm_task_exists:
            reason = "calendar_created_amocrm_task_missing"
        elif amocrm_task_exists and not calendar_exists:
            reason = "amocrm_task_created_calendar_event_missing"
        else:
            reason = "meeting_missing_in_calendar_and_amocrm"
        return VerificationResult(
            success,
            "calendar+amocrm",
            expected,
            {
                "calendar_event_exists": calendar_exists,
                "calendar_event_id": (calendar_event or {}).get("id"),
                "amocrm_task_exists": amocrm_task_exists,
                "amocrm_task_id": (amocrm_task or {}).get("id"),
                "lead_id": lead_id,
            },
            reason,
        )


class LiveVerifierRegistry:
    def __init__(self) -> None:
        self._verifiers: dict[str, Any] = {}

    def register(self, action_type: str, verifier: Any) -> Any:
        self._verifiers[str(action_type)] = verifier
        return verifier

    def get(self, action_type: str) -> Any:
        if action_type not in self._verifiers:
            raise KeyError(f"live_verifier_not_registered:{action_type}")
        return self._verifiers[action_type]

    async def verify(
        self,
        action: dict[str, Any],
        execution: dict[str, Any],
    ) -> VerificationResult:
        action_type = str(action.get("action_type") or "")
        verifier = self.get(action_type)
        return await verifier.verify(action, execution)


def build_live_verifier_registry(
    *,
    amocrm: Any = None,
    airtable: Any = None,
    telegram_reader: Any = None,
    calendar: Any = None,
) -> LiveVerifierRegistry:
    registry = LiveVerifierRegistry()
    if amocrm is not None:
        task_verifier = AmoCRMTaskLiveVerifier(amocrm)
        registry.register("amocrm.create_task", task_verifier)
        registry.register("amocrm.create_meeting_task", task_verifier)
        registry.register("amocrm.add_note", AmoCRMNoteLiveVerifier(amocrm))
    if airtable is not None:
        record_verifier = AirtableRecordLiveVerifier(airtable)
        registry.register("airtable.update_fields", record_verifier)
        registry.register("airtable.update_stage", record_verifier)
        registry.register("airtable.create_income", AirtableIncomeLiveVerifier(airtable))
    if telegram_reader is not None:
        registry.register(
            "telegram.send_message",
            TelegramMessageLiveVerifier(telegram_reader),
        )
    if calendar is not None and amocrm is not None:
        registry.register(
            "calendar.create_meeting",
            MeetingLiveVerifier(calendar, amocrm),
        )
    return registry
