"""Case publisher handler for @jonbranding channel."""
from __future__ import annotations

import logging
import asyncio

from src.settings import settings

logger = logging.getLogger(__name__)


async def case_publisher_handler(event):
    """Listen to @jonbranding channel messages and process/publish design cases."""
    if not settings.ENABLE_CASE_PUBLISHER:
        return

    try:
        chat = await event.get_chat()
        chat_username = getattr(chat, "username", None)
        chat_id = event.chat_id

        target = settings.JONBRANDING_CHANNEL.strip().lower()

        is_match = False
        if chat_username and chat_username.lower() == target:
            is_match = True
        elif target.startswith("-100") and str(chat_id) == target:
            is_match = True
        elif str(chat_id) == target:
            is_match = True

        if not is_match:
            return

        logger.info(
            f"[CASE_HANDLER] New message in target channel '{target}': msg_id={event.id}"
        )

        from src.services.core.case_publisher import CasePublisher
        publisher = CasePublisher(client=event.client)
        asyncio.create_task(publisher.process_message(event.message))

    except Exception as e:
        logger.error(f"[CASE_HANDLER] Error in handler: {e}")
