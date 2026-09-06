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
# Egalik band bo'lsa qayta urinishdan oldin kutish
OWNER_RETRY_DELAY_SECS = int(os.getenv("USERBOT_OWNER_RETRY_DELAY_SECS", "2"))

_INSTANCE_ID = f"{socket.gethostname()}:{os.getpid()}"


def _db_enabled() -> bool:
    """Session DB persistence / egalik lock yoqilganmi.

    Default yoqilgan; ``USERBOT_SESSION_DB_DISABLED=1`` yoki test muhiti
    (``SKIP_LIVE=1``, aniq belgilanmaganда) o'chiradi.
    """
    raw = os.environ.get("USERBOT_SESSION_DB_DISABLED", "").strip().lower()
    if raw in {"1", "true", "yes"}:
        return False
    return os.environ.get("SKIP_LIVE", "").strip() not in {"1", "true", "yes"}


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
    if not _db_enabled():
        return None
    try:
        return _run_coro_blocking(_load_session_async())
    except Exception as exc:
        logger.warning("[USERBOT SESSION STORE] DB o'qish xatosi: %s", type(exc).__name__)
        return None


def save_session_string_to_db(session_string: str) -> None:
    if not _db_enabled():
        return
    if not session_string or len(session_string) < 50:
        return
    try:
        _run_coro_blocking(_save_session_async(session_string))
    except Exception as exc:
        logger.warning("[USERBOT SESSION STORE] DB yozish xatosi: %s", type(exc).__name__)


# ─────────────────────────── Yagona egalik lock ───────────────────────────
#
# Egalik `oauth_tokens` jadvalidagi bitta qatorда yashaydi
# (`service_name='userbot_session_owner'`): `access_token` = ega instance id,
# `expires_at` = heartbeat muddati (hozir + TTL). Egalik olish ATOMIK: bitta
# shartli UPDATE (yangi ega olish uchun eski qator eskirgan yoki bizga tegishli
# bo'lishi kerak) + qator yo'q bo'lsa INSERT. `rowcount`/keyingi tekshiruv
# faqat bitta chaqiruvchi yutganini isbotlaydi — ikki instance parallel
# ishga tushса ham ikkalasi `True` qaytara olmaydi (AUTH_KEY_DUPLICATED
# oynasi yopiladi).

_OWNER_ACQUIRE_SQL = """
UPDATE oauth_tokens
   SET access_token = ?, expires_at = ?, updated_at = ?
 WHERE service_name = ?
   AND (access_token = ? OR expires_at < ?)
"""

_OWNER_INSERT_SQL = """
INSERT INTO oauth_tokens (service_name, access_token, refresh_token, expires_at, updated_at, extra_data)
VALUES (?, ?, 'n/a', ?, ?, NULL)
ON CONFLICT(service_name) DO NOTHING
"""

_OWNER_RELEASE_SQL = """
UPDATE oauth_tokens
   SET access_token = '', expires_at = ?, updated_at = ?
 WHERE service_name = ? AND access_token = ?
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _deadline_iso(extra_secs: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=extra_secs)).isoformat()


async def _try_acquire_owner_async(*, force: bool) -> bool:
    """Egalikni atomik olishga urinadi. True -> biz egamiz."""
    from src.db import get_db

    db = get_db()
    try:
        await db.oauth._init_tables()
    except Exception:
        logger.debug("[USERBOT OWNER] _init_tables skip", exc_info=True)

    conn = await db.oauth._get_conn()
    now_iso = _now_iso()
    new_deadline = _deadline_iso(OWNER_TTL_SECS)
    # force -> har qanday joriy egani bosib o'tish uchun "hozir"dan katta chegara
    stale_before = _deadline_iso(10**9) if force else now_iso

    # 1. Qator mavjud bo'lmasa yaratish (boshqa yozuvni buzmaydi)
    await conn.execute(_OWNER_INSERT_SQL, (OWNER_SERVICE_NAME, "", new_deadline, now_iso))
    # 2. Atomik shartli egalik olish
    await conn.execute(
        _OWNER_ACQUIRE_SQL,
        (_INSTANCE_ID, new_deadline, now_iso, OWNER_SERVICE_NAME, _INSTANCE_ID, stale_before),
    )
    await conn.commit()

    # 3. Kim yutganini o'qib tasdiqlash — faqat bitta chaqiruvchi bu yerда
    #    o'z id'ini ko'radi (UPDATE WHERE sharti tufayli)
    row = await db.oauth.get_tokens(OWNER_SERVICE_NAME)
    won = bool(row and row.get("access_token") == _INSTANCE_ID)
    return won


async def _write_owner_async(instance: str) -> None:
    """Heartbeat yangilash — faqat biz ega bo'lsak muddatni uzaytiradi."""
    from src.db import get_db

    db = get_db()
    conn = await db.oauth._get_conn()
    await conn.execute(
        _OWNER_ACQUIRE_SQL,
        (
            instance,
            _deadline_iso(OWNER_TTL_SECS),
            _now_iso(),
            OWNER_SERVICE_NAME,
            instance,
            _deadline_iso(10**9),  # heartbeat: doim o'zimizniki bo'lса yangilash
        ),
    )
    await conn.commit()


