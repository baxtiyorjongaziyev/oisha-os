"""Bridge lifecycle: build clients, connect channel, register Telegram handlers."""
from __future__ import annotations

import logging
from typing import Optional

from . import accounts, config, inbound
from .amojo_client import AmoJoClient
from .store import MessageStore

logger = logging.getLogger("TgAmoBridge.runtime")

_amojo: Optional[AmoJoClient] = None
_store = MessageStore()


def get_amojo() -> Optional[AmoJoClient]:
    global _amojo
    if _amojo is None and config.bridge_enabled():
        _amojo = config.build_amojo_client()
    return _amojo


def get_store() -> MessageStore:
    return _store


async def start(is_non_client=None) -> bool:
    """Connect channel (if scope_id unknown) and attach handlers. No-op when disabled."""
    if not config.bridge_enabled():
        return False
    amojo = get_amojo()
    if amojo is None:
        logger.error("[TG-AMO] enabled but AMOCRM_AMOJO_ID / channel id / secret missing")
        return False
    if not amojo.scope_id and not await amojo.connect():
        logger.error("[TG-AMO] channel connect failed; bridge not started")
        return False
    await _store.ensure()
    started = 0
    for acc in accounts.all_accounts():
        client = acc.get_client()
        if client is None:
            logger.warning("[TG-AMO] account %s has no client; skipped", acc.key)
            continue
        inbound.register(client, acc, amojo, _store, is_non_client=is_non_client)
        started += 1
    logger.info("[TG-AMO] bridge started for %d account(s)", started)
    return started > 0
