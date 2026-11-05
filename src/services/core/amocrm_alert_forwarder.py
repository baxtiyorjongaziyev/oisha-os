"""
Forwards AmoCRM overdue-task alerts into the sales team group/topic, two ways:

1. setup_handlers(): relays @amocrm_amobot daily summary reports (Отчет за сегодня)
   to the sales team group/topic and owner in clean Uzbek Markdown format.
   Routine task alert DM interception remains disabled per owner policy
   (handled directly via poll_overdue_tasks).

2. poll_overdue_tasks(): a userbot-independent fallback that asks AmoCRM's
   own REST API which tasks are overdue and relays those directly. This
   keeps overdue-task alerts flowing to the team even while the userbot
   session is down.

Both paths deliver through bot_runtime (the AGENTS.md-mandated migration
target for outbound team-facing messages) instead of a raw Telethon forward,
so the alert lands as a normal @jonairobot message with a working CRM link
button rather than a "forwarded from" copy of a private DM.
"""
import logging
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from telethon import TelegramClient, events
from telethon.tl.types import KeyboardButtonUrl

from src.settings import settings

logger = logging.getLogger("AmoCrmAlertForwarder")

AMOCRM_BOT_USERNAME = "amocrm_amobot"
TASHKENT_TZ = ZoneInfo("Asia/Tashkent")
SEEN_OVERDUE_TASKS_KEY = "amocrm_alert:seen_overdue_task_ids"
MAX_SEEN_TASK_IDS = 500


def _extract_crm_url(message) -> str | None:
    """Pull the "Перейти в amoCRM"-style URL button off the bot's own message."""
    markup = getattr(message, "reply_markup", None)
    rows = getattr(markup, "rows", None) or []
    for row in rows:
        for button in getattr(row, "buttons", None) or []:
            if isinstance(button, KeyboardButtonUrl) and button.url:
                return button.url
    return None


def _format_overdue_task_alert(task: dict[str, Any], subdomain: str) -> tuple[str, list[list[dict[str, str]]] | None]:
    """Build text and inline button for an overdue AmoCRM task."""
    entity_id = task.get("entity_id")
    entity_type = task.get("entity_type") or "leads"
    text_body = (task.get("text") or "Muddati o'tgan vazifa").strip()
    deadline = datetime.fromtimestamp(int(task["complete_till"]), tz=TASHKENT_TZ)
    message = (
        "⏰ Muddati o'tgan AmoCRM vazifasi\n\n"
        f"{text_body}\n\n"
        f"Muddat: {deadline.strftime('%d.%m.%Y %H:%M')}"
    )
    crm_url = f"https://{subdomain}.amocrm.ru/{entity_type}/detail/{entity_id}" if subdomain and entity_id else None
    buttons = [[{"text": "🌐 Перейти в amoCRM", "url": crm_url}]] if crm_url else None
    return message, buttons


class AmoCrmAlertForwarder:
    def __init__(self, user_client: TelegramClient | None, bot_runtime, amocrm=None, db=None):
        self.user_client = user_client
        self.bot_runtime = bot_runtime
        self.amocrm = amocrm
        self.db = db
        self.group_id = settings.AMOCRM_ALERT_FORWARD_GROUP_ID
        self.topic_id = settings.AMOCRM_ALERT_FORWARD_TOPIC_ID

    def setup_handlers(self) -> None:
        """Register handlers on user_client for daily report relay."""
        if not self.user_client:
            logger.info("[AMOCRM_ALERT] user_client is not set — amobot listener skipped.")
            return

        from src.services.core.crm.amobot_daily_report import is_amobot_daily_report, process_amobot_message

        @self.user_client.on(events.NewMessage(incoming=True, from_users=AMOCRM_BOT_USERNAME))
        async def _handle_amocrm_message(event):
            try:
                text = (event.message.text or event.message.message or "").strip()
                if not text:
                    return
                if is_amobot_daily_report(text):
                    logger.info("[AMOCRM_ALERT] Received daily report from @%s", AMOCRM_BOT_USERNAME)
                    await process_amobot_message(text, self.bot_runtime, self.user_client, self.db)
                else:
                    logger.debug("[AMOCRM_ALERT] Ignored non-report DM from @%s", AMOCRM_BOT_USERNAME)
            except Exception as e:
                logger.error("[AMOCRM_ALERT] Message handling error: %s", e)

        logger.info(f"[AMOCRM_ALERT] Listening for @{AMOCRM_BOT_USERNAME} daily reports -> Uzbek forwarder active.")

    async def check_and_relay_daily_report(self) -> bool:
        """Poll amocrm_amobot for today's report if missed."""
        from src.services.core.crm.amobot_daily_report import check_and_relay_amobot_report
        return await check_and_relay_amobot_report(self.user_client, self.bot_runtime, self.db)

    async def _send_overdue_task(self, task: dict[str, Any], subdomain: str, seen_ids: set) -> None:
        """Send a single overdue task alert and record its ID."""
        task_id = task.get("id")
        message, buttons = _format_overdue_task_alert(task, subdomain)
        try:
            await self.bot_runtime.send_message(
                self.group_id, message, message_thread_id=self.topic_id, buttons=buttons,
            )
            seen_ids.add(task_id)
            logger.info(f"[AMOCRM_ALERT] Polled overdue task {task_id} -> group {self.group_id}")
        except Exception as e:
            logger.error(f"[AMOCRM_ALERT] Poll relay failed for task {task_id}: {e}")

    async def poll_overdue_tasks(self) -> None:
        """Userbot-independent fallback: ask AmoCRM's REST API for overdue tasks."""
        if not self.group_id or not self.bot_runtime or not self.amocrm or not self.db:
            return
        try:
            tasks = await self.amocrm.get_tasks(is_completed=False)
        except Exception as e:
            logger.error(f"[AMOCRM_ALERT] Overdue task poll failed: {e}")
            return

        now = int(time.time())
        seen_ids = set(await self.db.get_state(SEEN_OVERDUE_TASKS_KEY, []) or [])
        overdue = [
            t for t in tasks
            if int(t.get("complete_till") or 0) and int(t["complete_till"]) < now and t.get("id") not in seen_ids
        ]
        if not overdue:
            return

        subdomain = settings.AMOCRM_SUBDOMAIN.strip()
        for task in overdue:
            await self._send_overdue_task(task, subdomain, seen_ids)

        trimmed_ids = list(seen_ids)[-MAX_SEEN_TASK_IDS:]
        await self.db.set_state(SEEN_OVERDUE_TASKS_KEY, trimmed_ids)
