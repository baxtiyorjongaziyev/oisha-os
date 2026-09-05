"""24/7 safety-net loop: answer Instagram comments the webhook missed.

The real-time path is `process_instagram_webhook` (comments answered as they
arrive). This loop is a backstop for comments that slipped through while the
server was down, the webhook delivery failed, or a comment predated the
subscription. It scans recent posts on an interval and likes + replies to any
comment that has no reply authored by our own IG account yet.
"""
from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)

# Env knobs (all optional; ultra-fast 20s default)
_INTERVAL_SEC = int(os.getenv("IG_COMMENT_BACKFILL_INTERVAL_SEC", "20"))  # 20 sec
_MEDIA_LIMIT = int(os.getenv("IG_COMMENT_BACKFILL_MEDIA_LIMIT", "15"))
_MAX_REPLIES = int(os.getenv("IG_COMMENT_BACKFILL_MAX_REPLIES", "25"))
_START_DELAY_SEC = int(os.getenv("IG_COMMENT_BACKFILL_START_DELAY_SEC", "2"))


def _enabled() -> bool:
    # On by default; set IG_COMMENT_BACKFILL_ENABLED=0 to turn it off.
    return os.getenv("IG_COMMENT_BACKFILL_ENABLED", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


async def instagram_comment_backfill_loop(db=None) -> None:
    if not _enabled():
        logger.info("[IG-BACKFILL] Disabled via IG_COMMENT_BACKFILL_ENABLED")
        return

    from src.services.core.instagram_agent import backfill_unanswered_comments

    await asyncio.sleep(_START_DELAY_SEC)
    while True:
        try:
            summary = await backfill_unanswered_comments(
                db,
                media_limit=_MEDIA_LIMIT,
                max_replies=_MAX_REPLIES,
                dry_run=False,
            )
            if summary.get("ok"):
                if summary.get("answered"):
                    logger.info(
                        "[IG-BACKFILL] Answered %s comment(s) (scanned %s across %s post(s))",
                        summary["answered"],
                        summary.get("scanned_comments", 0),
                        summary.get("scanned_media", 0),
                    )
            else:
                logger.info("[IG-BACKFILL] Skipped: %s", summary.get("error"))
        except Exception as exc:
            logger.error("[IG-BACKFILL] Loop error: %s", exc)
        await asyncio.sleep(_INTERVAL_SEC)
