"""Userbot session keep-alive va avtomatik session string yangilash.

Ushbu modul:
1. Har N minutda Telegram'ga "jon belgisi" (ping) yuboradi — session idle o'lmasin
2. Ulanish muvaffaqiyatli bo'lganda yangi session stringni faylga YOZADI
3. Session string o'zgarsa, DB ga ham yozadi — keyingi restart da yangi string ishlatiladi

Nima uchun bu kerak:
- Telegram StringSession RAM da — server restart = session yo'q
- Eski stringni ishlatsa, "401 Unauthorized" (session expired)
- Keep-alive bo'lmasa idle session eskiradi (~24h yoki kamroq)
- Session faylga to'g'ri saqlanmasa har deploy da login kerak bo'ladi
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

SESSION_STRING_FILE = "data/userbot_session_string.txt"
KEEPALIVE_INTERVAL_SECS = 300  # 5 daqiqada bir ping


def _read_session_string_from_file(path: str = SESSION_STRING_FILE) -> Optional[str]:
    """Fayldan session string o'qish."""
    try:
        if os.path.exists(path):
            data = open(path, encoding="utf-8").read().strip()
            if data:
                logger.info("[SESSION_KEEPER] Fayldan session string o'qildi (%d b)", len(data))
                return data
    except Exception as exc:
        logger.warning("[SESSION_KEEPER] Fayl o'qishda xato: %s", exc)
    return None


def _write_session_string_to_file(string: str, path: str = SESSION_STRING_FILE) -> bool:
    """Session string ni faylga yozish."""
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(string)
        logger.info("[SESSION_KEEPER] Session string faylga saqlandi (%d b)", len(string))
        return True
    except Exception as exc:
        logger.error("[SESSION_KEEPER] Fayl yozishda xato: %s", exc)
        return False


def get_best_session_string(env_var: str = "USERBOT_SESSION_STRING") -> Optional[str]:
    """Eng yaxshi session string — fayl > env var tartibida.

    Fayl ENV dan ustunlik qiladi, chunki:
    - Fayl har reconnect da yangilanadi (eng yangi valid string)
    - ENV restart'lar orasida eskirgan bo'lishi mumkin
    """
    # 1. Avval fayldan o'qish (eng yangi)
    from_file = _read_session_string_from_file()
    if from_file:
        return from_file

    # 2. Env var dan
    from_env = os.environ.get(env_var, "").strip()
    if from_env:
        logger.info("[SESSION_KEEPER] Env var'dan session string olinmoqda")
        return from_env

    return None


async def save_current_session_string(client: Any) -> Optional[str]:
    """Hozirgi Telethon client'dan session string olib faylga saqlash.

    Bu metod muvaffaqiyatli ulanishdan keyin chaqirilishi kerak.
    """
    try:
        from telethon.sessions import StringSession

        session_obj = getattr(client, "session", None)
        if session_obj is None:
            return None

        if hasattr(session_obj, "save") and hasattr(session_obj, "get_string"):
            # StringSession
            session_obj.save()
            string = session_obj.get_string()
        elif hasattr(session_obj, "get_string"):
            string = session_obj.get_string()
        elif callable(getattr(client, "session", None)):
            # Telethon 1.x API
            string = StringSession.save(client.session)  # type: ignore[arg-type]
        else:
            # SQLite session → string ga o'tkazamiz
            temp = StringSession()
            temp.set_dc(
                getattr(session_obj, "dc_id", 0),
                getattr(session_obj, "server_address", ""),
                getattr(session_obj, "port", 0),
            )
            auth_key = getattr(session_obj, "auth_key", None)
            if auth_key:
                temp.auth_key = auth_key
            string = temp.save()

        if string and len(string) > 50:
            _write_session_string_to_file(string)
            # ENV ga ham qo'yish (shu runtime uchun)
            os.environ["USERBOT_SESSION_STRING"] = string
            logger.info("[SESSION_KEEPER] Session string saqlandi va ENV yangilandi (%d b)", len(string))
            return string
        else:
            logger.warning("[SESSION_KEEPER] Session string juda qisqa yoki bo'sh: %r", string)
    except Exception as exc:
        logger.error("[SESSION_KEEPER] Session string saqlashda xato: %s", exc)
    return None


