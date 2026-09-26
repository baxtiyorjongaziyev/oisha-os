"""FloodWaitError'ni tutib, kerak bo'lsa kutib qayta yuboradigan wrapper.

Telethon ``flood_sleep_threshold`` (default 60s) dan past kutishlarni o'zi
avtomatik yutadi, lekin undan uzunroq flood-wait chaqiruvchi kodga
``FloodWaitError`` sifatida chiqadi va ushlanmasa xabar yuborilmay qoladi.
Bu ayniqsa broadcast/bridge kabi ko'p xabar yuboradigan yo'llarda muhim.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, TypeVar

from telethon.errors import FloodWaitError

logger = logging.getLogger("SafeSend")

T = TypeVar("T")


async def safe_send(
    send_coro_factory: Callable[[], Awaitable[T]],
    *,
    max_retries: int = 2,
    context: str = "",
) -> T | None:
    """``send_coro_factory()`` ni chaqiradi, FloodWaitError kelsa kutib qayta uradi.

    ``send_coro_factory`` — parametrsiz callable, chaqirilganda yuborish
    coroutine'ini qaytaradi (retry uchun har safar YANGI coroutine kerak,
    Telethon corolarni qayta ishlatishga ruxsat bermaydi).
    """
    attempt = 0
    while True:
        try:
            return await send_coro_factory()
        except FloodWaitError as e:
            attempt += 1
            wait_s = int(getattr(e, "seconds", 0) or 0)
            if attempt > max_retries:
                logger.error(
                    "[SAFE_SEND] FloodWait %ss, retries tugadi (%s): %s",
                    wait_s, context, e,
                )
                return None
            logger.warning(
                "[SAFE_SEND] FloodWait %ss, kutilmoqda (%d/%d) [%s]",
                wait_s, attempt, max_retries, context,
            )
            await asyncio.sleep(wait_s + 1)
        except Exception as exc:
            logger.error("[SAFE_SEND] Yuborishda xato (%s): %s", context, exc, exc_info=True)
            return None
