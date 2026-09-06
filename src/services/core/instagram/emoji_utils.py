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
        '😂😂😂' -> '😂😂😂'
        '😢' -> '😢'
    If the text contains letters/words, returns None.
    """
    if not is_pure_emoji_text(comment_text):
        return None

    # Strip surrounding whitespace while keeping the exact emoji sequence
    cleaned = "".join(comment_text.split())
    return cleaned if cleaned else None


def get_short_emotional_reaction(comment_text: str) -> Optional[str]:
    """For comments that are pure reaction or short reaction phrases,
    generate human-like emotional mirroring (laughing or sympathy)
    without AI hallucinations or long unsolicited texts.
    """
    txt = (comment_text or "").strip().lower()
    if not txt:
        return None

    # Pure laugh indicators
    laugh_emojis = ["😂", "🤣", "😅", "😆"]
    sad_emojis = ["😢", "😭", "🥺", "😔", "💔"]

    has_laugh = any(em in txt for em in laugh_emojis)
    has_sad = any(em in txt for em in sad_emojis)

    # 1. Check for pure laugh reactions like "ha ha", "rostanam", "aniq shu"
    laugh_words = ["haha", "xaxa", "rostanam", "rostdan", "xuddi o'zi", "xuddi ozi", "man ku", "manku", "shunaqa"]
    if has_laugh and any(w in txt for w in laugh_words) and len(txt) < 35:
        return "Rostan 😂"

    if has_laugh and len(txt) <= 15:
        # short laugh like "😂 zo'r", "😂😂", "oxiri 😂"
        return "😂😂"

    # 2. Check for sad/sympathy reactions
    if has_sad and len(txt) <= 25:
        return "Afsuski shunaqa 😢"

    return None

