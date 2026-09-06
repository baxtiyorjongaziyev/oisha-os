"""Helper methods for Meta Graph API messaging, likes, and comments."""
from __future__ import annotations

import requests
import structlog

logger = structlog.get_logger("InstagramAPIHelpers")


def send_ig_message_payload(recipient_payload: dict, text: str, access_token: str, log_tag: str) -> bool:
    if not access_token or not recipient_payload:
        logger.warning("[META] %s skipped: access_token or recipient missing", log_tag)
        return False
    url = "https://graph.facebook.com/v19.0/me/messages"
    try:
        resp = requests.post(
            url,
            json={"recipient": recipient_payload, "message": {"text": text}},
            headers={"Content-Type": "application/json"},
            params={"access_token": access_token},
            timeout=15,
        )
        if resp.status_code == 200:
            logger.info("[META] %s sent successfully", log_tag)
            return True
        logger.error("[META] %s failed", log_tag, status_code=resp.status_code, body=resp.text)
    except Exception as exc:
        logger.error("[META] %s exception", log_tag, error=str(exc))
    return False


def like_comment(comment_id: str, access_token: str) -> bool:
    """Likes a comment on Instagram via Graph API."""
    if not access_token:
        logger.warning("[META] PAGE_ACCESS_TOKEN not set, comment like not sent")
        return False

    url = f"https://graph.facebook.com/v19.0/{comment_id}/likes"
    params = {"access_token": access_token}

    try:
        resp = requests.post(url, params=params, timeout=10)
        if resp.status_code == 200:
            logger.info("[META] Comment liked successfully", comment_id=comment_id)
            return True
        logger.error("[META] Failed to like comment", status_code=resp.status_code, body=resp.text)
        return False
    except Exception as exc:
        logger.error("[META] Exception in like_comment", error=str(exc))
        return False


def reply_to_comment(comment_id: str, text: str, access_token: str) -> bool:
    """Replies to a comment on Instagram."""
    if not access_token:
        logger.warning("[META] PAGE_ACCESS_TOKEN not set, comment reply not sent")
        return False

    url = f"https://graph.facebook.com/v19.0/{comment_id}/replies"
    params = {
        "message": text,
        "access_token": access_token,
    }

    try:
        resp = requests.post(url, params=params, timeout=10)
        if resp.status_code == 200:
            logger.info("[META] Comment reply sent successfully", comment_id=comment_id)
            return True
        logger.error("[META] Failed to send comment reply", status_code=resp.status_code, body=resp.text)
        return False
    except Exception as exc:
        logger.error("[META] Exception in reply_to_comment", error=str(exc))
        return False


def fetch_media_caption(media_id: str, access_token: str) -> str:
    """Fetches the caption of the post a comment belongs to (for reply context)."""
    if not media_id or not access_token:
        return ""
    url = f"https://graph.facebook.com/v19.0/{media_id}"
    params = {"fields": "caption", "access_token": access_token}
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("caption", "") or ""
        logger.warning("[META] Failed to fetch media caption", status_code=resp.status_code)
    except Exception as exc:
        logger.error("[META] Exception in fetch_media_caption", error=str(exc))
    return ""
