"""Haftalik moliya nazorati — Oisha moliyachi ishini hafta kesimida tekshiradi.

Har dushanba 09:00 da faqat egasiga (OWNER_ID) oʻtgan hafta (dushanba–yakshanba)
boʻyicha bitta jamlama yuboriladi:

* kunlar kesimida Airtable yozuvlari va guruh xabarlari (yozuvsiz kunlar belgilanadi);
* haftalik kirim/chiqim;
* Hisobchi taxmini bilan moliyachi tanlovining moslik foizi;
* yozuv kamchiliklari soni va eng koʻp uchraganlari;
* hozirgi qoldiq holati: Airtable va fakt saldo farqlari, eskirgan fakt saldolar.

Hech narsa yozilmaydi, guruhga yuborilmaydi. Maʻlumot olinmasa raqam toʻqilmaydi.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Optional

from src.schedulers.moliya.cashflow import KATEGORIYA_JADVALLARI
from src.schedulers.moliya.helpers import esc, fmt, read_name_map, read_table_checked, select_name
from src.schedulers.moliya.kuzatuv import (
    _evaluate_today,
    _sana,
    learn_rules,
    load_observation,
    quality_gaps,
    send_owner_finance,
)

logger = logging.getLogger(__name__)

HAFTALIK_WEEKDAY = 0  # dushanba
HAFTALIK_HOUR = 9
KUN_NOMLARI = ("Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya")


def haftalik_target(now: datetime) -> Optional[date]:
    """Dushanba 09:00–09:04 da oʻtgan haftaning dushanbasini qaytaradi."""
    if now.weekday() == HAFTALIK_WEEKDAY and now.hour == HAFTALIK_HOUR and now.minute < 5:
        return (now - timedelta(days=7)).date()
    return None


def _week_days(week_start: date) -> list[str]:
    return [(week_start + timedelta(days=i)).isoformat() for i in range(7)]


def _summa(records: list[dict], turi: str) -> float:
    total = 0.0
    for r in records:
        f = r.get("fields") or {}
        if select_name(f.get("Turi")) != turi:
            continue
        try:
            total += float(f.get("Summa UZS") or 0)
        except (TypeError, ValueError):
            continue
    return total


def balance_lines(hisoblar: list[dict], today: date) -> list[str]:
    """Hozirgi qoldiq holati: farqi bor va eskirgan faol hisoblar."""
    from src.services.core.finance.balance_reconcile import (
        FAKT_DATE_FIELD,
        FAKT_FIELD,
        JORIY_FIELD,
        STALE_DAYS,
        _fmt,
        _select_name,
        _to_float,
        find_stale,
        threshold_for,
    )

    lines: list[str] = []
    for r in hisoblar:
        f = r.get("fields") or {}
        if not f.get("Faol"):
            continue
        joriy = _to_float(f.get(JORIY_FIELD))
        fakt = _to_float(f.get(FAKT_FIELD))
        if joriy is None or fakt is None:
            continue
        valyuta = _select_name(f.get("Valyuta")) or "UZS"
        if abs(fakt - joriy) > threshold_for(valyuta):
            sana = str(f.get(FAKT_DATE_FIELD) or "")[:10] or "—"
            lines.append(
                f"• {esc(f.get('Hisob nomi') or 'Hisob')}: farq "
                f"<b>{_fmt(fakt - joriy, valyuta)}</b> (fakt {sana})"
            )
    for s in find_stale(hisoblar, today):
        oxirgi = s.sana or "hech qachon"
        lines.append(f"• {esc(s.nom)}: fakt saldo {STALE_DAYS}+ kun yangilanmagan ({oxirgi})")
    return lines


async def build_haftalik_report(
    week_start: date,
    *,
    today: Optional[date] = None,
    records: Optional[list[dict]] = None,
    records_ok: Optional[bool] = None,
    hisoblar: Optional[list[dict]] = None,
    hisoblar_ok: Optional[bool] = None,
    nomlar: Optional[dict[str, str]] = None,
    observations: Optional[dict[str, dict]] = None,
) -> str:
    days = _week_days(week_start)
    today = today or (week_start + timedelta(days=7))
    title = f"📊 <b>Haftalik moliya nazorati — {days[0]} … {days[-1]}</b>"

    if observations is None:
        observations = {d: await load_observation(d) for d in days}
    if records is None:
        records, ok = await read_table_checked("Tranzaksiyalar")
        records_ok = ok if records_ok is None else records_ok
    if hisoblar is None:
        hisoblar, ok = await read_table_checked("Hisoblar")
        hisoblar_ok = ok if hisoblar_ok is None else hisoblar_ok

    lines = [title, "<i>Faqat nazorat: hech narsa yozilmadi.</i>\n"]

    if records_ok is False:
        lines.append("Tranzaksiyalar: maʼlumot olinmadi (manba tekshirilmadi)")
    else:
        if nomlar is None:
            nomlar = await read_name_map(*KATEGORIYA_JADVALLARI)
        week = [r for r in records if _sana(r) in days]
        history = [r for r in records if _sana(r) and _sana(r) < days[0]]
        rules = learn_rules(history)

        lines.append(
            f"Yozuvlar: <b>{len(week)}</b> ta "
            f"(kirim {fmt(_summa(week, 'Kirim'))}, chiqim {fmt(_summa(week, 'Chiqim'))} soʻm)"
        )

        per_day = Counter(_sana(r) for r in week)
        kun_qatorlari = []
        bosh_kunlar = []
        for i, d in enumerate(days):
            obs = observations.get(d) or {}
            msgs = int(obs.get("messages", 0))
            n = per_day.get(d, 0)
            belgi = ""
            if n == 0 and i < 6:
                bosh_kunlar.append(KUN_NOMLARI[i])
                belgi = " ⚠️"
            kun_qatorlari.append(f"{KUN_NOMLARI[i]} {d[5:]}: {n} yozuv, {msgs} xabar{belgi}")
        lines.append("\n<b>Kunlar:</b>")
        lines.extend(kun_qatorlari)
        if bosh_kunlar:
            lines.append(f"⚠️ Ish kunida yozuv yoʻq: {', '.join(bosh_kunlar)}")

        checked, right, wrong, _ = _evaluate_today(week, rules, nomlar)
        if checked:
            lines.append(
                f"\nTaxmin mosligi: <b>{right}/{checked}</b> ({right * 100 // checked}%)"
            )
        else:
            lines.append("\nTaxmin mosligi: maʼlumot yoʻq")
        if wrong:
            lines.append("<b>Farqli kategoriyalar:</b>")
            lines.extend(wrong)

        gap_counter: Counter = Counter()
        gapli = 0
        for r in week:
            gaps = quality_gaps(r.get("fields") or {})
            if gaps:
                gapli += 1
                gap_counter.update(gaps)
        if gapli:
            top = ", ".join(f"{g} — {c}" for g, c in gap_counter.most_common(5))
            lines.append(f"\n<b>Kamchilikli yozuvlar:</b> {gapli} ta ({top})")
        else:
            lines.append("\nKamchilikli yozuvlar: yoʻq")

    lines.append("\n<b>Qoldiq holati (hozir):</b>")
    if hisoblar_ok is False:
        lines.append("Hisoblar: maʼlumot olinmadi (manba tekshirilmadi)")
    else:
        bal = balance_lines(hisoblar or [], today)
        lines.extend(bal or ["✅ Farq va eskirgan fakt saldo yoʻq"])

    return "\n".join(lines)


async def run_haftalik_report(week_start: date) -> bool:
    text = await build_haftalik_report(week_start)
    ok = await send_owner_finance(text)
    if ok:
        logger.info("[HISOBCHI] Haftalik nazorat yuborildi (%s)", week_start)
    return ok
