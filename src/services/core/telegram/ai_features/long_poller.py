"""
TelegramBotAPILongPoller concurrent update polling and worker pipeline.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional

from src.services.core.telegram.ai_features.bot_api_client import (
    TelegramBotAPI10Client,
)
from src.services.core.telegram.ai_features.models import (
    BOT_API_10_ALLOWED_UPDATES,
    BotApiUpdateHandler,
    classify_update,
    extract_guest_message_context,
)

logger = logging.getLogger("TelegramBotAPILongPoller")

class TelegramBotAPILongPoller:
    """Receive Bot API-only updates when a public HTTPS webhook is unavailable."""

    SPECIAL_UPDATE_TYPES = {
        "guest_message",
        "business_connection",
        "business_message",
        "edited_business_message",
        "deleted_business_messages",
        "managed_bot",
    }

    def __init__(
        self,
        token: str,
        update_handler: BotApiUpdateHandler,
        *,
        timeout: int = 25,
        retry_delay: float = 3.0,
        worker_count: int = 2,
        max_pending_updates: int = 1000,
        client: Optional[TelegramBotAPI10Client] = None,
    ):
        self.client = client or TelegramBotAPI10Client(
            token,
            timeout=float(timeout + 10),
        )
        self.update_handler = update_handler
        self.timeout = timeout
        self.retry_delay = retry_delay
        self.worker_count = max(1, worker_count)
        self.max_pending_updates = max(1, max_pending_updates)
        self.offset: Optional[int] = None
        self._stopped = False
        self._queue: Optional[asyncio.Queue[Dict[str, Any]]] = None
        self._workers: List[asyncio.Task[Any]] = []

    def stop(self) -> None:
        self._stopped = True

    async def _dispatch_update(self, update: Dict[str, Any]) -> None:
        try:
            await self.update_handler(update)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "[TELEGRAM AI] update handler error=%s; continuing.",
                type(exc).__name__,
            )

    async def _worker(self) -> None:
        assert self._queue is not None
        while not self._stopped:
            update = await self._queue.get()
            try:
                await self._dispatch_update(update)
            finally:
                self._queue.task_done()

    def _start_workers(self) -> None:
        if self._queue is not None:
            return
        self._queue = asyncio.Queue(maxsize=self.max_pending_updates)
        self._workers = [
            asyncio.create_task(self._worker())
            for _ in range(self.worker_count)
        ]

    async def _stop_workers(self) -> None:
        workers, self._workers = self._workers, []
        for worker in workers:
            worker.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
        self._queue = None

    async def poll_once(self) -> Dict[str, int]:
        """Consume one batch and dispatch updates that need the raw Bot API path."""
        updates = await self.client.get_updates(
            offset=self.offset,
            timeout=self.timeout,
            allowed_updates=BOT_API_10_ALLOWED_UPDATES,
        )
        dispatched = 0
        for update in updates:
            if not isinstance(update, dict):
                continue
            update_id = int(update.get("update_id") or 0)
            self.offset = max(self.offset or 0, update_id + 1)
            if classify_update(update) not in self.SPECIAL_UPDATE_TYPES:
                continue
            if self._queue is None:
                await self._dispatch_update(update)
            else:
                await self._queue.put(update)
            dispatched += 1
        return {"received": len(updates), "dispatched": dispatched}

    async def run(self) -> None:
        webhook_cleared = False
        self._start_workers()
        try:
            while not self._stopped:
                try:
                    if not webhook_cleared:
                        await self.client.delete_webhook(drop_pending_updates=False)
                        webhook_cleared = True
                        logger.info("[TELEGRAM AI] Bot API long-poll receiver started.")
                    stats = await self.poll_once()
                    if stats["received"]:
                        logger.info(
                            "[TELEGRAM AI] long-poll received=%s queued=%s pending=%s",
                            stats["received"],
                            stats["dispatched"],
                            self._queue.qsize() if self._queue is not None else 0,
                        )
                except asyncio.CancelledError:
                    raise
                except TelegramBotAPIError as exc:
                    retry_after = int(exc.parameters.get("retry_after") or 0)
                    logger.warning(
                        "[TELEGRAM AI] long-poll Bot API error method=%s code=%s; retrying.",
                        exc.method,
                        exc.error_code,
                    )
                    await asyncio.sleep(max(self.retry_delay, retry_after))
                except Exception as exc:
                    logger.warning(
                        "[TELEGRAM AI] long-poll transport error=%s; retrying.",
                        type(exc).__name__,
                    )
                    await asyncio.sleep(self.retry_delay)
        finally:
            await self._stop_workers()
