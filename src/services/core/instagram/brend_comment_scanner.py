"""
Scanner and processor for Instagram comments on the target Brend/Patent video.
Enforces deduplication, user-level contact limits, rate-limiting, and resumption.
"""
from __future__ import annotations

import asyncio
import os
import random
from typing import Any, Dict, List, Optional
import structlog

from src.settings import settings
from src.services.core.instagram.agent_constants import (
    TARGET_BREND_VIDEO_SHORTCODE,
    BREND_COMMENT_DM_TEMPLATE,
    get_public_ack_for_comment,
)
from src.services.core.instagram.api_helpers import (
    send_ig_private_reply,
    like_comment,
    reply_to_comment,
)
from src.services.core.instagram.backfill import _fetch_media_comments
from src.services.core.instagram.brend_lead_flow import is_brend_keyword
from src.services.core.instagram.comment_store import InstagramCommentStore
from src.services.core.instagram.graph_client import InstagramGraphClient

logger = structlog.get_logger("BrendCommentScanner")

DEFAULT_BREND_MEDIA_ID = "18022341710945202"


def _is_own_account(from_obj: Optional[Dict[str, Any]], own_id: str) -> bool:
    """Detects if the comment author is our own account (loop prevention)."""
    if not from_obj:
        # Meta Graph API omits the 'from' field on comments made by the media owner
        return True
    commenter_id = str(from_obj.get("id") or "")
    if own_id and commenter_id and commenter_id == own_id:
        return True
    uname = (from_obj.get("username") or from_obj.get("name") or "").strip().lower().lstrip("@")
    return uname in ("baxtiyorjongaziyev", "jonbranding")


def _has_existing_reply(comment: Dict[str, Any], own_id: str) -> bool:
    """Checks if we already posted a public reply under this comment on Instagram."""
    replies = (comment.get("replies") or {}).get("data") or []
    for r in replies:
        from_obj = r.get("from") or {}
        fid = str(from_obj.get("id") or "")
        fuser = (r.get("username") or from_obj.get("username") or "").strip().lower()
        if (own_id and fid == own_id) or fuser in ("baxtiyorjongaziyev", "jonbranding"):
            return True
    return False


def _check_comment_eligibility(
    comment: Dict[str, Any],
    frm: Any,
    own_id: str,
    cid: str,
    media_id: str,
    user_id: str,
    username: str,
    text: str,
    store: InstagramCommentStore,
) -> Optional[str]:
    """Returns status outcome if comment should be skipped, else None."""
    if _is_own_account(frm, own_id):
        store.record_skipped(cid, media_id, "", "own_account", text, "own")
        return "skipped_own"
    if store.is_comment_processed(cid):
        return "already_processed"
    if _has_existing_reply(comment, own_id):
        store.record_skipped(cid, media_id, user_id, username, text, "already_replied")
        return "skipped_already_replied"
    if not is_brend_keyword(text):
        store.record_skipped(cid, media_id, user_id, username, text, "no_keyword")
        return "skipped_no_keyword"
    if store.has_user_received_dm(user_id, username, media_id):
        store.record_skipped(cid, media_id, user_id, username, text, "duplicate_user")
        return "skipped_duplicate_user"
    return None


async def _process_single_brend_comment(
    comment: Dict[str, Any],
    media_id: str,
    own_id: str,
    access_token: str,
    store: InstagramCommentStore,
    db: Any = None,
    dry_run: bool = False,
    notify_crm_fn: Any = None,
) -> str:
    """Processes one comment: validation -> deduplication -> outreach -> persistence."""
    cid = str(comment.get("id") or "")
    text = (comment.get("text") or "").strip()
    frm = comment.get("from")
    if not cid or not text:
        return "empty"

    user_id = str((frm or {}).get("id") or "")
    username = (frm or {}).get("username") or (frm or {}).get("name") or "Foydalanuvchi"

    skipped = _check_comment_eligibility(comment, frm, own_id, cid, media_id, user_id, username, text, store)
    if skipped:
        return skipped

    if dry_run:
        logger.info("[BREND-SCANNER] Dry run match", comment_id=cid, user=username, text=text)
        return "dry_run_matched"

    if not store.claim_comment(cid, media_id, user_id, username, text, "brend"):
        return "already_claimed"

    return await _execute_brend_outreach(
        cid=cid, media_id=media_id, user_id=user_id, username=username,
        text=text, access_token=access_token, store=store, db=db, notify_crm_fn=notify_crm_fn,
    )


