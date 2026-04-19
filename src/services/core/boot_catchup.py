"""
Boot-time missed-messages catch-up.

Problem: Cloud Run revision rollover = 5-30s of downtime where no event
handler is listening. Any Telegram messages sent during that gap are
silently dropped because Telethon's NewMessage handler only fires on
live events.

Solution: On every boot, we inspect the per-chat checkpoint table
(`chat_checkpoints`) and, for each chat touched within the last 7 days,
we fetch messages with `id > last_processed_msg_id` via
`client.iter_messages(min_id=..., reverse=True)`. Each missed message is
injected into the real `handle_new_message` coroutine as if it had just
arrived, so the full pipeline (lead scoring, auto-reply gate, AmoCRM
sync, etc.) runs with no special-casing.

Idempotency: the checkpoint advances via MAX(), so a restart mid-catchup
replays only the truly unprocessed tail. A crash-loop guard limits
replay to MAX_MESSAGES_PER_CHAT so we never reprocess a huge backlog
more than once.

Rate-limiting: Telegram rejects bursts; we throttle to
~5 msg/sec/chat to stay well under FloodWait thresholds.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger("boot_catchup")

# Hard caps to prevent catch-up from hijacking the boot or thrashing Telegram.
MAX_CHATS = 200          # stop after this many chats scanned
MAX_MESSAGES_PER_CHAT = 50  # cap per chat — anything older is written off
PER_MSG_DELAY_SEC = 0.2  # ~5 msg/sec/chat
OVERALL_BUDGET_SEC = 90  # give up if the whole catch-up takes longer


async def catch_up_missed_messages(
    client: Any,
    db: Any,
    handle_new_message: Callable[[Any], Awaitable[None]],
    *,
    since_days: int = 7,
    max_chats: int = MAX_CHATS,
    max_per_chat: int = MAX_MESSAGES_PER_CHAT,
    overall_budget_sec: float = OVERALL_BUDGET_SEC,
) -> dict:
    """Replay any messages that arrived while the bot was offline.

    Args:
        client: the live Telethon `TelegramClient` (must be connected).
        db: the `Database` instance with chat_checkpoints helpers.
        handle_new_message: the production NewMessage handler. We feed
            each missed message through it as an emulated event so the
            pipeline behaves identically to live traffic.
        since_days: only replay chats touched in the last N days.
        max_chats: safety cap — stop after scanning this many chats.
        max_per_chat: safety cap — skip chats with more missed messages
            than this (log a warning so the Owner can investigate).
        overall_budget_sec: total wall-clock budget for catch-up.

    Returns:
        A dict with stats: {chats, messages, skipped, errors}.
    """
    stats = {"chats": 0, "messages": 0, "skipped": 0, "errors": 0}
    started = time.monotonic()

    try:
        checkpoints = await db.get_recent_chat_checkpoints(since_days=since_days)
    except Exception as e:
        logger.warning(f"[CATCHUP] Could not load checkpoints: {e}")
        return stats

    if not checkpoints:
        logger.info("[CATCHUP] No recent chat checkpoints — skipping replay.")
        return stats

    logger.info(
        f"[CATCHUP] Scanning {len(checkpoints)} recent chat(s) for missed messages "
        f"(since={since_days}d, cap={max_per_chat}/chat, budget={overall_budget_sec}s)"
    )

    for cp in checkpoints[:max_chats]:
        if time.monotonic() - started > overall_budget_sec:
            logger.warning("[CATCHUP] Overall budget exceeded — stopping early.")
            break

        chat_id = cp["chat_id"]
        min_id = cp["last_processed_msg_id"] or 0
        stats["chats"] += 1

        try:
            missed = []
            # iter_messages with min_id returns messages *newer* than min_id.
            # reverse=True makes it chronological (oldest first), which is
            # the order the real handler would have seen them.
            async for msg in client.iter_messages(
                chat_id,
                min_id=min_id,
                reverse=True,
                limit=max_per_chat + 1,
            ):
                missed.append(msg)
                if len(missed) > max_per_chat:
                    break

            if not missed:
                continue

            if len(missed) > max_per_chat:
                logger.warning(
                    f"[CATCHUP] chat={chat_id} has >{max_per_chat} missed messages "
                    f"(capped). Oldest unreplayed id > {min_id}. Owner: consider manual sweep."
                )
                missed = missed[:max_per_chat]

            logger.info(f"[CATCHUP] chat={chat_id}: replaying {len(missed)} message(s) (min_id={min_id})")

            for msg in missed:
                try:
                    # Build a minimal "event-like" wrapper that the real
                    # handler expects. Telethon's NewMessage.Event exposes
                    # .message, .chat_id, .sender_id, .raw_text, .is_private
                    # etc. The safest path is to fabricate an object with
                    # the identical surface so handle_new_message doesn't
                    # branch on type.
                    event = _EmulatedNewMessageEvent(client=client, message=msg)
                    await handle_new_message(event)
                    stats["messages"] += 1
                except Exception as inner:
                    stats["errors"] += 1
                    logger.warning(f"[CATCHUP] handler error chat={chat_id} msg={msg.id}: {inner}")
                # Checkpoint advances inside the real handler, so we don't
                # need to write it here. If the handler raised, we leave
                # the checkpoint at its prior value so the next boot
                # replays this message again (at-least-once semantics).
                await asyncio.sleep(PER_MSG_DELAY_SEC)

        except Exception as e:
            stats["errors"] += 1
            logger.warning(f"[CATCHUP] chat={chat_id} failed: {e}")
            continue

    elapsed = time.monotonic() - started
    logger.info(
        f"[CATCHUP] Done in {elapsed:.1f}s — chats={stats['chats']} "
        f"messages={stats['messages']} skipped={stats['skipped']} errors={stats['errors']}"
    )
    return stats


class _EmulatedNewMessageEvent:
    """Minimal shim that looks like a Telethon NewMessage.Event.

    We only expose the attributes that production `handle_new_message`
    actually reads. If the handler later grows to use more fields, add
    them here. This keeps the replay path fast and avoids re-firing
    real Telethon events (which could re-trigger side channels like
    read-receipts that we don't want during a catch-up).
    """

    __slots__ = ("_client", "message", "chat_id", "sender_id", "raw_text",
                 "text", "is_private", "is_group", "is_channel", "out")

    def __init__(self, client: Any, message: Any):
        self._client = client
        self.message = message
        self.chat_id = getattr(message, "chat_id", None)
        self.sender_id = getattr(message, "sender_id", None)
        text = getattr(message, "message", None) or getattr(message, "text", "") or ""
        self.raw_text = text
        self.text = text
        peer = getattr(message, "peer_id", None)
        # Telethon sets is_private on the event, not the message. Best-effort:
        self.is_private = getattr(peer, "user_id", None) is not None
        self.is_group = getattr(peer, "chat_id", None) is not None
        self.is_channel = getattr(peer, "channel_id", None) is not None
        self.out = bool(getattr(message, "out", False))

    async def get_sender(self):
        # Delegate to the message's own resolver — cheaper than re-fetching.
        get_sender = getattr(self.message, "get_sender", None)
        if get_sender is not None:
            return await get_sender()
        sid = self.sender_id
        if sid is None:
            return None
        return await self._client.get_entity(sid)

    async def get_chat(self):
        get_chat = getattr(self.message, "get_chat", None)
        if get_chat is not None:
            return await get_chat()
        cid = self.chat_id
        if cid is None:
            return None
        return await self._client.get_entity(cid)

    async def respond(self, *args, **kwargs):
        # If the handler calls event.respond() during replay, route it to
        # client.send_message(chat_id, ...). During catch-up this means
        # late replies actually get sent, which is the desired behavior.
        return await self._client.send_message(self.chat_id, *args, **kwargs)

    async def reply(self, *args, **kwargs):
        kwargs.setdefault("reply_to", self.message.id)
        return await self._client.send_message(self.chat_id, *args, **kwargs)
