"""Telegram Bot API 10.4 widgets (sendWidget & co.) for Oisha.

aiogram / python-telegram-bot do not expose these methods yet, so they are
called through the existing raw ``TelegramBotAPI10Client``.
"""
from src.services.core.telegram.widgets.client import WidgetClient
from src.services.core.telegram.widgets.flags import widgets_enabled
from src.services.core.telegram.widgets.limits import (
    WidgetLimitError,
    validate_html,
    validate_state,
)
from src.services.core.telegram.widgets.router import (
    WIDGET_UPDATE_KEYS,
    WidgetQuery,
    WidgetQueryRouter,
)
from src.services.core.telegram.widgets.sender import send_widget_or_text
from src.services.core.telegram.widgets.templates import render_widget

__all__ = [
    "WIDGET_UPDATE_KEYS",
    "WidgetClient",
    "WidgetLimitError",
    "WidgetQuery",
    "WidgetQueryRouter",
    "render_widget",
    "send_widget_or_text",
    "validate_html",
    "validate_state",
    "widgets_enabled",
]
