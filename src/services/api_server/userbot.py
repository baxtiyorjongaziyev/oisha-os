"""
Userbot access probe and Telegram business connection filtering.
"""
import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.context import app_ctx
from src.settings import settings
from src.time_utils import get_local_now
from src.api.routes.state import api_state

logger = logging.getLogger("OishaAPI")

async def refresh_userbot_group_access_snapshot(client=None) -> Dict[str, Any]:
    """Read group/topic access through the already-connected production userbot."""
    active_client = client or app_ctx.user_client
    checked_at = get_local_now().isoformat()
    if active_client is None:
        api_state._userbot_group_access_snapshot = {
            "status": "unavailable",
            "checked_at": checked_at,
            "groups": {},
            "topics": {},
        }
        return dict(api_state._userbot_group_access_snapshot)

    groups: Dict[str, Dict[str, Any]] = {}
    resolved_entities: Dict[str, Any] = {}
    unresolved_groups: List[str] = []
    group_specs = {
        "crm_group": settings.CRM_GROUP_ID,
        "team_group": settings.TEAM_GROUP_ID,
        "projects_group": settings.PROJECTS_GROUP_ID,
    }
    tasks_group_label = "crm_group"
    if settings.TASKS_GROUP_ID:
        group_specs["tasks_group"] = settings.TASKS_GROUP_ID
        tasks_group_label = "tasks_group"
    for label, chat_id in group_specs.items():
        entry: Dict[str, Any] = {"configured": bool(chat_id), "chat_id": chat_id}
        if chat_id:
            try:
                entity = await asyncio.wait_for(
                    active_client.get_entity(chat_id), timeout=8.0
                )
                resolved_entities[label] = entity
                entry["readable"] = True
                entry["source"] = "entity_cache"
            except Exception as exc:
                logger.error("Exception handled in %s", __name__, exc_info=True)
                entry["readable"] = False
                entry["error"] = type(exc).__name__
                unresolved_groups.append(label)
        groups[label] = entry

    dialogs_loaded = False
    if unresolved_groups:
        try:
            dialogs = await asyncio.wait_for(
                active_client.get_dialogs(limit=500), timeout=20.0
            )
            dialogs_loaded = True
            dialog_entities = {
                int(dialog.id): dialog.entity
                for dialog in dialogs
                if getattr(dialog, "id", None) is not None
            }
            for label in unresolved_groups:
                entity = dialog_entities.get(int(groups[label]["chat_id"]))
                if entity is None:
                    continue
                resolved_entities[label] = entity
                groups[label].update({"readable": True, "source": "dialogs"})
                groups[label].pop("error", None)
        except Exception as exc:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            for label in unresolved_groups:
                groups[label]["dialogs_error"] = type(exc).__name__

    for label in unresolved_groups:
        if not groups[label].get("readable") and dialogs_loaded:
            groups[label]["reason"] = "not_in_userbot_dialogs"

    for label, entity in resolved_entities.items():
        forum = getattr(entity, "forum", None)
        if isinstance(forum, bool):
            groups[label]["forum"] = forum

    topics: Dict[str, Dict[str, Any]] = {}
    topic_specs = {
        "crm": ("crm_group", settings.TOPIC_CRM_ID or settings.CRM_TOPIC_ID),
        "reports": ("crm_group", settings.TOPIC_REPORTS_ID),
        "tasks": (tasks_group_label, settings.TOPIC_TASKS_ID),
        "general": ("team_group", settings.TOPIC_GENERAL_ID),
        "kirim": ("team_group", settings.TOPIC_KIRIM_ID),
    }
    for label, (group_label, topic_id) in topic_specs.items():
        group_entry = groups[group_label]
        entry = {"configured": bool(topic_id), "topic_id": topic_id, "group": group_label}
        if topic_id and group_entry.get("readable"):
            try:
                messages = await asyncio.wait_for(
                    active_client.get_messages(
                        resolved_entities.get(group_label, group_entry["chat_id"]),
                        limit=1,
                        reply_to=topic_id,
                    ),
                    timeout=8.0,
                )
                entry["readable"] = True
                entry["sample_messages"] = len(messages or [])
            except Exception as exc:
                # Topic o'chirilgan yoki ID noto'g'ri bo'lsa Telegram
                # BadRequestError (TOPIC_ID_INVALID) qaytaradi. Bu KUTILGAN
                # holat — quyida reason bilan qayd etiladi va snapshot uni
                # ko'rsatadi. Bu funksiya davriy ishlaydi, shuning uchun
                # unga to'liq traceback yozish jurnalni bir xil stack'lar
                # bilan to'ldiradi (prod'da aynan shunday bo'lgan). Faqat
                # kutilmagan xatolar uchun traceback qoldiramiz.
                invalid_topic = type(exc).__name__ == "BadRequestError"
                if invalid_topic:
                    logger.warning(
                        "[TELEGRAM PROBE] '%s' topic o'qilmadi "
                        "(group=%s, topic_id=%s): %s",
                        label,
                        group_label,
                        topic_id,
                        exc,
                    )
                else:
                    logger.error("Exception handled in %s", __name__, exc_info=True)
                entry["readable"] = False
                entry["error"] = type(exc).__name__
                entry["reason"] = (
                    "invalid_or_deleted_topic" if invalid_topic else "topic_unreadable"
                )
        elif topic_id and not group_entry.get("readable"):
            entry["reason"] = "group_unreadable"
        topics[label] = entry

    required_groups = [e for e in groups.values() if e.get("configured")]
    required_topics = [e for e in topics.values() if e.get("configured")]
    api_state._userbot_group_access_snapshot = {
        "status": (
            "ok"
            if all(e.get("readable") for e in required_groups + required_topics)
            else "degraded"
        ),
        "checked_at": checked_at,
        "groups": groups,
        "topics": topics,
    }
    return dict(api_state._userbot_group_access_snapshot)

