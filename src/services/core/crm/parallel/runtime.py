"""Runtime wiring, feature controls and seller identity mapping."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import HTTPException

from src.api.rbac import Permission, Role, has_permission

from .remote import AmoRemote
from .store import Store
from .sync import Sync

logger = logging.getLogger(__name__)
_store = None
_initialized = False
_wake = asyncio.Event()
_lock = asyncio.Lock()


def enabled():
    return os.getenv("OISHA_CRM_PARALLEL_ENABLED", "0") == "1"


def writable():
    return enabled() and os.getenv("OISHA_CRM_PARALLEL_WRITEBACK", "0") == "1"


async def get_store():
    global _store, _initialized
    if _store is None:
        from src.database_pool import db_pool
        _store = Store(db_pool)
    if not _initialized:
        async with _lock:
            if not _initialized:
                await _store.init()
                _initialized = True
    return _store


def get_remote():
    from src.api.routes.state import api_state
    client = api_state.amocrm_instance
    if client is None:
        from src.api.routes.amocrm_integration import _get_amocrm_instance
        client = _get_amocrm_instance()
    if client is None:
        raise HTTPException(503, "amoCRM ulanmagan")
    return AmoRemote(client)


def seller_id(principal):
    if has_permission(principal, Permission.LEAD_READ_ALL):
        return None
    if principal.role != Role.SELLER:
        raise HTTPException(403, "CRM ruxsati yo'q")
    try:
        mapping = json.loads(os.getenv("OISHA_CRM_SELLER_MAP_JSON", "{}"))
        value = mapping.get(principal.subject)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError("unmapped")
        return value
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(403, "Sotuvchi amoCRM foydalanuvchisiga bog'lanmagan")


async def owned_lead(store, lead_id, principal):
    owner = seller_id(principal)
    lead = await store.get("leads", lead_id)
    if lead is None or (owner is not None and lead["responsible_user_id"] != owner):
        raise HTTPException(404, "Bitim topilmadi")
    return lead


async def run_once():
    if not enabled():
        return {"state": "disabled"}
    store = await get_store()
    async with _lock:
        return await Sync(store, get_remote(), writeback=writable()).run()


async def worker():
    while True:
        try:
            if enabled():
                await get_store()
                await run_once()
        except Exception as exc:
            logger.warning("Parallel CRM sync unavailable: %s", type(exc).__name__)
        _wake.clear()
        try:
            await asyncio.wait_for(_wake.wait(), timeout=60)
        except TimeoutError:
            pass


def wake():
    _wake.set()


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(worker(), name="parallel-crm")
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
