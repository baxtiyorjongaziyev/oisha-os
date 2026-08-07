"""Telethon userbot session guard — AuthKeyDuplicatedError oldini oladi.

## Muammo

Prod userbot auth key (``USERBOT_SESSION_STRING``) Oracle VM dagi
``oisha-os.service`` ga tegishli: u doimiy Telethon ulanishini ushlab turadi.
O'sha auth key ni boshqa hostdan (masalan GitHub-hosted runner) ulasak,
Telegram buni "the authorization key was used under two different IP addresses
simultaneously" deb hisoblaydi va kalitni BUTUNLAY bekor qiladi
(``AuthKeyDuplicatedError``).

Bu qaytarib bo'lmaydigan xato — faqat bitta workflow emas, butun prod userbot
o'ladi va yangi session qo'lda generatsiya qilinishi kerak.

## Yechim

Har bir bir martalik (one-off) userbot skripti ulanishdan OLDIN shu moduldan
o'tadi:

1. :func:`resolve_session` — avval ATALGAN (dedicated) session qidiriladi,
   faqat u yo'q bo'lsa prod kaliti ishlatiladi.
2. :func:`assert_owner_host` — prod kaliti egasi bo'lmagan hostda (ya'ni
   GitHub-hosted runner da) ishlashni TAQIQLAYDI.
3. :func:`single_flight` — bitta hostda ikkita one-off skript bir vaqtda
   ulanmasligi uchun lock.
4. :func:`guarded_connect` — kalit kuygan bo'lsa xom traceback o'rniga aniq,
   nima qilish kerakligini aytadigan xato beradi.

Modul ataylab faqat stdlib ga (va ulanish paytida Telethon ga) tayanadi, chunki
skriptlar minimal muhitda ham ishlaydi.
"""

from __future__ import annotations

import contextlib
import logging
import os
import socket
from dataclasses import dataclass
from typing import Iterator, Mapping, Optional, Sequence

logger = logging.getLogger(__name__)

#: Barcha one-off skriptlar uchun umumiy atalgan session (prod dan alohida).
GENERIC_DEDICATED_ENV = "TELEGRAM_ONEOFF_SESSION_STRING"

#: Oracle VM dagi prod userbot kaliti — bu kalitning EGASI oisha-os.service.
SHARED_PROD_ENV = "USERBOT_SESSION_STRING"

#: Prod session stringi diskda saqlanadigan joylar (session_keeper yozadi).
SHARED_PROD_FILES: Sequence[str] = (
    "data/userbot_session_string.txt",
    "data/session_output.txt",
)

#: Prod kalitini begona hostda ishlatishga ruxsat beruvchi ataylab qo'yilgan
#: escape hatch. Faqat oisha-os.service TO'XTATILGAN bo'lsa ishlating.
ALLOW_SHARED_ENV = "ALLOW_SHARED_USERBOT_SESSION"

#: Ixtiyoriy: prod kaliti egasi bo'lgan hostname. Qo'yilgan bo'lsa, boshqa
#: hostda prod kaliti bilan ulanish taqiqlanadi.
OWNER_HOST_ENV = "USERBOT_SESSION_OWNER_HOST"

_LOCK_DIR = "data/locks"

_RECOVERY_STEPS = (
    "Tiklash tartibi:\n"
    "1. Prod kalitini ishlatayotgan HAMMA jarayonni to'xtating "
    "(Oracle: sudo systemctl stop oisha-os).\n"
    "2. Yangi session generatsiya qiling: generate-session.yml workflow "
    "yoki scripts/generate_session_string.py.\n"
    "3. Yangi stringni USERBOT_SESSION_STRING secret'iga va Oracle .env ga yozing.\n"
    "4. Servisni qayta ishga tushiring: sudo systemctl start oisha-os.\n"
    "5. One-off skriptlar uchun ALOHIDA session oling va uni "
    f"{GENERIC_DEDICATED_ENV} ga qo'ying — shunda prod kaliti hech qachon "
    "ikkinchi marta ochilmaydi."
)


class SessionConflictError(RuntimeError):
    """Session xavfsizlik qoidasi buzildi — ulanmaslik kerak."""


class SessionMissingError(RuntimeError):
    """Hech qanday session string topilmadi."""


@dataclass(frozen=True)
class SessionSource:
    """Qaysi session qayerdan olingani."""

    string: str
    origin: str
    is_shared_prod: bool

    def __repr__(self) -> str:  # pragma: no cover - faqat debug uchun
        return (
            f"SessionSource(origin={self.origin!r}, len={len(self.string)}, "
            f"is_shared_prod={self.is_shared_prod})"
        )


