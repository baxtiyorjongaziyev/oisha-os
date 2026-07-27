"""Lifecycle for Oisha's bot-token head.

The user-account head remains a separate Telethon client.  This module owns
only @jonairobot's Aiogram polling lifecycle and never receives a user session.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Iterable, Optional

logger = logging.getLogger(__name__)


class AiogramBotHead:
    def __init__(
        self,
        *,
        bot: Any,
        dispatcher: Any,
        allowed_updates: Optional[Iterable[str]] = None,
        raw_update_handler: Optional[
            Callable[[dict[str, Any]], Awaitable[Any]]
        ] = None,
    ):
        self.bot = bot
        self.dispatcher = dispatcher
        self.allowed_updates = list(allowed_updates or [])
        self.raw_update_handler = raw_update_handler
        self._polling_task: Optional[asyncio.Task] = None
        if raw_update_handler is not None:
            self._register_raw_update_middleware()

    def _register_raw_update_middleware(self) -> None:
        raw_update_handler = self.raw_update_handler

        async def _raw_update_middleware(handler, event, data):
            payload = event.model_dump(exclude_none=True)
            if "guest_message" in payload:
                return await raw_update_handler(payload)
            return await handler(event, data)

        self.dispatcher.update.outer_middleware.register(_raw_update_middleware)

    @property
    def running(self) -> bool:
        return self._polling_task is not None and not self._polling_task.done()

    def start(self) -> asyncio.Task:
        if self.running:
            return self._polling_task  # type: ignore[return-value]
        self._polling_task = asyncio.create_task(
            self.dispatcher.start_polling(
                self.bot,
                handle_signals=False,
                close_bot_session=False,
                allowed_updates=self.allowed_updates or None,
            ),
            name="aiogram_bot_head_polling",
        )
        logger.info("[BOT] Aiogram bot-token head polling started.")
        return self._polling_task

    async def stop(self) -> None:
        if self.running:
            await self.dispatcher.stop_polling()
        if self._polling_task is not None:
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            self._polling_task = None
        session = getattr(self.bot, "session", None)
        close = getattr(session, "close", None)
        if close is not None:
            await close()
        logger.info("[BOT] Aiogram bot-token head stopped.")
