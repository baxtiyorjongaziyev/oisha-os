"""
Assistant reminder for unattended owner DMs.

If a private human message to the owner (Baxtiyorjon Gaziyev) remains
unanswered by both the owner and the business assistant Shahnoza
(@jonbranding_assistant) after the configured delay, remind Shahnoza in
the team group by mentioning her username.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Optional

from src.settings import settings
from src.time_utils import get_local_now

logger = logging.getLogger("DelayedDmAssistantReminder")

# Shahnoza's identifiers (mirrors telegram_assistant_advisor.SHAHNOZA_* to avoid
# a hard import coupling between the two modules).
SHAHNOZA_USER_ID = 8802892610
SHAHNOZA_USERNAME = "jonbranding_assistant"
OWNER_USER_ID = 150074828
REMINDER_COOLDOWN_SECS = 43200  # 12 hours cooldown per chat

_IS_SCHEDULED: set[int] = set()


def is_assistant_reminder_enabled() -> bool:
    """Check if the assistant reminder feature is enabled."""
    return os.getenv("ENABLE_ASSISTANT_DM_REMINDER", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def get_delay_minutes() -> int:
    """Return configured delay in minutes (same source as delayed DM auto-reply)."""
    try:
        return int(os.getenv("DM_UNANSWERED_DELAY_MINUTES", "15"))
    except ValueError:
        return 15


def get_team_group_id() -> Optional[int]:
    """Return the configured team group ID, if any."""
    return getattr(settings, "TEAM_GROUP_ID", None)


async def _recent_outgoing_from(
    client: Any, chat_id: int, user_id: int, since_ts: float
) -> bool:
    """Return True if `user_id` sent an outgoing message in `chat_id` after `since_ts`."""
    try:
        messages = await client.get_messages(chat_id, limit=20)
    except Exception as exc:
        logger.warning("[ASSISTANT REMINDER] Cannot read history for %s: %s", chat_id, exc)
        return False
    for m in messages or []:
        if not getattr(m, "out", False):
            continue
        from_id = getattr(m, "from_id", None)
        msg_user_id = getattr(from_id, "user_id", None) if from_id else None
        if msg_user_id != user_id:
            continue
        m_date = getattr(m, "date", None)
        m_ts = m_date.timestamp() if m_date else 0.0
        if m_ts >= since_ts - 5.0:
            return True
    return False


async def schedule_assistant_reminder(event: Any, *, client: Any) -> None:
    """Schedule a group reminder to Shahnoza if the owner DM stays unanswered.

    Called once per incoming private DM. The actual reminder is sent only after
    the configured delay elapses without a reply from the owner or Shahnoza.
    """
    if not is_assistant_reminder_enabled():
        return
    chat_id = getattr(event, "chat_id", None)
    if not chat_id or not getattr(event, "is_private", False) or getattr(event, "out", False):
        return
    if chat_id < 0 or chat_id in _IS_SCHEDULED:
        return
    sender = await event.get_sender()
    if not sender or getattr(sender, "bot", False):
        return
    sender_id = getattr(sender, "id", None)
    if sender_id == SHAHNOZA_USER_ID:
        return

    delay_minutes = get_delay_minutes()
    _IS_SCHEDULED.add(chat_id)
    sender_name = getattr(sender, "first_name", "Mijoz") or "Mijoz"
    asyncio.create_task(
        _wait_and_remind(client, chat_id, sender_name, delay_minutes)
    )


async def _wait_and_remind(
    client: Any, chat_id: int, sender_name: str, delay_minutes: int
) -> None:
    """Wait the delay, re-verify no reply, then send the group reminder."""
    try:
        await _wait_and_remind_inner(client, chat_id, sender_name, delay_minutes)
    finally:
        # Aks holda chat bir marta eslatilgach qayta eslatma bo'lmaydi (restartgacha).
        _IS_SCHEDULED.discard(chat_id)


async def _wait_and_remind_inner(
    client: Any, chat_id: int, sender_name: str, delay_minutes: int
) -> None:
    try:
        await asyncio.sleep(delay_minutes * 60)
    except asyncio.CancelledError:
        return

    now_ts = get_local_now().timestamp()
    since_ts = now_ts - delay_minutes * 60

    owner_replied = await _recent_outgoing_from(client, chat_id, OWNER_USER_ID, since_ts)
    assistant_replied = await _recent_outgoing_from(
        client, chat_id, SHAHNOZA_USER_ID, since_ts
    )
    if owner_replied or assistant_replied:
        logger.info("[ASSISTANT REMINDER] Chat %s already answered; skipping", chat_id)
        return

    group_id = get_team_group_id()
    if not group_id:
        logger.warning("[ASSISTANT REMINDER] TEAM_GROUP_ID is not configured")
        return

    text = (
        f"🔔 <b>Shahnoza, shaxsiy DM eslatmasi</b>\n\n"
        f"{sender_name} Baxtiyorjonning shaxsiy xabariga {delay_minutes} daqiqadan beri "
        f"javob yoyilmagan.\n"
        f"Iltimos, guruhda @{SHAHNOZA_USERNAME} deb belgilab javob bering."
    )
    try:
        await client.send_message(group_id, text, parse_mode="html")
        logger.info("[ASSISTANT REMINDER] Sent reminder to group %s for chat %s", group_id, chat_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[ASSISTANT REMINDER] Failed to send reminder: %s", exc)
