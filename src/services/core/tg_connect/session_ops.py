"""Saqlangan menejer sessiyasi bilan amallar: dialoglar roʻyxati va uzish."""
from __future__ import annotations

from typing import Any, Callable

from src.services.core.tg_connect import store

DIALOG_LIMIT = 1000
SessionClientFactory = Callable[[str], Any]


def default_session_client(session: str) -> Any:
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    from src.settings import settings
    from src.services.core.tg_connect.qr_flow import DEVICE_MODEL

    return TelegramClient(StringSession(session), settings.API_ID, settings.API_HASH,
                          device_model=DEVICE_MODEL, system_version="Oisha OS", app_version="1.0")


def _kind(dialog: Any) -> str:
    if getattr(dialog, "is_user", False):
        return "private"
    if getattr(dialog, "is_channel", False) and not getattr(dialog, "is_group", False):
        return "channel"
    return "group"


async def list_dialogs(session: str, factory: SessionClientFactory = default_session_client) -> list[dict]:
    """Faqat sarlavha va turini oladi; xabar matni oʻqilmaydi."""
    client = factory(session)
    await client.connect()
    try:
        out = []
        async for d in client.iter_dialogs(limit=DIALOG_LIMIT):
            out.append({"id": int(d.id), "title": d.name or "—", "kind": _kind(d)})
        return out
    finally:
        await client.disconnect()


async def revoke(db, telegram_id: int, actor: str, ip: str | None = None,
                 factory: SessionClientFactory = default_session_client) -> dict | None:
    """Sessiyani Telegram serverida yopadi (Devices roʻyxatidan oʻchadi) va DB dan oʻchiradi.

    Telegram tomoni xato bersa ham DB dagi sessiya baribir oʻchiriladi: Oisha uni boshqa
    ishlata olmaydi, menejer esa Devices boʻlimidan qoʻlda ham yopishi mumkin.
    """
    acc = await store.account(db, telegram_id)
    if not acc or acc.get("status") != "connected":
        return None
    remote_ok = False
    if acc.get("session_enc"):
        client = None
        try:
            client = factory(store.decrypt_session(telegram_id, acc["session_enc"]))
            await client.connect()
            remote_ok = bool(await client.log_out())
        except Exception:  # noqa: BLE001 - quyida jurnalda koʻrinadi
            remote_ok = False
        finally:
            if client is not None and not remote_ok:
                try:
                    await client.disconnect()
                except Exception:  # noqa: BLE001
                    pass
    await store.mark_revoked(db, telegram_id)
    await store.audit(db, telegram_id, "revoked", actor, {"telegram_logout": remote_ok}, ip)
    # False boʻlsa menejer Telegram -> Devices dan "Oisha Connect"ni qoʻlda yopishi kerak.
    return {"telegram_logout": remote_ok}
