"""Destination/deadline-aware, cross-scheduler task delivery claims."""
import asyncio
import logging
import time

logger = logging.getLogger(__name__)
_LOCK = asyncio.Lock()
_SENT = set()


def delivery_key(task, seller, alert_type):
    return f"seller_task:v1:{task['id']}:{int(task.get('complete_till') or 0)}:{seller.chat_id}:{alert_type}"


async def deliver(bot, db, task, seller, alert_type, text, buttons):
    key = delivery_key(task, seller, alert_type)
    async with _LOCK:
        if key in _SENT:
            return False
        if db:
            try:
                if await db.get_state(key):
                    _SENT.add(key)
                    return False
                if not await db.claim_job_run(key, "delivery"):
                    return False
            except Exception:
                logger.exception("[TASK_DM] Persistent delivery claim unavailable")
                return False
        try:
            result = await bot.send_message(
                chat_id=seller.chat_id, text=text, buttons=buttons,
                parse_mode="HTML", disable_web_page_preview=True,
            )
        except Exception as exc:
            # Definitive rejection is safe to retry after recipient presses Start.
            # Transport timeouts are ambiguous: retain claim, never blindly replay.
            if db and type(exc).__name__ in {
                "TelegramBadRequest", "TelegramForbiddenError", "UserIsBlockedError",
                "ChatWriteForbiddenError", "PeerIdInvalidError",
            }:
                await db.release_job_run(key, "delivery")
            logger.warning("[TASK_DM] Send blocked seller=%s task=%s error=%s", seller.name, task["id"], type(exc).__name__)
            return False
        _SENT.add(key)
        if db:
            try:
                await db.set_state(key, {
                    "sent_at": time.time(), "task_id": task["id"],
                    "chat_id": seller.chat_id, "type": alert_type,
                    "message_id": getattr(result, "message_id", None) or getattr(result, "id", None),
                })
            except Exception:
                logger.exception("[TASK_DM] Send receipt persistence failed; claim retained")
        logger.info("[TASK_DM] Delivered task=%s seller=%s type=%s", task["id"], seller.name, alert_type)
        return True
