"""QR orqali Telegram sessiyasini olish (Telethon ``qr_login``).

Har bir menejer uchun bitta kutilayotgan urinish (jarayon xotirasida). Fon vazifasi
QR tasdiqlanishini kutadi; sahifa ``status`` ni soʻrab turadi. Telegram kodi yoki
SMS hech qachon soʻralmaydi. 2FA boʻlsa parol bir marta ``sign_in`` ga beriladi va
hech qayerda saqlanmaydi yoki loglanmaydi.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

QR_TTL_S = 25          # Telegram QR tokeni ~30s yashaydi; undan oldin yangilaymiz
ATTEMPT_TTL_S = 300    # butun urinish 5 daqiqa
DEVICE_MODEL = "Oisha Connect"

# state: waiting | password_required | done | wrong_account | expired | failed


@dataclass
class Attempt:
    telegram_id: int
    client: Any
    state: str = "waiting"
    url: Optional[str] = None
    started: float = field(default_factory=time.monotonic)
    task: Optional[asyncio.Task] = None
    result: Optional[dict] = None


ClientFactory = Callable[[], Any]
OnDone = Callable[[int, dict], Awaitable[None]]

_attempts: dict[int, Attempt] = {}


def default_client_factory() -> Any:
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    from src.settings import settings

    if not settings.API_ID or not settings.API_HASH:
        raise RuntimeError("telegram_api_not_configured")
    return TelegramClient(StringSession(), settings.API_ID, settings.API_HASH,
                          device_model=DEVICE_MODEL, system_version="Oisha OS", app_version="1.0")


def _password_needed(exc: BaseException) -> bool:
    return type(exc).__name__ == "SessionPasswordNeededError"


async def _finish(att: Attempt, on_done: OnDone) -> None:
    me = await att.client.get_me()
    if getattr(me, "id", None) != att.telegram_id:
        # Boshqa odamning akkaunti skanerlangan: sessiyani darhol yopamiz.
        att.state = "wrong_account"
        await _safe(att.client.log_out())
        return
    att.result = {"session": att.client.session.save(), "username": getattr(me, "username", None)}
    await on_done(att.telegram_id, att.result)
    att.state = "done"
    await _safe(att.client.disconnect())


async def _run(att: Attempt, on_done: OnDone) -> None:
    try:
        await att.client.connect()
        qr = await att.client.qr_login()
        while time.monotonic() - att.started < ATTEMPT_TTL_S:
            att.url = qr.url
            try:
                await qr.wait(timeout=QR_TTL_S)
                break
            except asyncio.TimeoutError:
                await qr.recreate()
        else:
            att.state = "expired"
            await _safe(att.client.disconnect())
            return
        await _finish(att, on_done)
    except Exception as exc:  # noqa: BLE001 - holat sahifaga qaytariladi
        if _password_needed(exc):
            att.state = "password_required"
            asyncio.get_running_loop().create_task(_expire_later(att))
            return
        logger.warning("tg_connect qr flow failed: %s", type(exc).__name__)
        att.state = "failed"
        await _safe(att.client.disconnect())


async def _expire_later(att: Attempt) -> None:
    """2FA bosqichida tashlab ketilgan urinishni muddat tugagach yopadi (hech kim soʻramasa ham)."""
    await asyncio.sleep(max(0.0, ATTEMPT_TTL_S - (time.monotonic() - att.started)))
    if att.state == "password_required":
        att.state = "expired"
        await _safe(att.client.disconnect())


async def _safe(coro) -> None:
    try:
        await coro
    except Exception:  # noqa: BLE001
        pass


async def start(telegram_id: int, on_done: OnDone,
                factory: ClientFactory = default_client_factory) -> Attempt:
    old = _attempts.pop(telegram_id, None)
    if old is not None:
        await cancel_attempt(old)
    att = Attempt(telegram_id=telegram_id, client=factory())
    _attempts[telegram_id] = att
    att.task = asyncio.create_task(_run(att, on_done))
    for _ in range(50):  # QR URL tayyor boʻlishini qisqa kutamiz
        if att.url or att.state != "waiting":
            break
        await asyncio.sleep(0.1)
    return att


def get(telegram_id: int) -> Optional[Attempt]:
    att = _attempts.get(telegram_id)
    if att and att.state in ("waiting", "password_required") and time.monotonic() - att.started > ATTEMPT_TTL_S:
        att.state = "expired"
        # 2FA da tashlab ketilgan urinish: Telegram ulanishini ham yopamiz.
        asyncio.get_running_loop().create_task(cancel_attempt(att))
    return att


async def submit_password(telegram_id: int, password: str, on_done: OnDone) -> str:
    att = _attempts.get(telegram_id)
    if att is None or att.state != "password_required":
        return "no_attempt"
    try:
        await att.client.sign_in(password=password)
    except Exception as exc:  # noqa: BLE001
        logger.info("tg_connect 2fa rejected: %s", type(exc).__name__)
        return "bad_password"
    await _finish(att, on_done)
    return att.state


async def cancel_attempt(att: Attempt) -> None:
    if att.task and not att.task.done():
        att.task.cancel()
    if att.state != "done":
        await _safe(att.client.disconnect())


def public_view(att: Optional[Attempt]) -> dict:
    if att is None:
        return {"state": "none"}
    view: dict = {"state": att.state}
    if att.state == "waiting" and att.url:
        view["qr_url"] = att.url
    return view


def clear(telegram_id: int) -> None:
    _attempts.pop(telegram_id, None)
