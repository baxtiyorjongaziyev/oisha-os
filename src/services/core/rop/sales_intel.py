"""Weekly Sales Intel: amoCRM + Moizvonki + Airtable joined into one CEO report.

1. Lead source attribution  — won revenue / conversion by amoCRM tag.
2. Manager score            — calls (Moizvonki) + conversion + revenue (amoCRM).
3. Early warnings           — silent deals with no calls; overdue Airtable
                              projects that still owe money.
4. Upsell                   — Airtable projects finished 60–180 days ago.

Pure build/render + one async `collect`. Never sends.
"""
from __future__ import annotations

import asyncio
import html
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from src.services.core.airtable.constants import DONE_STAGES, FIELD_MAP
from src.services.core.crm.amocrm_pipeline_config import STATUS_LOST, STATUS_WON
from src.services.core.rop.service import _find_seller_calls

WINDOW_DAYS = 7
UPSELL_MIN_DAYS, UPSELL_MAX_DAYS = 60, 180
LIST_N = 7
NO_SOURCE = "manbasiz"


@dataclass(frozen=True)
class SourceRow:
    source: str
    won: int
    lost: int
    revenue: int

    @property
    def conversion(self) -> float:
        closed = self.won + self.lost
        return self.won / closed * 100 if closed else 0.0


@dataclass(frozen=True)
class ManagerRow:
    name: str
    calls: int
    solid_calls: int
    won: int
    lost: int
    revenue: int
    score: int


@dataclass(frozen=True)
class Warning:
    kind: str  # "deal" | "payment"
    name: str
    amount: int
    detail: str


@dataclass(frozen=True)
class UpsellRow:
    name: str
    finished_days: int
    budget: int
    owner: str


@dataclass(frozen=True)
class SalesIntel:
    period: str
    sources: list[SourceRow]
    managers: list[ManagerRow]
    warnings: list[Warning] = field(default_factory=list)
    upsell: list[UpsellRow] = field(default_factory=list)


# ---- helpers ----

def lead_source(lead: dict) -> str:
    tags = (lead.get("_embedded") or {}).get("tags") or []
    names = [t.get("name") for t in tags if t.get("name")]
    return names[0] if names else NO_SOURCE


def af(record: dict, key: str, default=None):
    """Read an Airtable field by FIELD_MAP aliases."""
    fields = record.get("fields") or {}
    for name in FIELD_MAP.get(key, [key]):
        if fields.get(name) not in (None, ""):
            return fields[name]
    return default


def _num(v) -> int:
    if isinstance(v, list):
        v = v[0] if v else 0
    try:
        return int(float(str(v).replace(" ", "").replace(",", "")))
    except (TypeError, ValueError):
        return 0


def _date(v) -> datetime | None:
    if isinstance(v, list):
        v = v[0] if v else None
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _text(v) -> str:
    if isinstance(v, list):
        return ", ".join(str(x.get("name", x)) if isinstance(x, dict) else str(x) for x in v)
    if isinstance(v, dict):
        return str(v.get("name") or "")
    return str(v or "")


# ---- builders ----

def build_sources(won: list[dict], lost: list[dict]) -> list[SourceRow]:
    agg: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for l in won:
        a = agg[lead_source(l)]
        a[0] += 1
        a[2] += int(l.get("price") or 0)
    for l in lost:
        agg[lead_source(l)][1] += 1
    rows = [SourceRow(s, w, lo, r) for s, (w, lo, r) in agg.items()]
    rows.sort(key=lambda r: (r.revenue, r.won), reverse=True)
    return rows


def build_managers(roster, won, lost, calls_by_name) -> list[ManagerRow]:
    rows = []
    max_rev = max([sum(int(l.get("price") or 0) for l in won
                       if l.get("responsible_user_id") == s.responsible_user_id)
                   for s in roster] or [0]) or 1
    for s in roster:
        uid = s.responsible_user_id
        w = [l for l in won if l.get("responsible_user_id") == uid]
        lo = sum(1 for l in lost if l.get("responsible_user_id") == uid)
        rev = sum(int(l.get("price") or 0) for l in w)
        c = _find_seller_calls(s.seller_name, calls_by_name)
        calls, solid = int(c.get("total", 0)), int(c.get("solid_calls", 0))
        conv = len(w) / (len(w) + lo) if (w or lo) else 0.0
        target_calls = max(1, s.calls * 6)  # weekly = daily target × 6 working days
        # 40% revenue share, 30% conversion, 30% call activity vs target.
        score = round(
            40 * rev / max_rev + 30 * conv + 30 * min(1.0, calls / target_calls)
        )
        rows.append(ManagerRow(s.seller_name, calls, solid, len(w), lo, rev, score))
    rows.sort(key=lambda r: r.score, reverse=True)
    return rows


