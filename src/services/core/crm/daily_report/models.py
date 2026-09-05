"""
Data classes and time range utilities for CRM daily and weekly reporting.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from typing import Any, Dict, Optional, Tuple

def _ts_today() -> Tuple[int, int]:
    """Bugungi kunning Unix timestamp [from, to]."""
    today = date.today()
    t_from = int(datetime(today.year, today.month, today.day, 0, 0, 0).timestamp())
    t_to   = int(datetime(today.year, today.month, today.day, 23, 59, 59).timestamp())
    return t_from, t_to


def _ts_yesterday() -> Tuple[int, int]:
    yesterday = date.today() - timedelta(days=1)
    t_from = int(datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0).timestamp())
    t_to   = int(datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, 59).timestamp())
    return t_from, t_to


def _delta(today: int | float, yesterday: int | float) -> str:
    """'▲ +5' yoki '▼ -3' yoki '—' formatida delta."""
    diff = today - yesterday
    if diff > 0:
        return f"▲ +{diff:,.0f}"
    if diff < 0:
        return f"▼ {diff:,.0f}"
    return "—"


def _fmt_duration(seconds: float) -> str:
    """5h 27m formatida vaqt."""
    if seconds <= 0:
        return "—"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


def previous_week_range(today: Optional[date] = None) -> Tuple[date, date]:
    """Return previous Monday-Sunday range for weekly CRM reports."""
    anchor = today or date.today()
    this_monday = anchor - timedelta(days=anchor.weekday())
    start = this_monday - timedelta(days=7)
    end = this_monday - timedelta(days=1)
    return start, end


# ─────────────────────────────────────────────────────────────────────────────
# B) CRMDailyReporter — stat fetcher + formatter
# ─────────────────────────────────────────────────────────────────────────────

class CRMStats:
    """Bir kunlik CRM ko'rsatkichlari."""

    def __init__(self):
        self.date_label: str = ""
        self.total_leads: int = 0          # Tushgan leadlar
        self.contacted: int = 0            # Gaplashilgan
        self.qualified: int = 0            # Sifatli leadlar
        self.won: int = 0                  # Muvaffaqiyatli
        self.revenue: float = 0.0          # Daromad ($)
        self.incoming_calls: int = 0       # Kiruvchi qo'ng'iroqlar
        self.avg_response_sec: float = 0.0 # Bog'lanish tezligi (sekund)
        self.top_manager: str = ""         # Top sotuvchi
        self.top_manager_count: int = 0
        self.pipeline_value: float = 0.0   # Umumiy pipeline qiymati
        self.lost: int = 0                 # Yutqazilgan

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CRMStats":
        s = cls()
        for k, v in d.items():
            setattr(s, k, v)
        return s


@dataclass
class CRMWeeklyStats:
    period_start: date
    period_end: date
    active_leads: int = 0
    active_amount: float = 0.0
    won_leads: int = 0
    won_amount: float = 0.0
    lost_leads: int = 0
    lost_amount: float = 0.0
    new_leads: int = 0
    new_companies: int = 0
    new_contacts: int = 0