async def _execute_brend_outreach(
    cid: str,
    media_id: str,
    user_id: str,
    username: str,
    text: str,
    access_token: str,
    store: InstagramCommentStore,
    db: Any = None,
    notify_crm_fn: Any = None,
) -> str:
    """Executes like, private DM, public ack reply, CRM notification, and logs."""
    like_comment(cid, access_token)

    # 1. Private DM opener
    dm_sent = send_ig_private_reply(cid, BREND_COMMENT_DM_TEMPLATE, access_token)
    if not dm_sent:
        store.record_failure(cid, "private_dm_failed")
        return "dm_failed"

    # 2. Public acknowledgment
    public_ack = get_public_ack_for_comment(text)
    reply_to_comment(cid, public_ack, access_token)

    # 3. Durable persistence
    store.record_dm_success(
        comment_id=cid,
        media_id=media_id,
        user_id=user_id,
        username=username,
        dm_text=BREND_COMMENT_DM_TEMPLATE,
        public_reply_text=public_ack,
    )

    # 4. Optional db message history logging
    if db:
        user_id_str = f"ig_{user_id or username}"
        await db.log_message(user_id_str, f"COMMENT: {text}", is_ai=False)
        await db.log_message(user_id_str, BREND_COMMENT_DM_TEMPLATE, is_ai=True)

    # 5. CRM group alert
    if notify_crm_fn:
        try:
            notify_crm_fn(
                source="Instagram Brend Scanner",
                user_name=username,
                user_id=user_id or username,
                message=text,
                reply=BREND_COMMENT_DM_TEMPLATE,
            )
        except Exception as exc:
            logger.warning("[BREND-SCANNER] CRM notify failed: %s", exc)

    return "dm_sent"


async def _iterate_comment_batch(
    raw_comments: List[Dict[str, Any]],
    media_id: str,
    own_id: str,
    token: str,
    store: InstagramCommentStore,
    db: Any,
    dry_run: bool,
    notify_crm_fn: Any,
    max_dms: int,
    throttle_seconds: float,
    summary: Dict[str, Any],
) -> tuple[str, str]:
    last_cid = ""
    last_ts = ""
    for comment in raw_comments:
        if summary["dms_sent"] >= max_dms:
            logger.info("[BREND-SCANNER] Hit max_dms batch limit", limit=max_dms)
            break
        cid = str(comment.get("id") or "")
        ts = str(comment.get("timestamp") or "")
        outcome = await _process_single_brend_comment(
            comment=comment, media_id=media_id, own_id=own_id, access_token=token,
            store=store, db=db, dry_run=dry_run, notify_crm_fn=notify_crm_fn,
        )
        last_cid = cid or last_cid
        last_ts = ts or last_ts
        if outcome in summary:
            summary[outcome] += 1
        elif outcome == "dm_sent":
            summary["dms_sent"] += 1
            await asyncio.sleep(throttle_seconds + random.uniform(0.5, 1.5))
        elif outcome == "dm_failed":
            summary["dms_failed"] += 1
    return last_cid, last_ts


async def scan_and_process_brend_comments(
    media_id: str = DEFAULT_BREND_MEDIA_ID,
    access_token: Optional[str] = None,
    store: Optional[InstagramCommentStore] = None,
    db: Any = None,
    dry_run: bool = False,
    throttle_seconds: float = 3.5,
    max_dms: int = 25,
    notify_crm_fn: Any = None,
) -> Dict[str, Any]:
    """Main entry point: scans comments on the target video and reaches out to leads."""
    client = InstagramGraphClient()
    token = access_token or client.access_token
    if not token:
        return {"ok": False, "error": "access_token_missing"}

    own_id = str(getattr(client, "instagram_account_id", "") or getattr(settings, "META_INSTAGRAM_USER_ID", "") or "")
    store = store or InstagramCommentStore()
    if notify_crm_fn is None:
        try:
            from src.services.core.instagram_agent import notify_crm
            notify_crm_fn = notify_crm
        except Exception:
            notify_crm_fn = None

    raw_comments = await asyncio.to_thread(_fetch_media_comments, media_id, token)
    summary: Dict[str, Any] = {
        "ok": True, "media_id": media_id, "total_comments_fetched": len(raw_comments),
        "dms_sent": 0, "dms_failed": 0, "skipped_own": 0, "skipped_already_replied": 0,
        "skipped_no_keyword": 0, "skipped_duplicate_user": 0, "already_processed": 0, "dry_run": dry_run,
    }

    last_cid, last_ts = await _iterate_comment_batch(
        raw_comments=raw_comments, media_id=media_id, own_id=own_id, token=token,
        store=store, db=db, dry_run=dry_run, notify_crm_fn=notify_crm_fn,
        max_dms=max_dms, throttle_seconds=throttle_seconds, summary=summary,
    )

    store.update_checkpoint(media_id, last_cid, last_ts, len(raw_comments), summary["dms_sent"])
    logger.info("[BREND-SCANNER] Scan complete", scanned=len(raw_comments), dms_sent=summary["dms_sent"])
    return summary
