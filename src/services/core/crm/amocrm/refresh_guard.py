"""AmoCRM refresh_token oqimini SIGKILL/parallel-proof qiladigan qatlam.

Nega bu modul bor
=================
AmoCRM refresh_token'lari **rotatsiya** qilinadi: har muvaffaqiyatli
``grant_type=refresh_token`` so'rovi yangi ``refresh_token`` qaytaradi va
eskisi bir necha soniya ichida bekor bo'ladi. Bu ikkita nozik holatni
ochadi:

1. **Parallel refresh** — ikki instance (yoki bir instance ichida ikki
   scheduler) bir vaqtda refresh qilса, biri rotatsiyani yutadi, ikkinchisi
   endi bekor bo'lgan token bilan urinadi va HTTP 400 oladi. Kod uni
   "reauthorization required" deb 1 soatga bloklaydi — aslida token
   yangi, faqat boshqa joyda.

2. **Refresh o'rtasida process o'limi** — Oracle VM'da servis shutdown
   timeout'da ``SIGKILL`` (status=9) bilan o'ladi. Agar refresh 200 qaytarib,
   yangi payload diskка/DB'ga yozilishidan oldin process o'lса — keyingi
   start eski (endi bekor) refresh_token bilan boshlanadi va abadiy 400.

Yechim: refresh'ni **cross-process fayl-lock** ostida bajarish va 400/401'da
darrov bloklamasdan, bardavom joydan (Turso DB) eng yangi tokenни qayta
o'qib bir marta qayta urinish. Faqat DB'dagi token ham haqiqatan eskirgan
bo'lsagina blok + owner alert.

Windows'da (``fcntl`` yo'q, lokal userbot baribir o'chirilgan) lock no-op.
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, Optional

import structlog

logger = structlog.get_logger()

try:
    import fcntl  # type: ignore

    _HAVE_FCNTL = True
except ImportError:  # pragma: no cover - Windows dev
    _HAVE_FCNTL = False

# Lock ushlab turishning yuqori chegarasi. Refresh so'rovi 30s timeout bilan
# ketadi, DB o'qish yana ~20s; ikki barobar zaxira bilan 90s.
_LOCK_ACQUIRE_TIMEOUT_S = 90
_LOCK_POLL_INTERVAL_S = 0.5


def _lock_path() -> str:
    """``data/.amocrm-refresh.lock`` — token faylи yonida."""
    base = os.environ.get("OISHA_DATA_DIR") or os.path.join(os.getcwd(), "data")
    return os.path.join(base, ".amocrm-refresh.lock")


@contextmanager
def refresh_lock():
    """Cross-process eksklyuziv lock. Windows'da yoki lock olib bo'lmasa no-op.

    Timeout ичида lock olinmasa — bloklamaymiz, chaqiruvchi baribir davom
    etadi (eng yomon holatда parallel refresh bo'ladi, lekin uni keyingi
    DB-reload retry yopadi).
    """
    if not _HAVE_FCNTL:
        yield
        return

    path = _lock_path()
    try:
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    except OSError:
        yield
        return

    fd = None
    acquired = False
    deadline = time.monotonic() + _LOCK_ACQUIRE_TIMEOUT_S
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        while time.monotonic() < deadline:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError:
                time.sleep(_LOCK_POLL_INTERVAL_S)
        if not acquired:
            logger.warning("[AMOCRM REFRESH GUARD] Lock timeout — guardsiz davom")
        yield
    finally:
        if fd is not None:
            try:
                if acquired:
                    fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                os.close(fd)
            except OSError:
                pass


def _access_token_still_valid(token_data: Optional[Dict[str, Any]], skew_s: int = 120) -> bool:
    """DB'dan qayta o'qilgan payload hali API uchun yaroqlimi.

    ``expires_at`` kelajakда (skew zaxirasi bilan) va access_token bo'lса — ha.
    Long-lived token'да ``expires_at`` juda katta bo'ladi, bu ham to'g'ri o'tadi.
    """
    if not isinstance(token_data, dict):
        return False
    if not token_data.get("access_token"):
        return False
    exp = token_data.get("expires_at")
    if not isinstance(exp, (int, float)):
        return False
    return exp > (time.time() + skew_s)


def refresh_with_guard(
    do_refresh: Callable[[], bool],
    reload_freshest: Callable[[], Optional[Dict[str, Any]]],
    apply_token: Callable[[Dict[str, Any]], None],
) -> bool:
    """Sinmaydigan refresh oqimi.

    Parametrlar:
      * ``do_refresh`` — haqiqiy HTTP refresh (``AmoCRMAuthMixin._do_http_refresh``).
        ``True`` -> yangi token saqlandi.
      * ``reload_freshest`` — env/fayl/DB'dan eng yangi payload (``pick_freshest``
        natijasi) yoki ``None``.
      * ``apply_token`` — payload'ni mixin holatiga o'rnatadi (``_set_token_data``).

    Qaytaradi: token yangilangan yoki allaqachon yaroqli bo'lса ``True``.
    """
    with refresh_lock():
        # 1. Lock ostida — boshqa process bizdan oldin yangilagan bo'lishi mumkin.
        pre = _safe_call(reload_freshest)
        if _access_token_still_valid(pre):
            apply_token(pre)  # type: ignore[arg-type]
            logger.info("[AMOCRM REFRESH GUARD] Bardavom joyda yangi token topildi — HTTP refresh kerak emas")
            return True

        # 2. Haqiqiy refresh.
        if do_refresh():
            return True

        # 3. 400/401 keldi. Boshqa instance aynan hozir rotatsiya qilgan
        #    bo'lishi mumkin — DB'ni qayta o'qib bitta imkoniyat beramiz.
        post = _safe_call(reload_freshest)
        if post and post != pre and _access_token_still_valid(post):
            apply_token(post)
            logger.warning(
                "[AMOCRM REFRESH GUARD] HTTP refresh 4xx bo'ldi, lekin bardavom joyda "
                "yangiroq token bor — o'sha ishlatiladi (parallel rotatsiya)"
            )
            return True

        logger.critical(
            "[AMOCRM REFRESH GUARD] HTTP refresh ham, bardavom joydagi token ham "
            "yaroqsiz — owner qayta avtorizatsiya qilishi kerak"
        )
        return False


def _safe_call(fn: Callable[[], Optional[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    try:
        return fn()
    except Exception as exc:  # pragma: no cover - defensiv
        logger.warning("[AMOCRM REFRESH GUARD] reload xatosi: %s", type(exc).__name__)
        return None
