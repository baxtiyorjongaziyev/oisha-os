"""
Data classes and time range utilities for CRM daily and weekly reporting.
"""
import calendar
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, date
from enum import Enum
from typing import Any, Dict, Optional, Tuple


class PeriodType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class ManagerRow:
    user_id: int
    name: str
    won_count: int = 0
    won_amount: float = 0.0
    open_tasks: int = 0
    overdue_tasks: int = 0


@dataclass
class PeriodMetrics:
    period_type: PeriodType
    period_start: date
    period_end: date

    new_leads: int = 0
    won_count: int = 0
    won_amount: float = 0.0
    lost_count: int = 0
    lost_amount: float = 0.0

    active_count: int = 0
    active_amount: float = 0.0
    pipeline_value: float = 0.0
    stagnated_count: int = 0

    win_rate: float = 0.0
    avg_won_deal: float = 0.0

    new_contacts: int = 0
    new_companies: int = 0
    incoming_calls: int = 0

    tasks_created: int = 0
    tasks_completed: int = 0
    tasks_open: int = 0
    tasks_overdue: int = 0
    leads_without_task: int = 0

    managers: list = field(default_factory=list)

    def recompute_derived(self) -> None:
        denom = self.won_count + self.lost_count
        self.win_rate = (self.won_count / denom * 100) if denom else 0.0
        self.avg_won_deal = (self.won_amount / self.won_count) if self.won_count else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period_type": self.period_type.value,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            **{f: getattr(self, f) for f in _DELTA_FIELDS},
            "managers": [asdict(mr) for mr in self.managers],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PeriodMetrics":
        return cls(
            period_type=PeriodType(d["period_type"]),
            period_start=date.fromisoformat(d["period_start"]),
            period_end=date.fromisoformat(d["period_end"]),
            managers=[ManagerRow(**mr) for mr in d.get("managers", [])],
            **{f: d.get(f, 0) for f in _DELTA_FIELDS},
        )

    @property
    def total_leads(self) -> int:
        return self.new_leads

    @property
    def won(self) -> int:
        return self.won_count

    @property
    def lost(self) -> int:
        return self.lost_count

    @property
    def revenue(self) -> float:
        return self.won_amount

    @property
    def date_label(self) -> str:
        return self.period_end.strftime("%b %d, %Y")


_DELTA_FIELDS = (
    "new_leads", "won_count", "won_amount", "lost_count", "lost_amount",
    "active_count", "active_amount", "pipeline_value", "stagnated_count",
    "win_rate", "avg_won_deal",
    "new_contacts", "new_companies", "incoming_calls",
    "tasks_created", "tasks_completed", "tasks_open", "tasks_overdue", "leads_without_task",
)


@dataclass
class ReportResult:
    period_type: PeriodType
    period_start: date
    period_end: date
    metrics: PeriodMetrics
    previous: "PeriodMetrics | None"
    deltas: Dict[str, float]
    telegram_text: str
    fetch_ok: bool = True


def period_range(ptype: "PeriodType", anchor: date) -> Tuple[date, date]:
    if ptype == PeriodType.DAILY:
        return anchor, anchor
    if ptype == PeriodType.WEEKLY:
        start = anchor - timedelta(days=anchor.weekday())
        return start, start + timedelta(days=6)
    if ptype == PeriodType.MONTHLY:
        start = anchor.replace(day=1)
        last = calendar.monthrange(anchor.year, anchor.month)[1]
        return start, anchor.replace(day=last)
    raise ValueError(f"unknown period type: {ptype!r}")


def previous_anchor(ptype: "PeriodType", anchor: date) -> date:
    if ptype == PeriodType.DAILY:
        return anchor - timedelta(days=1)
    if ptype == PeriodType.WEEKLY:
        this_start = anchor - timedelta(days=anchor.weekday())
        return this_start - timedelta(days=7)
    if ptype == PeriodType.MONTHLY:
        first = anchor.replace(day=1)
        return (first - timedelta(days=1)).replace(day=1)
    raise ValueError(f"unknown period type: {ptype!r}")


def previous_range(ptype: "PeriodType", anchor: date) -> Tuple[date, date]:
    return period_range(ptype, previous_anchor(ptype, anchor))


def compute_deltas(cur: "PeriodMetrics", prev: "PeriodMetrics | None") -> Dict[str, float]:
    if prev is None:
        return {}
    return {f: getattr(cur, f) - getattr(prev, f) for f in _DELTA_FIELDS}


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

