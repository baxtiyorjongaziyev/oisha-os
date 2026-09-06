"""Userbot Telethon session string'ining Turso DB'da davomiy saqlanishi + yagona
egalik lock.

Ikki muammoni hal qiladi
========================

1. **Session yo'qolishi restart'da.** ``session_keeper`` session string'ni
   ``data/userbot_session_string.txt`` fayliga yozadi. Oracle VM'da ``data/``
   efemer bo'lса yoki container qayta yaratilса — fayl yo'qoladi va keyingi
   ishga tushishда eskirgan env string ishlatiladi -> ``Unauthorized``. Turso
   DB (``oauth_tokens`` jadvali, ``service_name='userbot_session'``) restart'ga
   chidamli yagona manba beradi.

2. **``AUTH_KEY_DUPLICATED`` — parallel login.** Bir session string ikki xost/
   process'dan ulanса Telegram DARHOL auth kalitni o'ldiradi. Buning ~90%
   sababi — ikkinchi instance (eski VPS, lokal dev, qayta ishga tushgan eski
   deploy) tasodifan bir vaqtda ishlab turishi. ``userbot_session_owner`` yozuvi
   (host + PID + heartbeat) yagona egани belgilaydi: ishga tushayotган instance
   boshqa egानинг heartbeat'i hali yangi (< TTL) bo'lса — userbot'ni ochmaydi.

Har qanday DB xatosi yutiladi: fayl/env fallback baribir ishlaydi, lock esa
"ega noaniq" holатда ruxsat berish tomonга yiqiladi (mavjud xatti-harakat).
"""

from __future__ import annotations

import asyncio
import os
import socket
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import structlog

logger = structlog.get_logger()

SESSION_SERVICE_NAME = "userbot_session"
OWNER_SERVICE_NAME = "userbot_session_owner"

# Ega heartbeat'i shuncha soniyadan eski bo'lsa — "tashlangan" deb hisoblanadi
OWNER_TTL_SECS = int(os.getenv("USERBOT_OWNER_TTL_SECS", "180"))
# Heartbeat yangilash oralig'i (TTL'ning ~1/3 i)
OWNER_HEARTBEAT_SECS = int(os.getenv("USERBOT_OWNER_HEARTBEAT_SECS", "60"))

_INSTANCE_ID = f"{socket.gethostname()}:{os.getpid()}"


