"""
Conversation loading, AmoCRM entity matching, and task adapter primitives.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import os
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from src.services.core.telegram_salescoach import (
    CrmMatch,
    TelegramConversationMessage,
)

logger = logging.getLogger("TelegramSalesCoachRuntime")

def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _parse_id_list(raw: str) -> set[int]:
    output: set[int] = set()
    for item in str(raw or "").split(","):
        try:
            value = int(item.strip())
        except ValueError:
            continue
        if value:
            output.add(value)
    return output


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class TelethonConversationLoader:
    """Loads a bounded real Telegram dialog with original message IDs."""

    def __init__(self, client: Any, *, limit: int = 50):
        self.client = client
        self.limit = max(2, min(int(limit), 50))

    async def __call__(self, telegram_user_id: int) -> list[TelegramConversationMessage]:
        values: list[TelegramConversationMessage] = []
        async for message in self.client.iter_messages(
            int(telegram_user_id),
            limit=self.limit,
        ):
            text = str(
                getattr(message, "raw_text", None)
                or getattr(message, "message", None)
                or ""
            ).strip()
            if not text:
                continue
            sent_at = getattr(message, "date", None)
            if not isinstance(sent_at, datetime):
                continue
            if sent_at.tzinfo is None:
                sent_at = sent_at.replace(tzinfo=timezone.utc)
            values.append(
                TelegramConversationMessage(
                    id=int(getattr(message, "id")),
                    role="manager" if bool(getattr(message, "out", False)) else "customer",
                    text=text,
                    sent_at=sent_at,
                )
            )
        values.reverse()
        return values


class AmoCRMConversationMatcher:
    """Matches Telegram users to active AmoCRM leads using verified phone only."""

    def __init__(self, *, db: Any, amocrm: Any):
        self.db = db
        self.amocrm = amocrm

    async def match(self, telegram_user_id: int) -> Optional[CrmMatch]:
        user = await self.db.get_user_info(int(telegram_user_id))
        if not isinstance(user, Mapping):
            return None
        phone = str(user.get("phone") or "").strip()
        if not phone:
            return None

        contact_getter = getattr(self.amocrm, "get_contact_by_phone", None)
        leads_getter = getattr(self.amocrm, "get_active_leads_for_contact", None)
        if not callable(contact_getter) or not callable(leads_getter):
            return None

        contact = await asyncio.to_thread(contact_getter, phone)
        if not isinstance(contact, Mapping) or not contact.get("id"):
            return None

        leads = await asyncio.to_thread(leads_getter, int(contact["id"]))
        eligible = [
            lead
            for lead in (leads or [])
            if isinstance(lead, Mapping)
            and lead.get("id")
            and int(lead.get("responsible_user_id") or 0) > 0
        ]
        if not eligible:
            return None

        lead = max(
            eligible,
            key=lambda item: (
                int(item.get("updated_at") or 0),
                int(item.get("created_at") or 0),
                int(item.get("id") or 0),
            ),
        )
        status = str(
            lead.get("status_name")
            or lead.get("status_id")
            or lead.get("status")
            or ""
        )
        return CrmMatch(
            lead_id=int(lead["id"]),
            contact_id=int(contact["id"]),
            responsible_user_id=int(lead["responsible_user_id"]),
            confidence=0.95,
            crm_status=status,
        )


class AmoCRMTaskAdapter:
    """Adapts the existing AmoCRMSync surface to SalesCoachTaskWriter."""

    def __init__(self, amocrm: Any):
        self.amocrm = amocrm
        self._created_task_lead_ids: dict[int, int] = {}

    async def get_lead(self, lead_id: int) -> dict[str, Any]:
        result = await _maybe_await(self.amocrm.get_lead(int(lead_id)))
        return dict(result) if isinstance(result, Mapping) else {}

    async def list_open_tasks(self, lead_id: int) -> list[dict[str, Any]]:
        getter = getattr(self.amocrm, "get_lead_open_tasks", None)
        if not callable(getter):
            return []
        result = await _maybe_await(getter(int(lead_id)))
        return [dict(item) for item in (result or []) if isinstance(item, Mapping)]

    async def create_note(self, lead_id: int, text: str) -> dict[str, Any]:
        creator = getattr(self.amocrm, "add_lead_note", None)
        if not callable(creator):
            return {}
        result = await asyncio.to_thread(creator, int(lead_id), str(text))
        if isinstance(result, Mapping):
            return dict(result)
        if isinstance(result, int):
            return {"id": result}
        return {"id": ""} if result else {}

    async def list_notes(self, lead_id: int) -> list[dict[str, Any]]:
        getter = getattr(self.amocrm, "get_lead_notes", None)
        if not callable(getter):
            return []
        result = await _maybe_await(getter(int(lead_id)))
        return [dict(item) for item in (result or []) if isinstance(item, Mapping)]

    async def create_task(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        result = await _maybe_await(
            self.amocrm.create_task(
                element_id=int(payload["entity_id"]),
                text=str(payload["text"]),
                complete_till=int(payload["complete_till"]),
                responsible_user_id=int(payload["responsible_user_id"]),
            )
        )
        normalized: dict[str, Any]
        if isinstance(result, Mapping):
            normalized = dict(result)
        elif isinstance(result, int) and not isinstance(result, bool):
            normalized = {"id": result}
        else:
            normalized = {}

        task_id = normalized.get("id")
        if task_id:
            self._created_task_lead_ids[int(task_id)] = int(payload["entity_id"])
            return normalized

        # Some legacy implementations return only True. Re-read the lead's
        # open tasks and locate the exact mutation instead of inventing an ID.
        if result:
            tasks = await self.list_open_tasks(int(payload["entity_id"]))
            for task in tasks:
                if (
                    str(task.get("text") or "").strip() == str(payload["text"]).strip()
                    and int(task.get("responsible_user_id") or 0)
                    == int(payload["responsible_user_id"])
                ):
                    found_id = int(task.get("id") or 0)
                    if found_id:
                        self._created_task_lead_ids[found_id] = int(payload["entity_id"])
                        return {"id": found_id}
        return {}

    async def get_task(self, task_id: int) -> dict[str, Any]:
        direct = getattr(self.amocrm, "get_task", None)
        if callable(direct):
            result = await _maybe_await(direct(int(task_id)))
            return dict(result) if isinstance(result, Mapping) else {}

        getter = getattr(self.amocrm, "get_tasks", None)
        if callable(getter):
            tasks = await _maybe_await(getter(is_completed=False))
            for task in tasks or []:
                if isinstance(task, Mapping) and int(task.get("id") or 0) == int(task_id):
                    return dict(task)

        lead_id = self._created_task_lead_ids.get(int(task_id))
        if lead_id:
            for task in await self.list_open_tasks(lead_id):
                if int(task.get("id") or 0) == int(task_id):
                    return task
        return {}