def parse_bool(value: Optional[str]) -> bool:
    """Env qiymatini truthy ga o'giradi (agent_runtime.parse_bool bilan bir xil)."""
    if not value:
        return False
    return str(value).replace("\ufeff", "").strip().lower() in {"1", "true", "yes", "on"}


def is_github_hosted_runner(env: Optional[Mapping[str, str]] = None) -> bool:
    """GitHub-hosted runner ustida turibmizmi?

    ``RUNNER_ENVIRONMENT`` ni GitHub o'zi ``github-hosted`` yoki ``self-hosted``
    qilib qo'yadi. Noma'lum qiymat fail-safe tarzda "hosted" deb qabul qilinadi:
    prod kalitini noaniq hostda ochgandan ko'ra ishni to'xtatgan yaxshiroq.

    appleboy/ssh-action orqali Oracle VM ichida bajarilgan buyruqlarga bu env
    lar uzatilmaydi, shuning uchun u yerda natija ``False`` bo'ladi.
    """
    env = os.environ if env is None else env
    if not parse_bool(env.get("GITHUB_ACTIONS")):
        return False
    return env.get("RUNNER_ENVIRONMENT", "").strip().lower() != "self-hosted"


def _read_file_session(path: str) -> str:
    try:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as handle:
                return handle.read().strip()
    except OSError as exc:
        logger.warning("[GUARD] %s o'qilmadi: %s", path, exc)
    return ""


def resolve_session(
    dedicated_env: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    shared_files: Optional[Sequence[str]] = None,
) -> SessionSource:
    """Ishlatiladigan session ni tanlaydi: ATALGAN > prod fayl > prod env.

    Args:
        dedicated_env: Skriptga xos env nomi, masalan ``JUMA_SESSION_STRING``.
        env: Environment mapping (test uchun).
        shared_files: Prod session fayllari (test uchun).

    Raises:
        SessionMissingError: hech qayerda session topilmasa.
    """
    env = os.environ if env is None else env
    shared_files = SHARED_PROD_FILES if shared_files is None else shared_files

    for name in (dedicated_env, GENERIC_DEDICATED_ENV):
        if not name:
            continue
        value = (env.get(name) or "").strip()
        if value:
            return SessionSource(string=value, origin=f"env:{name}", is_shared_prod=False)

    for path in shared_files:
        value = _read_file_session(path)
        if value:
            return SessionSource(string=value, origin=f"file:{path}", is_shared_prod=True)

    value = (env.get(SHARED_PROD_ENV) or "").strip()
    if value:
        return SessionSource(
            string=value, origin=f"env:{SHARED_PROD_ENV}", is_shared_prod=True
        )

    raise SessionMissingError(
        "Session string topilmadi. "
        f"{dedicated_env or GENERIC_DEDICATED_ENV} yoki {SHARED_PROD_ENV} kerak."
    )


def assert_owner_host(
    source: SessionSource,
    env: Optional[Mapping[str, str]] = None,
    hostname: Optional[str] = None,
) -> None:
    """Prod kalitini begona hostda ochishga urinilsa xato beradi.

    Atalgan session uchun hech qanday cheklov yo'q — u prod bilan raqobatlashmaydi.
    """
    env = os.environ if env is None else env
    if not source.is_shared_prod:
        return

    if parse_bool(env.get(ALLOW_SHARED_ENV)):
        logger.warning(
            "[GUARD] %s=1 — prod session tekshiruvi o'chirildi. "
            "oisha-os.service to'xtatilganiga ishonch hosil qiling!",
            ALLOW_SHARED_ENV,
        )
        return

    if is_github_hosted_runner(env):
        raise SessionConflictError(
            "Prod userbot session (%s) GitHub-hosted runner da ochilmaydi.\n"
            "Runner ning IP si Oracle VM dan boshqa — Telegram kalitni "
            "AuthKeyDuplicated qilib butunlay bekor qiladi va prod userbot o'ladi.\n"
            "Ishni Oracle VM da bajaring (ssh-action yoki [self-hosted, oracle] runner), "
            "yoki %s ga ALOHIDA session qo'ying." % (source.origin, GENERIC_DEDICATED_ENV)
        )

    owner_host = (env.get(OWNER_HOST_ENV) or "").strip()
    if owner_host:
        current = hostname or socket.gethostname()
        if current.strip().lower() != owner_host.lower():
            raise SessionConflictError(
                f"Prod userbot session faqat {owner_host!r} hostiga tegishli, "
                f"hozirgi host {current!r}. Ulanish to'xtatildi — aks holda "
                "AuthKeyDuplicated bo'ladi."
            )

    logger.warning(
        "[GUARD] Prod userbot session ishlatilmoqda (%s). oisha-os.service "
        "ayni paytda shu kalitni ushlab turadi — %s ga alohida session qo'yish tavsiya etiladi.",
        source.origin,
        GENERIC_DEDICATED_ENV,
    )


