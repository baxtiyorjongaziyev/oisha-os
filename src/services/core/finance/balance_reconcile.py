"""Kunlik qoldiq rekonsiliatsiyasi: Airtable joriy balansi va fakt saldoni solishtirish.

Airtable ``Hisoblar`` jadvalida har faol hisob uchun
``Joriy balans (hisob valyutasida)`` (formula) va moliyachi kiritadigan
``Fakt saldo (hisob valyutasida)`` + ``Fakt saldo sanasi`` bor.

* Fakt saldo bugungi sana bilan kiritilgan va farq chegaradan katta boʻlsa —
  moliya guruhining balans topigiga va Ownerga qisqa ogohlantirish.
  Farq yoʻq boʻlsa — jim.
* Fakt saldo 2 kundan ortiq yangilanmagan faol hisob boʻyicha bir martalik
  eslatma (har bir eski sana uchun faqat bir marta).

Yuborish ``claim_job_run`` orqali idempotent: hisob+kun boʻyicha bir marta,
restartdan keyin ham. Quiet-hours (23:00–07:00 Toshkent) da hech narsa
yuborilmaydi.
"""

from __future__ import annotations

import html
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

JORIY_FIELD = "Joriy balans (hisob valyutasida)"
FAKT_FIELD = "Fakt saldo (hisob valyutasida)"
FAKT_DATE_FIELD = "Fakt saldo sanasi"

THRESHOLD_UZS = 10_000.0
THRESHOLD_USD = 1.0
STALE_DAYS = 2

MISMATCH_JOB_PREFIX = "balance_reconcile:"
STALE_JOB_PREFIX = "balance_stale:"


@dataclass(frozen=True)
class Mismatch:
    record_id: str
    nom: str
    valyuta: str
    joriy: float
    fakt: float

    @property
    def farq(self) -> float:
        return self.fakt - self.joriy


@dataclass(frozen=True)
class StaleAccount:
    record_id: str
    nom: str
    sana: str  # oxirgi fakt saldo sanasi ("" — hech qachon kiritilmagan)


def _select_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or "")
    if isinstance(value, list) and value:
        return _select_name(value[0])
    return str(value or "")


def _to_float(value: Any) -> Optional[float]:
    if isinstance(value, list):
        value = value[0] if value else None
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def threshold_for(valyuta: str) -> float:
    return THRESHOLD_USD if valyuta.strip().upper() == "USD" else THRESHOLD_UZS


def _active(fields: dict) -> bool:
    # Airtable belgilanmagan checkboxni javobdan tushirib qoldiradi — yoʻq = nofaol.
    return bool(fields.get("Faol"))


def find_mismatches(records: list[dict], today_iso: str) -> list[Mismatch]:
    """Bugun fakt saldo kiritilgan va farq chegaradan katta faol hisoblar."""
    out: list[Mismatch] = []
    for r in records:
        f = r.get("fields") or {}
        if not _active(f):
            continue
        if str(f.get(FAKT_DATE_FIELD) or "")[:10] != today_iso:
            continue
        joriy = _to_float(f.get(JORIY_FIELD))
        fakt = _to_float(f.get(FAKT_FIELD))
        if joriy is None or fakt is None:
            continue
        valyuta = _select_name(f.get("Valyuta")) or "UZS"
        if abs(fakt - joriy) > threshold_for(valyuta):
            out.append(Mismatch(
                record_id=str(r.get("id") or ""),
                nom=str(f.get("Hisob nomi") or "Hisob"),
                valyuta=valyuta,
                joriy=joriy,
                fakt=fakt,
            ))
    return out


def find_stale(records: list[dict], today: date, days: int = STALE_DAYS) -> list[StaleAccount]:
    """Fakt saldo ``days`` kundan ortiq yangilanmagan faol hisoblar."""
    out: list[StaleAccount] = []
    for r in records:
        f = r.get("fields") or {}
        if not _active(f):
            continue
        sana = str(f.get(FAKT_DATE_FIELD) or "")[:10]
        stale = True
        if sana:
            try:
                stale = (today - date.fromisoformat(sana)).days > days
            except ValueError:
                stale = True
        if stale:
            out.append(StaleAccount(
                record_id=str(r.get("id") or ""),
                nom=str(f.get("Hisob nomi") or "Hisob"),
                sana=sana,
            ))
    return out


