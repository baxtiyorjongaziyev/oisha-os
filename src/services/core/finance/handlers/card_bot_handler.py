import logging
from typing import Optional
from datetime import datetime, timedelta, timezone
import html
import asyncio

from src.services.core.finance.hisobchi_engine import HisobchiEngine
from src.services.core.finance.hisobchi_card_parser import CARD_BOT_USERNAMES, parse_card_notification
from .utils import (
    resolve_finance_destination,
    _pick_topic,
    _as_bot_runtime,
    _bot_runtime_connected,
)

logger = logging.getLogger(__name__)

async def handle_card_bot_message(event, client, engine: HisobchiEngine, bot_client=None) -> Optional[int]:
    try:
        sender = await event.get_sender()
        username = (getattr(sender, "username", None) or "").lower()
        if username not in CARD_BOT_USERNAMES:
            return None

        text = event.message.message or ""
        tx = parse_card_notification(username, text)
        if not tx:
            logger.warning("[HISOBCHI] Failed to parse card notification: %s", text[:100])
            return None

        finance_group_id, kirim_topic_id, chiqim_topic_id = (
            await resolve_finance_destination(client)
        )

        topic_id = _pick_topic(tx.direction, kirim_topic_id, chiqim_topic_id)

        known_rule = await engine.get_known_rule(
            tx.merchant, tx.card_suffix, tx.direction, tx.amount
        )
        category = known_rule["category"] if known_rule else None
        ownership = known_rule["ownership"] if known_rule else "business"

        tx_id, created = await engine.save_transaction_once(
            source_bot=tx.source_bot,
            direction=tx.direction,
            amount=tx.amount,
            merchant=tx.merchant,
            card_suffix=tx.card_suffix,
            tx_time=tx.tx_time,
            balance=tx.balance,
            raw_text=text,
            category=category,
            ownership=ownership,
            status="pending",
            source_message_id=getattr(getattr(event, "message", None), "id", None),
        )
        if not created:
            logger.info("[HISOBCHI] Duplicate transaction ignored: #%s", tx_id)
            return tx_id

        from src.services.core.hisobchi_approval import (
            build_approval_keyboard,
            build_approval_message,
            register_pending,
        )

        await register_pending(tx_id, tx, ownership, category)

        owner_id = None
        try:
            from src.settings import settings
            owner_id = getattr(settings, "OWNER_ID", None)
        except Exception as exc:
            logger.debug("[HISOBCHI] OWNER_ID from settings: %s", exc)

        if owner_id:
            try:
                msg = build_approval_message(tx, tx_id, ownership)
                kb = build_approval_keyboard(tx_id, ownership)
                if category:
                    msg = f"🗂 <b>Avto-kategoriya:</b> {html.escape(category)}\n\n" + msg
                await client.send_message(int(owner_id), msg, parse_mode="html", buttons=kb)
                logger.info("[HISOBCHI] Sent approval request to owner #%s for tx #%s", owner_id, tx_id)
            except Exception as exc:
                logger.error("Error occurred: %s", exc, exc_info=True)

        if finance_group_id:
            bot_runtime = _as_bot_runtime(bot_client)
            if not _bot_runtime_connected(bot_client) or bot_runtime is None:
                logger.error(
                    "[HISOBCHI] bot_client yo'q — moliya guruhiga savol yuborilmadi (tx #%s)",
                    tx_id,
                )
            else:
                try:
                    kb = build_approval_keyboard(tx_id, ownership)
                    sent = await bot_runtime.send_message(
                        finance_group_id,
                        engine.build_finance_question(tx, tx_id),
                        parse_mode="HTML",
                        reply_to_message_id=topic_id,
                        buttons=kb,
                    )
                    await engine.update_finance_msg(
                        tx_id,
                        finance_msg_id=sent.message_id or getattr(sent.raw, "id", None),
                        finance_chat_id=finance_group_id,
                    )
                except Exception as exc:
                    logger.error("Error occurred: %s", exc, exc_info=True)
        return tx_id
    except Exception as exc:
        logger.error("Error occurred: %s", exc, exc_info=True)
        try:
            await event.reply(f"❌ Xatolik yuz berdi: {str(exc)}")
        except Exception:
            pass
        return None

