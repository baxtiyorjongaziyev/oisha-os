from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Each entry was reviewed against baxtiyorjongaziyev/telegram-mcp. Annotation
# alone is deliberately insufficient: a newly added tool must be reviewed here
# before Oisha can invoke it without owner approval.
READ_ALLOWLIST = frozenset(
    {
        "export_contacts",
        "get_admins",
        "get_banned_users",
        "get_blocked_users",
        "get_bot_info",
        "get_chat",
        "get_chats",
        "get_common_chats",
        "get_contact_chats",
        "get_contact_ids",
        "get_direct_chat_by_contact",
        "get_drafts",
        "get_folder",
        "get_full_chat",
        "get_full_user",
        "get_gif_search",
        "get_history",
        "get_invite_link",
        "get_last_interaction",
        "get_me",
        "get_media_info",
        "get_message_context",
        "get_message_link",
        "get_message_reactions",
        "get_message_read_by",
        "get_messages",
        "get_participants",
        "get_pinned_messages",
        "get_privacy_settings",
        "get_recent_actions",
        "get_scheduled_messages",
        "get_sticker_sets",
        "get_user_photos",
        "get_user_status",
        "list_accounts",
        "list_chats",
        "list_contacts",
        "list_folders",
        "list_inline_buttons",
        "list_messages",
        "list_topics",
        "resolve_username",
        "search_contacts",
        "search_global",
        "search_messages",
        "search_public_chats",
        "wait_for_new_message",
        "wait_for_settled_message",
    }
)

DESTRUCTIVE_PREFIXES = (
    "ban",
    "block",
    "delete",
    "discard",
    "kick",
    "leave",
    "remove",
    "revoke",
    "unpin",
)


@dataclass(frozen=True)
class ToolDecision:
    automatic: bool
    risk: str
    reason: str


def _annotation_value(annotations: Any, name: str) -> bool:
    if annotations is None:
        return False
    if isinstance(annotations, dict):
        value = annotations.get(name)
        if value is None:
            snake_name = name.replace("Hint", "_hint")
            value = annotations.get(snake_name)
        return value is True
    return getattr(annotations, name, False) is True


def classify_tool(name: str, annotations: Any = None) -> ToolDecision:
    normalized = (name or "").strip()
    annotated_read = _annotation_value(annotations, "readOnlyHint")
    if annotated_read and normalized in READ_ALLOWLIST:
        return ToolDecision(
            automatic=True,
            risk="read",
            reason="trusted read annotation and reviewed local allowlist",
        )

    lowered = normalized.lower()
    risk = (
        "destructive"
        if lowered.startswith(DESTRUCTIVE_PREFIXES)
        or _annotation_value(annotations, "destructiveHint")
        else "mutation"
    )
    return ToolDecision(
        automatic=False,
        risk=risk,
        reason="owner approval required by deny-by-default policy",
    )