def _fmt(amount: float, valyuta: str) -> str:
    if valyuta.strip().upper() == "USD":
        return f"{amount:,.2f}".replace(",", " ") + " $"
    return f"{amount:,.0f}".replace(",", " ") + " soʻm"


def format_mismatch(m: Mismatch) -> str:
    return (
        f"⚠️ <b>{html.escape(m.nom)}</b>: Airtable {_fmt(m.joriy, m.valyuta)}, "
        f"fakt {_fmt(m.fakt, m.valyuta)}, farq <b>{_fmt(m.farq, m.valyuta)}</b> — tekshiring "
        "(Chiqim oʻrniga Transfer? kiritilmagan kirim?)"
    )


def format_stale(s: StaleAccount) -> str:
    oxirgi = s.sana or "hech qachon"
    return (
        f"🔔 <b>{html.escape(s.nom)}</b>: fakt saldo {STALE_DAYS} kundan ortiq yangilanmagan "
        f"(oxirgi: <code>{oxirgi}</code>). Bugungi qoldiqni kiriting."
    )


async def _send_owner(text: str) -> bool:
    from src.settings import settings

    owner = int(getattr(settings, "OWNER_ID", 0) or 0)
    bot_token = os.environ.get("BOT_TOKEN") or getattr(settings, "BOT_TOKEN", None)
    if hasattr(bot_token, "get_secret_value"):
        bot_token = bot_token.get_secret_value()
    if owner <= 0 or not bot_token:
        return False
    try:
        from telegram import Bot

        await Bot(token=bot_token).send_message(chat_id=owner, text=text[:4000], parse_mode="HTML")
        return True
    except Exception:
        logger.error("[RECONCILE] Ownerga yuborilmadi", exc_info=True)
        return False


async def _send_group(text: str) -> bool:
    from src.schedulers.moliya.helpers import send

    return await send(text, "HISOBCHI_BALANCE_TOPIC_ID")


async def _claim(job: str, day: str) -> bool:
    from src.schedulers.moliya.helpers import once_per_day

    return await once_per_day(job, day)


async def _release(job: str, day: str) -> None:
    from src.schedulers.moliya.helpers import release_day

    await release_day(job, day)


async def _read_hisoblar() -> tuple[list[dict], bool]:
    from src.schedulers.moliya.helpers import read_table_checked

    return await read_table_checked("Hisoblar")


async def run_balance_reconcile(
    now: datetime,
    *,
    read_records: Callable[[], Awaitable[tuple[list[dict], bool]]] = _read_hisoblar,
    send_group: Callable[[str], Awaitable[bool]] = _send_group,
    send_owner: Callable[[str], Awaitable[bool]] = _send_owner,
    claim: Callable[[str, str], Awaitable[bool]] = _claim,
    release: Callable[[str, str], Awaitable[None]] = _release,
) -> int:
    """Bir marta tekshiradi; yuborilgan xabarlar sonini qaytaradi."""
    from src.time_utils import is_quiet_hours

    if is_quiet_hours(now):
        return 0
    records, ok = await read_records()
    if not ok:
        return 0
    today_iso = now.strftime("%Y-%m-%d")
    sent = 0

    for m in find_mismatches(records, today_iso):
        text = format_mismatch(m)
        # Har manzil uchun alohida claim: biri xato boʻlsa faqat shu qayta urinadi.
        for dest, sender in (("group", send_group), ("owner", send_owner)):
            job = f"{MISMATCH_JOB_PREFIX}{dest}:{m.record_id}"
            if not await _safe_claim(claim, job, today_iso):
                continue
            if await sender(text):
                sent += 1
            else:
                await release(job, today_iso)

    for s in find_stale(records, now.date()):
        # Har bir eski sana uchun bir marta: yangi fakt kiritilib yana eskirsa — yangi eslatma.
        job = f"{STALE_JOB_PREFIX}{s.record_id}"
        key = s.sana or "never"
        if not await _safe_claim(claim, job, key):
            continue
        if await send_group(format_stale(s)):
            sent += 1
        else:
            await release(job, key)
    return sent


async def _safe_claim(claim: Callable[[str, str], Awaitable[bool]], job: str, key: str) -> bool:
    try:
        return bool(await claim(job, key))
    except Exception:
        logger.warning("[RECONCILE] claim xatosi (%s)", job, exc_info=True)
        return False