async def session_keepalive_loop(
    client: Any,
    *,
    interval_secs: int = KEEPALIVE_INTERVAL_SECS,
    save_interval_multiplier: int = 12,  # Har 60 daqiqada session saqlash
    notify_callback: Optional[Callable[[str], Any]] = None,
    stop_event: Optional[asyncio.Event] = None,
) -> None:
    """Session keep-alive va periodic session saving.

    - Har `interval_secs` da `get_me()` chaqirib session'ni tirik ushlaydi
    - Har `interval_secs * save_interval_multiplier` da session string yangilab faylga yozadi
    - Disconnect bo'lsa log qiladi, reconnect manager o'z ishini qiladi
    """
    await asyncio.sleep(30)  # Avval connect bo'lsin
    logger.info("[SESSION_KEEPER] Keep-alive loop boshlandi (interval=%ds)", interval_secs)

    iteration = 0
    last_save_at = time.time()

    if stop_event is None:
        stop_event = asyncio.Event()

    while not stop_event.is_set():
        try:
            await asyncio.sleep(interval_secs)
            iteration += 1

            if stop_event.is_set():
                break

            if client is None:
                logger.debug("[SESSION_KEEPER] Client yo'q, keep-alive saklab o'tildi")
                continue

            # Ping — session'ni tirik ushlash
            try:
                me = await asyncio.wait_for(client.get_me(), timeout=20)
                if me:
                    logger.debug(
                        "[SESSION_KEEPER] ✅ Ping OK — @%s session active",
                        getattr(me, "username", "?"),
                    )
                else:
                    logger.warning("[SESSION_KEEPER] get_me() None qaytardi — session muammosi?")
            except asyncio.TimeoutError:
                logger.warning("[SESSION_KEEPER] Ping timeout (20s) — network muammosi?")
                continue
            except Exception as exc:
                error_str = f"{type(exc).__name__}:{exc}".upper()
                if "AUTH_KEY" in error_str or "UNAUTHORIZED" in error_str:
                    logger.critical("[SESSION_KEEPER] ❌ Auth xatosi ping'da: %s", exc)
                    if notify_callback:
                        try:
                            await notify_callback(
                                f"🚨 SESSION KEEPALIVE XATO\n\n"
                                f"Telegram userbot session ping'da auth xatosi:\n`{exc}`\n\n"
                                f"Reconnect manager ishga tushadi."
                            )
                        except Exception:
                            pass
                else:
                    logger.warning("[SESSION_KEEPER] Ping xatosi (davom etadi): %s", exc)
                continue

            # Har `save_interval_multiplier` iteratsiyada session string yangilash
            now = time.time()
            if (now - last_save_at) >= (interval_secs * save_interval_multiplier):
                saved = await save_current_session_string(client)
                if saved:
                    last_save_at = now
                    logger.info("[SESSION_KEEPER] Periodic session string yangilandi")

        except asyncio.CancelledError:
            logger.info("[SESSION_KEEPER] Keep-alive bekor qilindi")
            break
        except Exception as exc:
            logger.error("[SESSION_KEEPER] Keep-alive loop xatosi: %s", exc)
            await asyncio.sleep(30)

    logger.info("[SESSION_KEEPER] Keep-alive loop to'xtatildi")


def start_session_keepalive(
    client: Any,
    *,
    interval_secs: int = KEEPALIVE_INTERVAL_SECS,
    notify_callback: Optional[Callable[[str], Any]] = None,
    stop_event: Optional[asyncio.Event] = None,
) -> asyncio.Task:
    """Keep-alive taskni yaratib qaytaradi. boot.py dan chaqiriladi."""
    task = asyncio.create_task(
        session_keepalive_loop(
            client,
            interval_secs=interval_secs,
            notify_callback=notify_callback,
            stop_event=stop_event,
        ),
        name="userbot_session_keepalive",
    )
    logger.info("[SESSION_KEEPER] Keep-alive task yaratildi")
    return task
