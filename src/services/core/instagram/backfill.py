"""Instagram comments backfill operations."""
from __future__ import annotations

import re
import requests
import structlog

from src.settings import settings
from src.services.core.instagram.graph_client import InstagramGraphClient

logger = structlog.get_logger("InstagramBackfill")


def _fetch_comment_replies(comment_id: str, access_token: str) -> list:
    """Returns the reply objects on a comment (id, text, from)."""
    url = f"https://graph.facebook.com/v19.0/{comment_id}/replies"
    params = {"fields": "id,text,from,timestamp", "access_token": access_token}
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json().get("data", []) or []
        logger.warning("[META] Failed to fetch comment replies", status_code=resp.status_code)
    except Exception as exc:
        logger.error("[META] Exception in _fetch_comment_replies", error=str(exc))
    return []


def _fetch_media_comments(media_id: str, access_token: str) -> list:
    """Returns top-level comments on a post, following pagination."""
    url = f"https://graph.facebook.com/v19.0/{media_id}/comments"
    params = {
        "fields": "id,text,from,timestamp,like_count,replies{id,from,text}",
        "limit": 50,
        "access_token": access_token,
    }
    out: list = []
    try:
        while url:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code != 200:
                logger.warning("[META] Failed to fetch media comments", status_code=resp.status_code)
                break
            body = resp.json()
            out.extend(body.get("data", []) or [])
            url = (body.get("paging") or {}).get("next", "")
            params = {}
    except Exception as exc:
        logger.error("[META] Exception in _fetch_media_comments", error=str(exc))
    return out


async def backfill_unanswered_comments(
    db=None,
    *,
    media_limit: int = 15,
    max_replies: int = 200,
    dry_run: bool = False,
    generate_reply_fn=None,
    like_comment_fn=None,
    reply_to_comment_fn=None,
) -> dict:
    """Scan recent posts, find comments with no reply from us, like + reply to them."""
    client = InstagramGraphClient()
    if not getattr(client, "configured", False):
        return {"ok": False, "error": "instagram_not_configured"}

    token = client.access_token
    own_id = str(
        getattr(client, "instagram_account_id", "")
        or getattr(settings, "META_INSTAGRAM_USER_ID", "")
        or ""
    )
    summary = {
        "scanned_media": 0,
        "scanned_comments": 0,
        "answered": 0,
        "skipped": 0,
        "errors": 0,
        "dry_run": dry_run,
    }

    media_res = client.list_media(limit=media_limit)
    if not media_res.get("ok"):
        return {"ok": False, "error": media_res.get("error", "media_fetch_failed")}

    for media in media_res.get("data", []):
        media_id = str(media.get("id") or "")
        if not media_id:
            continue
        summary["scanned_media"] += 1
        caption = media.get("caption", "") or ""

        for comment in _fetch_media_comments(media_id, token):
            if summary["answered"] >= max_replies:
                logger.info("[META] Backfill hit max_replies cap", cap=max_replies)
                return {"ok": True, **summary}

            comment_id = str(comment.get("id") or "")
            text = (comment.get("text") or "").strip()
            frm = comment.get("from") or {}
            commenter_id = str(frm.get("id") or "")
            commenter_name = frm.get("username") or frm.get("name") or "Foydalanuvchi"

            if not comment_id or not text:
                continue
            summary["scanned_comments"] += 1

            if own_id and commenter_id == own_id:
                summary["skipped"] += 1
                continue

            replies_data = (comment.get("replies") or {}).get("data")
            if replies_data is not None:
                replies = replies_data
            else:
                replies = _fetch_comment_replies(comment_id, token)

            already = any(
                (r.get("from") or {}).get("id") == own_id
                or (r.get("from") or {}).get("username") == "baxtiyorjongaziyev"
                for r in replies
            )
            if already:
                summary["skipped"] += 1
                continue

            if dry_run:
                logger.info(
                    "[META] Backfill would answer",
                    comment_id=comment_id,
                    commenter=commenter_name,
                    text=text[:60],
                )
                summary["answered"] += 1
                continue

            try:
                if generate_reply_fn:
                    ai_reply = await generate_reply_fn(text, caption, commenter_name)
                else:
                    from src.services.core.instagram_agent import generate_comment_reply
                    ai_reply = await generate_comment_reply(text, caption, commenter_name)
                clean = re.sub(r"\[.*?\]", "", ai_reply).strip()
                if reply_to_comment_fn:
                    ok = reply_to_comment_fn(comment_id, clean, token)
                else:
                    from src.services.core.instagram_agent import reply_to_comment
                    ok = reply_to_comment(comment_id, clean, token)
                if ok:
                    summary["answered"] += 1
                    if db:
                        user_id_str = f"ig_comment_{commenter_id}"
                        await db.log_message(user_id_str, f"COMMENT: {text}", is_ai=False)
                        await db.log_message(user_id_str, clean, is_ai=True)

                    from src.services.core.instagram.lead_qualifier import (
                        should_trigger_dm,
                        generate_initial_dm_message,
                    )
                    is_trig, kw = should_trigger_dm(text, caption)
                    if is_trig:
                        from src.services.core.instagram_agent import send_ig_private_reply
                        initial_dm = generate_initial_dm_message(commenter_name, kw, caption)
                        send_ig_private_reply(comment_id, initial_dm, token)
                        if db:
                            dm_uid = f"ig_{commenter_id}"
                            await db.log_message(dm_uid, initial_dm, is_ai=True)
                else:
                    summary["errors"] += 1
            except Exception as exc:
                logger.error("[META] Backfill reply failed", comment_id=comment_id, error=str(exc))
                summary["errors"] += 1

    logger.info("[META] Backfill complete", **summary)
    return {"ok": True, **summary}
