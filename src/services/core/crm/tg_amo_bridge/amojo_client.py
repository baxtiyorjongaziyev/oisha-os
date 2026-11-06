"""Signed amoJo v2 client (custom chat channel).

Request signing: HMAC-SHA1 over
``METHOD\\nContent-MD5\\nContent-Type\\nDate\\nPath`` with the channel secret.
Content-MD5 is protocol metadata, not a security primitive.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import uuid
from email.utils import formatdate
from typing import Any, Optional

import httpx

logger = logging.getLogger("TgAmoBridge.amojo")

AMOJO_BASE = "https://amojo.amocrm.ru"

# amoJo delivery_status values (verify "read" against a live account).
STATUS_DELIVERED = 1
STATUS_READ = 2
STATUS_ERROR = -1

_MEDIA_TYPES = {"picture", "file", "voice", "video"}


def sign_request(secret: str, method: str, path: str, body: bytes, date: Optional[str] = None) -> dict:
    date = date or formatdate(timeval=None, localtime=False, usegmt=True)
    content_type = "application/json"
    md5 = hashlib.md5(body, usedforsecurity=False).hexdigest().lower()
    to_sign = f"{method}\n{md5}\n{content_type}\n{date}\n{path}"
    sig = hmac.new(secret.encode(), to_sign.encode(), hashlib.sha1).hexdigest().lower()
    return {
        "Content-Type": content_type,
        "Date": date,
        "Content-MD5": md5,
        "X-Signature": sig,
    }


class AmoJoClient:
    def __init__(self, amojo_id: str, channel_id: str, channel_secret: str, scope_id: Optional[str] = None):
        self.amojo_id = amojo_id
        self.channel_id = channel_id
        self.channel_secret = channel_secret
        self.scope_id = scope_id

    async def _post(self, path: str, payload: dict) -> Optional[dict]:
        if not self.channel_secret:
            logger.warning("[TG-AMO] channel secret missing")
            return None
        body = json.dumps(payload, separators=(",", ":")).encode()
        headers = sign_request(self.channel_secret, "POST", path, body)
        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                resp = await http.post(f"{AMOJO_BASE}{path}", content=body, headers=headers)
            if resp.status_code >= 400:
                logger.error("[TG-AMO] %s -> %s", path, resp.status_code)
                return None
            return resp.json() if resp.content else {}
        except (httpx.HTTPError, ValueError) as exc:
            logger.error("[TG-AMO] %s failed: %s", path, type(exc).__name__)
            return None

    async def connect(self, title: str = "Oisha Telegram") -> Optional[str]:
        """Connect account to channel; stores and returns scope_id."""
        path = f"/v2/origin/custom/{self.channel_id}/connect"
        data = await self._post(
            path,
            {"account_id": self.amojo_id, "title": title, "hook_api_version": "v2"},
        )
        scope_id = (data or {}).get("scope_id")
        if scope_id:
            self.scope_id = scope_id
        return scope_id

    def build_message_event(
        self,
        *,
        conversation_id: str,
        sender_id: str,
        sender_name: str,
        text: str = "",
        msg_id: Optional[str] = None,
        phone: Optional[str] = None,
        media_type: Optional[str] = None,
        media_url: Optional[str] = None,
        file_name: Optional[str] = None,
        file_size: Optional[int] = None,
        source_external_id: Optional[str] = None,
        silent: bool = False,
        is_manager: bool = False,
    ) -> dict:
        """Build a new_message event.

        is_manager=True: message was written by the manager in Telegram; the
        client is moved to the receiver side so amoCRM shows it as outgoing.
        """
        now = time.time()
        message: dict[str, Any] = {"type": "text", "text": text}
        if media_type:
            if media_type not in _MEDIA_TYPES:
                raise ValueError(f"unsupported media_type {media_type}")
            message = {"type": media_type, "media": media_url}
            if text:
                message["text"] = text
            if file_name:
                message["file_name"] = file_name
            if file_size is not None:
                message["file_size"] = file_size
        sender: dict[str, Any] = {"id": sender_id, "name": sender_name}
        if phone:
            sender["profile"] = {"phone": phone}
        payload: dict[str, Any] = {
            "timestamp": int(now),
            "msec_timestamp": int(now * 1000),
            "msgid": msg_id or str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "sender": sender,
            "message": message,
            "silent": silent,
        }
        if source_external_id:
            payload["source"] = {"external_id": source_external_id}
        if is_manager:
            payload["receiver"] = payload.pop("sender")
        return {"event_type": "new_message", "payload": payload}

    async def send_event(self, event: dict) -> Optional[dict]:
        if not self.scope_id:
            logger.warning("[TG-AMO] scope_id missing; call connect() first")
            return None
        return await self._post(f"/v2/origin/custom/{self.scope_id}", {"account_id": self.amojo_id, **event})

    async def send_status(self, msg_id: str, status: int, error: str = "") -> bool:
        if not self.scope_id:
            return False
        payload: dict[str, Any] = {"msgid": msg_id, "delivery_status": status}
        if status == STATUS_ERROR:
            payload["error_code"] = 901
            payload["error"] = error or "delivery failed"
        path = f"/v2/origin/custom/{self.scope_id}/{msg_id}/delivery_status"
        return await self._post(path, payload) is not None
