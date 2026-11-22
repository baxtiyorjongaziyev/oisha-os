"""Send a widget when enabled, otherwise (or on any failure) plain text."""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional, Union

from src.services.core.tool_registry import ToolResult
from src.services.core.telegram.widgets.client import WidgetClient
from src.services.core.telegram.widgets.flags import widgets_enabled

logger = logging.getLogger("WidgetSender")

TextSender = Callable[[Union[int, str], str], Awaitable[Any]]
HtmlBuilder = Callable[[], str]


async def send_widget_or_text(
    *,
    client: Optional[WidgetClient],
    chat_id: Union[int, str],
    module: str,
    build_html: HtmlBuilder,
    fallback_text: str,
    send_text: TextSender,
    caption: Optional[str] = None,
    allow_queries: bool = False,
    chat_data: Optional[str] = None,
    message_thread_id: Optional[int] = None,
) -> ToolResult:
    """Widgets work only in private chats in production; callers pass private chat ids."""
    tool = f"widget:{module}"
    if client is not None and widgets_enabled(module):
        try:
            html = build_html()
            result = await client.send_widget(
                chat_id,
                html,
                caption=caption,
                allow_queries=allow_queries,
                chat_data=chat_data,
                message_thread_id=message_thread_id,
            )
            mid = result.get("message_id")
            return ToolResult(
                tool_name=tool,
                success=True,
                sent_count=1,
                direct_message_ids=[mid] if isinstance(mid, int) else [],
                metadata={"mode": "widget"},
            )
        except Exception as exc:  # noqa: BLE001 - fall back to text on any widget failure
            logger.warning("[WIDGET] %s fell back to text: %s", module, type(exc).__name__)
            reason = f"widget_failed:{type(exc).__name__}"
    else:
        reason = "widgets_disabled"

    try:
        await send_text(chat_id, fallback_text)
    except Exception as exc:  # noqa: BLE001
        return ToolResult(tool_name=tool, success=False, status="error", reason=f"{reason};text_failed:{type(exc).__name__}")
    return ToolResult(tool_name=tool, success=True, sent_count=1, reason=reason, metadata={"mode": "text"})
