"""
Forwards @amocrm_amobot reminder/alert messages (overdue tasks, etc.) from the
owner's personal Telegram DM straight into the sales team group/topic.

The userbot session is the only thing that ever sees these DMs (amocrm_amobot
messages the owner's personal account, not @jonairobot), so it stays the
reader. Delivery goes through bot_runtime (the AGENTS.md-mandated migration
target for outbound team-facing messages) instead of a raw Telethon forward,
so the alert lands as a normal @jonairobot message with a working CRM link
button rather than a "forwarded from" copy of a private DM.
"""
import logging

from telethon import TelegramClient, events
from telethon.tl.types import KeyboardButtonUrl

from src.settings import settings

logger = logging.getLogger("AmoCrmAlertForwarder")

AMOCRM_BOT_USERNAME = "amocrm_amobot"


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
    def __init__(self, user_client: TelegramClient, bot_runtime):
        self.user_client = user_client
        self.bot_runtime = bot_runtime
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
