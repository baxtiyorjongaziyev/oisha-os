"""AI ROP weekly team progress + per-seller no-result streak. Stateless."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from src.services.core.crm.amocrm_pipeline_config import STATUS_WON


@dataclass(frozen=True)
class WeeklyProgress:
    won_count: int
    won_revenue: int
    sales_target: int
    revenue_target: int
    sales_pct: float
    revenue_pct: float


def monday_start(now: datetime) -> datetime:
    d = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return d - timedelta(days=d.weekday())


def progress(won_leads, config) -> WeeklyProgress:
    st = int(config["weekly.sales_target"])
    rt = int(config["weekly.revenue_target"])
    won = [l for l in won_leads if l.get("status_id") == STATUS_WON]
    count = len(won)
    revenue = sum(int(l.get("price") or 0) for l in won)
    return WeeklyProgress(
        won_count=count,
        won_revenue=revenue,
        sales_target=st,
        revenue_target=rt,
        sales_pct=(count / st * 100) if st else 0.0,
        revenue_pct=(revenue / rt * 100) if rt else 0.0,
    )


def no_result_streak_days(seller_won_closed_at, now: datetime) -> int:
    tz = now.tzinfo
    wins = [datetime.fromtimestamp(int(ts), tz=tz).date() for ts in seller_won_closed_at]
    win_days = set(wins)
    streak = 0
    day = now.date() - timedelta(days=1)
    while streak < 7:
        if day.weekday() == 6:  # Sunday — not a working day, skip without counting
            day -= timedelta(days=1)
            continue
        if day in win_days:
            break
        streak += 1
        day -= timedelta(days=1)
    return streak
