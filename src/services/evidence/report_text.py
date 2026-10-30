"""Telegram text for a payment promise report."""
from __future__ import annotations

from typing import List

from src.services.evidence.payment_promises import (
    TASHKENT_TZ,
    PaymentPromise,
    PromiseReport,
)

_MAX_ITEMS = 25
_MAX_QUOTE = 160


def _money(p: PaymentPromise) -> str:
    if p.amount is None:
        return "summa aytilmagan"
    if p.currency == "USD":
        return f"${p.amount:,}".replace(",", " ")
    return f"{p.amount:,} so'm".replace(",", " ")


def _line(p: PaymentPromise) -> str:
    when = p.promised_date.strftime("%d.%m.%Y") if p.promised_date else "sana noaniq"
    said = p.said_at.astimezone(TASHKENT_TZ).strftime("%d.%m %H:%M")
    quote = p.quote if len(p.quote) <= _MAX_QUOTE else p.quote[: _MAX_QUOTE - 1] + "…"
    lead = f"lid {p.lead_id}" if p.lead_id else "lid ?"
    return (
        f"• {when} — {_money(p)} ({lead})\n"
        f"  \"{quote}\"\n"
        f"  {p.speaker}, {said}, manba: {p.source} #{p.source_id}"
    )


def _section(title: str, items: List[PaymentPromise]) -> List[str]:
    if not items:
        return []
    out = [f"{title} ({len(items)}):"]
    out.extend(_line(p) for p in items[:_MAX_ITEMS])
    if len(items) > _MAX_ITEMS:
        out.append(f"… yana {len(items) - _MAX_ITEMS} ta")
    return out


def format_promise_report(report: PromiseReport, days: int) -> str:
    lines = [f"💰 To'lov va'dalari (oxirgi {days} kun)"]
    if not report.promises:
        lines.append("Va'da topilmadi.")
    lines += _section("Mijoz aytgan", report.client_promises)
    lines += _section("Menejer yozgan", report.manager_forecasts)
    if report.unknown_sources:
        reasons = ", ".join(
            f"{s}: {report.source_status[s]}" for s in report.unknown_sources
        )
        lines.append(f"⚠️ To'liq emas — o'qilmagan manba: {reasons}")
    return "\n".join(lines)
