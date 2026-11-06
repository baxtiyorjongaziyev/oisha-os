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


async def resolve_amojo_id(crm_client) -> Optional[str]:
    """Read the amoJo account uuid from amoCRM through Oisha's own client.

    GET /api/v4/account?with=amojo_id. Result is cached in the process env var
    AMOCRM_AMOJO_ID so config.amojo_id() picks it up; nothing is written to disk.
    """
    import asyncio
    import os

    import requests

    existing = config.amojo_id()
    if existing:
        return existing
    if crm_client is None:
        return None

    def _fetch() -> Optional[str]:
        try:
            resp = requests.get(
                f"{crm_client.base_url}/api/v4/account",
                params={"with": "amojo_id"},
                headers=crm_client._get_headers(),
                timeout=15,
            )
            if resp.status_code != 200:
                logger.error("[TG-AMO] account lookup HTTP %s", resp.status_code)
                return None
            return (resp.json() or {}).get("amojo_id")
        except Exception as exc:
            logger.error("[TG-AMO] account lookup failed: %s", type(exc).__name__)
            return None

    found = await asyncio.to_thread(_fetch)
    if found:
        # pyrefly: ignore[unnecessary-type-conversion]
        os.environ["AMOCRM_AMOJO_ID"] = found
        logger.info("[TG-AMO] amoJo account id resolved from amoCRM")
    return found


def get_store() -> MessageStore:
    return _store


async def start_from_app_ctx() -> bool:
    """Boot entry point: never raises; no-op when the flag is off.

    Must run BEFORE other userbot handlers are registered, because some of
    them raise StopPropagation and would starve a later-registered handler.
    """
    if not config.bridge_enabled():
        return False
    try:
        from src.context import app_ctx
        from src.services.core.crm.non_client_filter import is_sender_marked_as_non_client

        controller = getattr(app_ctx, "msg_controller", None)
        crm_client = getattr(getattr(controller, "crm", None), "amocrm", None)
        db = getattr(controller, "db", None)

        async def _is_non_client(phone=None, user_id=None, name=None):
            return await is_sender_marked_as_non_client(
                crm_client, phone=phone, user_id=user_id, name=name, db=db
            )

        return await start(is_non_client=_is_non_client, crm_client=crm_client)
    except Exception as exc:
        logger.error("[TG-AMO] start failed: %s", type(exc).__name__)
        return False


async def start(is_non_client=None, crm_client=None) -> bool:
    """Connect channel (if scope_id unknown) and attach handlers. No-op when disabled."""
    if not config.bridge_enabled():
        return False
    await resolve_amojo_id(crm_client)
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
