import pytest
from src.services.core.instagram.emoji_utils import (
    get_mirror_emoji_reply,
    strip_romantic_emojis,
    is_romantic_char,
)


def test_is_romantic_char_detects_all_romance():
    assert is_romantic_char(ord("❤️"[0])) or is_romantic_char(0x2764)
    assert is_romantic_char(ord("😍"))
    assert is_romantic_char(ord("🥰"))
    assert is_romantic_char(ord("😘"))
    assert is_romantic_char(ord("💋"))
    assert is_romantic_char(ord("🌹"))
    assert is_romantic_char(ord("💖"))
    assert is_romantic_char(ord("💔"))
    # Non-romantic emojis should return False
    assert not is_romantic_char(ord("🔥"))
    assert not is_romantic_char(ord("👏"))
    assert not is_romantic_char(ord("🤝"))
    assert not is_romantic_char(ord("🙌"))
    assert not is_romantic_char(ord("✨"))
    assert not is_romantic_char(ord("😂"))


def test_strip_romantic_emojis():
    assert strip_romantic_emojis("🔥❤️🔥🔥") == "🔥🔥🔥"
    assert strip_romantic_emojis("❤️🔥🔥") == "🔥🔥"
    assert strip_romantic_emojis("😍👏") == "👏"
    assert strip_romantic_emojis("😘👍") == "👍"
    assert strip_romantic_emojis("❤️❤️❤️") == ""
    assert strip_romantic_emojis("😍") == ""
    assert strip_romantic_emojis("Katta rahmat! ❤️") == "Katta rahmat!"
    assert strip_romantic_emojis("Ajoyib ish! 😍👏") == "Ajoyib ish! 👏"
    assert strip_romantic_emojis("Fikringiz uchun rahmat! 🤝") == "Fikringiz uchun rahmat! 🤝"


def test_get_mirror_emoji_reply_anti_romance():
    # Pure non-romantic emojis get mirrored
    assert get_mirror_emoji_reply("🔥🔥🔥") == "🔥🔥🔥"
    assert get_mirror_emoji_reply("😂😂😂") == "😂😂😂"
    assert get_mirror_emoji_reply("👏") == "👏"

    # Mixed emojis: romantic emojis stripped, remaining mirrored
    assert get_mirror_emoji_reply("🔥❤️🔥🔥") == "🔥🔥🔥"
    assert get_mirror_emoji_reply("😍👏") == "👏"

    # Pure romantic emojis: replaced with professional handshake 🤝
    assert get_mirror_emoji_reply("❤️❤️❤️") == "🤝"
    assert get_mirror_emoji_reply("❤️") == "🤝"
    assert get_mirror_emoji_reply("😍") == "🤝"
    assert get_mirror_emoji_reply("🥰😘") == "🤝"
    assert get_mirror_emoji_reply("🌹🌹") == "🤝"

    # Text comments return None (routed to AI)
    assert get_mirror_emoji_reply("Salom") is None
    assert get_mirror_emoji_reply("Rahmat aka ❤️") is None
