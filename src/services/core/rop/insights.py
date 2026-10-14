"""Daily CEO insights: answers three questions every morning.

1. Kecha sotuvda kim top bo'ldi?      (leaderboard)
2. Bugun KPI uchun nima qilish kerak? (weekly gap + HOT leads to push)
3. Qaysi mijozlar ketib qolish arafasida? (at-risk active leads)

Pure build/render + one async `collect` that uses RopFetcher. Never sends.
"""
from __future__ import annotations

import html
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from src.services.core.rop.daily import LeadScore, score_seller_leads
from src.services.core.rop.weekly import WeeklyProgress, monday_start, progress

TOP_N = 5
RISK_N = 7


@dataclass(frozen=True)
class SellerRow:
    name: str
    won: int
    revenue: int
    activities: int


@dataclass(frozen=True)
class RiskLead:
    name: str
    price: int
    owner: str
    idle_days: int
    reasons: list[str]


@dataclass(frozen=True)
class Insights:
    day_label: str
    leaderboard: list[SellerRow]
    weekly: WeeklyProgress
    working_days_left: int
    push_leads: list[LeadScore]
    at_risk: list[RiskLead] = field(default_factory=list)


def working_days_left(now: datetime) -> int:
    """Mon–Sat working days from today to Saturday, inclusive."""
    return max(0, 5 - now.weekday() + 1) if now.weekday() <= 5 else 0


def build_leaderboard(roster, won_leads, completed_by_user) -> list[SellerRow]:
    rows = []
    for s in roster:
        mine = [l for l in won_leads if l.get("responsible_user_id") == s.responsible_user_id]
        rows.append(SellerRow(
            name=s.seller_name,
            won=len(mine),
            revenue=sum(int(l.get("price") or 0) for l in mine),
            activities=len(completed_by_user.get(s.responsible_user_id, [])),
        ))
    rows.sort(key=lambda r: (r.revenue, r.won, r.activities), reverse=True)
    return rows


def find_at_risk(leads, open_tasks, owner_names, config, now) -> list[RiskLead]:
    stagnant_days = int(config["discipline.stagnant_days"])
    now_ts = now.timestamp()
    out = []
    for lead in leads:
        lid = lead.get("id")
        idle = int((now_ts - float(lead.get("updated_at") or now_ts)) // 86400)
        tasks = [t for t in open_tasks.get(lid, []) if not t.get("is_completed")]
        reasons = []
        if idle >= stagnant_days:
            reasons.append(f"{idle} kun jim")
        if not tasks:
            reasons.append("keyingi vazifa yo'q")
        elif any((t.get("complete_till") or 0) and float(t["complete_till"]) < now_ts for t in tasks):
            reasons.append("vazifa muddati o'tgan")
        # Risk = silence plus at least one process gap; silence alone is not churn.
        if idle >= stagnant_days and len(reasons) >= 2:
            out.append(RiskLead(
                name=lead.get("name") or f"Lead {lid}",
                price=int(lead.get("price") or 0),
                owner=owner_names.get(lead.get("responsible_user_id"), "egasiz"),
                idle_days=idle,
                reasons=reasons,
            ))
    out.sort(key=lambda r: (r.price, r.idle_days), reverse=True)
    return out[:RISK_N]


def build_insights(
    roster, leads, open_tasks, won_yesterday, won_week, completed_by_user, config, now,
) -> Insights:
    owner_names = {s.responsible_user_id: s.seller_name for s in roster}
    scored = score_seller_leads(leads, open_tasks, {}, {}, config, now)
    push = [s for s in scored if s.band in ("HOT", "WARM")][:TOP_N]
    return Insights(
        day_label=(now - timedelta(days=1)).strftime("%d.%m"),
        leaderboard=build_leaderboard(roster, won_yesterday, completed_by_user),
        weekly=progress(won_week, config),
        working_days_left=working_days_left(now),
        push_leads=push,
        at_risk=find_at_risk(leads, open_tasks, owner_names, config, now),
    )


def _money(v: int) -> str:
    return f"{v:,}".replace(",", " ")


def render(ins: Insights) -> str:
    e = html.escape
    lines = ["🧭 <b>Oisha — kunlik 3 savol</b>", ""]

    lines.append(f"🏆 <b>1. Kecha ({ins.day_label}) sotuvda top</b>")
    active = [r for r in ins.leaderboard if r.won or r.activities]
    if not active:
        lines.append("— kecha sotuv ham, yopilgan vazifa ham yo'q")
    for i, r in enumerate(active[:TOP_N], 1):
        lines.append(
            f"{i}. {e(r.name)} — {r.won} ta sotuv, {_money(r.revenue)} so'm, "
            f"{r.activities} ta faollik"
        )
    lines.append("")

    w = ins.weekly
    lines.append("🎯 <b>2. Bugun KPI uchun nima qilish kerak</b>")
    lines.append(
        f"Hafta: {w.won_count}/{w.sales_target} sotuv ({w.sales_pct:.0f}%), "
        f"{_money(w.won_revenue)}/{_money(w.revenue_target)} so'm ({w.revenue_pct:.0f}%)"
    )
    gap_sales = max(0, w.sales_target - w.won_count)
    gap_rev = max(0, w.revenue_target - w.won_revenue)
    if gap_sales == 0 and gap_rev == 0:
        lines.append("✅ Haftalik target bajarildi.")
    elif ins.working_days_left:
        d = ins.working_days_left
        lines.append(
            f"Qoldi: {gap_sales} sotuv / {_money(gap_rev)} so'm, {d} ish kuni → "
            f"kuniga ~{-(-gap_sales // d)} sotuv, ~{_money(gap_rev // d)} so'm"
        )
    if ins.push_leads:
        lines.append("Bugun bosish kerak bo'lgan bitimlar:")
        for s in ins.push_leads:
            lines.append(f"• {e(s.name)} ({_money(s.price)}, {s.band} {s.score}) — {e(s.action)}")
    lines.append("")

    lines.append("⚠️ <b>3. Ketib qolish arafasidagi mijozlar</b>")
    if not ins.at_risk:
        lines.append("— xavfli bitim topilmadi")
    for r in ins.at_risk:
        lines.append(
            f"• {e(r.name)} ({_money(r.price)}) — {e(r.owner)}: {e(', '.join(r.reasons))}"
        )
    lines.append("")
    lines.append("<i>AI bahosi (taxminiy), fakt emas.</i>")
    return "\n".join(lines)


async def collect(fetcher, roster, config, now: datetime) -> Insights:
    """Fetch AmoCRM data for `now` (morning) and build insights."""
    yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    leads = await fetcher.fetch_active_sales_leads()
    open_tasks = await fetcher.fetch_open_tasks_for_leads([l["id"] for l in leads])
    won_since_y = await fetcher.fetch_won_leads_since(int(yesterday_start.timestamp()))
    won_yesterday = [
        l for l in won_since_y if int(l.get("closed_at") or 0) < int(today_start.timestamp())
    ]
    won_week = await fetcher.fetch_won_leads_since(int(monday_start(now).timestamp()))
    _, completed_by_user = await fetcher.fetch_today_completed_tasks(
        [s.responsible_user_id for s in roster], now=yesterday_start + timedelta(hours=12),
    )
    return build_insights(
        roster, leads, open_tasks, won_yesterday, won_week, completed_by_user, config, now,
    )
