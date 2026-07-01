"""Database module — thin facade over src.db package.

All production code should import from here:
    from src.database import Database

The Database class delegates to repositories in src/db/.
TursoAdapter is kept here for backward compatibility.
"""
from __future__ import annotations

import logging
from typing import Any

from src.db import Database, get_db, db  # noqa: F401 — re-export
from src.db.turso import TursoAdapter  # noqa: F401 — backward compat
from src.settings import settings  # noqa: F401 — test_turso_adapter expects this

try:
    import libsql  # noqa: F401
except ImportError:
    libsql = None

logger = logging.getLogger(__name__)

# Backward compat: _is_benign_schema_error used by some modules
from src.db.repositories.base import _is_benign_schema_error  # noqa: F401

# Backward compat helpers used by tests and some modules
def _normalize_turso_url(url: str) -> str:
    if url.startswith("libsql://"):
        return "https://" + url[len("libsql://"):]
    return url
