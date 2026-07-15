"""Shared database helpers — single source of truth.

These utilities were previously duplicated across ``database.py``,
``database_pool.py``, ``db/connection.py`` and ``db/turso.py`` with slightly
divergent behaviour. They now live here so every layer normalizes URLs and
unwraps secret values identically.
"""
from __future__ import annotations

from typing import Any

# Zero-width byte-order mark. Written as an escape (not a literal invisible
# char) so editors/formatters cannot silently drop or mangle it.
_BOM = "\ufeff"


def normalize_turso_url(url: str) -> str:
    """Convert a ``libsql://`` URL to the ``https://`` form libsql expects."""
    if url and url.startswith("libsql://"):
        return "https://" + url[len("libsql://"):]
    return url


def setting_text(value: Any) -> str:
    """Return a clean string for a settings value.

    Unwraps Pydantic ``SecretStr`` (``get_secret_value``), strips a leading BOM
    and surrounding whitespace, then removes any remaining control characters
    (``ord < 32``). This is the strictest of the former variants and is now the
    canonical behaviour everywhere.
    """
    if value is None:
        return ""
    getter = getattr(value, "get_secret_value", None)
    if callable(getter):
        try:
            value = getter()
        except Exception:
            value = str(value)

    text = str(value).replace(_BOM, "").strip()
    return "".join(char for char in text if ord(char) >= 32)
