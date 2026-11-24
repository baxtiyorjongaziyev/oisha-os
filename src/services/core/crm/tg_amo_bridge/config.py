"""Bridge configuration. Reads env/settings lazily; settings.py is coordinator-owned."""
from __future__ import annotations

import os
from typing import Optional


def _secret(value) -> str:
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return str(value or "")


def bridge_enabled() -> bool:
    return os.getenv("TG_AMO_BRIDGE_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}


def amojo_id() -> str:
    """amoJo account uuid (NOT the numeric amoCRM account id)."""
    return os.getenv("AMOCRM_AMOJO_ID", "").strip()


def scope_id() -> Optional[str]:
    return os.getenv("AMOCRM_AMOJO_SCOPE_ID", "").strip() or None


def channel_id() -> str:
    from src.settings import settings

    return str(getattr(settings, "AMOCRM_CHAT_CHANNEL_ID", "") or "")


def channel_secret() -> str:
    from src.settings import settings

    return _secret(getattr(settings, "AMOCRM_CHAT_CHANNEL_SECRET", None))


def build_amojo_client():
    """Return a configured AmoJoClient or None when config is incomplete."""
    from .amojo_client import AmoJoClient

    aid, cid, sec = amojo_id(), channel_id(), channel_secret()
    if not (aid and cid and sec):
        return None
    return AmoJoClient(aid, cid, sec, scope_id=scope_id())


def automerge_enabled() -> bool:
    """Enable proactive Telegram-to-contact linking & duplicate deal auto-merge."""
    return os.getenv("TG_AMO_AUTOMERGE_ENABLED", "1").strip().lower() in {"1", "true", "yes", "on"}


def automerge_dry_run() -> bool:
    return os.getenv("TG_AMO_AUTOMERGE_DRY_RUN", "0").strip().lower() in {"1", "true", "yes", "on"}


def automerge_interval_seconds() -> int:
    raw = os.getenv("TG_AMO_AUTOMERGE_INTERVAL_SECONDS", "300").strip()
    try:
        return max(30, int(raw))
    except ValueError:
        return 300


def automerge_loss_reason_id() -> Optional[int]:
    """Optional amoCRM loss_reason_id for closed duplicate Telegram leads."""
    raw = os.getenv("TG_AMO_MERGE_LOSS_REASON_ID", "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return None
