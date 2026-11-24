"""Bridge lifecycle: build clients, connect channel, register Telegram handlers."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from . import accounts, config, inbound
from .amojo_client import AmoJoClient
from .automerge import TelegramDealAutoMerger
from .reconciler import automerge_loop
from .store import MessageStore

logger = logging.getLogger("TgAmoBridge.runtime")

_amojo: Optional[AmoJoClient] = None
_store = MessageStore()
_merger: Optional[TelegramDealAutoMerger] = None
_reconciler_task: Optional[asyncio.Task] = None


def get_merger() -> Optional[TelegramDealAutoMerger]:
    return _merger


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


async def resolve_manager_ref_id(crm_client) -> Optional[str]:
    """amojo uuid of the amoCRM user that owns the API token.

    Manager messages written in Telegram are echoed to amoJo with
    sender={"ref_id": <this uuid>}. Cached in AMOCRM_BRIDGE_MANAGER_REF_ID.
    """
    import asyncio
    import os

    import requests

    existing = os.getenv("AMOCRM_BRIDGE_MANAGER_REF_ID")
    if existing:
        return existing
    if crm_client is None:
        return None

    def _fetch() -> Optional[str]:
        try:
            headers = crm_client._get_headers()
            acc = requests.get(f"{crm_client.base_url}/api/v4/account", headers=headers, timeout=15)
            user_id = (acc.json() or {}).get("current_user_id") if acc.status_code == 200 else None
            if not user_id:
                logger.error("[TG-AMO] current_user_id lookup HTTP %s", acc.status_code)
                return None
            resp = requests.get(
                f"{crm_client.base_url}/api/v4/users/{int(user_id)}",
                params={"with": "amojo_id"},
                headers=headers,
                timeout=15,
            )
            if resp.status_code != 200:
                logger.error("[TG-AMO] user amojo_id lookup HTTP %s", resp.status_code)
                return None
            return (resp.json() or {}).get("amojo_id")
        except Exception as exc:
            logger.error("[TG-AMO] manager ref lookup failed: %s", type(exc).__name__)
            return None

    found = await asyncio.to_thread(_fetch)
    if found:
        # pyrefly: ignore[unnecessary-type-conversion]
        os.environ["AMOCRM_BRIDGE_MANAGER_REF_ID"] = str(found)
        logger.info("[TG-AMO] manager amojo ref resolved from amoCRM")
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

        return await start(is_non_client=_is_non_client, crm_client=crm_client, db=db)
    except Exception as exc:
        logger.error("[TG-AMO] start failed: %s", type(exc).__name__)
        return False


async def start(is_non_client=None, crm_client=None, db=None) -> bool:
    """Connect channel (if scope_id unknown) and attach handlers. No-op when disabled."""
    global _merger, _reconciler_task
    if not config.bridge_enabled():
        return False
    await resolve_amojo_id(crm_client)
    await resolve_manager_ref_id(crm_client)
    amojo = get_amojo()
    if amojo is None:
        logger.error("[TG-AMO] enabled but AMOCRM_AMOJO_ID / channel id / secret missing")
        return False
    if not amojo.scope_id and not await amojo.connect():
        logger.error("[TG-AMO] channel connect failed; bridge not started")
        return False
    await _store.ensure()
    if crm_client is not None and config.automerge_enabled():
        _merger = TelegramDealAutoMerger(
            crm=crm_client,
            amojo=amojo,
            store=_store,
            db=db,
            dry_run=config.automerge_dry_run(),
            loss_reason_id=config.automerge_loss_reason_id(),
        )
    else:
        _merger = None

    started = 0
    for acc in accounts.all_accounts():
        client = acc.get_client()
        if client is None:
            logger.warning("[TG-AMO] account %s has no client; skipped", acc.key)
            continue
        inbound.register(
            client, acc, amojo, _store, is_non_client=is_non_client, merger=_merger
        )
        started += 1
    if started > 0 and _merger is not None and (_reconciler_task is None or _reconciler_task.done()):
        _reconciler_task = asyncio.create_task(
            automerge_loop(_merger, interval_seconds=config.automerge_interval_seconds()),
            name="tg_amo_automerge_loop",
        )
    logger.info("[TG-AMO] bridge started for %d account(s) (automerge=%s)", started, _merger is not None)
    return started > 0
