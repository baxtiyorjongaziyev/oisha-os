"""Webhook lifecycle for the isolated @jonairobot Aiogram head.

This module never accepts or imports a Telethon user session.  Telegram update
delivery, durable duplicate suppression, webhook registration, and shutdown
sit behind the small ``AiogramWebhookHead`` interface.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Any, Iterable, Protocol

logger = logging.getLogger(__name__)


class UpdateReceiptStore(Protocol):
    async def contains(self, update_id: int) -> bool: ...

    async def add(self, update_id: int) -> None: ...


class InMemoryUpdateReceiptStore:
    """Bounded test/local adapter for update receipts."""

    def __init__(self, *, capacity: int = 256) -> None:
        self._capacity = max(1, capacity)
        self._order: deque[int] = deque(maxlen=self._capacity)
        self._ids: set[int] = set()

    async def contains(self, update_id: int) -> bool:
        return update_id in self._ids

    async def add(self, update_id: int) -> None:
        if update_id in self._ids:
            return
        if len(self._order) == self._capacity:
            self._ids.discard(self._order[0])
        self._order.append(update_id)
        self._ids.add(update_id)


class DatabaseUpdateReceiptStore:
    """Persistent adapter backed by Oisha's shared key-value database."""

    def __init__(
        self,
        database: Any,
        *,
        key: str = "telegram:aiogram:webhook:update_receipts",
        capacity: int = 256,
    ) -> None:
        self._database = database
        self._key = key
        self._capacity = max(1, capacity)

    async def _read(self) -> list[int]:
        raw = await self._database.get_state(self._key, [])
        if not isinstance(raw, list):
            return []
        receipts: list[int] = []
        for item in raw[-self._capacity :]:
            try:
                receipts.append(int(item))
            except (TypeError, ValueError):
                continue
        return receipts

    async def contains(self, update_id: int) -> bool:
        return update_id in await self._read()

    async def add(self, update_id: int) -> None:
        receipts = await self._read()
        if update_id not in receipts:
            receipts.append(update_id)
        await self._database.set_state(self._key, receipts[-self._capacity :])


class AiogramWebhookHead:
    """Own @jonairobot webhook ingress without any userbot capability."""

    def __init__(
        self,
        *,
        bot: Any,
        dispatcher: Any,
        receipt_store: UpdateReceiptStore,
        webhook_url: str = "",
        webhook_secret: str,
        allowed_updates: Iterable[str] | None = None,
    ) -> None:
        if webhook_url and not webhook_url.startswith("https://"):
            raise ValueError("Aiogram webhook URL must use HTTPS")
        if not webhook_secret:
            raise ValueError("Aiogram webhook secret is required")
        self.bot = bot
        self.dispatcher = dispatcher
        self.receipt_store = receipt_store
        self.webhook_url = webhook_url
        self.webhook_secret = webhook_secret
        self.allowed_updates = list(allowed_updates or [])
        self._update_lock = asyncio.Lock()
        self._started = False
        self._webhook_registered = False
        self._last_update_id: int | None = None

    @property
    def running(self) -> bool:
        return self._started

    async def start(self) -> None:
        if self._started:
            return
        if self.webhook_url:
            await self.bot.set_webhook(
                url=self.webhook_url,
                secret_token=self.webhook_secret,
                allowed_updates=self.allowed_updates or None,
                drop_pending_updates=False,
            )
            self._webhook_registered = True
        else:
            logger.warning("[BOT] Webhook base URL is not configured yet.")
        self._started = True
        logger.info("[BOT] Aiogram webhook head registered at Telegram.")

    async def receive(self, payload: dict[str, Any]) -> dict[str, Any]:
        update_id = payload.get("update_id")
        if isinstance(update_id, bool) or not isinstance(update_id, int) or update_id < 0:
            raise ValueError("Telegram update_id must be a non-negative integer")

        async with self._update_lock:
            if await self.receipt_store.contains(update_id):
                return {"ok": True, "duplicate": True, "update_id": update_id}
            await self.dispatcher.feed_webhook_update(self.bot, payload)
            await self.receipt_store.add(update_id)
            self._last_update_id = update_id
        return {"ok": True, "duplicate": False, "update_id": update_id}

    def health(self) -> dict[str, Any]:
        return {
            "status": (
                "ok"
                if self._started and self._webhook_registered
                else "degraded" if self._started else "starting"
            ),
            "head": "aiogram_bot_token",
            "ingress": "webhook",
            "userbot_enabled": False,
            "webhook_registered": self._webhook_registered,
            "last_update_id": self._last_update_id,
        }

    async def stop(self) -> None:
        session = getattr(self.bot, "session", None)
        close = getattr(session, "close", None)
        if close is not None:
            await close()
        self._started = False
        self._webhook_registered = False
        logger.info("[BOT] Aiogram webhook head stopped.")
