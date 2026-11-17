"""Collect recent chat transcripts from managers' dedicated sessions (read-only).

Reuses ``card_watch`` sessions/scanner rules: same dialogs (private chats for
manager sessions, "X | Jon Branding" groups for the owner client), same
prod-session guards. No new logins, nothing is ever sent from these clients.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypeVar

from src.services.core.card_watch.config import Manager
from src.services.core.card_watch.scanner import (
    DEVICE_MODEL,
    MAX_DIALOGS,
    REVOKED_ERRORS,
    SESSION_STATUS,
    _client_name,
    _is_scannable,
    forbidden_sessions,
)

logger = logging.getLogger("SalesCopilot")

MAX_MESSAGES = 40
OWNER_KEY = "owner"
# Non-sales staff (patent expert / PM) whose messages in client groups are "our side".
DEFAULT_STAFF_USERNAMES = ("jonbranding_pm", "hasan_yahyo")

T = TypeVar("T")


@dataclass(frozen=True)
class Msg:
    side: str  # "manager" | "staff" | "client"
    at: datetime
    text: str
    sender_key: str = ""


@dataclass
class Transcript:
    manager_key: str
    chat_id: int
    chat_title: str
    client_name: str
    messages: List[Msg] = field(default_factory=list)  # oldest first

    @property
    def uid(self) -> str:
        if self.chat_id < 0:
            return f"g:{self.chat_id}"
        return f"{self.manager_key}:{self.chat_id}"

    @property
    def last_at(self) -> Optional[datetime]:
        return self.messages[-1].at if self.messages else None


def staff_usernames() -> set[str]:
    raw = os.getenv("SALES_COPILOT_STAFF_USERNAMES", "")
    names = [n.strip().lstrip("@").lower() for n in raw.split(",") if n.strip()]
    return set(names or DEFAULT_STAFF_USERNAMES)


def media_text(msg: Any) -> str:
    """Message text, or a marker for voice/photo/file (real chats are mostly media)."""
    text = (getattr(msg, "message", "") or "").strip()
    if text:
        return text
    if getattr(msg, "voice", None):
        return "[ovozli xabar]"
    if getattr(msg, "photo", None):
        return "[rasm]"
    if getattr(msg, "media", None):
        return "[fayl]"
    return ""


async def _sender_username(msg: Any) -> str:
    try:
        sender = await msg.get_sender()
    except Exception:  # cache miss / network
        return ""
    return (getattr(sender, "username", "") or "").lower()


async def classify_sender(
    msg: Any, owner_mode: bool, managers: Dict[str, str], staff: set[str]
) -> tuple[str, str]:
    """Return (side, manager_key) for one message."""
    if not owner_mode:
        return ("manager", "") if getattr(msg, "out", False) else ("client", "")
    if getattr(msg, "out", False):
        return "staff", OWNER_KEY
    username = await _sender_username(msg)
    if username in managers:
        return "manager", managers[username]
    if username in staff:
        return "staff", ""
    return "client", ""


def dominant_manager(keys: List[str], default: str) -> str:
    counts: Dict[str, int] = {}
    for k in keys:
        if k and k != OWNER_KEY:
            counts[k] = counts.get(k, 0) + 1
    return max(counts, key=lambda k: counts[k]) if counts else default


async def collect_transcripts(
    client: Any,
    manager_key: str,
    since: datetime,
    owner_mode: bool = False,
    username_map: Optional[Dict[str, str]] = None,
    max_messages: int = MAX_MESSAGES,
) -> List[Transcript]:
    """Last ``max_messages`` text messages of every relevant dialog active since ``since``."""
    managers = {k.lower(): v for k, v in (username_map or {}).items()}
    staff = staff_usernames()
    out: List[Transcript] = []
    async for dialog in client.iter_dialogs(limit=MAX_DIALOGS):
        if not _is_scannable(dialog, owner_mode):
            continue
        last = getattr(dialog, "date", None)
        if last and last < since:
            continue
        msgs: List[Msg] = []
        keys: List[str] = []
        async for msg in client.iter_messages(dialog.id, limit=max_messages):
            text = media_text(msg)
            if not text:
                continue
            side, key = await classify_sender(msg, owner_mode, managers, staff)
            keys.append(key)
            msgs.append(Msg(side=side, at=msg.date, text=text[:1000], sender_key=key))
        if not msgs:
            continue
        msgs.reverse()
        owner = dominant_manager(keys, manager_key) if owner_mode else manager_key
        out.append(Transcript(
            manager_key=owner,
            chat_id=int(dialog.id),
            chat_title=getattr(dialog, "name", "") or "",
            client_name=_client_name(dialog),
            messages=msgs,
        ))
    return out


async def with_manager_client(
    manager: Manager, api_id: int, api_hash: str, work: Callable[[Any], Awaitable[T]], default: T
) -> T:
    """Open the manager's dedicated card_watch session, run ``work``, disconnect."""
    if manager.session is None:
        SESSION_STATUS[manager.key] = "missing"
        return default
    from src.services.core.card_watch.vault import SessionVaultError, decrypt

    try:
        secret = decrypt(manager.key, manager.session.get_secret_value())
    except SessionVaultError:
        SESSION_STATUS[manager.key] = "invalid"
        return default
    if secret in forbidden_sessions():
        SESSION_STATUS[manager.key] = "invalid"
        logger.error("[SALES_COPILOT] %s session equals a prod session; skipped", manager.key)
        return default
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    except ImportError:
        return default
    client = TelegramClient(StringSession(secret), api_id, api_hash, device_model=DEVICE_MODEL)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            SESSION_STATUS[manager.key] = "revoked"
            return default
        result = await work(client)
        SESSION_STATUS[manager.key] = "ok"
        return result
    except Exception as exc:  # network/auth errors must not kill the loop
        name = type(exc).__name__
        SESSION_STATUS[manager.key] = "revoked" if name in REVOKED_ERRORS else "error"
        logger.error("[SALES_COPILOT] %s client failed: %s", manager.key, name)
        return default
    finally:
        try:
            await client.disconnect()
        except Exception:  # nosec B110 - best-effort cleanup
            pass