async def _release_owner_async(instance: str) -> None:
    from src.db import get_db

    db = get_db()
    conn = await db.oauth._get_conn()
    await conn.execute(_OWNER_RELEASE_SQL, (_now_iso(), _now_iso(), OWNER_SERVICE_NAME, instance))
    await conn.commit()


def acquire_session_ownership(*, force: bool = False) -> bool:
    """Bu instance userbot session'ni ochishга haqli-yo'qligini ATOMIK aniqlaydi.

    True  -> egalik bizda (yoki DB/lock o'chiq — eski xatti-harakat).
    False -> boshqa instance tirik ega. Userbot OCHILMASIN.

    Ikki urinish qilinadi: birinchisi eskirmagan begona egaga duch kelса,
    ~2s kutib yana bir marta (oldingi jarayon shu orada release qilishi
    yoki TTL tugashi mumkin — normal systemd restart sikli).
    """
    if os.getenv("USERBOT_OWNER_LOCK_DISABLED", "").strip() in {"1", "true", "yes"}:
        return True
    if not _db_enabled():
        return True

    for attempt in (1, 2):
        try:
            if _run_coro_blocking(_try_acquire_owner_async(force=force)):
                logger.info("[USERBOT OWNER] ✅ Egalik olindi (atomik): %s", _INSTANCE_ID)
                return True
        except Exception as exc:
            logger.warning(
                "[USERBOT OWNER] Egalik olish xatosi (urinish %d), lock o'tkazib yuborildi: %s",
                attempt, type(exc).__name__,
            )
            return True
        if attempt == 1:
            logger.warning(
                "[USERBOT OWNER] Boshqa instance tirik ega — %ds kutib qayta urinaman",
                OWNER_RETRY_DELAY_SECS,
            )
            time.sleep(OWNER_RETRY_DELAY_SECS)

    logger.critical(
        "[USERBOT OWNER] ❌ Egalik olinmadi — boshqa instance tirik. "
        "Userbot bu yerда OCHILMAYDI (AUTH_KEY_DUPLICATED oldini olish). "
        "Heartbeat loop egalik bo'shashini kutadi."
    )
    return False


def release_session_ownership() -> None:
    """Graceful shutdown'да egalikni bo'shatadi — keyingi instance darhol olsin."""
    if not _db_enabled():
        return
    try:
        _run_coro_blocking(_release_owner_async(_INSTANCE_ID))
        logger.info("[USERBOT OWNER] Egalik bo'shatildi: %s", _INSTANCE_ID)
    except Exception as exc:
        logger.warning("[USERBOT OWNER] Egalik bo'shatish xatosi: %s", type(exc).__name__)


async def owner_heartbeat_loop(stop_event: Optional[asyncio.Event] = None) -> None:
    """Egalik heartbeat'ini davriy yangilab turadi — boshqa instance'lar bizni
    'tirik ega' deb ko'rishi uchun."""
    if stop_event is None:
        stop_event = asyncio.Event()
    if not _db_enabled():
        logger.info("[USERBOT OWNER] DB o'chiq — heartbeat loop ishga tushmaydi")
        return
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


async def owner_reacquire_watch(
    on_acquired,
    *,
    stop_event: Optional[asyncio.Event] = None,
    interval_secs: int = OWNER_HEARTBEAT_SECS,
) -> None:
    """Egalik ololmagan instance uchun: davriy ravishda qayta urinadi va
    egalik bo'shashi bilan ``on_acquired`` chaqiriladi.

    ``acquire_session_ownership`` allaqachon ega bo'lganida (normal holat) bu
    darrov chiqadi — faqat lock rad etilgan instance'da foydali.
    """
    if not _db_enabled():
        return
    if stop_event is None:
        stop_event = asyncio.Event()
    while not stop_event.is_set():
        try:
            await asyncio.sleep(interval_secs)
            if stop_event.is_set():
                break
            if _run_coro_blocking(_try_acquire_owner_async(force=False)):
                logger.warning("[USERBOT OWNER] Egalik bo'shadi — userbot tiklanmoqda")
                res = on_acquired()
                if asyncio.iscoroutine(res):
                    await res
                return
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("[USERBOT OWNER] Reacquire watch xatosi: %s", type(exc).__name__)
            await asyncio.sleep(10)


def start_owner_reacquire_watch(stop_event: Optional[asyncio.Event] = None) -> Optional[asyncio.Task]:
    """Bu instance ALLAQACHON ega bo'lса — hech narsa qilmaydi (None).

    Aks holда egalikni kuzatib, bo'shashi bilan jarayonni qayta ishga
    tushirishни so'raydi (systemd userbot'ni toza holатда qayta ko'taradi).
    """
    if not _db_enabled():
        return None
    try:
        already_owner = _run_coro_blocking(_try_acquire_owner_async(force=False))
    except Exception:
        return None
    if already_owner:
        return None

    def _request_restart() -> None:
        logger.critical(
            "[USERBOT OWNER] Egalik olindi — process qayta ishga tushirilishi kerak "
            "(systemd Restart=always buni bajaradi)."
        )
        os._exit(3)

    return asyncio.create_task(
        owner_reacquire_watch(_request_restart, stop_event=stop_event),
        name="userbot_owner_reacquire_watch",
    )
