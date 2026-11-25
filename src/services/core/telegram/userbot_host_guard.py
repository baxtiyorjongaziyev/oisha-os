"""Userbot single-host guard — AuthKeyDuplicatedError ni KOD darajasida oldini oladi.

Prod userbot auth key (``USERBOT_SESSION_STRING``) faqat Hetzner prod hostida
(``jon-ai-prod-01``) va u yerda ham faqat BITTA jarayonda ishlatilishi mumkin.
Ikkinchi joydan ulanish Telegram tomonidan kalitni butunlay bekor qiladi.

Himoya hookʼlarga emas, kodga tayanadi:

* :func:`install` Telethon ``TelegramBaseClient.connect`` ni oʼraydi. ``src``
  paketini import qilgan har qanday jarayon (``src/main.py``, skriptlar,
  session manager) avtomatik himoyalanadi.
* Ulanishdan oldin klientning auth key si prod session auth key bilan
  solishtiriladi. Mos kelsa:
    - prod host boʼlmasa (marker fayl + hostname) — ``ALLOW_LOCAL_RUN=1`` boʼlsa
      ham :class:`UserbotHostGuardError`;
    - prod hostda — eksklyuziv ``flock`` olinadi; ikkinchi jarayon ulanmaydi.
* Alohida dev session (boshqa auth key) istalgan joyda ruxsat etiladi.

Session string yoki auth key hech qachon logga chiqarilmaydi.
"""
from __future__ import annotations

import hashlib
import logging
import os
import socket
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("UserbotHostGuard")

PROD_HOSTNAME = "jon-ai-prod-01"
PROD_MARKER_FILE = "/etc/oisha-prod-host"
_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_LOCK_FILE = str(_REPO_ROOT / "data" / ".userbot.lock")

_lock_fd: Optional[int] = None
_installed = False


class UserbotHostGuardError(RuntimeError):
    """Prod userbot session ruxsat etilmagan joyda/ikkinchi marta ulanmoqda."""


def _key_digest(session_string: str) -> Optional[str]:
    """Session string dan auth key ning sha256 digest i (raw kalit saqlanmaydi)."""
    session_string = (session_string or "").strip()
    if not session_string:
        return None
    try:
        from telethon.sessions import StringSession

        auth_key = StringSession(session_string).auth_key
    except Exception:  # noqa: BLE001 — yaroqsiz string: solishtirib boʼlmaydi
        return None
    if auth_key is None or not getattr(auth_key, "key", None):
        return None
    return hashlib.sha256(auth_key.key).hexdigest()


def _client_key_digest(client: Any) -> Optional[str]:
    session = getattr(client, "session", None)
    auth_key = getattr(session, "auth_key", None)
    raw = getattr(auth_key, "key", None)
    if not raw:
        return None
    return hashlib.sha256(raw).hexdigest()


def _prod_session_string() -> str:
    value = os.environ.get("USERBOT_SESSION_STRING", "").strip()
    if value:
        return value
    try:  # pydantic settings .env ni os.environ ga eksport qilmaydi
        from src.settings import settings

        secret = getattr(settings, "USERBOT_SESSION_STRING", None)
        return secret.get_secret_value().strip() if secret else ""
    except Exception:  # noqa: BLE001 — settings yuklanmasa env yetarli
        return ""


def prod_key_digest() -> Optional[str]:
    return _key_digest(_prod_session_string())


def is_prod_host(
    marker_file: str = PROD_MARKER_FILE, hostname: Optional[str] = None
) -> bool:
    """Prod host = marker fayl mavjud VA hostname mos keladi."""
    expected = os.environ.get("OISHA_PROD_HOSTNAME", PROD_HOSTNAME).strip()
    actual = (hostname if hostname is not None else socket.gethostname()).strip()
    return os.path.isfile(marker_file) and bool(expected) and actual == expected


def assert_mcp_session_distinct() -> None:
    """TELEGRAM_MCP_SESSION_STRING prod userbot bilan bir xil boʼlishi taqiqlanadi."""
    prod = prod_key_digest()
    mcp = _key_digest(os.environ.get("TELEGRAM_MCP_SESSION_STRING", ""))
    if prod and mcp and prod == mcp:
        raise UserbotHostGuardError(
            "TELEGRAM_MCP_SESSION_STRING == USERBOT_SESSION_STRING: Telegram MCP "
            "alohida (dedicated) session ishlatishi shart."
        )


def acquire_single_instance_lock(lock_file: Optional[str] = None) -> None:
    """Prod session uchun jarayon-umrlik eksklyuziv flock. Qayta chaqirish xavfsiz."""
    global _lock_fd
    if _lock_fd is not None:
        return
    path = lock_file or os.environ.get("OISHA_USERBOT_LOCK_FILE") or DEFAULT_LOCK_FILE
    try:
        import fcntl
    except ImportError as exc:  # Windows — prod emas, bu yerga yetib kelmaydi
        raise UserbotHostGuardError("fcntl yoʼq: single-instance lock imkonsiz") from exc
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        os.close(fd)
        raise UserbotHostGuardError(
            f"Prod userbot session allaqachon boshqa jarayonda ulangan (lock: {path}). "
            "Ikkinchi instansiya ulanmaydi."
        ) from exc
    os.ftruncate(fd, 0)
    os.write(fd, str(os.getpid()).encode())
    _lock_fd = fd


def check_client(client: Any) -> None:
    """Ulanishdan oldin chaqiriladi. Prod key boʼlsa host + lock tekshiriladi."""
    prod = prod_key_digest()
    if not prod:
        return
    if _client_key_digest(client) != prod:
        return  # dev / MCP / boshqa session — ruxsat
    assert_mcp_session_distinct()
    if not is_prod_host():
        raise UserbotHostGuardError(
            "Prod USERBOT_SESSION_STRING faqat Hetzner prod hostida "
            f"({PROD_HOSTNAME}, marker {PROD_MARKER_FILE}) ulanishi mumkin. "
            "Lokal ishlatish uchun alohida dev session string bering."
        )
    acquire_single_instance_lock()


def install() -> bool:
    """Telethon connect ni oʼraydi. Idempotent; telethon yoʼq boʼlsa False."""
    global _installed
    if _installed:
        return True
    try:
        from telethon.client.telegrambaseclient import TelegramBaseClient
    except ImportError:
        return False
    original = TelegramBaseClient.connect

    async def guarded_connect(self, *args, **kwargs):
        try:
            check_client(self)
        except UserbotHostGuardError as exc:
            logger.critical("[USERBOT GUARD] Ulanish bloklandi: %s", exc)
            raise
        return await original(self, *args, **kwargs)

    guarded_connect.__wrapped__ = original  # type: ignore[attr-defined]
    TelegramBaseClient.connect = guarded_connect  # type: ignore[method-assign]
    _installed = True
    return True
