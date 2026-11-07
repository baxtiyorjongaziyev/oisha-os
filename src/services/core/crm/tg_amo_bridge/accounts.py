"""Manager Telegram accounts served by the bridge.

Stage 2: only the owner account, which reuses the production userbot client
(app_ctx.client). Per-manager Telethon sessions (Rayxona, Mumtozmaxal,
Shahnoza) are a later stage and need dedicated, non-production sessions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class Account:
    key: str
    display_name: str
    source_external_id: str
    get_client: Callable[[], Any]


def _owner_client():
    from src.context import app_ctx

    return getattr(app_ctx, "client", None)


OWNER = Account(
    key="owner",
    display_name="Baxtiyorjon Gaziyev",
    source_external_id="oisha-tg-owner",
    get_client=_owner_client,
)

_ACCOUNTS = {OWNER.key: OWNER}


def all_accounts() -> list[Account]:
    return list(_ACCOUNTS.values())


def by_source(source_external_id: Optional[str]) -> Account:
    """Account for an amoJo source id; unknown/missing falls back to owner."""
    for acc in _ACCOUNTS.values():
        if acc.source_external_id == source_external_id:
            return acc
    return OWNER