def build_warnings(roster, active_leads, calls_by_name, projects, now) -> list[Warning]:
    out: list[Warning] = []
    names = {s.responsible_user_id: s.seller_name for s in roster}
    now_ts = now.timestamp()
    for l in active_leads:
        idle = (now_ts - float(l.get("updated_at") or now_ts)) / 86400
        owner = names.get(l.get("responsible_user_id"))
        if idle < 5 or not owner:
            continue
        if _find_seller_calls(owner, calls_by_name).get("total", 0) == 0:
            detail = f"{int(idle)} kun jim, {owner} haftada 0 qo'ng'iroq"
        else:
            detail = f"{int(idle)} kun jim ({owner})"
        out.append(Warning("deal", l.get("name") or f"Lead {l.get('id')}",
                           int(l.get("price") or 0), detail))

    today = now.replace(tzinfo=None)
    for p in projects:
        stage = _text(af(p, "stage"))
        if stage in DONE_STAGES:
            continue
        deadline = _date(af(p, "deadline"))
        remaining = _num(af(p, "remaining_usd", 0))
        if deadline and deadline < today and remaining > 0:
            out.append(Warning(
                "payment", _text(af(p, "project_name")) or "Loyiha", remaining,
                f"deadline {(today - deadline).days} kun o'tgan, qoldiq ${remaining}",
            ))
    out.sort(key=lambda w: w.amount, reverse=True)
    return out[:LIST_N * 2]


def build_upsell(projects, now) -> list[UpsellRow]:
    today = now.replace(tzinfo=None)
    out = []
    for p in projects:
        if _text(af(p, "stage")) not in DONE_STAGES:
            continue
        end = _date(af(p, "deadline"))
        if not end:
            continue
        days = (today - end).days
        if UPSELL_MIN_DAYS <= days <= UPSELL_MAX_DAYS:
            out.append(UpsellRow(
                _text(af(p, "project_name")) or "Loyiha", days,
                _num(af(p, "budget", 0)),
                _text(af(p, "seller")) or _text(af(p, "manager")) or "—",
            ))
    out.sort(key=lambda r: r.budget, reverse=True)
    return out[:LIST_N]


def build_intel(roster, won, lost, active, calls_by_name, projects, now) -> SalesIntel:
    start = now - timedelta(days=WINDOW_DAYS)
    return SalesIntel(
        period=f"{start:%d.%m}–{now:%d.%m}",
        sources=build_sources(won, lost),
        managers=build_managers(roster, won, lost, calls_by_name),
        warnings=build_warnings(roster, active, calls_by_name, projects, now),
        upsell=build_upsell(projects, now),
    )


# ---- render ----

def _m(v: int) -> str:
    return f"{v:,}".replace(",", " ")


def render(si: SalesIntel) -> str:
    e = html.escape
    out = [f"📈 <b>Sales Intel — haftalik ({si.period})</b>", ""]

    out.append("🧲 <b>1. Qaysi manba pul olib keldi</b>")
    if not si.sources:
        out.append("— hafta davomida yopilgan bitim yo'q")
    for r in si.sources[:LIST_N]:
        out.append(f"• {e(r.source)}: {r.won} sotuv / {r.lost} yo'qotildi "
                   f"({r.conversion:.0f}%), {_m(r.revenue)} so'm")
    out.append("")

    out.append("🏅 <b>2. Menejer skori</b> (daromad 40 · konversiya 30 · qo'ng'iroq 30)")
    for i, r in enumerate(si.managers, 1):
        out.append(f"{i}. {e(r.name)} — <b>{r.score}</b>: {r.calls} qo'ng'iroq "
                   f"({r.solid_calls} jiddiy), {r.won}/{r.won + r.lost} yopildi, "
                   f"{_m(r.revenue)} so'm")
    out.append("")

    out.append("🚨 <b>3. Erta ogohlantirish</b>")
    if not si.warnings:
        out.append("— xavf topilmadi")
    for w in si.warnings:
        icon = "💸" if w.kind == "payment" else "🔕"
        out.append(f"{icon} {e(w.name)} — {e(w.detail)}")
    out.append("")

    out.append("🔁 <b>4. Qayta sotish imkoniyati</b> (60–180 kun oldin topshirilgan)")
    if not si.upsell:
        out.append("— nomzod yo'q")
    for u in si.upsell:
        out.append(f"• {e(u.name)} — {u.finished_days} kun oldin, "
                   f"{_m(u.budget)} so'm, mas'ul: {e(u.owner)}")
    out.append("")
    out.append("<i>Manba = amoCRM'dagi birinchi teg. Skor taxminiy.</i>")
    return "\n".join(out)


async def collect(fetcher, airtable, roster, now: datetime) -> SalesIntel:
    since = int((now - timedelta(days=WINDOW_DAYS)).timestamp())
    won = await fetcher.fetch_closed_leads_since(STATUS_WON, since)
    lost = await fetcher.fetch_closed_leads_since(STATUS_LOST, since)
    active = await fetcher.fetch_active_sales_leads()
    calls = await fetcher.fetch_calls_between(since, int(now.timestamp()), now)
    projects = await asyncio.to_thread(airtable.get_projects) if airtable else []
    return build_intel(roster, won, lost, active, calls, projects, now)