# Bot-to-bot safeguards (used by process_telegram_update)
# ---------------------------------------------------------------------------

_bot2bot_tracker: Dict[str, list] = {}
BOT2BOT_MAX_ROUNDS = int(os.getenv("TELEGRAM_BOT_TO_BOT_MAX_ROUNDS", "1"))
BOT2BOT_COOLDOWN_SEC = int(os.getenv("TELEGRAM_BOT_TO_BOT_COOLDOWN_SECONDS", "300"))


def _bot2bot_allowed(from_id: int, chat_id: int) -> bool:
    key = f"{from_id}:{chat_id}"
    now = time.time()
    history = _bot2bot_tracker.get(key, [])
    history = [ts for ts in history if now - ts < BOT2BOT_COOLDOWN_SEC]
    if len(history) >= BOT2BOT_MAX_ROUNDS:
        return False
    history.append(now)
    _bot2bot_tracker[key] = history
    return True


def _bot2bot_skip_reason(from_user: Dict[str, Any], chat_id: int) -> str:
    if not from_user.get("is_bot"):
        return ""
    if not settings.TELEGRAM_BOT_TO_BOT_ENABLED:
        return "disabled"
    if not _bot2bot_allowed(from_user.get("id", 0), chat_id):
        return "rate_limit"
    return ""


def _business_message_skip_reason(message: Dict[str, Any]) -> str:
    if not isinstance(message, dict):
        return ""
    if message.get("sender_business_bot"):
        return "sender_business_bot"
    try:
        sender_id = int((message.get("from") or {}).get("id") or 0)
    except (TypeError, ValueError):
        sender_id = 0
    if not sender_id:
        return ""
    owner_ids = {int(getattr(settings, "OWNER_ID", 0) or 0)}
    connection_id = str(message.get("business_connection_id") or "")
    connection = api_state.business_connections.get(connection_id) or {}
    try:
        owner_ids.add(int(connection.get("user_id") or 0))
    except (TypeError, ValueError):
        pass
    if sender_id in owner_ids:
        return "business_owner"
    message_date = message.get("date")
    if not message_date:
        return ""
    try:
        message_age = datetime.now(timezone.utc).timestamp() - int(message_date)
        max_backlog_age = int(os.getenv("TELEGRAM_BUSINESS_MAX_BACKLOG_SECONDS", "300"))
    except (TypeError, ValueError):
        return ""
    return "stale_backlog" if message_age > max_backlog_age else ""

