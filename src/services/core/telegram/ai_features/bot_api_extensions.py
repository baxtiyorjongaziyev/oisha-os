"""
Bot API 9.0–10.5 extension methods mixin for TelegramBotAPI10Client.
Covers:
- Bot API 9.0: readBusinessMessage, deleteBusinessMessages
- Bot API 9.1: sendChecklist, editMessageChecklist
- Bot API 9.3/9.4: createForumTopic, editForumTopic (1-on-1 & supergroups)
- Bot API 9.5: setChatMemberTag
- Bot API 10.1/10.3: sendRichMessageDraft, editEphemeralMessageText
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

ALLOWED_FORUM_ICON_COLORS = (
    7322096,   # 0x6FB9F0 (Blue)
    16766590,  # 0xFFD67E (Yellow)
    13338331,  # 0xCB86DB (Violet)
    9367192,   # 0x8EEE98 (Green)
    16749490,  # 0xFF93B2 (Rose)
    16478047,  # 0xFB6F5F (Red)
)


class BotAPIExtensionsMixin:
    """Mixin adding Bot API 9.0–10.5 methods to TelegramBotAPI10Client."""

    async def call(self, method: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        raise NotImplementedError

    async def read_business_message(
        self,
        business_connection_id: str,
        chat_id: int,
        message_id: int,
    ) -> bool:
        """Mark an incoming message as read on behalf of a business account (Bot API 9.0)."""
        result = await self.call(
            "readBusinessMessage",
            {
                "business_connection_id": business_connection_id,
                "chat_id": chat_id,
                "message_id": message_id,
            },
        )
        return bool(result)

    async def delete_business_messages(
        self,
        business_connection_id: str,
        message_ids: List[int],
    ) -> bool:
        """Delete 1–100 messages on behalf of a business account (Bot API 9.0)."""
        if not message_ids or len(message_ids) > 100:
            raise ValueError("message_ids must contain 1 to 100 identifiers")
        result = await self.call(
            "deleteBusinessMessages",
            {
                "business_connection_id": business_connection_id,
                "message_ids": list(message_ids),
            },
        )
        return bool(result)

    async def send_checklist(
        self,
        business_connection_id: str,
        chat_id: int | str,
        checklist: Dict[str, Any],
        *,
        disable_notification: Optional[bool] = None,
        protect_content: Optional[bool] = None,
        message_effect_id: Optional[str] = None,
        reply_parameters: Optional[Dict[str, Any]] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send a native interactive checklist (Bot API 9.1 ``sendChecklist``)."""
        result = await self.call(
            "sendChecklist",
            {
                "business_connection_id": business_connection_id,
                "chat_id": chat_id,
                "checklist": checklist,
                "disable_notification": disable_notification,
                "protect_content": protect_content,
                "message_effect_id": message_effect_id,
                "reply_parameters": reply_parameters,
                "reply_markup": reply_markup,
            },
        )
        return result if isinstance(result, dict) else {}

    async def edit_message_checklist(
        self,
        business_connection_id: str,
        chat_id: int,
        message_id: int,
        checklist: Dict[str, Any],
        *,
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Edit an existing native checklist (Bot API 9.1 ``editMessageChecklist``)."""
        result = await self.call(
            "editMessageChecklist",
            {
                "business_connection_id": business_connection_id,
                "chat_id": chat_id,
                "message_id": message_id,
                "checklist": checklist,
                "reply_markup": reply_markup,
            },
        )
        return result if isinstance(result, dict) else {}

    async def create_forum_topic(
        self,
        chat_id: int | str,
        name: str,
        *,
        icon_color: Optional[int] = None,
        icon_custom_emoji_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a topic in a forum supergroup or 1-on-1 private chat (Bot API 9.3/9.4)."""
        clean_name = (name or "").strip()
        if not clean_name or len(clean_name) > 128:
            raise ValueError("Topic name must be 1 to 128 characters")
        if icon_color is not None and icon_color not in ALLOWED_FORUM_ICON_COLORS:
            raise ValueError(f"Unsupported icon_color: {icon_color}")
        result = await self.call(
            "createForumTopic",
            {
                "chat_id": chat_id,
                "name": clean_name,
                "icon_color": icon_color,
                "icon_custom_emoji_id": icon_custom_emoji_id,
            },
        )
        return result if isinstance(result, dict) else {}

    async def edit_forum_topic(
        self,
        chat_id: int | str,
        message_thread_id: int,
        *,
        name: Optional[str] = None,
        icon_custom_emoji_id: Optional[str] = None,
    ) -> bool:
        """Edit name or icon of a topic in a supergroup or private chat (Bot API 9.3/9.4)."""
        result = await self.call(
            "editForumTopic",
            {
                "chat_id": chat_id,
                "message_thread_id": message_thread_id,
                "name": name,
                "icon_custom_emoji_id": icon_custom_emoji_id,
            },
        )
        return bool(result)

    async def set_chat_member_tag(
        self,
        chat_id: int | str,
        user_id: int,
        *,
        tag: Optional[str] = None,
    ) -> bool:
        """Assign or remove a custom tag (0-16 chars) for a group member (Bot API 9.5)."""
        if tag is not None and len(tag) > 16:
            raise ValueError("Member tag must be at most 16 characters")
        result = await self.call(
            "setChatMemberTag",
            {
                "chat_id": chat_id,
                "user_id": user_id,
                "tag": tag,
            },
        )
        return bool(result)

    async def send_rich_message_draft(
        self,
        chat_id: int,
        draft_id: int,
        rich_message: Dict[str, Any],
        *,
        message_thread_id: Optional[int] = None,
        can_stop: Optional[bool] = None,
        keep_on_stop: Optional[bool] = None,
    ) -> bool:
        """Stream a rich message draft with optional Stop button (Bot API 10.1/10.3)."""
        result = await self.call(
            "sendRichMessageDraft",
            {
                "chat_id": chat_id,
                "message_thread_id": message_thread_id,
                "draft_id": draft_id,
                "rich_message": rich_message,
                "can_stop": can_stop,
                "keep_on_stop": keep_on_stop,
            },
        )
        return bool(result)

    async def edit_ephemeral_message_text(
        self,
        ephemeral_message_id: int,
        *,
        chat_id: Optional[int | str] = None,
        text: Optional[str] = None,
        parse_mode: Optional[str] = "HTML",
        rich_message: Optional[Dict[str, Any]] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Edit an ephemeral message in-place with text or rich_message (Bot API 10.3)."""
        return await self.call(
            "editEphemeralMessageText",
            {
                "chat_id": chat_id,
                "ephemeral_message_id": ephemeral_message_id,
                "text": text,
                "parse_mode": parse_mode if text is not None else None,
                "rich_message": rich_message,
                "reply_markup": reply_markup,
            },
        )

    async def set_my_settings(
        self,
        *,
        supports_inline_queries: Optional[bool] = None,
        inline_query_placeholder: Optional[str] = None,
        needs_inline_query_location: Optional[bool] = None,
        inline_feedback_share_denominator: Optional[int] = None,
        can_join_groups: Optional[bool] = None,
        can_read_all_group_messages: Optional[bool] = None,
        can_connect_to_business: Optional[bool] = None,
        can_manage_bots: Optional[bool] = None,
        supports_guest_queries: Optional[bool] = None,
        supports_join_request_queries: Optional[bool] = None,
        has_topics_enabled: Optional[bool] = None,
        allows_users_to_create_topics: Optional[bool] = None,
        has_topic_sidebar: Optional[bool] = None,
        can_communicate_with_bots: Optional[bool] = None,
        callback_query_mode: Optional[str] = None,
    ) -> bool:
        """Automate bot configuration (Bot API 10.5 ``setMySettings``)."""
        if callback_query_mode is not None and callback_query_mode not in ("default", "auto", "inline"):
            raise ValueError(f"Invalid callback_query_mode: {callback_query_mode}")
        if inline_feedback_share_denominator is not None and inline_feedback_share_denominator not in (0, 1, 10, 100, 1000):
            raise ValueError(f"Invalid inline_feedback_share_denominator: {inline_feedback_share_denominator}")
        result = await self.call("setMySettings", {
            "supports_inline_queries": supports_inline_queries, "inline_query_placeholder": inline_query_placeholder,
            "needs_inline_query_location": needs_inline_query_location, "inline_feedback_share_denominator": inline_feedback_share_denominator,
            "can_join_groups": can_join_groups, "can_read_all_group_messages": can_read_all_group_messages,
            "can_connect_to_business": can_connect_to_business, "can_manage_bots": can_manage_bots,
            "supports_guest_queries": supports_guest_queries, "supports_join_request_queries": supports_join_request_queries,
            "has_topics_enabled": has_topics_enabled, "allows_users_to_create_topics": allows_users_to_create_topics,
            "has_topic_sidebar": has_topic_sidebar, "can_communicate_with_bots": can_communicate_with_bots,
            "callback_query_mode": callback_query_mode,
        })
        return bool(result)