@contextlib.contextmanager
def single_flight(name: str, lock_dir: str = _LOCK_DIR) -> Iterator[None]:
    """Bitta hostda bir vaqtning o'zida bitta one-off userbot skripti ishlasin.

    ``fcntl`` yo'q platformalarda (Windows dev) lock o'tkazib yuboriladi.
    """
    try:
        import fcntl
    except ImportError:  # pragma: no cover - Windows
        logger.warning("[GUARD] fcntl yo'q — single-flight lock o'tkazib yuborildi")
        yield
        return

    os.makedirs(lock_dir, exist_ok=True)
    path = os.path.join(lock_dir, f"{name}.lock")
    handle = open(path, "w", encoding="utf-8")  # noqa: SIM115 - lock umri context bilan
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise SessionConflictError(
                f"Boshqa userbot skripti allaqachon ishlayapti ({path}). "
                "Ikkita Telethon client bir kalit bilan ulanmasligi uchun to'xtatildi."
            ) from exc
        handle.write(str(os.getpid()))
        handle.flush()
        yield
    finally:
        with contextlib.suppress(OSError):
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def is_auth_key_duplicated(exc: BaseException) -> bool:
    """Xato AuthKeyDuplicated (kalit kuygan) ekanini aniqlaydi.

    ``telegram_session_manager._is_auth_key_duplicated`` bilan bir xil mantiq,
    lekin bu yerda src ga bog'liqliksiz.
    """
    text = f"{type(exc).__name__}:{exc}".upper()
    return (
        "AUTH_KEY_DUPLICATED" in text
        or "AUTHKEYDUPLICATED" in text
        or "TWO DIFFERENT IP ADDRESSES" in text
    )


def burned_session_report(source: SessionSource, exc: BaseException) -> str:
    """Kalit kuyganda egasiga yuboriladigan aniq xabar."""
    return (
        "🔴 SESSION KUYDI (AuthKeyDuplicated)\n\n"
        f"Manba: {source.origin}\n"
        f"Telegram: {exc}\n\n"
        "Sabab: shu auth key bir vaqtda ikki xil IP dan ishlatilgan — "
        "odatda prod kaliti Oracle VM dan tashqarida (GitHub runner, lokal mashina) "
        "ochilganda sodir bo'ladi.\n\n" + _RECOVERY_STEPS
    )


async def guarded_connect(client, source: SessionSource):
    """``client.connect()`` — kuygan kalitni aniq xato bilan xabar qiladi.

    Raises:
        SessionConflictError: kalit AuthKeyDuplicated bo'lsa (tiklash yo'riqnomasi bilan).
    """
    try:
        await client.connect()
    except Exception as exc:
        if is_auth_key_duplicated(exc):
            raise SessionConflictError(burned_session_report(source, exc)) from exc
        raise
    return client


async def guarded_is_authorized(client, source: SessionSource) -> bool:
    """``client.is_user_authorized()`` — kuygan kalitni aniq xato bilan xabar qiladi.

    Telethon transport darajasida ulana olishi, lekin kalit kuyganini faqat
    birinchi RPC da bildirishi mumkin — shuning uchun bu tekshiruv ham
    guard'dan o'tishi kerak.
    """
    try:
        return bool(await client.is_user_authorized())
    except Exception as exc:
        if is_auth_key_duplicated(exc):
            raise SessionConflictError(burned_session_report(source, exc)) from exc
        raise


def prepare(dedicated_env: Optional[str] = None) -> SessionSource:
    """Skriptlar uchun qulay yig'ma qadam: resolve + owner-host tekshiruvi."""
    source = resolve_session(dedicated_env=dedicated_env)
    assert_owner_host(source)
    logger.info("[GUARD] Session manbasi: %s", source.origin)
    return source
