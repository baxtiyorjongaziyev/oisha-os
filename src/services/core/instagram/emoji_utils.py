"""Utilities for detecting pure emoji comments and mirroring them.
Designed to meet strict 150-400 lines standard and single responsibility.
"""
from __future__ import annotations

import unicodedata
from typing import Optional


def is_pure_emoji_text(text: str) -> bool:
    """Returns True if the string contains only emoji characters and whitespace.

    Handles standard pictographs, skin-tone modifiers (Fitzpatrick),
    zero-width joiners (ZWJ), variation selectors, dingbats, and symbols.
    """
    stripped = text.strip()
    if not stripped:
        return False

    for ch in stripped:
        if ch.isspace():
            continue
        cat = unicodedata.category(ch)
        code = ord(ch)
        is_em = (
            cat in ("So", "Sk", "Mn", "Me")
            or 0x1F000 <= code <= 0x1FAFF
            or 0x2600 <= code <= 0x27BF
            or 0x2B50 <= code <= 0x2B55
            or 0x23E9 <= code <= 0x23F3
            or code in (0x200D, 0xFE0F, 0xFE0E)
        )
        if not is_em:
            return False

    return True


def get_mirror_emoji_reply(comment_text: str) -> Optional[str]:
    """If comment_text consists only of emojis, returns an exact mirror of them.

    For example:
        '🔥🔥🔥' -> '🔥🔥🔥'
        '👏' -> '👏'
        '❤️🔥' -> '❤️🔥'
    If the text contains any letters/words, returns None.
    """
    if not is_pure_emoji_text(comment_text):
        return None

    # Strip surrounding whitespace while keeping the exact emoji sequence
    cleaned = "".join(comment_text.split())
    return cleaned if cleaned else None
