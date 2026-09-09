"""AmoCRM OAuth token'ining Turso DB'da (oauth_tokens jadvali) davomiy saqlanishi.

Nima uchun bu modul bor
=======================
`AmoCRMAuthMixin` faqat env var + lokal fayldan token o'qir/yozardi. Oracle VM
restart bo'lganda ``data/`` katalog yo'qolса (yoki hech qachon yozilmagan bo'lsa)
va env'dagi ``AMOCRM_TOKEN_JSON`` eskirgan bo'lsa — token butunlay yo'qoladi va
integratsiya ``access_token_missing`` bilan yiqiladi. Aynan shu holat productionда
"degraded" deploy'ga sabab bo'lgan.

AmoCRM refresh_token'lari **rotatsiya** qilinadi: har refreshdan keyin yangi
refresh_token qaytadi va eskisi bir muddat ichida bekor bo'ladi. Shu sababli
yangilangan payload'ni bardavom joyga (Turso) yozib qo'ymasak, zanjir uziladi.

Bu modul ``oauth_tokens`` jadvalига (``service_name='amocrm'``) sync kontekstdан
o'qish/yozishни ta'minlaydi. Mixin sync, ``OAuthRepository`` esa async —
shuning uchun bu yer async coroutine'ni xavfsiz ko'prik orqali ishga tushiradi:

* Agar joriy thread'da ishlayotgan event loop bo'lmasa — ``asyncio.run``.
* Agar loop ishlayotgan bo'lsa (masalan FastAPI ичидан chaqirilса) — token
  yozish fire-and-forget task sifatida rejalashtiriladi, o'qish esa alohida
  thread'dagi yangi loop'da bajariladi (asosiy loop'ni bloklamaslik uchun).

Har qanday DB xatosi **yutiladi**: bu qatlam faqat "bonus davomiylik" beradi,
fayl/env fallback baribir ishlayveradi.
"""

from __future__ import annotations

import asyncio
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import structlog

logger = structlog.get_logger()

SERVICE_NAME = "amocrm"


def _db_persist_enabled() -> bool:
    """DB persistence yoqilganmi.

    Default: yoqilgan. ``AMOCRM_TOKEN_DB_PERSIST=0`` bilan o'chiriladi —
    test muhitida (``SKIP_LIVE=1`` bo'lganda avtomatik o'chadi), chunki
    bir nechta test bir xil Turso DB'ni bo'lishishi mumkin va determinism
    buziladi.
    """
    raw = os.environ.get("AMOCRM_TOKEN_DB_PERSIST", "").strip().lower()
    if raw in {"0", "false", "no"}:
        return False
    if raw in {"1", "true", "yes"}:
        return True
    # Aniq belgilanmagan — test muhitida o'chiq
    return os.environ.get("SKIP_LIVE", "").strip() not in {"1", "true", "yes"}


def _run_coro_blocking(coro) -> Any:
    """Coroutine'ni joriy sync kontekstdan xavfsiz bajaradi.

    Ishlayotgan event loop bo'lsa — uni bloklamaslik uchun alohida thread'da
    yangi loop ochiladi. Aks holda oddiy ``asyncio.run``.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # Loop yo'q — to'g'ridan-to'g'ri
        return asyncio.run(coro)

    # Loop bor — boshqa thread'da yangi loop
    result: Dict[str, Any] = {}

    def _worker() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except Exception as exc:  # pragma: no cover - defensiv
            result["error"] = exc

    t = threading.Thread(target=_worker, name="amocrm-token-store", daemon=True)
    t.start()
    t.join(timeout=20)
    if "error" in result:
        raise result["error"]
    return result.get("value")


async def _load_async() -> Optional[Dict[str, Any]]:
    from src.db import get_db

    db = get_db()
    try:
        await db.oauth._init_tables()
    except Exception:
        logger.debug("[AMOCRM TOKEN STORE] _init_tables skip", exc_info=True)

    row = await db.oauth.get_tokens(SERVICE_NAME)
    if not row:
        return None

    token_data: Dict[str, Any] = {}
    extra = row.get("extra_data") or {}
    if isinstance(extra, dict):
        token_data.update(extra)

    if row.get("access_token"):
        token_data["access_token"] = row["access_token"]
    if row.get("refresh_token") and row["refresh_token"] != "long_lived_token":
        token_data["refresh_token"] = row["refresh_token"]

    expires_at = row.get("expires_at")
    if isinstance(expires_at, datetime):
        token_data.setdefault("expires_at", int(expires_at.timestamp()))

    return token_data or None


async def _save_async(token_data: Dict[str, Any]) -> None:
    from src.db import get_db

    db = get_db()
    try:
        await db.oauth._init_tables()
    except Exception:
        logger.debug("[AMOCRM TOKEN STORE] _init_tables skip", exc_info=True)

    access_token = str(token_data.get("access_token") or "")
    refresh_token = str(token_data.get("refresh_token") or "long_lived_token")
    if not access_token:
        logger.debug("[AMOCRM TOKEN STORE] access_token yo'q, DB yozuv o'tkazib yuborildi")
        return

    expires_raw = token_data.get("expires_at")
    if isinstance(expires_raw, (int, float)) and expires_raw > 0:
        expires_at = datetime.fromtimestamp(float(expires_raw), tz=timezone.utc)
    else:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    await db.oauth.save_tokens(
        service_name=SERVICE_NAME,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        extra_data=token_data,
    )
    logger.info("[AMOCRM TOKEN STORE] Token Turso DB'ga saqlandi (rotatsiyaga chidamli)")


def load_token_from_db() -> Optional[Dict[str, Any]]:
    """DB'dagi AmoCRM token payload'ini qaytaradi yoki xatoда None."""
    if not _db_persist_enabled():
        return None
    try:
        return _run_coro_blocking(_load_async())
    except Exception as exc:
        logger.warning("[AMOCRM TOKEN STORE] DB'dan o'qish xatosi: %s", type(exc).__name__)
        return None


def save_token_to_db(token_data: Dict[str, Any]) -> None:
    """Token payload'ini DB'ga saqlaydi. Xato yutiladi (fayl fallback baribir bor)."""
    if not _db_persist_enabled():
        return
    if not isinstance(token_data, dict):
        return
    try:
        _run_coro_blocking(_save_async(dict(token_data)))
    except Exception as exc:
        logger.warning("[AMOCRM TOKEN STORE] DB'ga yozish xatosi: %s", type(exc).__name__)


def _token_freshness(token_data: Optional[Dict[str, Any]]) -> int:
    """Solishtirish uchun 'yangilik' balli — expires_at katta bo'lsa yangiroq."""
    if not isinstance(token_data, dict):
        return -1
    exp = token_data.get("expires_at")
    if isinstance(exp, (int, float)):
        return int(exp)
    if token_data.get("refresh_token"):
        return 0
    return -1


def pick_freshest(*candidates: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Bir nechta token payload'idan eng yangisini tanlaydi (expires_at bo'yicha)."""
    best: Optional[Dict[str, Any]] = None
    best_score = -1
    for cand in candidates:
        score = _token_freshness(cand)
        if cand and score > best_score:
            best = cand
            best_score = score
    return best
