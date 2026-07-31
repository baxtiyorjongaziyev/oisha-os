"""Production adapters and feature-flagged installer for Telegram SalesCoach."""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional

from telethon import events

from src.services.core.crm.salescoach_task_writer import SalesCoachTaskWriter
from src.services.core.salescoach_sync import get_salescoach_sync
from src.services.core.telegram_salescoach import (
    CrmMatch,
    TelegramConversationMessage,
    TelegramSalesCoach,
)
from src.services.core.telegram_salescoach_store import TelegramSalesCoachStore


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


class TelegramSalesCoachNotifier:
    """Owner-only summaries; never includes raw customer messages or phones."""

    def __init__(self, *, bot_runtime: Any, owner_id: int):
        self.bot_runtime = bot_runtime
        self.owner_id = int(owner_id)

    async def send(
        self,
        *,
        analysis_id: int,
        lead_id: int,
        score: int,
        risk: Any,
        next_action: Any,
        recommended_tasks: Iterable[Any],
    ) -> None:
        task_names = [
            str(item.get("type"))
            for item in recommended_tasks
            if isinstance(item, Mapping) and item.get("type")
        ]
        text = (
            "🧭 SalesCoach tasdiqlashi\n"
            f"Lead: {int(lead_id)}\n"
            f"Baho: {max(0, min(int(score), 100))}/100\n"
            f"Risk: {str(risk or 'medium')}\n"
            f"Keyingi qadam: {str(next_action or '-')}\n"
            f"Tasklar: {', '.join(task_names) or '-'}\n"
            f"Analysis ID: {int(analysis_id)}"
        )
        await self.bot_runtime.send_message(self.owner_id, text)

    async def notify_write_failure(self, **payload: Any) -> None:
        await self.bot_runtime.send_message(
            self.owner_id,
            "⚠️ SalesCoach AmoCRM yozuvi tasdiqlanmadi\n"
            f"Lead: {int(payload.get('lead_id') or 0)}\n"
            f"Kod: {str(payload.get('failure_code') or 'unknown')}",
        )


async def _personal_sender_checker(sender: Any) -> bool:
    try:
        from src.main import _is_personal_folder_sender

        return bool(await _is_personal_folder_sender(sender))
    except Exception as exc:
        logger.warning("Personal folder adapter failed: %s", type(exc).__name__)
        return True


def _internal_user_ids(settings: Any) -> set[int]:
    values = _parse_id_list(os.getenv("SALESCOACH_INTERNAL_TELEGRAM_IDS", ""))
    owner_id = int(getattr(settings, "OWNER_ID", 0) or 0)
    if owner_id:
        values.add(owner_id)
    for item in getattr(settings, "SALES_MANAGER_IDS", []) or []:
        try:
            values.add(int(item))
        except (TypeError, ValueError):
            continue
    return values


async def install_telegram_salescoach(context: Any) -> Optional[TelegramSalesCoach]:
    """Install once on the Oracle userbot runtime; default is disabled."""
    if not _env_bool("TELEGRAM_SALESCOACH_ENABLED", False):
        return None
    if getattr(context, "telegram_salescoach", None) is not None:
        return context.telegram_salescoach

    client = getattr(context, "client", None)
    msg_controller = getattr(context, "msg_controller", None)
    if client is None or msg_controller is None:
        return None

    from src.settings import settings

    salescoach_sync = get_salescoach_sync()
    if not salescoach_sync.enabled:
        logger.warning("Telegram SalesCoach disabled: salescoach_api_unconfigured")
        return None

    store = TelegramSalesCoachStore(msg_controller.db)
    await store.initialize()
    notifier = TelegramSalesCoachNotifier(
        bot_runtime=getattr(context, "bot_runtime", None),
        owner_id=int(getattr(settings, "OWNER_ID", 0) or 0),
    )
    amocrm_adapter = AmoCRMTaskAdapter(msg_controller.crm.amocrm)
    task_writer = SalesCoachTaskWriter(
        amocrm=amocrm_adapter,
        store=store,
        admin_notifier=notifier,
    )
    coach = TelegramSalesCoach(
        store=store,
        salescoach_sync=salescoach_sync,
        crm_matcher=AmoCRMConversationMatcher(
            db=msg_controller.db,
            amocrm=msg_controller.crm.amocrm,
        ),
        task_writer=task_writer,
        message_loader=TelethonConversationLoader(client, limit=50),
        personal_sender_checker=_personal_sender_checker,
        internal_user_ids=_internal_user_ids(settings),
        approval_notifier=notifier,
        enabled=True,
        mode=os.getenv("TELEGRAM_SALESCOACH_MODE", "shadow"),
        idle_seconds=_env_int("TELEGRAM_SALESCOACH_IDLE_SECONDS", 600),
    )

    async def _event_handler(event: Any) -> None:
        try:
            sender = await event.get_sender()
            await coach.handle_private_event(
                event,
                sender=sender,
                client=client,
            )
        except Exception as exc:
            logger.warning("SalesCoach event hook failed: %s", type(exc).__name__)

    client.add_event_handler(_event_handler, events.NewMessage(incoming=True))
    client.add_event_handler(_event_handler, events.NewMessage(outgoing=True))
    context.telegram_salescoach = coach
    context.telegram_salescoach_store = store
    context.salescoach_task_writer = task_writer
    logger.info(
        "Telegram SalesCoach installed: mode=%s idle_seconds=%s",
        coach.mode,
        coach.idle_seconds,
    )
    return coach
