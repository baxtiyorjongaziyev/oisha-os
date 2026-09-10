"""AI ROP per-seller + CEO view models and builders. Pure; injected `now`."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.services.core.rop.config import DEFAULTS  # noqa: F401 (kept for parity)
from src.services.core.rop.discipline import Finding
from src.services.core.rop.scoring import derive_features, score_lead
from src.services.core.rop.targets import SellerTarget
from src.services.core.rop.traffic_light import TrafficResult
from src.services.core.rop.weekly import WeeklyProgress

_ACTION_BY_REASON = [
    ("Ochiq e'tiroz bor", "narx objection yop"),
    ("Uchrashuv", "uchrashuv belgila"),
    ("To'lov va'da qilingan", "bugun qo'ng'iroq"),
    ("Bosqich yakuniga yaqin", "bugun qo'ng'iroq"),
]


def pick_action(reasons: list[str]) -> str:
    for needle, action in _ACTION_BY_REASON:
        if any(needle in r for r in reasons):
            return action
    return "follow-up"


@dataclass(frozen=True)
class LeadScore:
    lead_id: int
    name: str
    price: int
    score: int
    band: str
    reasons: list[str]
    action: str


@dataclass(frozen=True)
class ExpectedItem:
    name: str
    revenue_est: int
    score: int


@dataclass(frozen=True)
class SellerMorningPlan:
    seller: SellerTarget
    top_closings: list[LeadScore]
    open_tasks_count: int
    overdue_tasks: list[tuple[str, str]]
    followup_due: list[str]
    expected: list[ExpectedItem]
    expected_revenue_total: int
    discipline_findings: list[Finding]


@dataclass(frozen=True)
class SellerMiddayCheck:
    seller: SellerTarget
    plan: int
    fakt: int
    calls_done: int
    follow_ups_done: int
    meetings_done: int
    hot_not_touched: list[str]
    priority_now: list[LeadScore]
    on_track: bool


@dataclass(frozen=True)
class SellerEveningResult:
    seller: SellerTarget
    sales_done: int
    revenue_today: int
    calls_done: int
    follow_ups_done: int
    meetings_done: int
    overdue_count: int
    tomorrow_closings: list[LeadScore]


@dataclass(frozen=True)
class CeoMorning:
    total_expected_sales: int
    total_expected_revenue: int
    total_overdue: int
    seller_count: int
    missing_tg: list[str]
    no_owner: list[str]
    weekly_recap: WeeklyProgress | None


@dataclass(frozen=True)
class CeoMidday:
    off_track: list[tuple[str, str]]
    any_alert: bool


@dataclass(frozen=True)
class CeoDashboard:
    team_plan: int
    team_fakt: int
    team_revenue: int
    expected_tomorrow: int
    team_overdue: int
    weekly: WeeklyProgress
    seller_lights: list[tuple[str, str, list[str]]]
    skipped_sellers: int


def score_seller_leads(
    leads, tasks_by_lead, notes_by_lead, events_by_lead, config, now: datetime
) -> list[LeadScore]:
    out: list[LeadScore] = []
    for lead in leads:
        lid = lead.get("id")
        feats = derive_features(
            lead,
            tasks_by_lead.get(lid, []),
            notes_by_lead.get(lid, []),
            events_by_lead.get(lid, []),
            config,
            now,
        )
        res = score_lead(feats, config)
        out.append(
            LeadScore(
                lead_id=lid,
                name=lead.get("name") or f"Lead {lid}",
                price=int(lead.get("price") or 0),
                score=res.score,
                band=res.band,
                reasons=res.reasons,
                action=pick_action(res.reasons),
            )
        )
    out.sort(key=lambda s: s.score, reverse=True)
    return out


def _is_hot(scored: list[LeadScore], s: LeadScore) -> bool:
    """A lead worth flagging: HOT/WARM band, or the seller's single best live lead."""
    if s.band in ("HOT", "WARM"):
        return True
    return bool(scored) and s is scored[0] and s.score > 0


def _expected(scored: list[LeadScore]) -> tuple[list[ExpectedItem], int]:
    items = [
        ExpectedItem(s.name, int(s.price * s.score / 100), s.score)
        for s in scored
        if _is_hot(scored, s)
    ]
    return items, sum(i.revenue_est for i in items)


