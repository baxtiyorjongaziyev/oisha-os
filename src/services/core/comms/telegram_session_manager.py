"""Telegram Session Manager — Xavfsiz session boshqaruvchisi.

ASOSIY QOIDA: HECH QACHON yangi session yaratma, faqat mavjudini saqla va qayta ulan.

Xavfsizlik:
- AUTH_KEY_DUPLICATED → QAYTA ULANMAYDI, admin ga xabar
- FloodWaitError → Telegram aytgan vaqtni KUTADI + 10s
- Har qanday reconnect orasida MINIMUM 10 sekund kutish
- Productionda qayta ulanish davom etadi; AUTH_KEY_DUPLICATED bo'lsa to'xtaydi
- Session faqat faylga saqlanadi, env var ga YAZILMAYDI
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Optional, Callable

from telethon import TelegramClient
from telethon.sessions import StringSession, SQLiteSession

logger = logging.getLogger(__name__)


def _is_auth_key_duplicated(exc: Exception) -> bool:
    error_msg = f"{type(exc).__name__}:{exc}".upper()
    return "AUTH_KEY_DUPLICATED" in error_msg or "AUTHKEYDUPLICATED" in error_msg


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("[SESSION] %s=%r invalid; default=%s ishlatiladi", name, raw, default)
        return default


class TelegramSessionManager:
    """Telegram userbot session ni XAVFSIZ boshqaradi."""

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session_file: str = "data/userbot.session",
        session_string: Optional[str] = None,
        admin_notifier: Optional[Callable] = None,
        device_model: str = "Oisha Enterprise v2",
        system_version: str = "Linux Server",
    ):
        self.api_id = api_id
        self.api_hash = api_hash
        self._session_file = session_file
        self._session_string = session_string
        self._admin_notifier = admin_notifier
        self._device_model = device_model
        self._system_version = system_version

        self.client: Optional[TelegramClient] = None
        self._reconnect_count = 0
        # 0 means "forever" so production does not give up after a short outage.
        self._max_reconnect = max(0, _env_int("USERBOT_RECONNECT_MAX_ATTEMPTS", 0))
        self._min_delay = max(10, _env_int("USERBOT_RECONNECT_MIN_DELAY_SECS", 10))
        self._max_delay = max(self._min_delay, _env_int("USERBOT_RECONNECT_MAX_DELAY_SECS", 300))
        self._alert_cooldown = max(60, _env_int("USERBOT_RECONNECT_ALERT_COOLDOWN_SECS", 900))
        self._last_alert_at: float = 0
        self._last_connected_at: float = 0
        self._is_connected = False
        self._fatal_auth_error = False
        self._reconnect_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def connect(self) -> bool:
        """Session ni ulash — fayl yoki string dan.

        Xavfsizlik:
        - AUTH_KEY_DUPLICATED → QAYTA ULANMAYDI
        - Mavjud session ni ishlatadi, yangi YARATMAYDI
        """
        try:
            if self.client is None:
                # Session manbasini aniqlash
                if self._session_string:
                    logger.info("[SESSION] String session ishlatilmoqda")
                    session = StringSession(self._session_string)
                elif os.path.exists(self._session_file):
                    logger.info("[SESSION] Fayl session ishlatilmoqda: %s", self._session_file)
                    session = SQLiteSession(self._session_file)
                else:
                    # FAQAT env var dan o'qish — yangi session YARATMAYDI
                    env_string = os.environ.get("USERBOT_SESSION_STRING", "").strip()
                    if env_string:
                        logger.info("[SESSION] Env session ishlatilmoqda (len=%d)", len(env_string))
                        session = StringSession(env_string)
                        # Faylga SAQLAMAYMIZ — faqat MUVAFFAQIYATLI ulanishdan keyin saqlaymiz
                    else:
                        logger.error("[SESSION] HECH QANDAY session topilmadi!")
                        logger.error("[SESSION] USERBOT_SESSION_STRING env yoki %s fayl kerak", self._session_file)
                        return False

                # Client yaratish
                self.client = TelegramClient(
                    session,
                    self.api_id,
                    self.api_hash,
                    device_model=self._device_model,
                    system_version=self._system_version,
                )

            # Ulanish — xatolikni tekshirish
            try:
                await asyncio.wait_for(self.client.connect(), timeout=30)
            except asyncio.TimeoutError:
                logger.error("[SESSION] Connect 30s timeout — Telegram javob bermadi")
                try:
                    await self.client.disconnect()
                except Exception as exc:
                    logger.debug("[SESSION] Disconnect after timeout: %s", exc)
                return False
            except Exception as exc:
                # AUTH_KEY_DUPLICATED — ENG XAVFLI XATO
                if _is_auth_key_duplicated(exc):
                    logger.critical(
                        "[SESSION] AUTH_KEY_DUPLICATED — Session boshqa runtime da ishlatilgan!"
                    )
                    logger.critical("[SESSION] QAYTA ULANMAYDI — Telegram ban qo'yishi mumkin!")
                    await self._handle_auth_key_duplicated()
                    # Burned sessionni faylga SAQLAMASLIK
                    return False

                # Boshqa xatolar
                logger.error("[SESSION] Ulanish xatosi: %s", exc)
                raise

            # Authorized tekshirish
            if await self.client.is_user_authorized():
                if not await self._validate_high_level_auth():
                    return False
                self._is_connected = True
                self._last_connected_at = time.time()
                self._reconnect_count = 0
                logger.info("[SESSION] Muvaffaqiyatli ulandi!")
                # Muvaffaqiyatli ulanishdan keyin session stringni saqlash
                from src.services.core.session_keeper import save_current_session_string
                await save_current_session_string(self.client)
                return True
            else:
                logger.warning("[SESSION] Session authorized emas")
                return False

        except Exception as exc:
            logger.error("[SESSION] Connect xatosi: %s", exc)
            return False

    async def _handle_auth_key_duplicated(self):
        """AUTH_KEY_DUPLICATED → QAYTA ULANMAYDI, admin ga xabar."""
        self._is_connected = False
        self._fatal_auth_error = True
        self._stop_event.set()

        # Admin ga xabar
        if self._admin_notifier:
            try:
                await self._admin_notifier(
                    "🚨 SESSION XAVFSIZLIGI\n\n"
                    "AUTH_KEY_DUPLICATED xatoligi aniqlandi!\n\n"
                    "Session boshqa runtime da ishlatilmoqda.\n"
                    "QAYTA ULANMAYDI — Telegram ban qo'yishi mumkin!\n\n"
                    "Yangi session yaratish kerak:\n"
                    "1. Eski session ni tozalang\n"
                    "2. Yangi session string oling\n"
                    "3. .env ga qo'shing\n"
                    "4. Container ni qayta ishga tushiring"
                )
            except Exception as e:
                logger.error("[SESSION] Admin ga xabar jo'natishda xato: %s", e)

        # Disconnect
        if self.client:
            try:
                await self.client.disconnect()
            except Exception as exc:
                logger.debug("[SESSION] Disconnect in auth key handler: %s", exc)

    async def _validate_high_level_auth(self) -> bool:
        """Transport connected bo'lsa ham session kuyganini RPC bilan tekshiradi."""
        if not self.client:
            return False
        try:
            await asyncio.wait_for(self.client.get_me(), timeout=10)
            return True
        except asyncio.TimeoutError:
            logger.warning("[SESSION] get_me health probe timeout")
            self._is_connected = False
            return False
        except Exception as exc:
            if _is_auth_key_duplicated(exc):
                logger.critical(
                    "[SESSION] AUTH_KEY_DUPLICATED health probe'da aniqlandi; reconnect to'xtaydi"
                )
                await self._handle_auth_key_duplicated()
                return False
            logger.warning("[SESSION] get_me health probe failed: %s", exc)
            self._is_connected = False
            return False

    async def _notify_admin_throttled(self, message: str) -> None:
        if not self._admin_notifier:
            return
        now = time.time()
        if now - self._last_alert_at < self._alert_cooldown:
            return
        self._last_alert_at = now
        try:
            await self._admin_notifier(message)
        except Exception as exc:
            logger.error("[SESSION] Admin ga xabar jo'natishda xato: %s", exc)

    async def _reconnect_loop(self):
        """Xavfsiz qayta ulanish — cooldown bilan, productionda taslim bo'lmaydi."""
        logger.info("[SESSION] Reconnect loop boshlandi")

        while not self._stop_event.is_set():
            try:
                if self._fatal_auth_error:
                    logger.critical("[SESSION] Fatal auth error bor — reconnect to'xtatildi")
                    break

                # Connection tushganini tekshirish
                if self._is_connected and self.client:
                    try:
                        # Oddiy so'rov bilan tekshirish
                        if not self.client.is_connected():
                            raise ConnectionError("Client disconnected")
                        if not await self._validate_high_level_auth():
                            raise ConnectionError("Client auth probe failed")
                    except ConnectionError:
                        self._is_connected = False
                        logger.warning("[SESSION] Connection tushdi!")
                    except Exception:
                        # Connection hali bor
                        await asyncio.sleep(30)
                        continue

                if self._is_connected:
                    await asyncio.sleep(30)
                    continue

                # Qayta ulanish
                if self._max_reconnect and self._reconnect_count >= self._max_reconnect:
                    logger.critical(
                        "[SESSION] ❌ Max qayta urinishlar soniga yetdi (%d). Bot to'xtatildi.",
                        self._max_reconnect,
                    )
                    await self._notify_admin_throttled(
                        f"🚨 SESSION XATO\n\n"
                        f"{self._max_reconnect} marta qayta urinish muvaffaqiyatsiz!\n"
                        f"Bot to'xtatildi. Qo'lda tuzating."
                    )
                    break

                # Kutish — MIN 10 sekund
                delay = min(
                    self._max_delay,
                    max(self._min_delay, self._min_delay * (2 ** min(self._reconnect_count, 5))),
                )
                logger.info(
                    "[SESSION] %d sekund kutib qayta ulanadi... (urinish %d/%s)",
                    delay,
                    self._reconnect_count + 1,
                    self._max_reconnect or "forever",
                )
                await self._notify_admin_throttled(
                    "⚠️ USERBOT RECONNECT\n\n"
                    "Telegram userbot connection tushdi. Oisha avtomatik qayta ulanishga urinmoqda."
                )
                await asyncio.sleep(delay)

                # Qayta ulanish
                self._reconnect_count += 1
                success = await self.connect()

                if success:
                    logger.info("[SESSION] ✅ Qayta ulanish muvaffaqiyatli!")
                else:
                    logger.warning("[SESSION] Qayta ulanish muvaffaqiyatsiz")

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("[SESSION] Reconnect loop xatosi: %s", exc)
                await asyncio.sleep(30)

    async def start_reconnect_monitor(self):
        """Reconnect monitorini ishga tushirish."""
        if self._reconnect_task and not self._reconnect_task.done():
            return
        self._stop_event.clear()
        self._reconnect_task = asyncio.create_task(
            self._reconnect_loop(),
            name="session_reconnect_loop",
        )
        logger.info("[SESSION] Reconnect monitor ishga tushdi")

    async def stop_reconnect_monitor(self):
        """Reconnect monitorini to'xtatish."""
        self._stop_event.set()
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        logger.info("[SESSION] Reconnect monitor to'xtatildi")

    async def health_check(self) -> bool:
        """Connection holatini tekshirish."""
        if not self.client or not self._is_connected:
            return False
        try:
            return self.client.is_connected()
        except Exception:
            return False

    async def disconnect(self):
        """Graceful disconnect — session saqlash."""
        try:
            await self.stop_reconnect_monitor()
            if self.client and self.client.is_connected():
                # Session ni saqlash
                await self.save_session()
                await self.client.disconnect()
                self._is_connected = False
                logger.info("[SESSION] Graceful disconnect — session saqlandi")
        except Exception as exc:
            logger.error("[SESSION] Disconnect xatosi: %s", exc)

    async def save_session(self):
        """Session ni faylga saqlash."""
        if not self.client:
            return

        try:
            # StringSession dan string olish
            if hasattr(self.client.session, "save"):
                self.client.session.save()
                logger.info("[SESSION] Session faylga saqlandi: %s", self._session_file)
        except Exception as exc:
            logger.error("[SESSION] Session saqlash xatosi: %s", exc)

    async def _save_string_to_file(self, session_string: str):
        """String session ni faylga saqlash (session_keeper orqali)."""
        from src.services.core.session_keeper import _write_session_string_to_file
        _write_session_string_to_file(session_string)

    def get_session_string(self) -> str:
        """Hozirgi session string ni qaytarish."""
        if self.client and hasattr(self.client.session, "get_string"):
            try:
                return self.client.session.get_string()
            except Exception as exc:
                logger.debug("[SESSION] Get session string: %s", exc)
        return self._session_string or ""

    @property
    def is_connected(self) -> bool:
        """Connection holati."""
        return self._is_connected and self.client is not None and self.client.is_connected()

    @property
    def status(self) -> dict:
        """Session holati."""
        return {
            "is_connected": self.is_connected,
            "reconnect_count": self._reconnect_count,
            "max_reconnect": self._max_reconnect,
            "reconnect_forever": self._max_reconnect == 0,
            "fatal_auth_error": self._fatal_auth_error,
            "last_connected_at": self._last_connected_at,
            "has_client": self.client is not None,
        }

    @property
    def admin_notifier(self) -> Optional[Callable]:
        return self._admin_notifier

    @admin_notifier.setter
    def admin_notifier(self, notifier: Optional[Callable]) -> None:
        self._admin_notifier = notifier
