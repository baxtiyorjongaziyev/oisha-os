"""Local presence checks only; never return or log credential values."""
from __future__ import annotations

import logging
import os
from threading import Lock

logger = logging.getLogger(__name__)
REQUIRED_GROUPS = (
    ("META_PAGE_ACCESS_TOKEN",),
    ("META_INSTAGRAM_USER_ID", "META_INSTAGRAM_ACCOUNT_ID"),
    ("META_APP_SECRET",),
    ("META_VERIFY_TOKEN", "INSTAGRAM_VERIFY_TOKEN"),
)
ACTION = (
    "Check the service environment source for the missing keys; restore through "
    "the approved secret workflow, restart the service, then verify health. "
    "Do not paste credential values into logs or alerts."
)
_lock = Lock()
_alerted = False


def _present(value) -> bool:
    if value is None:
        return False
    getter = getattr(value, "get_secret_value", None)
    value = getter() if callable(getter) else value
    return isinstance(value, str) and bool(value.strip())


def check_meta_config(settings_obj=None, environ=None) -> dict:
    """Inspect effective runtime config, with one error per outage per process.

    Aliases satisfy a group; output uses its canonical key name. This does not
    validate tokens or reread the on-disk .env behind cached runtime settings.
    """
    global _alerted
    if settings_obj is None:
        from src.settings import settings
        settings_obj = settings
    env = os.environ if environ is None else environ
    missing = [
        group[0] for group in REQUIRED_GROUPS
        if not any(
            _present(env.get(key)) or _present(getattr(settings_obj, key, None))
            for key in group
        )
    ]
    with _lock:
        if missing and not _alerted:
            logger.error(
                "instagram_not_configured missing_keys=%s action=%s",
                ",".join(missing), ACTION,
            )
        _alerted = bool(missing)
    return {"configured": not missing, "missing_keys": missing}


def add_meta_health(checks: dict, problems: list) -> None:
    checks["meta_config"] = check_meta_config()
    if not checks["meta_config"]["configured"]:
        problems.append("instagram_not_configured")
