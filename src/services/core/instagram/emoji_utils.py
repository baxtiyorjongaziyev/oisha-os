"""Utilities for detecting pure emoji comments, mirroring them, and enforcing Anti-Romance.
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


def is_romantic_char(code: int) -> bool:
    """Checks if a unicode codepoint represents a romantic, heart, kiss or affection emoji."""
    return (
        code in {
            0x2764,  # Heavy black heart (standard red heart ❤️)
            0x2665,  # Black heart suit (♥️)
            0x2763,  # Heavy heart exclamation (❣️)
            0x1F48B,  # Kiss mark (💋)
            0x1F48C,  # Love letter (💌)
            0x1F48F,  # Kiss (💏)
            0x1F490,  # Bouquet (💐)
            0x1F491,  # Couple with heart (💑)
            0x1F339,  # Rose (🌹)
            0x1F940,  # Wilted flower (🥀)
            0x1F3E9,  # Love hotel (🏩)
            0x1F60D,  # Heart eyes (😍)
            0x1F970,  # Smiling face with hearts (🥰)
            0x1F618,  # Face blowing kiss (😘)
            0x1F617,  # Kissing face (😗)
            0x1F61A,  # Kissing face closed eyes (😚)
            0x1F619,  # Kissing face smiling eyes (😙)
            0x1F63B,  # Cat heart eyes (😻)
            0x1F63D,  # Cat kiss (😽)
            0x1FAC0,  # Anatomical heart (🫀)
            0x1F5A4,  # Black heart (🖤)
            0x1F90D,  # White heart (🤍)
            0x1F90E,  # Brown heart (🤎)
            0x1F9E1,  # Orange heart (🧡)
        }
        or 0x1F493 <= code <= 0x1F49F  # Hearts range (💓, 💔, 💕, 💖, 💗, 💘, 💙, 💚, 💛, 💜, 💝, 💞, 💟)
    )


def strip_romantic_emojis(text: str) -> str:
    """Removes all romantic/heart/kiss emojis from text.
    Ensures our account never sends romantic emojis on behalf of the owner.
    """
    if not text:
        return ""

    out: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        code = ord(ch)
        if is_romantic_char(code):
            # Skip this romantic emoji and any attached variation selectors / joiners
            i += 1
            while i < len(text) and ord(text[i]) in (0xFE0F, 0xFE0E, 0x200D):
                i += 1
            continue
        out.append(ch)
        i += 1

    return "".join(out).strip()


def get_mirror_emoji_reply(comment_text: str) -> Optional[str]:
    """If comment_text consists only of emojis, returns a mirror of non-romantic emojis.

    Strict Anti-Romance Policy:
    - Never echoes hearts, kisses, or romantic symbols on behalf of Baxtiyorjon Gaziyev.
    - If user sends mixed emojis (e.g. '🔥❤️🔥🔥'), romantic emojis are removed -> '🔥🔥🔥'.
    - If user sends purely romantic emojis (e.g. '❤️❤️❤️', '😍', '😘'), returns a professional
      handshake '🤝' instead of mirroring romantic symbols.
    - If text contains letters/words, returns None (routed to contextual AI generator).
    """
    if not is_pure_emoji_text(comment_text):
        return None

    cleaned_emojis = "".join(comment_text.split())
    non_romantic = strip_romantic_emojis(cleaned_emojis)

    if non_romantic:
        return non_romantic
    # If the user sent only romantic emojis (e.g. ❤️❤️❤️ or 😍), respond with a professional handshake
    return "🤝"


def get_short_emotional_reaction(comment_text: str) -> Optional[str]:
    """Deprecated: All textual comments must be evaluated in context of the video
    caption by the AI router to prevent inappropriate canned laughing or crying.
    Pure emoji comments continue to be handled by get_mirror_emoji_reply.
    """
    return None
