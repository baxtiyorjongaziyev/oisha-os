import logging
import re
from typing import Optional

from src.context import app_ctx
from src.services.core.telegram.bot_runtime import BotRuntimePort, TelethonBotRuntime
from src.settings import settings

logger = logging.getLogger(__name__)

_topic_cache: dict[int, tuple[Optional[int], Optional[int]]] = {}
_FINANCE_GROUP_WORDS = frozenset({"moliya", "finance", "buxgalter", "accounting", "hisobchi"})
_PRIVATE_RECEIPT_PHOTO_PREFIXES = (
    "/kirim",
    "/chiqim",
    "/chek",
    "/receipt",
    "#kirim",
    "#chiqim",
)

def _as_bot_runtime(bot_client) -> BotRuntimePort | None:
    if bot_client is None:
        return None
    if hasattr(bot_client, "backend") and hasattr(bot_client, "send_message"):
        return bot_client
    return TelethonBotRuntime(bot_client)

def _bot_runtime_connected(bot_client) -> bool:
    if bot_client is None:
        return False
    is_connected = getattr(bot_client, "is_connected", None)
    if callable(is_connected):
        return bool(is_connected())
    return True

def should_process_private_receipt_photo(*, is_owner: bool, has_photo: bool, text: str = "") -> bool:
    if not is_owner or not has_photo:
        return False
    normalized = (text or "").strip().lower()
    return normalized.startswith(_PRIVATE_RECEIPT_PHOTO_PREFIXES)

def _get_finance_config() -> tuple[Optional[int], Optional[int], Optional[int]]:
    try:
        return (
            getattr(settings, "HISOBCHI_FINANCE_GROUP_ID", None),
            getattr(settings, "HISOBCHI_KIRIM_TOPIC_ID", None),
            getattr(settings, "HISOBCHI_CHIQIM_TOPIC_ID", None),
        )
    except Exception as exc:
        logger.error("Error occurred: %s", exc, exc_info=True)
        return None, None, None

async def _discover_topics(client, group_id: int) -> tuple[Optional[int], Optional[int]]:
    if group_id in _topic_cache:
        return _topic_cache[group_id]
    kirim_id: Optional[int] = None
    chiqim_id: Optional[int] = None
    try:
        from telethon.tl.functions.messages import GetForumTopicsRequest
        result = await client(
            GetForumTopicsRequest(
                channel=group_id,
                q="",
                offset_date=0,
                offset_id=0,
                offset_topic=0,
                limit=100,
            )
        )
        for topic in getattr(result, "topics", []):
            title = (getattr(topic, "title", "") or "").strip().lower()
            tid = getattr(topic, "id", None)
            if title == "kirim":
                kirim_id = tid
            elif title == "chiqim":
                chiqim_id = tid
        logger.info("[HISOBCHI] Topics discovered — Kirim: %s, Chiqim: %s", kirim_id, chiqim_id)
    except Exception as exc:
        logger.error("Error occurred: %s", exc, exc_info=True)
    _topic_cache[group_id] = (kirim_id, chiqim_id)
    return kirim_id, chiqim_id

async def _resolve_topics(client, group_id: int, kirim_cfg: Optional[int], chiqim_cfg: Optional[int]) -> tuple[Optional[int], Optional[int]]:
    if kirim_cfg is not None and chiqim_cfg is not None:
        return kirim_cfg, chiqim_cfg
    disc_kirim, disc_chiqim = await _discover_topics(client, group_id)
    return (
        kirim_cfg if kirim_cfg is not None else disc_kirim,
        chiqim_cfg if chiqim_cfg is not None else disc_chiqim,
    )

async def _discover_finance_group(client) -> Optional[int]:
    if getattr(app_ctx, "finance_group_cache", None) is not None:
        return app_ctx.finance_group_cache
    try:
        dialogs = await client.get_dialogs(limit=500)
        for dialog in dialogs:
            title = (
                getattr(dialog, "name", None)
                or getattr(getattr(dialog, "entity", None), "title", None)
                or ""
            )
            words = set(re.findall(r"[\w'’]+", title.casefold(), flags=re.UNICODE))
            if words & _FINANCE_GROUP_WORDS:
                group_id = getattr(dialog, "id", None)
                if group_id is not None:
                    app_ctx.finance_group_cache = int(group_id)
                    logger.info("[HISOBCHI] Finance group discovered: %s (%s)", title, app_ctx.finance_group_cache)
                    return app_ctx.finance_group_cache
    except Exception as exc:
        logger.error("Error occurred: %s", exc, exc_info=True)
    return None

async def resolve_finance_destination(client) -> tuple[Optional[int], Optional[int], Optional[int]]:
    configured_group, kirim_cfg, chiqim_cfg = _get_finance_config()
    group_id = configured_group or await _discover_finance_group(client)
    if group_id is None:
        team_group_id = getattr(settings, "TEAM_GROUP_ID", None)
        if team_group_id:
            team_kirim, team_chiqim = await _resolve_topics(client, int(team_group_id), kirim_cfg, chiqim_cfg)
            if team_kirim is not None or team_chiqim is not None:
                logger.info("[HISOBCHI] Finance topics found in TEAM_GROUP_ID: %s", team_group_id)
                return int(team_group_id), team_kirim, team_chiqim
        logger.error("[HISOBCHI] Finance destination is not configured or discoverable; card details will not be sent to a generic group.")
        return None, None, None
    kirim_topic, chiqim_topic = await _resolve_topics(client, int(group_id), kirim_cfg, chiqim_cfg)
    return int(group_id), kirim_topic, chiqim_topic

def _pick_topic(direction: str, kirim_topic: Optional[int], chiqim_topic: Optional[int]) -> Optional[int]:
    if direction == "in":
        return kirim_topic
    return chiqim_topic

async def _reply_via_bot(event, bot_client, text: str, *, parse_mode: Optional[str] = None) -> None:
    bot_runtime = _as_bot_runtime(bot_client)
    if not _bot_runtime_connected(bot_client) or bot_runtime is None:
        logger.error("[HISOBCHI] bot_client yo'q — moliya guruhiga javob yuborilmadi: %s", text[:60])
        return
    try:
        await bot_runtime.send_message(
            event.chat_id,
            text,
            reply_to_message_id=event.message.id,
            parse_mode=parse_mode.upper() if parse_mode else None,
        )
    except Exception as exc:
        logger.warning("[HISOBCHI] Group reply with reply_to failed, retrying without it: %s", exc)
        try:
            await bot_runtime.send_message(
                event.chat_id,
                text,
                parse_mode=parse_mode.upper() if parse_mode else None,
            )
        except Exception as retry_exc:
            logger.error("Error occurred: %s", retry_exc, exc_info=True)
