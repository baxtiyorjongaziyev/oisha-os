"""Canonical Uzbekistan (+998) phone formatting for amoCRM writes."""
from __future__ import annotations

import re
from typing import Any

# Valid Uzbekistan 2-digit mobile and regional operator prefixes
# (includes newer mobile codes 87 and 92 observed in live amoCRM contacts).
UZ_PHONE_PREFIXES = frozenset(
    {
        "20", "33", "50", "55", "61", "62", "65", "66", "67", "69",
        "70", "71", "72", "73", "74", "75", "76", "77", "78", "79",
        "87", "88", "90", "91", "92", "93", "94", "95", "97", "98", "99",
    }
)

_FLOAT_ZERO_RE = re.compile(r"^(\+?\d+)\.0+$")
_PHONE_CHARS_RE = re.compile(r"^\(?\+?[\d\s\-().]+$")


def normalize_amocrm_phone(phone: Any) -> str:
    """Normalize Uzbekistan phone numbers to E.164 ``+998XXXXXXXXX`` format.

    - Handles 9-digit local numbers (``901234567``), 12-digit ``998...`` without
      ``+``, formatted ``+998 ...`` or ``(+998) ...``, ``0998``/``8998``/``00998``
      variants, and Excel float strings (``998974077229.0``).
    - Preserves foreign international numbers (e.g. ``+7...``, ``+1...``,
      ``+44 (0)20 7946 0958``, ``+992...``) and ambiguous national formats
      (such as 10-digit ``8...``/``0...``) verbatim without ever corrupting them.
    - Returns empty string for blank inputs and preserves non-phone/ambiguous
      strings verbatim so nothing is silently corrupted.
    """
    raw = str(phone or "").strip()
    if not raw:
        return ""

    # Strip spreadsheet float suffix like "998974077229.0" before digit extraction.
    float_match = _FLOAT_ZERO_RE.fullmatch(raw)
    candidate = float_match.group(1) if float_match else raw

    if not _PHONE_CHARS_RE.fullmatch(candidate):
        return raw

    digits = re.sub(r"\D+", "", candidate)
    if not digits:
        return raw

    has_plus = candidate.lstrip("(").startswith("+")

    if len(digits) == 12 and digits.startswith("998") and digits[3:5] in UZ_PHONE_PREFIXES:
        return f"+{digits}"
    if len(digits) == 9 and not has_plus and digits[:2] in UZ_PHONE_PREFIXES:
        return f"+998{digits}"
    if (
        len(digits) == 13
        and digits[:4] in ("0998", "8998")
        and digits[4:6] in UZ_PHONE_PREFIXES
    ):
        return f"+{digits[1:]}"
    if (
        len(digits) == 14
        and not has_plus
        and digits.startswith("00998")
        and digits[5:7] in UZ_PHONE_PREFIXES
    ):
        return f"+{digits[2:]}"

    return raw