def _run_coro_blocking(coro) -> Any:
    """Sync kontekstdan coroutine'ni xavfsiz ishga tushiradi (token_store bilan bir xil naqsh)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: Dict[str, Any] = {}

    def _worker() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except Exception as exc:  # pragma: no cover - defensiv
            result["error"] = exc

    t = threading.Thread(target=_worker, name="userbot-session-store", daemon=True)
    t.start()
    t.join(timeout=20)
    if "error" in result:
        raise result["error"]
    return result.get("value")


# ─────────────────────────── Session string (DB) ───────────────────────────

async def _load_session_async() -> Optional[str]:
    from src.db import get_db

    db = get_db()
    try:
        await db.oauth._init_tables()
    except Exception:
        logger.debug("[USERBOT SESSION STORE] _init_tables skip", exc_info=True)

    row = await db.oauth.get_tokens(SESSION_SERVICE_NAME)
    if not row:
        return None
    # session string access_token maydonida saqlanadi (refresh_token = placeholder)
    val = row.get("access_token")
    return val.strip() if isinstance(val, str) and val.strip() else None


async def _save_session_async(session_string: str) -> None:
    from src.db import get_db

    db = get_db()
    try:
        await db.oauth._init_tables()
    except Exception:
        logger.debug("[USERBOT SESSION STORE] _init_tables skip", exc_info=True)

    await db.oauth.save_tokens(
        service_name=SESSION_SERVICE_NAME,
        access_token=session_string,
        refresh_token="n/a",  # NOT NULL cheklovini qondirish uchun
        expires_at=datetime.now(timezone.utc) + timedelta(days=3650),
        extra_data={"instance": _INSTANCE_ID, "saved_at": int(time.time())},
    )
    logger.info("[USERBOT SESSION STORE] Session string Turso DB'ga saqlandi (%d b)", len(session_string))


def load_session_string_from_db() -> Optional[str]:
    try:
        return _run_coro_blocking(_load_session_async())
    except Exception as exc:
        logger.warning("[USERBOT SESSION STORE] DB o'qish xatosi: %s", type(exc).__name__)
        return None


def save_session_string_to_db(session_string: str) -> None:
    if not session_string or len(session_string) < 50:
        return
    try:
        _run_coro_blocking(_save_session_async(session_string))
    except Exception as exc:
        logger.warning("[USERBOT SESSION STORE] DB yozish xatosi: %s", type(exc).__name__)


# ─────────────────────────── Yagona egalik lock ───────────────────────────

async def _read_owner_async() -> Optional[Dict[str, Any]]:
    from src.db import get_db

    db = get_db()
    try:
        await db.oauth._init_tables()
    except Exception:
        logger.debug("[USERBOT OWNER] _init_tables skip", exc_info=True)

    row = await db.oauth.get_tokens(OWNER_SERVICE_NAME)
    if not row:
        return None
    extra = row.get("extra_data") or {}
    owner = str(row.get("access_token") or "")
    hb = 0
    if isinstance(extra, dict):
        try:
            hb = int(extra.get("heartbeat", 0))
        except (TypeError, ValueError):
            hb = 0
    return {"instance": owner, "heartbeat": hb}


async def _write_owner_async(instance: str) -> None:
    from src.db import get_db

    db = get_db()
    try:
        await db.oauth._init_tables()
    except Exception:
        logger.debug("[USERBOT OWNER] _init_tables skip", exc_info=True)

    now = int(time.time())
    await db.oauth.save_tokens(
        service_name=OWNER_SERVICE_NAME,
        access_token=instance,
        refresh_token="n/a",
        expires_at=datetime.now(timezone.utc) + timedelta(days=3650),
        extra_data={"heartbeat": now},
    )


def acquire_session_ownership(*, force: bool = False) -> bool:
    """Bu instance userbot session'ni ochishга haqli-yo'qligini aniqlaydi.

    True  -> ega bo'ldik (yoki ega noaniq / DB yo'q — eski xatti-harakat).
    False -> boshqa instance active heartbeat bilan ega. Userbot OCHILMASIN.

    ``force=True`` — heartbeat holatidан qat'i nazar egalikni tortib oladi
    (masalan qo'lда "men yagonaman" deб ishonch bilan qayта ishga tushirish).
    """
    if os.getenv("USERBOT_OWNER_LOCK_DISABLED", "").strip() in {"1", "true", "yes"}:
        return True
    try:
        current = _run_coro_blocking(_read_owner_async())
    except Exception as exc:
        logger.warning("[USERBOT OWNER] O'qish xatosi, lock o'tkazib yuborildi: %s", type(exc).__name__)
        return True

    now = int(time.time())
    if current and not force:
        other = current.get("instance") or ""
        hb = current.get("heartbeat") or 0
        age = now - hb
        if other and other != _INSTANCE_ID and age < OWNER_TTL_SECS:
            logger.critical(
                "[USERBOT OWNER] ❌ Boshqa instance ega: %s (heartbeat %ds oldin). "
                "Bu instance userbot'ni OCHMAYDI — AUTH_KEY_DUPLICATED oldini olish.",
                other, age,
            )
            return False
        if other and other != _INSTANCE_ID:
            logger.warning(
                "[USERBOT OWNER] Oldingi ega %s tashlangan (heartbeat %ds oldin) — egalik olinmoqda",
                other, age,
            )

    try:
        _run_coro_blocking(_write_owner_async(_INSTANCE_ID))
        logger.info("[USERBOT OWNER] ✅ Egalik olindi: %s", _INSTANCE_ID)
        return True
    except Exception as exc:
        logger.warning("[USERBOT OWNER] Yozish xatosi, lock o'tkazib yuborildi: %s", type(exc).__name__)
        return True


async def owner_heartbeat_loop(stop_event: Optional[asyncio.Event] = None) -> None:
    """Egalik heartbeat'ini davriy yangilab turadi — boshqa instance'lar bizni
    'tirik ega' deb ko'rishi uchun."""
    if stop_event is None:
        stop_event = asyncio.Event()
    logger.info("[USERBOT OWNER] Heartbeat loop boshlandi (interval=%ds, TTL=%ds)",
                OWNER_HEARTBEAT_SECS, OWNER_TTL_SECS)
    while not stop_event.is_set():
        try:
            await asyncio.sleep(OWNER_HEARTBEAT_SECS)
            if stop_event.is_set():
                break
            await _write_owner_async(_INSTANCE_ID)
            logger.debug("[USERBOT OWNER] Heartbeat yangilandi")
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("[USERBOT OWNER] Heartbeat xatosi: %s", type(exc).__name__)
            await asyncio.sleep(10)
    logger.info("[USERBOT OWNER] Heartbeat loop to'xtadi")


def start_owner_heartbeat(stop_event: Optional[asyncio.Event] = None) -> asyncio.Task:
    return asyncio.create_task(owner_heartbeat_loop(stop_event), name="userbot_owner_heartbeat")
