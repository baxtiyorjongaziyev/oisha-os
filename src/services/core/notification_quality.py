"""Fail closed on unresolved or example data in automated notifications."""
import re
from html import unescape


def notification_is_publishable(value: object) -> bool:
    """Inspect visible text, allowing record IDs only inside link targets."""
    if not isinstance(value, str) or not value.strip():
        return False
    text = unescape(re.sub(r"<[^>]*>", "", value)).casefold()
    for apostrophe in ("’", "‘", "ʻ", "ʼ", "`"):
        text = text.replace(apostrophe, "'")
    blocked = (
        "noma'lum", "nomalum", "mas'ul aniqlansin", "mas'ul belgilanmagan",
        "buyurtmachi a", "loyiha #", "ðÿ", "â€", "�",
    )
    return not any(token in text for token in blocked) and not re.search(
        r"\brec[a-z0-9]{10,}\b", text
    )
