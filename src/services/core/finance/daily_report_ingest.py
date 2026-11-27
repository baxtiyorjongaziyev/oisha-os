"""Moliya guruhidagi "Kunlik moliya" hisobotidan fakt saldoni olish.

Moliyachi har kuni guruhga hisobot yozadi; uning "Kun oxiri pul" boʻlimi
toʻrt hisobning fakt qoldigʻini beradi. Bu modul:

1. boʻlimni parse qiladi (NBSP / narrow NBSP boʻshliqlar, vergulli oʻnlik, "900$");
2. Airtable ``Hisoblar`` ga ``Fakt saldo`` maydonlarini yozadi (oxirgisi yutadi);
3. yangilangan joriy balans bilan solishtirib, reply matnini qaytaradi.

Faqat moliyachi (``MOLIYACHI_TELEGRAM_ID``) yoki Owner yuborgan xabar qabul qilinadi.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Awaitable, Callable, Optional

from src.services.core.finance.balance_reconcile import (
    FAKT_DATE_FIELD,
    FAKT_FIELD,
    JORIY_FIELD,
    _fmt,
    _to_float,
    threshold_for,
)

logger = logging.getLogger(__name__)

SOURCE_LABEL = "Moliya guruhi — kunlik hisobot"
SOURCE_FIELD = "Fakt saldo manbasi"
HEADER_MARK = "kunlik moliya"
SECTION_MARK = "kun oxiri pul"
MAX_DATE_SKEW_DAYS = 2

# hisobot qatori -> (Airtable record id, valyuta)
ACCOUNT_MAP: dict[str, tuple[str, str]] = {
    "P2P": ("recNtlN2Sj7LDtkMG", "UZS"),
    "Bank": ("recHVOcCQkisfitiD", "UZS"),
    "Naqd UZS": ("recTZ8GgVFBdZGf8s", "UZS"),
    "Naqd USD": ("recseGjV7hF4L1vl7", "USD"),
}

_SPACES = re.compile(r"[\s    ]+")
_DATE_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")
_LINE_RE = re.compile(r"^\s*(P2P|Bank|Naqd\s+UZS|Naqd\s+USD)\s*[—–:\-]+\s*(.+?)\s*$", re.IGNORECASE)


@dataclass
class DailyReport:
    report_date: Optional[date]
    balances: dict[str, float] = field(default_factory=dict)


# Sarlavha xabar boshida boʻlishi shart: "📊 Kunlik moliya — DD.MM.YYYY".
# Qoida/pin xabarlarida ibora matn ichida uchraydi — ular eʼtiborsiz qoladi.
_HEADER_RE = re.compile(
    r"^\W*kunlik\s+moliya\s*[—–:\-]*\s*\d{1,2}\.\d{1,2}\.\d{4}",
    re.IGNORECASE,
)


def is_daily_report(text: str) -> bool:
    first = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    return bool(_HEADER_RE.match(first))


def parse_amount(raw: str) -> Optional[float]:
    s = _SPACES.sub("", raw or "")
    s = re.sub(r"(?i)(\$|usd|uzs|so.?m|сум)", "", s)
    if not s:
        return None
    s = s.replace(",", ".")
    if s.count(".") > 1:  # 1.234.567 — minglik nuqtalar
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def _canon(name: str) -> str:
    n = _SPACES.sub(" ", name).strip().lower()
    for key in ACCOUNT_MAP:
        if key.lower() == n:
            return key
    return name


def parse_daily_report(text: str) -> DailyReport:
    """Faqat "Kun oxiri pul" boʻlimidan qoldiqlarni oladi."""
    report_date: Optional[date] = None
    m = _DATE_RE.search(text or "")
    if m:
        try:
            report_date = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            report_date = None

    balances: dict[str, float] = {}
    in_section = False
    for line in (text or "").splitlines():
        low = line.strip().lower()
        if not in_section:
            if low.startswith(SECTION_MARK):
                in_section = True
            continue
        if not low:
            if balances:
                break
            continue
        if low.startswith("nazorat"):
            break
        lm = _LINE_RE.match(line)
        if not lm:
            continue
        amount = parse_amount(lm.group(2))
        if amount is not None:
            balances[_canon(lm.group(1))] = amount
    return DailyReport(report_date=report_date, balances=balances)


def is_authorized_sender(user_id: int) -> bool:
    from src.settings import settings

    allowed = set()
    for raw in (os.getenv("MOLIYACHI_TELEGRAM_ID", ""), getattr(settings, "OWNER_ID", None)):
        try:
            uid = int(raw or 0)
        except (TypeError, ValueError):
            continue
        if uid > 0:
            allowed.add(uid)
    return user_id > 0 and user_id in allowed


def build_reconcile_reply(report: DailyReport, records: list[dict]) -> tuple[str, bool]:
    """(matn, farq_bor) — hisobotdagi fakt va Airtable joriy balans solishtiruvi."""
    by_id = {str(r.get("id")): (r.get("fields") or {}) for r in records}
    lines: list[str] = []
    for key, fakt in report.balances.items():
        rid, valyuta = ACCOUNT_MAP[key]
        joriy = _to_float(by_id.get(rid, {}).get(JORIY_FIELD))
        if joriy is None:
            lines.append(f"❔ {key}: Airtable balansi topilmadi")
            continue
        if abs(fakt - joriy) > threshold_for(valyuta):
            lines.append(
                f"⚠️ {key}: Airtable {_fmt(joriy, valyuta)}, hisobot {_fmt(fakt, valyuta)}, "
                f"farq {_fmt(fakt - joriy, valyuta)}"
            )
    if not lines:
        return "✅ Airtable bilan mos", False
    lines.append("Tekshiring: Chiqim oʻrniga Transfer? kiritilmagan kirim?")
    return "\n".join(lines), True


async def _write_airtable(record_id: str, fields: dict) -> bool:
    from src.services.core.airtable_sync import AirtableSync

    def _patch() -> bool:
        return bool(AirtableSync(table_name="Hisoblar").update_project_fields(record_id, fields))

    return await asyncio.to_thread(_patch)


async def _read_hisoblar() -> tuple[list[dict], bool]:
    from src.schedulers.moliya.helpers import read_table_checked

    return await read_table_checked("Hisoblar")


async def ingest_daily_report(
    text: str,
    *,
    sender_id: int,
    message_date: date,
    write: Callable[[str, dict], Awaitable[bool]] = _write_airtable,
    read_records: Callable[[], Awaitable[tuple[list[dict], bool]]] = _read_hisoblar,
    notify_owner: Optional[Callable[[str], Awaitable[bool]]] = None,
) -> Optional[str]:
    """Hisobotni qayta ishlaydi; guruhga reply matnini qaytaradi (None — eʼtiborsiz)."""
    if not is_daily_report(text) or not is_authorized_sender(sender_id):
        return None
    report = parse_daily_report(text)
    if not report.balances:
        return "⚠️ «Kun oxiri pul» boʻlimidan qoldiq oʻqilmadi — format tekshiring."
    rdate = report.report_date or message_date
    skew = abs((message_date - rdate).days)
    if skew > MAX_DATE_SKEW_DAYS:
        return (
            f"⚠️ Hisobot sanasi {rdate:%d.%m.%Y}, xabar sanasi {message_date:%d.%m.%Y} — "
            f"farq {skew} kun. Sanani tekshiring; Airtable ga yozilmadi."
        )

    failed: list[str] = []
    for key, amount in report.balances.items():
        rid, _ = ACCOUNT_MAP[key]
        ok = await write(rid, {
            FAKT_FIELD: amount,
            FAKT_DATE_FIELD: rdate.isoformat(),
            SOURCE_FIELD: SOURCE_LABEL,
        })
        if not ok:
            failed.append(key)

    records, ok = await read_records()
    if not ok:
        return "⚠️ Fakt saldo yozildi, lekin Airtable balansi oʻqilmadi — solishtirish boʻlmadi."
    reply, has_diff = build_reconcile_reply(report, records)
    if failed:
        reply += "\n❗ Airtable ga yozilmadi: " + ", ".join(failed)
    if has_diff and notify_owner is not None:
        await notify_owner(f"📊 Kunlik moliya {rdate:%d.%m.%Y}\n{reply}")
    return reply