def is_card_bot_sender(sender) -> bool:
    username = (getattr(sender, "username", None) or "").lower()
    return username in CARD_BOT_USERNAMES

class _CardBackfillEvent:
    def __init__(self, message, sender) -> None:
        self.message = message
        self.id = getattr(message, "id", None)
        self.is_private = True
        self.out = False
        self._sender = sender

    async def get_sender(self):
        return self._sender

async def _gather_card_messages_since(client, username: str, cutoff: datetime, limit: int) -> tuple:
    entity = await client.get_entity(username)
    messages = []
    async for message in client.iter_messages(entity, limit=limit):
        message_date = getattr(message, "date", None)
        if message_date is not None:
            if message_date.tzinfo is None:
                message_date = message_date.replace(tzinfo=timezone.utc)
            if message_date < cutoff:
                break
        messages.append(message)
    return entity, list(reversed(messages))

async def _process_one_card_message(
    message, entity, username: str, client, engine: HisobchiEngine, bot_client, stats: dict
) -> Optional[int]:
    stats["scanned"] += 1
    try:
        text = getattr(message, "message", None) or ""
        tx = parse_card_notification(username, text)
        if tx is None:
            return None
        existed = await engine.transaction_exists(
            source_bot=tx.source_bot, direction=tx.direction, amount=tx.amount,
            merchant=tx.merchant, card_suffix=tx.card_suffix, tx_time=tx.tx_time,
            source_message_id=getattr(message, "id", None),
        )
        if existed:
            stats["duplicates"] += 1
            return None
        tx_id = await handle_card_bot_message(
            _CardBackfillEvent(message, entity), client, engine, bot_client=bot_client,
        )
        if tx_id is not None:
            stats["created"] += 1
        return tx_id
    except Exception as exc:
        stats["errors"] += 1
        logger.error("Error occurred: %s", exc, exc_info=True)
        return None

async def backfill_card_bot_messages(
    client,
    engine: HisobchiEngine,
    *,
    bot_client=None,
    limit: int = 50,
    max_age_hours: int = 72,
    since: Optional[datetime] = None,
    delay_seconds: float = 0.05,
) -> dict[str, int]:
    stats = {"scanned": 0, "created": 0, "duplicates": 0, "errors": 0}
    cutoff = since if since is not None else datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

    for username in sorted(CARD_BOT_USERNAMES):
        try:
            entity, messages = await _gather_card_messages_since(client, username, cutoff, limit)
            for message in messages:
                await _process_one_card_message(message, entity, username, client, engine, bot_client, stats)
                if delay_seconds:
                    await asyncio.sleep(delay_seconds)
        except Exception as exc:
            stats["errors"] += 1
            logger.error("Error occurred: %s", exc, exc_info=True)

    logger.info("[HISOBCHI] Backfill finished: %s", stats)
    return stats

async def resync_since_sequential(
    client,
    engine: HisobchiEngine,
    *,
    bot_client=None,
    since: datetime,
    limit: int = 5000,
    poll_interval_sec: float = 5.0,
    max_wait_sec: float = 3600.0,
) -> dict[str, int]:
    stats = {"scanned": 0, "created": 0, "duplicates": 0, "errors": 0, "timed_out": 0}

    for username in sorted(CARD_BOT_USERNAMES):
        try:
            entity, messages = await _gather_card_messages_since(client, username, since, limit)
            for message in messages:
                try:
                    tx_id = await _process_one_card_message(
                        message, entity, username, client, engine, bot_client, stats
                    )
                    if tx_id is None:
                        continue
                    waited = 0.0
                    while waited < max_wait_sec:
                        await asyncio.sleep(poll_interval_sec)
                        waited += poll_interval_sec
                        status = await engine.get_transaction_status(tx_id)
                        if status != "pending":
                            break
                    else:
                        stats["timed_out"] += 1
                        logger.warning(
                            "[HISOBCHI] Resync: tx #%s unanswered after %.0fs, moving on",
                            tx_id, max_wait_sec,
                        )
                except Exception as exc:
                    stats["errors"] += 1
                    logger.error("Error occurred: %s", exc, exc_info=True)
        except Exception as exc:
            stats["errors"] += 1
            logger.error("Error occurred: %s", exc, exc_info=True)

    logger.info("[HISOBCHI] Sequential resync finished: %s", stats)
    return stats
