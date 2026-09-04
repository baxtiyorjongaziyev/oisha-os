"""24/7 loop: answer YouTube comments on our recent uploads.

YouTube has no realtime comment webhook, so polling is the only option.
Interval defaults to 5 min (YouTube Data API quota is 10k units/day and a
comment sweep costs a few hundred units).
"""
from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)

_INTERVAL_SEC = int(os.getenv("YT_COMMENT_BACKFILL_INTERVAL_SEC", "300"))
_MAX_VIDEOS = int(os.getenv("YT_COMMENT_BACKFILL_MAX_VIDEOS", "10"))
_MAX_REPLIES = int(os.getenv("YT_COMMENT_BACKFILL_MAX_REPLIES", "20"))
_START_DELAY_SEC = int(os.getenv("YT_COMMENT_BACKFILL_START_DELAY_SEC", "60"))


def _enabled() -> bool:
    return os.getenv("YT_COMMENT_BACKFILL_ENABLED", "1").strip().lower() not in {
        "0", "false", "no", "off",
    }


async def youtube_comment_backfill_loop() -> None:
    if not _enabled():
        logger.info("[YT-BACKFILL] Disabled via YT_COMMENT_BACKFILL_ENABLED")
        return

    from src.services.core.youtube_agent import backfill_youtube_comments

    await asyncio.sleep(_START_DELAY_SEC)
    while True:
        try:
            summary = await backfill_youtube_comments(
                max_videos=_MAX_VIDEOS, max_replies=_MAX_REPLIES, dry_run=False
            )
            if summary.get("ok") and summary.get("answered"):
                logger.info("[YT-BACKFILL] Answered %s comment(s)", summary["answered"])
            elif not summary.get("ok"):
                logger.info("[YT-BACKFILL] Skipped: %s", summary.get("error"))
        except Exception as exc:  # noqa: BLE001
            logger.error("[YT-BACKFILL] Loop error: %s", exc)
        await asyncio.sleep(_INTERVAL_SEC)
