"""
Forwards @amocrm_amobot reminder/alert messages (overdue tasks, etc.) from the
owner's personal Telegram DM straight into the sales team group/topic.
"""
import logging

from telethon import Button, TelegramClient, events
from telethon.tl.types import KeyboardButtonUrl

from src.settings import settings

logger = logging.getLogger("AmoCrmAlertForwarder")

AMOCRM_BOT_USERNAME = "amocrm_amobot"


def _extract_crm_url(message) -> str | None:
    """Pull the "Перейти в amoCRM"-style URL button off the bot's own
    message, if present — Telethon does not carry reply_markup across a
    plain forward/send_message, so it has to be rebuilt manually."""
    markup = getattr(message, "reply_markup", None)
    rows = getattr(markup, "rows", None) or []
    for row in rows:
        for button in getattr(row, "buttons", None) or []:
            if isinstance(button, KeyboardButtonUrl) and button.url:
                return button.url
    return None


class AmoCrmAlertForwarder:
    def __init__(self, user_client: TelegramClient):
        self.user_client = user_client
        self.group_id = settings.AMOCRM_ALERT_FORWARD_GROUP_ID
        self.topic_id = settings.AMOCRM_ALERT_FORWARD_TOPIC_ID

    def setup_handlers(self) -> None:
        if not self.group_id:
            logger.warning(
                "[AMOCRM_ALERT] AMOCRM_ALERT_FORWARD_GROUP_ID sozlanmagan — forwarder o'chirilgan."
            )
            return

        @self.user_client.on(
            events.NewMessage(
                incoming=True,
                from_users=AMOCRM_BOT_USERNAME,
            )
        )
        async def _forward_amocrm_alert(event):
            try:
                # forward_messages() has no topic/reply_to support; send_message()
                # accepts a Message object (forwards it, keeping the "Forwarded
                # from" header) and does support reply_to for forum topics.
                # It does NOT carry reply_markup across, though — the original
                # "Перейти в amoCRM" button is lost — so rebuild it as a
                # Telethon userbot-compatible Button.url if one was present.
                crm_url = _extract_crm_url(event.message)
                buttons = [[Button.url("🌐 Перейти в amoCRM", crm_url)]] if crm_url else None

                await self.user_client.send_message(
                    entity=self.group_id,
                    message=event.message,
                    reply_to=self.topic_id,
                    buttons=buttons,
                )
                logger.info(
                    f"[AMOCRM_ALERT] Forwarded alert from @{AMOCRM_BOT_USERNAME} to {self.group_id}"
                    + (" (with CRM link)" if crm_url else " (no CRM link found)")
                )
            except Exception as e:
                logger.error(f"[AMOCRM_ALERT] Forward failed: {e}")

        logger.info(
            f"[AMOCRM_ALERT] Listening for @{AMOCRM_BOT_USERNAME} alerts -> group {self.group_id}"
        )
