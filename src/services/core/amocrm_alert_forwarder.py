"""
Forwards AmoCRM overdue-task alerts into the sales team group/topic, two ways:

1. setup_handlers(): relays @amocrm_amobot's reminder DMs to the owner's
   personal Telegram account. Only the userbot session can ever see those
   DMs (amocrm_amobot messages the owner's personal account, not
   @jonairobot), so this path stays hard-dependent on the userbot.

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
    """Pull the "Перейти в amoCRM"-style URL button off the bot's own
    message, if present — a plain text relay would otherwise lose it."""
    markup = getattr(message, "reply_markup", None)
    rows = getattr(markup, "rows", None) or []
    for row in rows:
        for button in getattr(row, "buttons", None) or []:
            if isinstance(button, KeyboardButtonUrl) and button.url:
                return button.url
    return None


class AmoCrmAlertForwarder:
    def __init__(self, user_client: TelegramClient | None, bot_runtime, amocrm=None, db=None):
        self.user_client = user_client
        self.bot_runtime = bot_runtime
        self.amocrm = amocrm
        self.db = db
        self.group_id = settings.AMOCRM_ALERT_FORWARD_GROUP_ID
        self.topic_id = settings.AMOCRM_ALERT_FORWARD_TOPIC_ID

    def setup_handlers(self) -> None:
        if not self.group_id:
            logger.warning(
                "[AMOCRM_ALERT] AMOCRM_ALERT_FORWARD_GROUP_ID sozlanmagan — forwarder o'chirilgan."
            )
            return
        if not self.bot_runtime:
            logger.warning(
                "[AMOCRM_ALERT] bot_runtime mavjud emas — forwarder o'chirilgan."
            )
            return
        if not self.user_client:
            logger.warning(
                "[AMOCRM_ALERT] user_client mavjud emas — forwarder o'chirilgan."
            )
            return

        @self.user_client.on(
            events.NewMessage(
                incoming=True,
                from_users=AMOCRM_BOT_USERNAME,
            )
        )
        async def _relay_amocrm_alert(event):
            try:
                # event.message.text re-renders formatting entities as
                # Telethon's own markdown dialect (** for bold, not Telegram
                # Bot API's single-* Markdown or MarkdownV2 escaping rules),
                # so relaying it with a matching parse_mode would need exact
                # dialect parity we can't guarantee. raw_text is the
                # unformatted original — safe to send as plain text, no
                # literal "**" markers leaking into the relayed message.
                text = (event.message.raw_text or event.message.message or "").strip()
                if not text:
                    return
                crm_url = _extract_crm_url(event.message)
                buttons = [[{"text": "🌐 Перейти в amoCRM", "url": crm_url}]] if crm_url else None

                await self.bot_runtime.send_message(
                    self.group_id,
                    text,
                    message_thread_id=self.topic_id,
                    buttons=buttons,
                )
                logger.info(
                    f"[AMOCRM_ALERT] Relayed alert from @{AMOCRM_BOT_USERNAME} to {self.group_id}"
                    + (" (with CRM link)" if crm_url else " (no CRM link found)")
                )
            except Exception as e:
                logger.error(f"[AMOCRM_ALERT] Relay failed: {e}")

        logger.info(
            f"[AMOCRM_ALERT] Listening for @{AMOCRM_BOT_USERNAME} alerts -> group {self.group_id} "
            f"(via {getattr(self.bot_runtime, 'backend', 'bot_runtime')})"
        )

    async def poll_overdue_tasks(self) -> None:
        """Userbot-independent fallback: ask AmoCRM's REST API for overdue
        tasks directly instead of relaying @amocrm_amobot's private DM, and
        relay newly-overdue ones via bot_runtime. Dedupes across calls via
        the db kv_settings table so a task already alerted isn't repeated
        every autopilot cycle."""
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
            task
            for task in tasks
            if int(task.get("complete_till") or 0)
            and int(task["complete_till"]) < now
            and task.get("id") not in seen_ids
        ]
        if not overdue:
            return

        subdomain = settings.AMOCRM_SUBDOMAIN.strip()
        for task in overdue:
            task_id = task.get("id")
            entity_id = task.get("entity_id")
            entity_type = task.get("entity_type") or "leads"
            text_body = (task.get("text") or "Muddati o'tgan vazifa").strip()
            deadline = datetime.fromtimestamp(int(task["complete_till"]), tz=TASHKENT_TZ)
            message = (
                "⏰ Muddati o'tgan AmoCRM vazifasi\n\n"
                f"{text_body}\n\n"
                f"Muddat: {deadline.strftime('%d.%m.%Y %H:%M')}"
            )
            crm_url = (
                f"https://{subdomain}.amocrm.ru/{entity_type}/detail/{entity_id}"
                if subdomain and entity_id
                else None
            )
            buttons = [[{"text": "🌐 Перейти в amoCRM", "url": crm_url}]] if crm_url else None

            try:
                await self.bot_runtime.send_message(
                    self.group_id,
                    message,
                    message_thread_id=self.topic_id,
                    buttons=buttons,
                )
                seen_ids.add(task_id)
                logger.info(f"[AMOCRM_ALERT] Polled overdue task {task_id} -> group {self.group_id}")
            except Exception as e:
                logger.error(f"[AMOCRM_ALERT] Poll relay failed for task {task_id}: {e}")

        trimmed_ids = list(seen_ids)[-MAX_SEEN_TASK_IDS:]
        await self.db.set_state(SEEN_OVERDUE_TASKS_KEY, trimmed_ids)
