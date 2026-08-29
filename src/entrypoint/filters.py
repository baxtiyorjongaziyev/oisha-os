"""
Telegram folder and private message filtering utilities.
"""
import logging
import time
from typing import Any, Dict, Optional, Set, Tuple
from src.settings import settings
from src.context import app_ctx

logger = logging.getLogger("OishaFilters")

_EXCLUDED_FOLDER_USER_CACHE: Dict[str, Any] = {"expires_at": 0.0, "user_ids": set()}

def _userbot_private_replies_disabled() -> bool:
    return True


def _is_private_userbot_event(event: Any) -> bool:
    return bool(getattr(event, "is_private", False)) and not bool(
        getattr(event, "out", False)
    )


def _should_block_private_userbot_reply(event: Any) -> bool:
    return _userbot_private_replies_disabled() and _is_private_userbot_event(event)


def _folder_exclusion_enabled() -> bool:
    return os.getenv("ENABLE_PERSONAL_FOLDER_EXCLUSION", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _excluded_folder_keywords() -> tuple[str, ...]:
    raw = os.getenv(
        "PERSONAL_FOLDER_KEYWORDS", "oila,family,shaxsiy,personal,do'st,dost,friends"
    )
    return tuple(item.strip().lower() for item in raw.split(",") if item.strip())


def _dialog_filter_title(dialog_filter: Any) -> str:
    title = getattr(dialog_filter, "title", "")
    if isinstance(title, str):
        return title
    return getattr(title, "text", str(title or ""))


def _peer_user_id(peer: Any) -> Optional[int]:
    return getattr(peer, "user_id", None) or getattr(peer, "userId", None)


async def _excluded_folder_user_ids() -> set[int]:
    now = time.time()
    async with _EXCLUDED_FOLDER_CACHE_LOCK:
        if _EXCLUDED_FOLDER_USER_CACHE["expires_at"] > now:
            return set(_EXCLUDED_FOLDER_USER_CACHE["user_ids"])

        user_ids: set[int] = set()
        try:
            raw_filters = await client(functions.messages.GetDialogFiltersRequest())
            filters = getattr(raw_filters, "filters", raw_filters)
            keywords = _excluded_folder_keywords()
            for dialog_filter in filters or []:
                title = _dialog_filter_title(dialog_filter).lower()
                if not title or not any(keyword in title for keyword in keywords):
                    continue
                for attr in ("include_peers", "pinned_peers"):
                    for peer in getattr(dialog_filter, attr, []) or []:
                        user_id = _peer_user_id(peer)
                        if user_id:
                            user_ids.add(int(user_id))
        except Exception as exc:
            logger.warning(
                f"[FOLDER_GUARD] Could not inspect Telegram folders: {type(exc).__name__}"
            )

        ttl = _negotiation_int("PERSONAL_FOLDER_CACHE_SECS", 600)
        _EXCLUDED_FOLDER_USER_CACHE["expires_at"] = now + ttl
        _EXCLUDED_FOLDER_USER_CACHE["user_ids"] = user_ids
        return set(user_ids)


async def _is_personal_folder_sender(sender: Any) -> bool:
    if not _folder_exclusion_enabled() or not sender:
        return False
    sender_id = getattr(sender, "id", None)
    if sender_id is None:
        return False
    return int(sender_id) in await _excluded_folder_user_ids()

