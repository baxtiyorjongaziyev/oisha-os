"""
Main notifier class for AmoCRM task alerts.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from src.settings import settings
from src.services.core.crm.task_notifier.routing import resolve_seller
from src.services.core.crm.task_notifier.delivery import deliver

from src.services.core.crm.task_notifier.formatter import (
    format_task_notification,
    DEFAULT_SUBDOMAIN,
)

logger = logging.getLogger('AmoCRMTaskNotifier')

DEFAULT_FORWARD_GROUP_ID = -1003854308552
DEFAULT_FORWARD_TOPIC_ID = 443

def _is_working_hours() -> bool:
    """Check if current time is within official working hours (10:00 - 18:00, Mon-Sat)."""
    from src.time_utils import get_local_now
    now = get_local_now()
    if now.weekday() == 6:  # Sunday
        return False
    return 10 <= now.hour < 18


class AmoCrmTaskNotifier:
    """Direct amoCRM task notification engine using @jonairobot."""

    def __init__(self, amocrm=None, db=None, bot_runtime=None):
        self.amocrm = amocrm
        self.db = db
        self.bot_runtime = bot_runtime
        from aiogram import Bot
        from telethon import TelegramClient
        from src.services.core.telegram.bot_runtime import AiogramBotRuntime, TelethonBotRuntime
        if isinstance(bot_runtime, TelegramClient):
            self.bot_runtime = TelethonBotRuntime(bot_runtime)
        elif isinstance(bot_runtime, Bot):
            self.bot_runtime = AiogramBotRuntime(bot_runtime)
        self._sent_alerts: Set[str] = set()

    def _get_target_destination(self) -> Tuple[Optional[int], Optional[int]]:
        """Get destination chat_id and message_thread_id."""
        group_id = (
            getattr(settings, "AMOCRM_ALERT_FORWARD_GROUP_ID", None)
            or DEFAULT_FORWARD_GROUP_ID
            or getattr(settings, "CRM_GROUP_ID", None)
            or getattr(settings, "TEAM_GROUP_ID", None)
        )
        topic_id = (
            getattr(settings, "AMOCRM_ALERT_FORWARD_TOPIC_ID", None)
            or DEFAULT_FORWARD_TOPIC_ID
            or getattr(settings, "TOPIC_FOLLOWUP_ID", None)
            or getattr(settings, "TOPIC_TASKS_ID", None)
        )
        return group_id, topic_id

    def _dedup_key(self, task_id: int, alert_type: str) -> str:
        return f"amocrm_task_alert:{task_id}:{alert_type}"

    async def is_alert_sent(self, task_id: int, alert_type: str) -> bool:
        """Check if alert was already sent."""
        key = self._dedup_key(task_id, alert_type)
        if key in self._sent_alerts:
            return True
        if self.db and hasattr(self.db, "get_state"):
            try:
                state = await self.db.get_state(key)
                if state:
                    self._sent_alerts.add(key)
                    return True
            except Exception as e:
                logger.debug(f"[TASK_NOTIFIER] DB dedup check warning: {e}")
        return False

    async def mark_alert_sent(self, task_id: int, alert_type: str) -> None:
        """Mark alert as sent in memory and persistent DB."""
        key = self._dedup_key(task_id, alert_type)
        self._sent_alerts.add(key)
        if self.db and hasattr(self.db, "set_state"):
            try:
                await self.db.set_state(key, {"sent_at": time.time(), "task_id": task_id, "type": alert_type})
            except Exception as e:
                logger.debug(f"[TASK_NOTIFIER] DB dedup save warning: {e}")

    async def send_task_alert(
        self,
        task: Dict[str, Any],
        alert_type: str = "due",
        force: bool = False,
    ) -> bool:
        """Send a task only to its verified seller through Oisha."""
        task_id = task.get("id")
        if not task_id:
            return False
        if task.get("_event_type") == "add":
            alert_type = "new"
        if task.get("is_completed") in (True, 1, "1", "true"):
            return False
        if not self.bot_runtime:
            logger.warning("[TASK_NOTIFIER] bot_runtime not available. Cannot send alert.")
            return False

        entity_type = task.get("entity_type") or task.get("element_type") or "leads"
        if entity_type not in ("leads", 2, "2"):
            return False

        # Fetch full task data if needed
        if self.amocrm and (not task.get("text") or (not task.get("entity_id") and not task.get("element_id"))):
            try:
                if hasattr(self.amocrm, "get_task"):
                    full_task = await self.amocrm.get_task(int(task_id))
                    if full_task and isinstance(full_task, dict):
                        task = {**full_task, **task}
            except Exception as e:
                logger.debug(f"[TASK_NOTIFIER] Could not auto-fetch full task {task_id}: {e}")

        if task.get("is_completed") in (True, 1, "1", "true"):
            return False

        # Guard future due alerts
        complete_till = task.get("complete_till")
        now_ts = time.time()
        if alert_type == "due" and complete_till and int(complete_till) > (now_ts + 900):
            logger.debug(f"[TASK_NOTIFIER] Task {task_id} deadline is in the future ({complete_till}). Skipping due alert.")
            return False

        # Skip empty alerts
        if not task.get("text") and not task.get("entity_id") and not task.get("element_id"):
            logger.debug(f"[TASK_NOTIFIER] Task {task_id} has no entity or text. Skipping empty alert.")
            return False

        # Resolve entity & user info
        entity_type = "leads"
        entity_id = task.get("entity_id") or task.get("element_id")
        lead_or_contact = None
        contact_details = None
        phone = None
        responsible_name = None

        if self.amocrm:
            try:
                resp_id = task.get("responsible_user_id")
                if resp_id and hasattr(self.amocrm, "get_user_name"):
                    responsible_name = self.amocrm.get_user_name(resp_id)
                if entity_id:
                    if entity_type in ("leads", 2) and hasattr(self.amocrm, "get_lead"):
                        lead_or_contact = await self.amocrm.get_lead(int(entity_id))
                        if hasattr(self.amocrm, "get_lead_phone"):
                            phone = self.amocrm.get_lead_phone(int(entity_id))
                        contacts = lead_or_contact.get("_embedded", {}).get("contacts", []) if lead_or_contact else []
                        if contacts and hasattr(self.amocrm, "get_contact_details_async"):
                            first_contact_id = contacts[0].get("id")
                            if first_contact_id:
                                contact_details = await self.amocrm.get_contact_details_async(int(first_contact_id))
                    elif entity_type in ("contacts", 1) and hasattr(self.amocrm, "get_contact_details_async"):
                        lead_or_contact = await self.amocrm.get_contact_details_async(int(entity_id))
                        if lead_or_contact and "phone" in lead_or_contact:
                            phone = lead_or_contact.get("phone")
            except Exception as e:
                logger.error(f"[TASK_NOTIFIER] Error resolving entity details for task {task_id}: {e}")

        # Check non-client filter
        if entity_id and entity_type in ("leads", 2):
            try:
                from src.services.core.crm.non_client_filter import is_non_client_lead
                is_nc, reason = await is_non_client_lead(int(entity_id), amocrm_client=self.amocrm, lead_data=lead_or_contact)
                if is_nc:
                    logger.info(f"[TASK_NOTIFIER] Task {task_id} blocked: lead {entity_id} is marked as non-client ({reason})")
                    await self.mark_alert_sent(task_id, alert_type)
                    return False
            except Exception as e:
                logger.debug(f"[TASK_NOTIFIER] Non-client check warning: {e}")

        seller = resolve_seller(lead_or_contact)
        if lead_or_contact and str(lead_or_contact.get("status_id")) in {"142", "143"}:
            return False
        if not seller:
            logger.warning("[TASK_DM] Unresolved/conflicting seller task=%s lead=%s", task_id, entity_id)
            return False
        responsible_name = seller.name
        subdomain = getattr(self.amocrm, "subdomain", None) or DEFAULT_SUBDOMAIN
        text, buttons = format_task_notification(
            task=task,
            lead_or_contact=lead_or_contact,
            contact_details=contact_details,
            phone=phone,
            responsible_name=responsible_name,
            alert_type=alert_type,
            subdomain=subdomain,
        )
        return await deliver(self.bot_runtime, self.db, task, seller, alert_type, text, buttons)

    async def check_and_notify_due_tasks(self, limit: int = 250) -> Dict[str, int]:
        """Proactive check of open tasks from AmoCRM API."""
        stats = {"due_sent": 0, "overdue_sent": 0, "skipped": 0, "total_open": 0}
        if not _is_working_hours():
            logger.debug("[TASK_NOTIFIER] Outside working hours (10:00-18:00 Mon-Sat). Skipping task notification loop.")
            return stats
        if not self.amocrm:
            logger.debug("[TASK_NOTIFIER] AmoCRM client not available for polling.")
            return stats
        try:
            tasks = await self.amocrm.get_tasks(is_completed=False)
            stats["total_open"] = len(tasks)
            now = time.time()
            for task in tasks:
                complete_till = task.get("complete_till")
                if not complete_till:
                    stats["skipped"] += 1
                    continue
                diff = now - complete_till
                if -900 <= diff <= 900:
                    sent = await self.send_task_alert(task, alert_type="due")
                    if sent:
                        stats["due_sent"] += 1
                    else:
                        stats["skipped"] += 1
                elif 900 < diff <= (4 * 3600):
                    sent = await self.send_task_alert(task, alert_type="overdue")
                    if sent:
                        stats["overdue_sent"] += 1
                    else:
                        stats["skipped"] += 1
                elif 0 <= now - int(task.get("created_at") or 0) < 900:
                    if await self.send_task_alert(task, alert_type="new"):
                        stats["new_sent"] = stats.get("new_sent", 0) + 1
                    else:
                        stats["skipped"] += 1
                else:
                    stats["skipped"] += 1
            if stats["due_sent"] > 0 or stats["overdue_sent"] > 0:
                logger.info(
                    f"[TASK_NOTIFIER] Proactive cycle complete: {stats['due_sent']} due, {stats['overdue_sent']} overdue sent out of {stats['total_open']} tasks."
                )
        except Exception as e:
            logger.error(f"[TASK_NOTIFIER] Error in proactive task check: {e}", exc_info=True)
        return stats

def parse_amocrm_task_webhook_data(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse AmoCRM form-data / JSON webhook payload to extract task objects."""
    tasks: List[Dict[str, Any]] = []
    if "tasks" in data and isinstance(data["tasks"], list):
        return data["tasks"]
    extracted: Dict[str, Dict[str, Any]] = {}
    for key, val in data.items():
        if "tasks[" in key:
            parts = key.replace("]", "").split("[")
            if len(parts) >= 4:
                event_type = parts[1]
                idx = parts[2]
                field = parts[3]
                item_key = f"{event_type}_{idx}"
                if item_key not in extracted:
                    extracted[item_key] = {"_event_type": event_type}
                extracted[item_key][field] = val
    for item in extracted.values():
        if "id" in item:
            try:
                item["id"] = int(item["id"])
            except (ValueError, TypeError):
                pass
            if "complete_till" in item:
                try:
                    item["complete_till"] = int(item["complete_till"])
                except (ValueError, TypeError):
                    pass
            tasks.append(item)
    return tasks