def build_morning(seller, scored, tasks_by_lead, findings, config, now) -> SellerMorningPlan:
    now_epoch = now.timestamp()
    overdue: list[tuple[str, str]] = []
    followup_due: list[str] = []
    open_count = 0
    by_id = {s.lead_id: s for s in scored}
    for lid, tasks in tasks_by_lead.items():
        for t in tasks:
            if t.get("is_completed"):
                continue
            open_count += 1
            name = by_id[lid].name if lid in by_id else f"Lead {lid}"
            ct = t.get("complete_till") or 0
            if ct and float(ct) < now_epoch:
                overdue.append((name, str(t.get("text") or "")))
            elif ct and float(ct) <= now_epoch + 86400:
                followup_due.append(name)
    exp, exp_total = _expected(scored)
    return SellerMorningPlan(
        seller=seller,
        top_closings=scored[:3],
        open_tasks_count=open_count,
        overdue_tasks=overdue,
        followup_due=followup_due,
        expected=exp,
        expected_revenue_total=exp_total,
        discipline_findings=findings,
    )


def build_midday(seller, scored, actuals, touched_lead_ids, config) -> SellerMiddayCheck:
    pace = config["midday.pace_pct"]
    hot_not_touched = [
        s.name for s in scored if _is_hot(scored, s) and s.lead_id not in touched_lead_ids
    ]
    priority_now = [s for s in scored if s.lead_id not in touched_lead_ids][:3]
    buckets = [
        (actuals["calls"], seller.calls),
        (actuals["follow_ups"], seller.follow_ups),
        (actuals["meetings"], seller.meetings),
    ]
    on_track = all(
        done >= pace * target for done, target in buckets if target > 0
    ) and not hot_not_touched
    return SellerMiddayCheck(
        seller=seller,
        plan=seller.expected_sales,
        fakt=actuals["won"],
        calls_done=actuals["calls"],
        follow_ups_done=actuals["follow_ups"],
        meetings_done=actuals["meetings"],
        hot_not_touched=hot_not_touched,
        priority_now=priority_now,
        on_track=on_track,
    )


def build_evening(seller, scored, actuals, overdue_count) -> SellerEveningResult:
    return SellerEveningResult(
        seller=seller,
        sales_done=actuals["won"],
        revenue_today=int(actuals.get("won_revenue") or 0),
        calls_done=actuals["calls"],
        follow_ups_done=actuals["follow_ups"],
        meetings_done=actuals["meetings"],
        overdue_count=overdue_count,
        tomorrow_closings=scored[:3],
    )


def build_ceo_morning(morning_plans, no_owner_findings, weekly_recap) -> CeoMorning:
    return CeoMorning(
        total_expected_sales=sum(1 for mp in morning_plans for _ in mp.expected if _.score >= 70),
        total_expected_revenue=sum(mp.expected_revenue_total for mp in morning_plans),
        total_overdue=sum(len(mp.overdue_tasks) for mp in morning_plans),
        seller_count=len(morning_plans),
        missing_tg=[mp.seller.seller_name for mp in morning_plans if mp.seller.telegram_user_id is None],
        no_owner=[f.lead_name for f in no_owner_findings],
        weekly_recap=weekly_recap,
    )


def build_ceo_midday(midday_checks, traffic_results) -> CeoMidday:
    off = []
    for c in midday_checks:
        if c.on_track:
            continue
        why = "sur'at past"
        if c.hot_not_touched:
            why = f"{len(c.hot_not_touched)} ta issiq mijoz ishlanmagan"
        off.append((c.seller.seller_name, why))
    any_alert = bool(off) or any(
        t.level in ("YELLOW", "RED") for t in traffic_results.values()
    )
    return CeoMidday(off_track=off, any_alert=any_alert)


def build_ceo_dashboard(
    evening_results, traffic_results, weekly, expected_tomorrow, skipped
) -> CeoDashboard:
    lights = []
    for ev in evening_results:
        tr = traffic_results.get(ev.seller.responsible_user_id, TrafficResult("GREEN", []))
        emoji = {"GREEN": "\U0001F7E2", "YELLOW": "\U0001F7E1", "RED": "\U0001F534"}[tr.level]
        lights.append((ev.seller.seller_name, emoji, tr.reasons))
    return CeoDashboard(
        team_plan=sum(ev.seller.expected_sales for ev in evening_results),
        team_fakt=sum(ev.sales_done for ev in evening_results),
        team_revenue=sum(ev.revenue_today for ev in evening_results),
        expected_tomorrow=expected_tomorrow,
        team_overdue=sum(ev.overdue_count for ev in evening_results),
        weekly=weekly,
        seller_lights=lights,
        skipped_sellers=skipped,
    )
