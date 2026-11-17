"""Production ulanishi: app_ctx klientlaridan Deps yigʻish, kunlik job, callback.

boot.py (Coordinator fayli) ga ulash:
    from src.services.core.community_sync.wiring import scheduled_job, register_callbacks
    scheduler.add_job(scheduled_job, "cron", hour=10, minute=0, args=[app_ctx])
    register_callbacks(app_ctx.bot_client, app_ctx)
"""

import logging

from src.settings import settings

from .adapters.amocrm import AmoAdapter
from .adapters.google import GoogleAdapter
from .adapters.telegram import TelegramAdapter, drip
from .approval import handle_callback
from .collector import collect
from .runner import Deps, run_once
from .store import SyncStore

logger = logging.getLogger(__name__)


def _cfg(name: str, default):
    return getattr(settings, name, default)


def _owner_id() -> int:
    return int(getattr(settings, "OWNER_ID", 0) or 0)


def _notifier(bot):
    async def notify(text: str, buttons=None):
        if not bot or not _owner_id():
            logger.info("[COMMUNITY_SYNC] %s", text)
            return
        from telethon import Button

        rows = [[Button.inline(label, data.encode())] for label, data in buttons or []]
        await bot.send_message(_owner_id(), text, buttons=rows or None)

    return notify


def _adapters(app_ctx, store) -> list:
    out = []
    try:
        from src.services.core.gcontacts import GoogleContactsSync

        creds = _cfg("COMMUNITY_SYNC_GCONTACTS_CREDS", "service_account.json")
        out.append(GoogleAdapter(GoogleContactsSync(credentials_path=creds)))
    except Exception as exc:
        logger.error("[COMMUNITY_SYNC] google adapter: %s", exc)
    try:
        from src.services.core.crm.amocrm_sync import AmoCRMSync

        out.append(AmoAdapter(AmoCRMSync()))
    except Exception as exc:
        logger.error("[COMMUNITY_SYNC] amocrm adapter: %s", exc)
    out.append(TelegramAdapter(app_ctx.client, store))
    return out


def build_deps(app_ctx) -> Deps:
    store = SyncStore()
    client = app_ctx.client
    folder_id = int(_cfg("COMMUNITY_SYNC_FOLDER_ID", 13))

    async def _collect():
        return await collect(client, folder_id)

    async def _drip(store_, people, limit, now):
        return await drip(store_, client, people, limit, now)

    return Deps(
        store=store,
        collect=_collect,
        adapters=_adapters(app_ctx, store),
        notify=_notifier(getattr(app_ctx, "bot_client", None)),
        drip=_drip,
        enabled=bool(_cfg("COMMUNITY_SYNC_ENABLED", False)),
        dry_run=bool(_cfg("COMMUNITY_SYNC_DRY_RUN", True)),
        bulk_threshold=int(_cfg("COMMUNITY_SYNC_BULK_THRESHOLD", 20)),
        tg_daily_limit=int(_cfg("COMMUNITY_SYNC_TG_DAILY_LIMIT", 120)),
        folder_id=folder_id,
    )


async def scheduled_job(app_ctx, dry_run=None) -> dict:
    if not getattr(app_ctx, "client", None):
        logger.warning("[COMMUNITY_SYNC] userbot klienti yöq, ötkazildi")
        return {"status": "no_client"}
    deps = build_deps(app_ctx)
    await deps.store.ensure_schema()
    try:
        return await run_once(deps, dry_run=dry_run)
    except Exception as exc:
        logger.exception("[COMMUNITY_SYNC] run xato: %s", exc)
        return {"status": "error", "error": str(exc)}


def register_callbacks(bot, app_ctx) -> None:
    from telethon import events

    from src.time_utils import get_local_now

    @bot.on(events.CallbackQuery(pattern=b"cs:"))
    async def _on_cs(event):
        if event.sender_id != _owner_id():
            return
        store = SyncStore()
        ok = await handle_callback(event.data.decode(), store, now=get_local_now())
        await event.answer("Qabul qilindi" if ok else "Eskirgan tugma")
        if ok and event.data == b"cs:approve":
            await scheduled_job(app_ctx, dry_run=False)
