"""Widget size limits from https://core.telegram.org/bots/widgets."""
from __future__ import annotations

import zlib
from typing import Optional

MAX_HTML_BYTES = 32768
MAX_HTML_COMPRESSED_BYTES = 4096
MAX_STATE_BYTES = 1024
MAX_QUERY_DATA_BYTES = 64
MAX_ANSWER_BYTES = 1024
MIN_SHARED_CACHE_TIME = 5
MAX_SHARED_CACHE_TIME = 3600


class WidgetLimitError(ValueError):
    """Raised when widget content breaks a Telegram limit."""


def compressed_size(html: str) -> int:
    return len(zlib.compress(html.encode("utf-8"), 9))


def validate_html(html: str) -> None:
    raw = html.encode("utf-8")
    if not raw:
        raise WidgetLimitError("html is empty")
    if "\x00" in html:
        raise WidgetLimitError("html must not contain NUL characters")
    if len(raw) > MAX_HTML_BYTES:
        raise WidgetLimitError(f"html is {len(raw)} bytes, limit {MAX_HTML_BYTES}")
    packed = compressed_size(html)
    if packed > MAX_HTML_COMPRESSED_BYTES:
        raise WidgetLimitError(
            f"compressed html is {packed} bytes, limit {MAX_HTML_COMPRESSED_BYTES}"
        )


def validate_state(name: str, value: Optional[str], limit: int = MAX_STATE_BYTES) -> None:
    if value is None:
        return
    size = len(value.encode("utf-8"))
    if size > limit:
        raise WidgetLimitError(f"{name} is {size} bytes, limit {limit}")
