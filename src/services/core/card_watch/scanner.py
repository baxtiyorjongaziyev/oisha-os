"""Telethon scanning: managers' own sessions + optional in-process owner client.

Each manager uses a DEDICATED StringSession (``CARD_WATCH_SESSION_<KEY>``),
never ``USERBOT_SESSION_STRING`` / ``TELEGRAM_MCP_SESSION_STRING``. The owner's
groups are read through the already-running prod client passed in by the
scheduler, so no second connection of the prod session is ever opened.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from src.services.core.card_watch.config import GROUP_TITLE_MARKER, Manager
from src.services.core.card_watch.detector import CardSend, extract_amount, find_card

logger = logging.getLogger("CardWatch")

MAX_DIALOGS = 300
MAX_MESSAGES_PER_CHAT = 200


def forbidden_sessions() -> set[str]:
    """Prod session strings that a manager slot must never reuse."""
    return {
        v.strip()
        for v in (
            os.getenv("USERBOT_SESSION_STRING", ""),
            os.getenv("TELEGRAM_MCP_SESSION_STRING", ""),
        )
        if v.strip()
    }


def _is_scannable(dialog: Any, owner_mode: bool) -> bool:
    title = (getattr(dialog, "name", "") or "").lower()
    if getattr(dialog, "is_user", False):
        entity = getattr(dialog, "entity", None)
        return not owner_mode and not getattr(entity, "bot", False)
    if getattr(dialog, "is_group", False):
        return GROUP_TITLE_MARKER in title
    return False


async def _sender_key(msg: Any, username_map: Dict[str, str], default: str) -> str:
    """Attribute a group message to a manager by sender username."""
    try:
        sender = await msg.get_sender()
    except Exception:  # cache miss / network: keep default attribution
        return default
    username = (getattr(sender, "username", "") or "").lower()
    return username_map.get(username, default)


def _client_name(dialog: Any) -> str:
    title = getattr(dialog, "name", "") or ""
    if "|" in title:
        return title.split("|", 1)[0].strip()
    return title.strip()


async def scan_client(
    client: Any,
    manager_key: str,
    cards: List[str],
    since: datetime,
    owner_mode: bool = False,
    username_map: Optional[Dict[str, str]] = None,
) -> List[CardSend]:
    """Collect messages with a company card from relevant dialogs.

    Manager mode: only outgoing messages in private chats and "X | Jon Branding"
    groups. Owner mode: only those groups, any sender (a manager posting the card
    in a shared group counts too).
    """
    found: List[CardSend] = []
    async for dialog in client.iter_dialogs(limit=MAX_DIALOGS):
        if not _is_scannable(dialog, owner_mode):
            continue
        last = getattr(dialog, "date", None)
        if last and last < since:
            continue
        async for msg in client.iter_messages(dialog.id, limit=MAX_MESSAGES_PER_CHAT):
            if msg.date < since:
                break
            if not owner_mode and not getattr(msg, "out", False):
                continue
            text = getattr(msg, "message", "") or ""
            card = find_card(text, cards)
            if not card:
                continue
            key = manager_key
            if owner_mode and username_map:
                key = await _sender_key(msg, username_map, manager_key)
            found.append(CardSend(
                manager_key=key,
                chat_id=int(dialog.id),
                chat_title=getattr(dialog, "name", "") or "",
                client_name=_client_name(dialog),
                message_id=int(msg.id),
                sent_at=msg.date,
                amount=extract_amount(text),
                card=card,
            ))
    return found


async def scan_manager(
    manager: Manager, api_id: int, api_hash: str, cards: List[str], lookback_days: int
) -> List[CardSend]:
    """Open the manager's dedicated session, scan, disconnect. Never raises."""
    if manager.session is None:
        return []
    secret = manager.session.get_secret_value()
    if secret in forbidden_sessions():
        logger.error("[CARD_WATCH] %s session equals a prod session; skipped", manager.key)
        return []
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    except ImportError:
        return []
    client: Optional[Any] = TelegramClient(StringSession(secret), api_id, api_hash)
    since = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            logger.warning("[CARD_WATCH] %s session not authorized; re-login needed", manager.key)
            return []
        return await scan_client(client, manager.key, cards, since)
    except Exception as exc:  # network/auth errors must not kill the loop
        logger.error("[CARD_WATCH] scan %s failed: %s", manager.key, type(exc).__name__)
        return []
    finally:
        try:
            await client.disconnect()
        except Exception:  # nosec B110 - best-effort cleanup
            pass
