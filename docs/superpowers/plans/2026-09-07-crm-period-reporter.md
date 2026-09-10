# CRM Period Reporter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One `CRMPeriodReporter` that produces daily / weekly / monthly amoCRM reports for both the sales-team Telegram group and the Oisha dashboard from a single `build()` call.

**Architecture:** Rework the existing `src/services/core/crm/daily_report/` mixin package to be period-agnostic. A single `PeriodMetrics` dataclass carries deal / contact / task / manager numbers. `fetcher.py` pulls them from amoCRM in one pass; `formatter.py` renders the Uzbek Telegram text; `history_db.py` snapshots each period into a new `crm_report_snapshots` SQLite table for delta comparison; `reporter.py` orchestrates fetch → load-previous → format → save. Telegram scheduler and a new `/api/crm/reports` endpoint both call `CRMPeriodReporter.build(ptype)` — numbers and text are computed exactly once.

**Tech Stack:** Python 3.11 / asyncio, `requests` (sync, wrapped in `asyncio.to_thread` / `amocrm._request_with_auth`), FastAPI, `db_pool` (libsql/sqlite sync), pytest + pytest-asyncio, Next.js / React (dashboard).

## Global Constraints

- Python runtime: 3.11. New deps: none.
- amoCRM: v4 REST. `WON_STATUS = 142`, `LOST_STATUS = 143`. Pagination `limit=250`, max 20 pages per collection.
- Stagnation threshold: open lead with `now - updated_at > 3 * 86400` seconds.
- Proxy metrics are FORBIDDEN: never compute or display `contacted`, `qualified`, `avg_response_sec`.
- Sales-team Telegram target: `CRM_SALES_REPORT_GROUP_ID = -1003854308552`, `CRM_SALES_REPORT_TOPIC_ID = 115` (defaults in `settings.py`, overridable via `.env`). If group id is falsy → do not send, log a warning.
- Telegram schedule: DAILY 19:30 every day; WEEKLY 09:00 when `now.weekday() == 0`; MONTHLY 09:00 when `now.day == 1`.
- Money formatting: integer with space thousands separator, suffix ` so'm` (e.g. `1 234 567 so'm`). Reuse `FormatMixin._fmt_money`.
- Delta rendering: `▲ +N` (increase), `▼ -N` (decrease), `—` (no change); if `previous is None`, omit deltas entirely.
- Reports and all user-facing copy are in Uzbek. Code, comments, commit messages in English.
- Test gate before every commit that touches `src/`: `SKIP_LIVE=1 python -m pytest -q` and `bandit -r src/ -ll`.
- Snapshot DB lives in `data/report_history.db` accessed through `db_pool.get_connection()` (sync). Never open a raw `sqlite3.connect`.
- Backward compatibility: `CRMStats`, `CRMWeeklyStats`, `CRMDailyReporter`, `ReportBot`, `build_reportagram_report`, `previous_week_range`, `fetch_stats`, `fetch_weekly_stats`, `format_report(stats, prev)`, `format_weekly_report_uz`, `get_history` must keep working (aliases / thin wrappers). Existing `tests/test_crm_weekly_report.py` must stay green.
- RBAC for the new endpoint: `Permission.DASHBOARD_READ` (Seller/Viewer included; not `FINANCE_READ`).

---

## File Structure

**Python — created:**
- `src/api/routes/crm_reports.py` — the `/api/crm/reports` endpoint (one responsibility: HTTP surface over `CRMPeriodReporter.build`).
- `tests/test_crm_period_models.py`
- `tests/test_crm_period_fetcher.py`
- `tests/test_crm_period_formatter.py`
- `tests/test_crm_period_snapshot.py`
- `tests/test_crm_reports_api.py`

**Python — modified:**
- `src/services/core/crm/daily_report/models.py` — add `PeriodType`, `PeriodMetrics`, `ManagerRow`, `ReportResult`, `period_range`, `previous_range`, `compute_deltas`; keep `CRMStats`/`CRMWeeklyStats` as compat shims.
- `src/services/core/crm/daily_report/fetcher.py` — add `fetch_metrics(ptype, anchor)`; keep `fetch_stats` / `fetch_weekly_stats` as wrappers.
- `src/services/core/crm/daily_report/formatter.py` — add `format_report(ptype, current, previous)`; keep old 2-arg `format_report` and `format_weekly_report_uz`.
- `src/services/core/crm/daily_report/history_db.py` — add `crm_report_snapshots` table + `save_snapshot` / `load_snapshot` / `list_snapshots`; route `_save_stats` / `_load_prev_stats` / `get_history` through them.
- `src/services/core/crm/daily_report/reporter.py` — add `CRMPeriodReporter` (subclass or extend `CRMDailyReporter`) with `build`.
- `src/services/core/crm/daily_report/__init__.py` — export new names.
- `src/services/core/crm/crm_daily_report.py` — re-export new names from facade.
- `src/settings.py` — add `CRM_SALES_REPORT_GROUP_ID`, `CRM_SALES_REPORT_TOPIC_ID`.
- `.env.example` — document the two new vars.
- `src/schedulers/main_loop/periodic_reports.py` — replace `_check_daily_reports` CRM block + `_check_weekly_and_stagnation` weekly block with a shared `_send_period_report(ptype, ...)`; add monthly trigger.
- `src/schedulers/bg_monitor/jobs_crm.py` — point its weekly path (lines ~198-218) at `CRMPeriodReporter.build(WEEKLY)`.
- `src/commands/dashboard.py` — `/report` via `build(DAILY)`, add `/report_week`, `/report_month`, update `/stats` and `/history`.
- `src/services/api_server/core.py` — import + `include_router(crm_reports_router)`.

**TypeScript — created:**
- `apps/web/src/app/api/oisha/crm-reports/route.ts` — proxy.

**TypeScript — modified:**
- `apps/web/src/app/(dashboard)/analytics/page.tsx` — new "CRM Hisobot" tab with period buttons and metric cards.

---

## Task 1: Period model — `PeriodType`, ranges, deltas

**Files:**
- Modify: `src/services/core/crm/daily_report/models.py`
- Test: `tests/test_crm_period_models.py`

**Interfaces:**
- Consumes: nothing (pure Python, stdlib `datetime`, `enum`, `dataclasses`).
- Produces:
  - `class PeriodType(str, Enum)` with members `DAILY = "daily"`, `WEEKLY = "weekly"`, `MONTHLY = "monthly"`.
  - `period_range(ptype: PeriodType, anchor: datetime.date) -> tuple[date, date]` — inclusive `(start, end)`.
  - `previous_range(ptype: PeriodType, anchor: date) -> tuple[date, date]` — the immediately-preceding period's `(start, end)`.
  - `previous_anchor(ptype: PeriodType, anchor: date) -> date` — a date inside the previous period (its `start`).
  - `compute_deltas(cur: "PeriodMetrics", prev: "PeriodMetrics | None") -> dict[str, float]` — `{}` when `prev is None`, else `cur_value - prev_value` for every numeric scalar field listed in `_DELTA_FIELDS` (defined in Task 2). For Task 1, `compute_deltas` may be stubbed to `{}` and completed in Task 2 — but write it now against a module-level `_DELTA_FIELDS: tuple[str, ...] = ()` placeholder so imports resolve.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_crm_period_models.py
from datetime import date

from src.services.core.crm.daily_report.models import (
    PeriodType,
    period_range,
    previous_range,
    previous_anchor,
)


def test_daily_range_is_single_day():
    assert period_range(PeriodType.DAILY, date(2026, 9, 7)) == (date(2026, 9, 7), date(2026, 9, 7))


def test_weekly_range_is_monday_to_sunday():
    # 2026-09-07 is a Monday
    assert period_range(PeriodType.WEEKLY, date(2026, 9, 9)) == (date(2026, 9, 7), date(2026, 9, 13))


def test_monthly_range_covers_whole_month_incl_dec():
    assert period_range(PeriodType.MONTHLY, date(2026, 12, 15)) == (date(2026, 12, 1), date(2026, 12, 31))


def test_monthly_range_february_non_leap():
    assert period_range(PeriodType.MONTHLY, date(2026, 2, 10)) == (date(2026, 2, 1), date(2026, 2, 28))


def test_previous_daily_is_yesterday():
    assert previous_range(PeriodType.DAILY, date(2026, 9, 7)) == (date(2026, 9, 6), date(2026, 9, 6))


def test_previous_weekly_is_prior_monday_block():
    assert previous_range(PeriodType.WEEKLY, date(2026, 9, 9)) == (date(2026, 8, 31), date(2026, 9, 6))


def test_previous_monthly_wraps_year():
    assert previous_range(PeriodType.MONTHLY, date(2026, 1, 20)) == (date(2025, 12, 1), date(2025, 12, 31))


def test_previous_anchor_is_start_of_previous_period():
    assert previous_anchor(PeriodType.WEEKLY, date(2026, 9, 9)) == date(2026, 8, 31)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_crm_period_models.py -q`
Expected: FAIL — `ImportError: cannot import name 'PeriodType'`.

- [ ] **Step 3: Write minimal implementation**

Add to `src/services/core/crm/daily_report/models.py` (top-level, after existing imports; `calendar` is stdlib):

```python
import calendar
from enum import Enum


class PeriodType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


_DELTA_FIELDS: tuple[str, ...] = ()  # filled in Task 2


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `SKIP_LIVE=1 python -m pytest tests/test_crm_period_models.py -q`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add tests/test_crm_period_models.py src/services/core/crm/daily_report/models.py
git commit -m "feat(crm): add PeriodType and period range helpers

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 2: `PeriodMetrics` and `ManagerRow` dataclasses + delta fields

**Files:**
- Modify: `src/services/core/crm/daily_report/models.py`
- Test: `tests/test_crm_period_models.py` (append)

**Interfaces:**
- Consumes: `PeriodType` (Task 1).
- Produces:
  - `@dataclass class ManagerRow` with fields: `user_id: int`, `name: str`, `won_count: int = 0`, `won_amount: float = 0.0`, `open_tasks: int = 0`, `overdue_tasks: int = 0`.
  - `@dataclass class PeriodMetrics` with fields exactly:
    `period_type: PeriodType`, `period_start: date`, `period_end: date`,
    `new_leads: int = 0`, `won_count: int = 0`, `won_amount: float = 0.0`, `lost_count: int = 0`, `lost_amount: float = 0.0`,
    `active_count: int = 0`, `active_amount: float = 0.0`, `pipeline_value: float = 0.0`, `stagnated_count: int = 0`,
    `win_rate: float = 0.0`, `avg_won_deal: float = 0.0`,
    `new_contacts: int = 0`, `new_companies: int = 0`, `incoming_calls: int = 0`,
    `tasks_created: int = 0`, `tasks_completed: int = 0`, `tasks_open: int = 0`, `tasks_overdue: int = 0`, `leads_without_task: int = 0`,
    `managers: list[ManagerRow] = field(default_factory=list)`.
  - `PeriodMetrics.recompute_derived() -> None` — sets `win_rate = won_count / (won_count + lost_count) * 100` (0 when denom 0) and `avg_won_deal = won_amount / won_count` (0 when `won_count` 0).
  - `PeriodMetrics.to_dict() -> dict` — JSON-safe: `period_type` as its `.value`, dates as `.isoformat()`, `managers` as list of `asdict`.
  - `PeriodMetrics.from_dict(d: dict) -> PeriodMetrics` — inverse.
  - Compat `@property` on `PeriodMetrics`: `total_leads -> new_leads`, `won -> won_count`, `lost -> lost_count`, `revenue -> won_amount`, `date_label -> period_end.strftime("%b %d, %Y")`.
  - Module-level `_DELTA_FIELDS` now set to every numeric scalar `PeriodMetrics` field (all fields above except `period_type`, `period_start`, `period_end`, `managers`).
  - `@dataclass class ReportResult` with fields: `period_type: PeriodType`, `period_start: date`, `period_end: date`, `metrics: PeriodMetrics`, `previous: "PeriodMetrics | None"`, `deltas: dict[str, float]`, `telegram_text: str`, `fetch_ok: bool = True`.

- [ ] **Step 1: Write the failing test (append to `tests/test_crm_period_models.py`)**

```python
from src.services.core.crm.daily_report.models import (
    PeriodMetrics,
    ManagerRow,
    compute_deltas,
)


def _metrics(**kw):
    base = dict(
        period_type=PeriodType.WEEKLY,
        period_start=date(2026, 9, 7),
        period_end=date(2026, 9, 13),
    )
    base.update(kw)
    return PeriodMetrics(**base)


def test_recompute_derived_win_rate_and_avg_deal():
    m = _metrics(won_count=3, lost_count=1, won_amount=30_000_000)
    m.recompute_derived()
    assert m.win_rate == 75.0
    assert m.avg_won_deal == 10_000_000


def test_recompute_derived_handles_zero_denominators():
    m = _metrics(won_count=0, lost_count=0, won_amount=0)
    m.recompute_derived()
    assert m.win_rate == 0
    assert m.avg_won_deal == 0


def test_to_dict_from_dict_roundtrip():
    m = _metrics(new_leads=12, won_count=5, won_amount=45_000_000,
                 managers=[ManagerRow(user_id=1, name="Oydin", won_count=3, won_amount=27_000_000)])
    restored = PeriodMetrics.from_dict(m.to_dict())
    assert restored == m
    assert restored.managers[0].name == "Oydin"


def test_compat_properties():
    m = _metrics(new_leads=9, won_count=4, lost_count=2, won_amount=8_000_000)
    assert m.total_leads == 9
    assert m.won == 4
    assert m.lost == 2
    assert m.revenue == 8_000_000
    assert m.date_label == "Sep 13, 2026"


def test_compute_deltas_subtracts_numeric_fields():
    cur = _metrics(new_leads=12, won_count=5)
    prev = _metrics(new_leads=9, won_count=7)
    d = compute_deltas(cur, prev)
    assert d["new_leads"] == 3
    assert d["won_count"] == -2
    assert "managers" not in d
    assert "period_type" not in d


def test_compute_deltas_none_previous_is_empty():
    assert compute_deltas(_metrics(), None) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_crm_period_models.py -q`
Expected: FAIL — `ImportError: cannot import name 'PeriodMetrics'`.

- [ ] **Step 3: Write minimal implementation**

Add to `models.py` (after `PeriodType`; `from dataclasses import dataclass, field, asdict` — extend existing import):

```python
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
```

Note: `_DELTA_FIELDS` is defined twice now (placeholder in Task 1, real value here). Delete the Task 1 placeholder line so only this definition remains.

- [ ] **Step 4: Run test to verify it passes**

Run: `SKIP_LIVE=1 python -m pytest tests/test_crm_period_models.py -q`
Expected: PASS (14 passed).

- [ ] **Step 5: Commit**

```bash
git add tests/test_crm_period_models.py src/services/core/crm/daily_report/models.py
git commit -m "feat(crm): add PeriodMetrics, ManagerRow, ReportResult, deltas

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 3: `format_report(ptype, current, previous)` in FormatMixin

**Files:**
- Modify: `src/services/core/crm/daily_report/formatter.py`
- Test: `tests/test_crm_period_formatter.py`

**Interfaces:**
- Consumes: `PeriodType`, `PeriodMetrics`, `ManagerRow`, `compute_deltas` (Tasks 1-2); existing `FormatMixin._fmt_money`, `DIVIDER`.
- Produces:
  - `FormatMixin.format_period_report(self, ptype: PeriodType, current: PeriodMetrics, previous: PeriodMetrics | None) -> str` — the full Uzbek text block per the spec layout.
  - Helper `FormatMixin._delta_str(cur: float, prev: float | None) -> str` — returns `"  ▲ +N"`, `"  ▼ -N"`, `"  —"`, or `""` when `prev is None`. Integers render without decimals; the `%` suffix is caller-added, not here.
  - Helper `FormatMixin._period_heading(ptype) -> str` — `"KUNLIK HISOBOT"` / `"HAFTALIK HISOBOT"` / `"OYLIK HISOBOT"`.
  - Helper `FormatMixin._period_label(ptype, start, end) -> str` — DAILY `"07.09.2026"`; WEEKLY `"01.09 - 07.09.2026"`; MONTHLY Uzbek month name + year, e.g. `"Sentyabr 2026"` (month names list in Uzbek, index by `start.month`).
  - `format_report` (existing 2-arg) is kept; add an overload path: if first positional arg is a `PeriodType`, delegate to `format_period_report`. Simplest: rename the existing body to `_format_daily_legacy` and make `format_report(*args)` dispatch on `isinstance(args[0], PeriodType)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_crm_period_formatter.py
from datetime import date

from src.services.core.crm.daily_report.models import PeriodType, PeriodMetrics, ManagerRow
from src.services.core.crm.daily_report.reporter import CRMDailyReporter


def _reporter(tmp_path):
    class _Amo:
        base_url = "https://jonbrandingagency.amocrm.ru"
    return CRMDailyReporter(amocrm=_Amo(), db_path=str(tmp_path / "r.db"))


def _metrics(ptype, start, end, **kw):
    m = PeriodMetrics(period_type=ptype, period_start=start, period_end=end, **kw)
    m.recompute_derived()
    return m


def test_daily_report_heading_and_label(tmp_path):
    r = _reporter(tmp_path)
    m = _metrics(PeriodType.DAILY, date(2026, 9, 7), date(2026, 9, 7), new_leads=12)
    text = r.format_period_report(PeriodType.DAILY, m, None)
    assert "AmoCRM KUNLIK HISOBOT | 07.09.2026" in text
    assert "Yangi bitimlar: 12" in text
    assert "Oisha-OS orqali yuborilgan" in text


def test_weekly_label_range(tmp_path):
    r = _reporter(tmp_path)
    m = _metrics(PeriodType.WEEKLY, date(2026, 9, 1), date(2026, 9, 7))
    text = r.format_period_report(PeriodType.WEEKLY, m, None)
    assert "AmoCRM HAFTALIK HISOBOT | 01.09 - 07.09.2026" in text


def test_monthly_label_uzbek_month(tmp_path):
    r = _reporter(tmp_path)
    m = _metrics(PeriodType.MONTHLY, date(2026, 9, 1), date(2026, 9, 30))
    text = r.format_period_report(PeriodType.MONTHLY, m, None)
    assert "AmoCRM OYLIK HISOBOT | Sentyabr 2026" in text


def test_deltas_render_with_arrows(tmp_path):
    r = _reporter(tmp_path)
    cur = _metrics(PeriodType.DAILY, date(2026, 9, 7), date(2026, 9, 7), new_leads=12, won_count=5)
    prev = _metrics(PeriodType.DAILY, date(2026, 9, 6), date(2026, 9, 6), new_leads=9, won_count=7)
    text = r.format_period_report(PeriodType.DAILY, cur, prev)
    assert "Yangi bitimlar: 12  ▲ +3" in text
    assert "Yutilgan: 5" in text and "▼ -2" in text


def test_empty_sections_still_render_zero(tmp_path):
    r = _reporter(tmp_path)
    m = _metrics(PeriodType.DAILY, date(2026, 9, 7), date(2026, 9, 7))
    text = r.format_period_report(PeriodType.DAILY, m, None)
    assert "Yaratilgan: 0" in text
    assert "Zadachasiz ochiq bitimlar: 0" in text


def test_manager_lines(tmp_path):
    r = _reporter(tmp_path)
    m = _metrics(
        PeriodType.WEEKLY, date(2026, 9, 1), date(2026, 9, 7),
        managers=[
            ManagerRow(user_id=1, name="Oydin", won_count=3, won_amount=27_000_000),
            ManagerRow(user_id=2, name="Jasur", won_count=2, won_amount=18_000_000, open_tasks=7, overdue_tasks=2),
        ],
    )
    text = r.format_period_report(PeriodType.WEEKLY, m, None)
    assert "Oydin" in text and "27 000 000 so'm" in text
    assert "ochiq zadacha: 7" in text and "muddati o'tgan: 2" in text


def test_legacy_two_arg_format_report_still_works(tmp_path):
    r = _reporter(tmp_path)
    from src.services.core.crm.daily_report.models import CRMStats
    s = CRMStats()
    s.date_label = "Sep 07, 2026"
    s.total_leads = 4
    out = r.format_report(s, None)
    assert "Sep 07, 2026" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_crm_period_formatter.py -q`
Expected: FAIL — `AttributeError: 'CRMDailyReporter' object has no attribute 'format_period_report'`.

- [ ] **Step 3: Write minimal implementation**

In `formatter.py`, add imports `from src.services.core.crm.daily_report.models import PeriodType, PeriodMetrics, compute_deltas` and:

```python
_UZ_MONTHS = [
    "", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr",
]


class FormatMixin:
    # ... existing methods unchanged ...

    @staticmethod
    def _delta_str(cur, prev):
        if prev is None:
            return ""
        diff = cur - prev
        if abs(diff) < 1e-9:
            return "  —"
        sign = "▲ +" if diff > 0 else "▼ "
        return f"  {sign}{diff:,.0f}".replace(",", " ")

    @staticmethod
    def _period_heading(ptype):
        return {
            PeriodType.DAILY: "KUNLIK HISOBOT",
            PeriodType.WEEKLY: "HAFTALIK HISOBOT",
            PeriodType.MONTHLY: "OYLIK HISOBOT",
        }[ptype]

    @staticmethod
    def _period_label(ptype, start, end):
        if ptype == PeriodType.DAILY:
            return start.strftime("%d.%m.%Y")
        if ptype == PeriodType.WEEKLY:
            return f"{start.strftime('%d.%m')} - {end.strftime('%d.%m.%Y')}"
        return f"{_UZ_MONTHS[start.month]} {start.year}"

    def format_period_report(self, ptype, current, previous):
        p = previous
        d = self._delta_str
        m = current

        def pv(field):
            return getattr(p, field) if p is not None else None

        lines = [
            f"📊 AmoCRM {self._period_heading(ptype)} | {self._period_label(ptype, m.period_start, m.period_end)}",
            DIVIDER,
            "🎯 BITIMLAR",
            f"  Yangi bitimlar: {m.new_leads}{d(m.new_leads, pv('new_leads'))}",
            f"  Faol bitimlar: {m.active_count} ({self._fmt_money(m.active_amount)} so'm)",
            f"  Yutilgan: {m.won_count} ({self._fmt_money(m.won_amount)} so'm){d(m.won_count, pv('won_count'))}",
            f"  Yutqazilgan: {m.lost_count} ({self._fmt_money(m.lost_amount)} so'm){d(m.lost_count, pv('lost_count'))}",
            f"  Win rate: {m.win_rate:.0f}%{d(m.win_rate, pv('win_rate'))}",
            f"  O'rtacha yutilgan bitim: {self._fmt_money(m.avg_won_deal)} so'm",
            f"  Pipeline qiymati: {self._fmt_money(m.pipeline_value)} so'm",
            f"  ⚠️ Stagnatsiya (3+ kun): {m.stagnated_count}",
            "",
            "📞 ALOQA",
            f"  Yangi kontaktlar: {m.new_contacts}{d(m.new_contacts, pv('new_contacts'))}",
            f"  Yangi kompaniyalar: {m.new_companies}",
            f"  Kiruvchi qo'ng'iroqlar: {m.incoming_calls}{d(m.incoming_calls, pv('incoming_calls'))}",
            "",
            "✅ ZADACHALAR",
            f"  Yaratilgan: {m.tasks_created}{d(m.tasks_created, pv('tasks_created'))}",
            f"  Bajarilgan: {m.tasks_completed}",
            f"  Ochiq: {m.tasks_open}",
            f"  🔴 Muddati o'tgan: {m.tasks_overdue}",
            f"  🚨 Zadachasiz ochiq bitimlar: {m.leads_without_task}",
            "",
            "🏆 MENEJERLAR (yutilgan bo'yicha)",
        ]

        medals = ["🥇", "🥈", "🥉"]
        if not m.managers:
            lines.append("  Ma'lumot yo'q")
        for i, mr in enumerate(m.managers):
            badge = medals[i] if i < 3 else f"  {i + 1}."
            lines.append(
                f"  {badge} {mr.name} — {mr.won_count} ta / {self._fmt_money(mr.won_amount)} so'm"
            )
            if mr.open_tasks or mr.overdue_tasks:
                lines.append(
                    f"     └ ochiq zadacha: {mr.open_tasks} | muddati o'tgan: {mr.overdue_tasks}"
                )

        links = self._period_links(ptype, m.period_start, m.period_end)
        lines += [
            "",
            DIVIDER,
            "🔗 AmoCRM'da ochish:",
            f"  [Yangi bitimlar]({links['new_leads']}) · [Yutilgan]({links['won']}) · [Yutqazilgan]({links['lost']})",
            "",
            "Oisha-OS orqali yuborilgan",
        ]
        return "\n".join(lines)

    def _period_links(self, ptype, start, end):
        # reuse existing _weekly_report_links machinery for date filters
        return self._weekly_report_links(start, end)
```

Then wrap the existing `format_report`: rename current `def format_report(self, stats, prev=None)` to `def _format_legacy_report(self, stats, prev=None)` and add:

```python
    def format_report(self, *args):
        if args and isinstance(args[0], PeriodType):
            ptype, current, previous = (args + (None,))[:3]
            return self.format_period_report(ptype, current, previous)
        stats = args[0]
        prev = args[1] if len(args) > 1 else None
        return self._format_legacy_report(stats, prev)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `SKIP_LIVE=1 python -m pytest tests/test_crm_period_formatter.py tests/test_crm_weekly_report.py -q`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add tests/test_crm_period_formatter.py src/services/core/crm/daily_report/formatter.py
git commit -m "feat(crm): add period-aware format_period_report

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 4: Snapshot DB — `crm_report_snapshots` table + save/load/list

**Files:**
- Modify: `src/services/core/crm/daily_report/history_db.py`
- Test: `tests/test_crm_period_snapshot.py`

**Interfaces:**
- Consumes: `PeriodType`, `PeriodMetrics` (Tasks 1-2); existing `HistoryDBMixin._history_conn()`.
- Produces:
  - `HistoryDBMixin.save_snapshot(self, m: PeriodMetrics) -> None` — `INSERT OR REPLACE INTO crm_report_snapshots (period_type, period_start, period_end, metrics_json) VALUES (?,?,?,?)` with `m.period_type.value`, `m.period_start.isoformat()`, `m.period_end.isoformat()`, `json.dumps(m.to_dict())`.
  - `HistoryDBMixin.load_snapshot(self, ptype: PeriodType, period_start: date) -> PeriodMetrics | None`.
  - `HistoryDBMixin.list_snapshots(self, ptype: PeriodType, limit: int = 12) -> list[PeriodMetrics]` — `ORDER BY period_start DESC LIMIT ?`.
  - `_ensure_db` also creates `crm_report_snapshots` (keep the existing `daily_stats` create).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_crm_period_snapshot.py
from datetime import date

from src.services.core.crm.daily_report.models import PeriodType, PeriodMetrics, ManagerRow
from src.services.core.crm.daily_report.reporter import CRMDailyReporter


def _reporter(tmp_path):
    class _Amo:
        base_url = "https://x.amocrm.ru"
    return CRMDailyReporter(amocrm=_Amo(), db_path=str(tmp_path / "r.db"))


def _m(ptype, start, end, **kw):
    return PeriodMetrics(period_type=ptype, period_start=start, period_end=end, **kw)


def test_save_and_load_roundtrip(tmp_path):
    r = _reporter(tmp_path)
    m = _m(PeriodType.WEEKLY, date(2026, 9, 1), date(2026, 9, 7),
           new_leads=12, won_count=5, won_amount=45_000_000,
           managers=[ManagerRow(user_id=1, name="Oydin", won_count=3)])
    r.save_snapshot(m)
    got = r.load_snapshot(PeriodType.WEEKLY, date(2026, 9, 1))
    assert got == m


def test_load_missing_returns_none(tmp_path):
    r = _reporter(tmp_path)
    assert r.load_snapshot(PeriodType.MONTHLY, date(2020, 1, 1)) is None


def test_save_is_idempotent_on_primary_key(tmp_path):
    r = _reporter(tmp_path)
    r.save_snapshot(_m(PeriodType.DAILY, date(2026, 9, 7), date(2026, 9, 7), new_leads=1))
    r.save_snapshot(_m(PeriodType.DAILY, date(2026, 9, 7), date(2026, 9, 7), new_leads=9))
    got = r.load_snapshot(PeriodType.DAILY, date(2026, 9, 7))
    assert got.new_leads == 9


def test_list_snapshots_desc_by_start(tmp_path):
    r = _reporter(tmp_path)
    for day in (5, 6, 7):
        r.save_snapshot(_m(PeriodType.DAILY, date(2026, 9, day), date(2026, 9, day), new_leads=day))
    rows = r.list_snapshots(PeriodType.DAILY, limit=2)
    assert [x.period_start.day for x in rows] == [7, 6]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_crm_period_snapshot.py -q`
Expected: FAIL — `AttributeError: ... 'save_snapshot'`.

- [ ] **Step 3: Write minimal implementation**

In `history_db.py` add `from datetime import date` (extend existing import) and `from src.services.core.crm.daily_report.models import PeriodType, PeriodMetrics`. Extend `_ensure_db`:

```python
    def _ensure_db(self) -> None:
        with self._history_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    report_date TEXT PRIMARY KEY,
                    stats_json  TEXT NOT NULL,
                    created_at  TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS crm_report_snapshots (
                    period_type   TEXT NOT NULL,
                    period_start  TEXT NOT NULL,
                    period_end    TEXT NOT NULL,
                    metrics_json  TEXT NOT NULL,
                    created_at    TEXT DEFAULT (datetime('now')),
                    PRIMARY KEY (period_type, period_start)
                )
            """)
            conn.commit()

    def save_snapshot(self, m: PeriodMetrics) -> None:
        try:
            with self._history_conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO crm_report_snapshots "
                    "(period_type, period_start, period_end, metrics_json) VALUES (?, ?, ?, ?)",
                    (
                        m.period_type.value,
                        m.period_start.isoformat(),
                        m.period_end.isoformat(),
                        json.dumps(m.to_dict()),
                    ),
                )
                conn.commit()
        except Exception as exc:
            logger.debug("[CRMPeriodReporter] save_snapshot: %s", exc)

    def load_snapshot(self, ptype: PeriodType, period_start: date):
        try:
            with self._history_conn() as conn:
                row = conn.execute(
                    "SELECT metrics_json FROM crm_report_snapshots "
                    "WHERE period_type = ? AND period_start = ?",
                    (ptype.value, period_start.isoformat()),
                ).fetchone()
            if row:
                return PeriodMetrics.from_dict(json.loads(row[0]))
        except Exception as exc:
            logger.debug("[CRMPeriodReporter] load_snapshot: %s", exc)
        return None

    def list_snapshots(self, ptype: PeriodType, limit: int = 12):
        out = []
        try:
            with self._history_conn() as conn:
                rows = conn.execute(
                    "SELECT metrics_json FROM crm_report_snapshots "
                    "WHERE period_type = ? ORDER BY period_start DESC LIMIT ?",
                    (ptype.value, limit),
                ).fetchall()
            for (j,) in rows:
                out.append(PeriodMetrics.from_dict(json.loads(j)))
        except Exception as exc:
            logger.debug("[CRMPeriodReporter] list_snapshots: %s", exc)
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `SKIP_LIVE=1 python -m pytest tests/test_crm_period_snapshot.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add tests/test_crm_period_snapshot.py src/services/core/crm/daily_report/history_db.py
git commit -m "feat(crm): add crm_report_snapshots table and accessors

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 5: `fetch_metrics(ptype, anchor)` in AmoFetcherMixin

**Files:**
- Modify: `src/services/core/crm/daily_report/fetcher.py`
- Test: `tests/test_crm_period_fetcher.py`

**Interfaces:**
- Consumes: `PeriodType`, `PeriodMetrics`, `ManagerRow`, `period_range` (Tasks 1-2); existing `AmoFetcherMixin._fetch_amocrm_collection`, reporter constants `WON_STATUS`, `LOST_STATUS`; `self._crm.get_user_name` (fallback to `f"Manager #{uid}"`).
- Produces:
  - `AmoFetcherMixin.fetch_metrics(self, ptype: PeriodType, anchor: date | None = None) -> PeriodMetrics` — populated `PeriodMetrics` with `recompute_derived()` called, `managers` truncated to top 5 by `won_amount` desc. On total amoCRM failure returns an all-zero `PeriodMetrics` (never raises).
  - Private helper `AmoFetcherMixin._aggregate_metrics(ptype, start, end, *, leads_all, leads_created, leads_closed, contacts_new, companies_new, calls, tasks_all, tasks_created, tasks_done, user_names) -> PeriodMetrics` — pure aggregation, unit-testable without HTTP.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_crm_period_fetcher.py
import time
from datetime import date

import pytest

from src.services.core.crm.daily_report.models import PeriodType, PeriodMetrics
from src.services.core.crm.daily_report.reporter import CRMDailyReporter


class _Amo:
    base_url = "https://jonbrandingagency.amocrm.ru"

    def __init__(self, collections):
        # collections: dict[str, list[dict]] keyed by amocrm collection name +
        # a suffix: "leads", "leads_created", "leads_closed", "contacts",
        # "companies", "calls", "tasks_open", "tasks_created", "tasks_done"
        self._c = collections

    def get_user_name(self, uid):
        return {1: "Oydin", 2: "Jasur"}.get(uid, f"Manager #{uid}")


@pytest.fixture
def reporter(tmp_path, monkeypatch):
    r = CRMDailyReporter(amocrm=_Amo({}), db_path=str(tmp_path / "r.db"))
    return r


def test_aggregate_counts_deals_and_derived(reporter):
    now = int(time.time())
    leads_all = [
        {"status_id": 1, "price": 1000, "updated_at": now, "id": 10},
        {"status_id": 1, "price": 2000, "updated_at": now - 5 * 86400, "id": 11},  # stagnated
        {"status_id": 142, "price": 9000, "updated_at": now, "id": 12},
        {"status_id": 143, "price": 500, "updated_at": now, "id": 13},
    ]
    leads_created = [{"id": i} for i in range(12)]
    leads_closed = [
        {"status_id": 142, "price": 9000, "responsible_user_id": 1},
        {"status_id": 142, "price": 6000, "responsible_user_id": 2},
        {"status_id": 143, "price": 500, "responsible_user_id": 2},
    ]
    m = reporter._aggregate_metrics(
        PeriodType.WEEKLY, date(2026, 9, 1), date(2026, 9, 7),
        leads_all=leads_all, leads_created=leads_created, leads_closed=leads_closed,
        contacts_new=[{"id": i} for i in range(7)],
        companies_new=[{"id": i} for i in range(3)],
        calls=[{"id": i} for i in range(22)],
        tasks_all=[{"entity_id": 10, "entity_type": "leads", "is_completed": 0,
                    "complete_till": now - 100, "responsible_user_id": 2}],
        tasks_created=[{"id": i} for i in range(30)],
        tasks_done=[{"id": i} for i in range(25)],
        user_names={1: "Oydin", 2: "Jasur"},
    )
    assert m.new_leads == 12
    assert m.active_count == 2
    assert m.active_amount == 3000
    assert m.stagnated_count == 1
    assert m.won_count == 2 and m.won_amount == 15000
    assert m.lost_count == 1 and m.lost_amount == 500
    assert m.win_rate == pytest.approx(66.6667, rel=1e-3)
    assert m.avg_won_deal == 7500
    assert m.new_contacts == 7 and m.new_companies == 3
    assert m.incoming_calls == 22
    assert m.tasks_created == 30 and m.tasks_completed == 25
    assert m.tasks_open == 1 and m.tasks_overdue == 1
    # lead 11, 12, 13 are open?/closed — open leads without a task: id 11 only
    # (10 has a task; 12 & 13 are won/lost so excluded)
    assert m.leads_without_task == 1
    # managers ranked by won_amount desc
    assert [mr.name for mr in m.managers] == ["Oydin", "Jasur"]
    assert m.managers[1].open_tasks == 1 and m.managers[1].overdue_tasks == 1


def test_managers_truncated_to_top_5(reporter):
    leads_closed = [
        {"status_id": 142, "price": p, "responsible_user_id": uid}
        for uid, p in enumerate(range(100, 800, 100), start=1)
    ]
    m = reporter._aggregate_metrics(
        PeriodType.DAILY, date(2026, 9, 7), date(2026, 9, 7),
        leads_all=[], leads_created=[], leads_closed=leads_closed,
        contacts_new=[], companies_new=[], calls=[],
        tasks_all=[], tasks_created=[], tasks_done=[], user_names={},
    )
    assert len(m.managers) == 5
    assert m.managers[0].won_amount == 700


@pytest.mark.asyncio
async def test_fetch_metrics_survives_total_amocrm_failure(tmp_path):
    class _Broken:
        base_url = "https://x.amocrm.ru"

        async def _fetch_amocrm_collection(self, *a, **k):
            raise RuntimeError("amocrm down")

    r = CRMDailyReporter(amocrm=_Broken(), db_path=str(tmp_path / "r.db"))
    m = await r.fetch_metrics(PeriodType.DAILY, date(2026, 9, 7))
    assert isinstance(m, PeriodMetrics)
    assert m.new_leads == 0 and m.won_count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_crm_period_fetcher.py -q`
Expected: FAIL — `AttributeError: ... '_aggregate_metrics'`.

- [ ] **Step 3: Write minimal implementation**

In `fetcher.py` add imports `import time`, `from datetime import date`, `from src.services.core.crm.daily_report.models import (PeriodType, PeriodMetrics, ManagerRow, period_range)`. Add to `AmoFetcherMixin`:

```python
    def _aggregate_metrics(
        self,
        ptype,
        start,
        end,
        *,
        leads_all,
        leads_created,
        leads_closed,
        contacts_new,
        companies_new,
        calls,
        tasks_all,
        tasks_created,
        tasks_done,
        user_names,
    ) -> PeriodMetrics:
        now = time.time()
        won_s, lost_s = self.WON_STATUS, self.LOST_STATUS

        m = PeriodMetrics(period_type=ptype, period_start=start, period_end=end)
        m.new_leads = len(leads_created)
        m.new_contacts = len(contacts_new)
        m.new_companies = len(companies_new)
        m.incoming_calls = len(calls)
        m.tasks_created = len(tasks_created)
        m.tasks_completed = len(tasks_done)

        open_lead_ids = set()
        for l in leads_all:
            sid = l.get("status_id")
            price = l.get("price") or 0
            if sid in (won_s, lost_s):
                continue
            m.active_count += 1
            m.active_amount += price
            open_lead_ids.add(l.get("id"))
            if (now - (l.get("updated_at") or 0)) > 3 * 86400:
                m.stagnated_count += 1
        m.pipeline_value = m.active_amount

        mgr = {}
        for l in leads_closed:
            sid = l.get("status_id")
            price = l.get("price") or 0
            uid = l.get("responsible_user_id")
            if sid == won_s:
                m.won_count += 1
                m.won_amount += price
                if uid:
                    row = mgr.setdefault(uid, ManagerRow(user_id=uid, name=user_names.get(uid, f"Manager #{uid}")))
                    row.won_count += 1
                    row.won_amount += price
            elif sid == lost_s:
                m.lost_count += 1
                m.lost_amount += price

        leads_with_task = {
            t.get("entity_id")
            for t in tasks_all
            if t.get("entity_type") == "leads" and not t.get("is_completed")
        }
        for t in tasks_all:
            if t.get("is_completed"):
                continue
            m.tasks_open += 1
            till = t.get("complete_till") or 0
            overdue = bool(till) and till < now
            if overdue:
                m.tasks_overdue += 1
            uid = t.get("responsible_user_id")
            if uid:
                row = mgr.setdefault(uid, ManagerRow(user_id=uid, name=user_names.get(uid, f"Manager #{uid}")))
                row.open_tasks += 1
                if overdue:
                    row.overdue_tasks += 1

        m.leads_without_task = len(open_lead_ids - leads_with_task)

        m.managers = sorted(mgr.values(), key=lambda r: r.won_amount, reverse=True)[:5]
        m.recompute_derived()
        return m

    async def fetch_metrics(self, ptype, anchor=None) -> PeriodMetrics:
        anchor = anchor or date.today()
        start, end = period_range(ptype, anchor)
        t_from = int(datetime(start.year, start.month, start.day, 0, 0, 0).timestamp())
        t_to = int(datetime(end.year, end.month, end.day, 23, 59, 59).timestamp())

        async def _safe(coll, extra=None, **kw):
            try:
                return await self._fetch_amocrm_collection(coll, extra, **kw)
            except Exception as exc:
                logger.warning("[CRMPeriodReporter] fetch %s failed: %s", coll, exc)
                return []

        created = {"filter[created_at][from]": t_from, "filter[created_at][to]": t_to}
        closed = {"filter[closed_at][from]": t_from, "filter[closed_at][to]": t_to}
        done = {"filter[is_completed]": 1,
                "filter[updated_at][from]": t_from, "filter[updated_at][to]": t_to}
        open_tasks = {"filter[is_completed]": 0}

        (
            leads_all, leads_created, leads_closed,
            contacts_new, companies_new, calls,
            tasks_all, tasks_created, tasks_done,
        ) = await asyncio.gather(
            _safe("leads"),
            _safe("leads", created),
            _safe("leads", closed),
            _safe("contacts", created),
            _safe("companies", created),
            _safe("calls", created),
            _safe("tasks", open_tasks),
            _safe("tasks", {"filter[created_at][from]": t_from, "filter[created_at][to]": t_to}),
            _safe("tasks", done),
        )

        uids = {l.get("responsible_user_id") for l in leads_closed if l.get("responsible_user_id")}
        uids |= {t.get("responsible_user_id") for t in tasks_all if t.get("responsible_user_id")}
        user_names = {}
        for uid in uids:
            try:
                user_names[uid] = self._crm.get_user_name(uid)
            except Exception:
                user_names[uid] = f"Manager #{uid}"

        return self._aggregate_metrics(
            ptype, start, end,
            leads_all=leads_all, leads_created=leads_created, leads_closed=leads_closed,
            contacts_new=contacts_new, companies_new=companies_new, calls=calls,
            tasks_all=tasks_all, tasks_created=tasks_created, tasks_done=tasks_done,
            user_names=user_names,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `SKIP_LIVE=1 python -m pytest tests/test_crm_period_fetcher.py tests/test_crm_weekly_report.py -q`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add tests/test_crm_period_fetcher.py src/services/core/crm/daily_report/fetcher.py
git commit -m "feat(crm): add fetch_metrics + pure _aggregate_metrics

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 6: `CRMPeriodReporter.build()` orchestration + exports

**Files:**
- Modify: `src/services/core/crm/daily_report/reporter.py`
- Modify: `src/services/core/crm/daily_report/__init__.py`
- Modify: `src/services/core/crm/crm_daily_report.py`
- Test: `tests/test_crm_period_snapshot.py` (append `build()` tests)

**Interfaces:**
- Consumes: `fetch_metrics` (Task 5), `format_period_report` (Task 3), `save_snapshot` / `load_snapshot` (Task 4), `PeriodType`, `previous_anchor`, `previous_range`, `compute_deltas`, `ReportResult` (Tasks 1-2).
- Produces:
  - `class CRMPeriodReporter(CRMDailyReporter)` — same constructor signature `(amocrm, db_path="data/report_history.db")`.
  - `async CRMPeriodReporter.build(self, ptype: PeriodType, anchor: date | None = None) -> ReportResult`:
    1. `anchor = anchor or date.today()`
    2. `start, end = period_range(ptype, anchor)`
    3. `current = await self.fetch_metrics(ptype, anchor)`
    4. `fetch_ok = any numeric field of current is non-zero OR self._last_fetch_ok` — simpler: track `self._last_fetch_ok: bool` set inside `fetch_metrics` (add `self._last_fetch_ok = True` at successful end, `False` in the total-failure path). Task 5's `fetch_metrics` must set this flag; update Task 5 code accordingly when implementing Task 6 (add the two assignments).
    5. `prev_start = previous_anchor(ptype, anchor)`; `previous = self.load_snapshot(ptype, previous_range(ptype, anchor)[0])` — note snapshot key is the previous period's `start`, which equals `previous_range(...)[0]`.
    6. if `previous is None`: `previous = await self.fetch_metrics(ptype, prev_start)` (best-effort; wrap in try/except → `None` on failure).
    7. `text = self.format_period_report(ptype, current, previous)`
    8. `self.save_snapshot(current)`
    9. return `ReportResult(period_type=ptype, period_start=start, period_end=end, metrics=current, previous=previous, deltas=compute_deltas(current, previous), telegram_text=text, fetch_ok=fetch_ok)`
  - `CRMDailyReporter` keeps a convenience `async def get_weekly_report(self) -> str` returning `(await CRMPeriodReporter(self._crm, self._db_path).build(PeriodType.WEEKLY)).telegram_text` — fixes the broken caller in `periodic_reports.py` even before Task 8.
  - `__init__.py` and `crm_daily_report.py` re-export: `CRMPeriodReporter`, `PeriodType`, `PeriodMetrics`, `ManagerRow`, `ReportResult`, `period_range`, `previous_range`, `previous_anchor`, `compute_deltas`.

- [ ] **Step 1: Write the failing test (append to `tests/test_crm_period_snapshot.py`)**

```python
import pytest
from src.services.core.crm.daily_report.reporter import CRMPeriodReporter


class _StubAmo:
    base_url = "https://jonbrandingagency.amocrm.ru"

    def __init__(self, per_call):
        self._per_call = per_call
        self.n = 0

    def get_user_name(self, uid):
        return f"U{uid}"

    async def _fetch_amocrm_collection(self, coll, extra=None, **kw):
        return self._per_call.get(coll, [])


@pytest.mark.asyncio
async def test_build_produces_result_and_persists_snapshot(tmp_path):
    amo = _StubAmo({
        "leads": [{"status_id": 1, "price": 1000, "updated_at": 9e12, "id": 1}],
        "contacts": [{"id": 1}, {"id": 2}],
    })
    r = CRMPeriodReporter(amocrm=amo, db_path=str(tmp_path / "r.db"))
    res = await r.build(PeriodType.DAILY, date(2026, 9, 7))
    assert res.period_type == PeriodType.DAILY
    assert res.metrics.active_count == 1
    assert res.metrics.new_contacts == 2
    assert "KUNLIK HISOBOT" in res.telegram_text
    # snapshot saved for today
    assert r.load_snapshot(PeriodType.DAILY, date(2026, 9, 7)) is not None


@pytest.mark.asyncio
async def test_build_uses_prior_snapshot_for_deltas(tmp_path):
    amo = _StubAmo({"contacts": [{"id": i} for i in range(5)]})
    r = CRMPeriodReporter(amocrm=amo, db_path=str(tmp_path / "r.db"))
    # seed yesterday
    prev = PeriodMetrics(period_type=PeriodType.DAILY,
                         period_start=date(2026, 9, 6), period_end=date(2026, 9, 6),
                         new_contacts=2)
    r.save_snapshot(prev)
    res = await r.build(PeriodType.DAILY, date(2026, 9, 7))
    assert res.previous is not None
    assert res.deltas["new_contacts"] == 3
    assert "▲ +3" in res.telegram_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_crm_period_snapshot.py -q`
Expected: FAIL — `ImportError: cannot import name 'CRMPeriodReporter'`.

- [ ] **Step 3: Write minimal implementation**

In `reporter.py` add imports:

```python
from datetime import date
from src.services.core.crm.daily_report.models import (
    PeriodType, PeriodMetrics, ReportResult,
    period_range, previous_range, previous_anchor, compute_deltas,
)
```

Add to `CRMDailyReporter`:

```python
    async def get_weekly_report(self) -> str:
        res = await CRMPeriodReporter(self._crm, self._db_path).build(PeriodType.WEEKLY)
        return res.telegram_text
```

Add new class at end of module (before `build_reportagram_report`):

```python
class CRMPeriodReporter(CRMDailyReporter):
    """Unified daily / weekly / monthly amoCRM reporter."""

    async def build(self, ptype: PeriodType, anchor: "date | None" = None) -> ReportResult:
        anchor = anchor or date.today()
        start, end = period_range(ptype, anchor)

        current = await self.fetch_metrics(ptype, anchor)
        fetch_ok = getattr(self, "_last_fetch_ok", True)

        prev_start = previous_range(ptype, anchor)[0]
        previous = self.load_snapshot(ptype, prev_start)
        if previous is None:
            try:
                previous = await self.fetch_metrics(ptype, previous_anchor(ptype, anchor))
            except Exception as exc:
                logger.debug("[CRMPeriodReporter] previous fetch failed: %s", exc)
                previous = None

        text = self.format_period_report(ptype, current, previous)
        self.save_snapshot(current)

        return ReportResult(
            period_type=ptype,
            period_start=start,
            period_end=end,
            metrics=current,
            previous=previous,
            deltas=compute_deltas(current, previous),
            telegram_text=text,
            fetch_ok=fetch_ok,
        )
```

In Task 5's `fetch_metrics`, add `self._last_fetch_ok = True` just before the `return self._aggregate_metrics(...)` line, and in the `_safe` total-failure situation there is no single failure point — instead set `self._last_fetch_ok = not all_empty` where `all_empty = not any([leads_all, leads_created, leads_closed, contacts_new, companies_new, calls, tasks_all, tasks_created, tasks_done])`. Add:

```python
        self._last_fetch_ok = any([
            leads_all, leads_created, leads_closed, contacts_new,
            companies_new, calls, tasks_all, tasks_created, tasks_done,
        ])
```

right before the `return self._aggregate_metrics(...)`.

In `__init__.py` extend imports and `__all__`:

```python
from src.services.core.crm.daily_report.models import (
    CRMStats, CRMWeeklyStats, PeriodType, PeriodMetrics, ManagerRow, ReportResult,
    period_range, previous_range, previous_anchor, compute_deltas,
    _ts_today, _ts_yesterday, _delta, _fmt_duration, previous_week_range,
)
from src.services.core.crm.daily_report.reporter import (
    CRMDailyReporter, CRMPeriodReporter, ReportBot, build_reportagram_report,
)

__all__ = [
    "CRMStats", "CRMWeeklyStats", "CRMDailyReporter", "CRMPeriodReporter",
    "PeriodType", "PeriodMetrics", "ManagerRow", "ReportResult",
    "period_range", "previous_range", "previous_anchor", "compute_deltas",
    "ReportBot", "build_reportagram_report",
    "_ts_today", "_ts_yesterday", "_delta", "_fmt_duration", "previous_week_range",
]
```

In `crm_daily_report.py` mirror the same additions to its import block and `__all__`.

- [ ] **Step 4: Run full CRM report test suite**

Run: `SKIP_LIVE=1 python -m pytest tests/test_crm_period_models.py tests/test_crm_period_formatter.py tests/test_crm_period_snapshot.py tests/test_crm_period_fetcher.py tests/test_crm_weekly_report.py -q`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/services/core/crm/daily_report/ src/services/core/crm/crm_daily_report.py tests/test_crm_period_snapshot.py
git commit -m "feat(crm): CRMPeriodReporter.build orchestration + exports

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 7: Settings + `.env.example` for the sales-team target

**Files:**
- Modify: `src/settings.py:183-210` (the GROUP_ID block)
- Modify: `.env.example` (after the `TN` groups block, ~line 186)
- Test: `tests/test_crm_reports_api.py` (create with a settings assertion; API tests added in Task 9)

**Interfaces:**
- Produces: `settings.CRM_SALES_REPORT_GROUP_ID: Optional[int]` (default `-1003854308552`), `settings.CRM_SALES_REPORT_TOPIC_ID: Optional[int]` (default `115`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_crm_reports_api.py
def test_sales_report_settings_defaults():
    from src.settings import settings
    assert settings.CRM_SALES_REPORT_GROUP_ID == -1003854308552
    assert settings.CRM_SALES_REPORT_TOPIC_ID == 115
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_crm_reports_api.py -q`
Expected: FAIL — `AttributeError: 'AppSettings' object has no attribute 'CRM_SALES_REPORT_GROUP_ID'`.

- [ ] **Step 3: Write minimal implementation**

In `src/settings.py`, in the GROUP_ID cluster (next to `CRM_GROUP_ID`):

```python
    CRM_SALES_REPORT_GROUP_ID: Optional[int] = -1003854308552   # Sotuv bo'limi guruhi (CRM davriy hisobotlar)
    CRM_SALES_REPORT_TOPIC_ID: Optional[int] = 115              # Hisobotlar topic
```

In `.env.example`, after the `TN` groups block:

```bash
# --- CRM PERIOD REPORTS (kunlik/haftalik/oylik -> sotuv bo'limi guruhi) ---
# CRM_SALES_REPORT_GROUP_ID=-1003854308552
# CRM_SALES_REPORT_TOPIC_ID=115
```

- [ ] **Step 4: Run test to verify it passes**

Run: `SKIP_LIVE=1 python -m pytest tests/test_crm_reports_api.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add src/settings.py .env.example tests/test_crm_reports_api.py
git commit -m "feat(crm): add CRM_SALES_REPORT_GROUP_ID / TOPIC_ID settings

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 8: Scheduler — send daily / weekly / monthly to the sales group

**Files:**
- Modify: `src/schedulers/main_loop/periodic_reports.py`
- Modify: `src/schedulers/bg_monitor/jobs_crm.py:198-218`
- Test: `tests/test_crm_period_scheduler.py` (create)

**Interfaces:**
- Consumes: `CRMPeriodReporter`, `PeriodType` (Task 6); `settings.CRM_SALES_REPORT_GROUP_ID` / `_TOPIC_ID` (Task 7); existing `_is_due`, `_is_job_sent`, module `m` (`src.main`).
- Produces:
  - `periodic_reports._send_period_report(ptype: PeriodType, now: datetime, task, *, reporter_factory=None) -> None` — builds and sends. `reporter_factory` is an injection seam for tests (defaults to constructing from `CRMService().amocrm`).
  - `run_periodic_reports` calls it for DAILY (19:30), WEEKLY (Mon 09:00), MONTHLY (day==1 09:00).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_crm_period_scheduler.py
from datetime import datetime

import pytest

from src.services.core.crm.daily_report.models import PeriodType, ReportResult, PeriodMetrics
from src.schedulers.main_loop import periodic_reports as pr


class _Task:
    pass


class _FakeReporter:
    def __init__(self):
        self.built = []

    async def build(self, ptype):
        self.built.append(ptype)
        m = PeriodMetrics(period_type=ptype,
                          period_start=datetime(2026, 9, 7).date(),
                          period_end=datetime(2026, 9, 7).date())
        return ReportResult(ptype, m.period_start, m.period_end, m, None, {}, "TEXT-BODY", True)


class _Bot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat, text, **kw):
        self.sent.append((chat, text, kw))


@pytest.mark.asyncio
async def test_send_period_report_dispatches_to_sales_group(monkeypatch):
    bot = _Bot()
    rep = _FakeReporter()
    monkeypatch.setattr(pr.m, "bot_runtime", bot, raising=False)
    monkeypatch.setattr(pr.settings, "CRM_SALES_REPORT_GROUP_ID", -1003854308552, raising=False)
    monkeypatch.setattr(pr.settings, "CRM_SALES_REPORT_TOPIC_ID", 115, raising=False)

    await pr._send_period_report(
        PeriodType.WEEKLY, datetime(2026, 9, 7, 9, 0), _Task(),
        reporter_factory=lambda: rep,
    )
    assert rep.built == [PeriodType.WEEKLY]
    assert bot.sent == [(-1003854308552, "TEXT-BODY", {"message_thread_id": 115})]


@pytest.mark.asyncio
async def test_send_period_report_skips_when_group_unset(monkeypatch):
    bot = _Bot()
    monkeypatch.setattr(pr.m, "bot_runtime", bot, raising=False)
    monkeypatch.setattr(pr.settings, "CRM_SALES_REPORT_GROUP_ID", None, raising=False)
    await pr._send_period_report(
        PeriodType.DAILY, datetime(2026, 9, 7, 19, 30), _Task(),
        reporter_factory=lambda: _FakeReporter(),
    )
    assert bot.sent == []


@pytest.mark.asyncio
async def test_send_period_report_is_idempotent_per_day(monkeypatch):
    bot = _Bot()
    rep = _FakeReporter()
    monkeypatch.setattr(pr.m, "bot_runtime", bot, raising=False)
    monkeypatch.setattr(pr.settings, "CRM_SALES_REPORT_GROUP_ID", -1, raising=False)
    monkeypatch.setattr(pr.settings, "CRM_SALES_REPORT_TOPIC_ID", None, raising=False)
    task = _Task()
    for _ in range(2):
        await pr._send_period_report(
            PeriodType.DAILY, datetime(2026, 9, 7, 19, 30), task,
            reporter_factory=lambda: rep,
        )
    assert rep.built == [PeriodType.DAILY]  # built once
    assert len(bot.sent) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_crm_period_scheduler.py -q`
Expected: FAIL — `AttributeError: module 'src.schedulers.main_loop.periodic_reports' has no attribute '_send_period_report'`.

- [ ] **Step 3: Write minimal implementation**

In `periodic_reports.py` add near the top:

```python
from src.services.core.crm.daily_report.models import PeriodType


def _default_period_reporter():
    from src.services.core.crm.daily_report import CRMPeriodReporter
    from src.services.core.crm.crm_service import CRMService
    crm = CRMService()
    if not crm.amocrm:
        return None
    return CRMPeriodReporter(amocrm=crm.amocrm)


async def _send_period_report(ptype, now, task, *, reporter_factory=None):
    key = f"crm_{ptype.value}_report_{now:%Y-%m-%d}"
    if _is_job_sent(task, key):
        return
    try:
        reporter = (reporter_factory or _default_period_reporter)()
        if reporter is None:
            logger.warning("[SCHEDULE][%s] no amocrm; skip", ptype.value)
            return
        result = await reporter.build(ptype)
        group = settings.CRM_SALES_REPORT_GROUP_ID
        topic = settings.CRM_SALES_REPORT_TOPIC_ID
        bot_rt = getattr(m, "bot_runtime", None) or getattr(m, "bot_client", None)
        if not group or not bot_rt:
            logger.warning("[SCHEDULE][%s] group/bot missing; skip", ptype.value)
            return
        kw = {"message_thread_id": topic} if topic else {}
        await bot_rt.send_message(group, result.telegram_text, **kw)
        logger.info("[SCHEDULE][%s] CRM report sent to %s", ptype.value, group)
    except Exception as exc:
        logger.error("[SCHEDULE][%s] Error: %s", ptype.value, exc)
```

Replace the CRM block in `_check_daily_reports` (the `crm_daily_report_{today_str}` `if` at lines ~90-106) with:

```python
    if _is_due(now, 19, 30):
        await _send_period_report(PeriodType.DAILY, now, task)
```

Replace the weekly block in `_check_weekly_and_stagnation` (lines ~111-129) with:

```python
    if now.weekday() == 0 and _is_due(now, 9, 0):
        await _send_period_report(PeriodType.WEEKLY, now, task)

    if now.day == 1 and _is_due(now, 9, 0):
        await _send_period_report(PeriodType.MONTHLY, now, task)
```

Leave the 18:00 efficiency report block and the stagnation block untouched.

In `src/schedulers/bg_monitor/jobs_crm.py` around lines 198-218, replace the `fetch_weekly_stats` + `format_weekly_report_uz` pair with:

```python
                from src.services.core.crm.crm_daily_report import CRMPeriodReporter
                from src.services.core.crm.daily_report.models import PeriodType
                reporter = CRMPeriodReporter(amocrm=amocrm_client)
                report_text = (await reporter.build(PeriodType.WEEKLY)).telegram_text
```

(Keep the surrounding send logic and the existing `import previous_week_range` line only if still referenced; if not, drop it.)

- [ ] **Step 4: Run tests**

Run: `SKIP_LIVE=1 python -m pytest tests/test_crm_period_scheduler.py tests/test_crm_weekly_report.py -q`
Expected: PASS.
Run: `SKIP_LIVE=1 python -m pytest -q` (full suite smoke) — expect no new failures.

- [ ] **Step 5: Commit**

```bash
git add src/schedulers/main_loop/periodic_reports.py src/schedulers/bg_monitor/jobs_crm.py tests/test_crm_period_scheduler.py
git commit -m "feat(crm): schedule daily/weekly/monthly reports to sales group

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 9: API endpoint `/api/crm/reports`

**Files:**
- Create: `src/api/routes/crm_reports.py`
- Modify: `src/services/api_server/core.py:118` (import) and `:139` (include_router)
- Test: `tests/test_crm_reports_api.py` (append)

**Interfaces:**
- Consumes: `CRMPeriodReporter`, `PeriodType`, `ReportResult` (Task 6); `api_state` (`src/api/routes/state.py`); `_get_amocrm_instance` (`src/api/routes/amocrm_integration.py`); `require_permissions`, `Permission`, `Principal` (`src/api/rbac.py`).
- Produces:
  - `router = APIRouter(prefix="/api/crm", tags=["crm-reports"])`.
  - `GET /api/crm/reports?period=daily|weekly|monthly` → JSON:
    ```json
    {
      "available": true,
      "period": "daily",
      "period_start": "2026-09-07",
      "period_end": "2026-09-07",
      "metrics": { ...PeriodMetrics.to_dict()... },
      "previous": { ... } | null,
      "deltas": { "new_leads": 3, ... },
      "telegram_text": "..."
    }
    ```
  - When no amocrm instance: `{"available": false, "period": <period>}` (HTTP 200).

- [ ] **Step 1: Write the failing test (append to `tests/test_crm_reports_api.py`)**

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services.core.crm.daily_report.models import PeriodType, PeriodMetrics, ReportResult


@pytest.fixture
def client(monkeypatch):
    from src.api.routes import crm_reports

    class _Rep:
        def __init__(self, *a, **k):
            pass

        async def build(self, ptype):
            m = PeriodMetrics(period_type=ptype,
                              period_start=__import__("datetime").date(2026, 9, 7),
                              period_end=__import__("datetime").date(2026, 9, 7),
                              new_leads=12)
            m.recompute_derived()
            return ReportResult(ptype, m.period_start, m.period_end, m, None, {}, "BODY", True)

    monkeypatch.setattr(crm_reports, "CRMPeriodReporter", _Rep)
    monkeypatch.setattr(crm_reports, "_resolve_amocrm", lambda: object())

    app = FastAPI(title="test")
    app.include_router(crm_reports.router)
    # bypass RBAC dependency
    from src.api.rbac import Principal, Role
    app.dependency_overrides[crm_reports._principal_dep] = lambda: Principal(
        subject="t", role=Role.VIEWER
    )
    return TestClient(app)


def test_reports_endpoint_daily(client):
    r = client.get("/api/crm/reports?period=daily")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert body["period"] == "daily"
    assert body["metrics"]["new_leads"] == 12
    assert body["telegram_text"] == "BODY"


def test_reports_endpoint_rejects_bad_period(client):
    r = client.get("/api/crm/reports?period=hourly")
    assert r.status_code == 422


def test_reports_endpoint_unavailable_without_amocrm(client, monkeypatch):
    from src.api.routes import crm_reports
    monkeypatch.setattr(crm_reports, "_resolve_amocrm", lambda: None)
    r = client.get("/api/crm/reports?period=weekly")
    assert r.status_code == 200
    assert r.json() == {"available": False, "period": "weekly"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_crm_reports_api.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.api.routes.crm_reports'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/api/routes/crm_reports.py`:

```python
"""CRM davriy hisobotlar API — kunlik / haftalik / oylik.

`GET /api/crm/reports?period=daily|weekly|monthly` bitta manbadan
(`CRMPeriodReporter.build`) to'liq metrika JSON qaytaradi. Telegram matni
va dashboard raqamlari shu yerdan keladi.
"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter

from src.api.rbac import Permission, Principal, require_permissions
from src.api.routes.state import api_state
from src.services.core.crm.daily_report import CRMPeriodReporter
from src.services.core.crm.daily_report.models import PeriodType

router = APIRouter(prefix="/api/crm", tags=["crm-reports"])
logger = logging.getLogger(__name__)

_principal_dep = require_permissions(Permission.DASHBOARD_READ)


def _resolve_amocrm():
    if api_state.amocrm_instance:
        return api_state.amocrm_instance
    try:
        from src.api.routes.amocrm_integration import _get_amocrm_instance
        return _get_amocrm_instance()
    except Exception as exc:
        logger.debug("[crm-reports] amocrm lookup failed: %s", exc)
        return None


@router.get("/reports")
async def crm_reports(
    period: Literal["daily", "weekly", "monthly"] = "daily",
    principal: Principal = _principal_dep,
):
    amocrm = _resolve_amocrm()
    if amocrm is None:
        return {"available": False, "period": period}

    ptype = PeriodType(period)
    result = await CRMPeriodReporter(amocrm=amocrm).build(ptype)
    return {
        "available": result.fetch_ok,
        "period": period,
        "period_start": result.period_start.isoformat(),
        "period_end": result.period_end.isoformat(),
        "metrics": result.metrics.to_dict(),
        "previous": result.previous.to_dict() if result.previous else None,
        "deltas": result.deltas,
        "telegram_text": result.telegram_text,
    }
```

In `src/services/api_server/core.py`, next to the existing `crm_dashboard` import (line ~118):

```python
from src.api.routes.crm_reports import router as crm_reports_router
```

and next to `app.include_router(crm_dashboard_router)` (line ~139):

```python
app.include_router(crm_reports_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `SKIP_LIVE=1 python -m pytest tests/test_crm_reports_api.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/crm_reports.py src/services/api_server/core.py tests/test_crm_reports_api.py
git commit -m "feat(crm): add GET /api/crm/reports endpoint

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 10: Telegram slash commands — `/report_week`, `/report_month`, update `/stats` `/history`

**Files:**
- Modify: `src/commands/dashboard.py:42-110`
- Test: `tests/test_crm_period_commands.py` (create)

**Interfaces:**
- Consumes: `CRMPeriodReporter`, `PeriodType` (Task 6); existing `register_command`, `ctx` dict with `msg_controller`, `get_surgical_integration`.
- Produces: command handlers `cmd_report_week`, `cmd_report_month`; `cmd_report` rewritten to use `build(DAILY)`; `cmd_stats` and `cmd_history` updated to `PeriodMetrics` field names.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_crm_period_commands.py
import pytest

from src.services.core.crm.daily_report.models import PeriodType, PeriodMetrics, ReportResult
from src.commands import dashboard as dash


class _Event:
    def __init__(self):
        self.responses = []

    async def respond(self, text):
        self.responses.append(text)


class _Rep:
    def __init__(self, *a, **k):
        pass

    async def build(self, ptype):
        m = PeriodMetrics(period_type=ptype,
                          period_start=__import__("datetime").date(2026, 9, 1),
                          period_end=__import__("datetime").date(2026, 9, 30))
        return ReportResult(ptype, m.period_start, m.period_end, m, None, {},
                            f"BODY-{ptype.value}", True)


@pytest.fixture(autouse=True)
def _patch(monkeypatch):
    monkeypatch.setattr(dash, "CRMPeriodReporter", _Rep, raising=False)


@pytest.mark.asyncio
async def test_cmd_report_month(monkeypatch):
    ev = _Event()
    await dash.cmd_report_month(ev, msg_controller=None,
                                get_surgical_integration=lambda: type("S", (), {"amocrm": object()}))
    assert any("BODY-monthly" in r for r in ev.responses)


@pytest.mark.asyncio
async def test_cmd_report_week(monkeypatch):
    ev = _Event()
    await dash.cmd_report_week(ev, msg_controller=None,
                              get_surgical_integration=lambda: type("S", (), {"amocrm": object()}))
    assert any("BODY-weekly" in r for r in ev.responses)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SKIP_LIVE=1 python -m pytest tests/test_crm_period_commands.py -q`
Expected: FAIL — `AttributeError: module 'src.commands.dashboard' has no attribute 'cmd_report_month'`.

- [ ] **Step 3: Write minimal implementation**

In `src/commands/dashboard.py` add at import time:

```python
from src.services.core.crm.daily_report import CRMPeriodReporter
from src.services.core.crm.daily_report.models import PeriodType
```

Add a helper and two commands, and rewrite `cmd_report`:

```python
def _amocrm_from_ctx(msg_controller, get_surgical_integration):
    amocrm = None
    if msg_controller and getattr(msg_controller, "crm", None):
        amocrm = getattr(msg_controller.crm, "amocrm", None)
    if not amocrm:
        amocrm = get_surgical_integration().amocrm
    return amocrm


async def _run_period(event, ptype, msg_controller, get_surgical_integration):
    try:
        amocrm = _amocrm_from_ctx(msg_controller, get_surgical_integration)
        res = await CRMPeriodReporter(amocrm=amocrm).build(ptype)
        await event.respond(res.telegram_text)
    except Exception as e:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        await event.respond(f"❌ Xatolik yuz berdi: {e}")


@register_command("/report")
async def cmd_report(event, **ctx):
    await event.respond("⏳ Oisha-OS: Kunlik CRM hisobot tayyorlanmoqda...")
    await _run_period(event, PeriodType.DAILY, ctx["msg_controller"], ctx["get_surgical_integration"])


@register_command("/report_week")
async def cmd_report_week(event, **ctx):
    await event.respond("⏳ Haftalik CRM hisobot tayyorlanmoqda...")
    await _run_period(event, PeriodType.WEEKLY, ctx["msg_controller"], ctx["get_surgical_integration"])


@register_command("/report_month")
async def cmd_report_month(event, **ctx):
    await event.respond("⏳ Oylik CRM hisobot tayyorlanmoqda...")
    await _run_period(event, PeriodType.MONTHLY, ctx["msg_controller"], ctx["get_surgical_integration"])
```

Update `cmd_stats` body text block to use `PeriodMetrics` fields:

```python
        reporter = CRMPeriodReporter(amocrm=amocrm_client)
        res = await reporter.build(PeriodType.DAILY)
        m = res.metrics
        text = (
            f"📊 **Bugungi holat ({m.date_label})**\n"
            f"Yangi bitimlar: {m.new_leads}\n"
            f"Faol: {m.active_count} ({m.active_amount:,.0f} so'm)\n".replace(",", " ")
            + f"Yutilgan: {m.won_count} | Daromad: {m.won_amount:,.0f} so'm\n".replace(",", " ")
            + f"Pipeline: {m.pipeline_value:,.0f} so'm".replace(",", " ")
        )
        await event.respond(text)
```

Update `cmd_history` to use `list_snapshots`:

```python
        reporter = CRMPeriodReporter(amocrm=None)
        history = reporter.list_snapshots(PeriodType.DAILY, 7)
        if not history:
            await event.respond("📅 Tarix topilmadi. Hisobotlar hali keshga yozilmagan.")
            return
        lines = ["📅 **So'nggi 7 kunlik CRM hisobotlar:**"]
        for s in history:
            lines.append(
                f"• {s.date_label}: {s.new_leads} lead | {s.won_count} won | {s.won_amount:,.0f} so'm".replace(",", " ")
            )
        await event.respond("\n".join(lines))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `SKIP_LIVE=1 python -m pytest tests/test_crm_period_commands.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/commands/dashboard.py tests/test_crm_period_commands.py
git commit -m "feat(crm): add /report_week /report_month, update /stats /history

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 11: Python gate + Telegram/backward-compat smoke

**Files:** none new — verification task.

- [ ] **Step 1: Full test suite**

Run: `SKIP_LIVE=1 python -m pytest -q --tb=short`
Expected: PASS. If `tests/test_crm_weekly_report.py` or any `test_crm_daily_report*` fails, fix the compat shim in `models.py` / `formatter.py` / `fetcher.py` (do NOT change the tests).

- [ ] **Step 2: Security scan**

Run: `bandit -r src/ -ll`
Expected: no new HIGH/MEDIUM findings in the touched files.

- [ ] **Step 3: Import smoke for legacy callers**

Run:
```bash
SKIP_LIVE=1 python -c "
from src.services.core.crm.crm_daily_report import CRMDailyReporter, CRMPeriodReporter, CRMStats, CRMWeeklyStats, PeriodType, previous_week_range, build_reportagram_report
from src.services.core.crm.daily_report import CRMPeriodReporter as R2
import src.services.core.dispatcher.handlers_crm_coach  # noqa
import src.services.core.admin_bot.reports  # noqa
import src.services.reporter.plans  # noqa
import src.schedulers.main_loop.periodic_reports  # noqa
import src.schedulers.bg_monitor.jobs_crm  # noqa
import src.api.routes.crm_reports  # noqa
print('imports OK')
"
```
Expected: `imports OK`.

- [ ] **Step 4: Commit (if any fixes were needed)**

```bash
git add -A
git commit -m "test(crm): green gate for unified period reporter

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

If nothing changed, skip the commit.

---

## Task 12: Frontend — proxy route

**Files:**
- Create: `apps/web/src/app/api/oisha/crm-reports/route.ts`

**Interfaces:**
- Produces: `GET /api/oisha/crm-reports?period=…` → forwards to backend `/api/crm/reports?period=…`, same auth-header pattern as `dashboard-overview/route.ts`.

- [ ] **Step 1: Create the route (mirror `dashboard-overview/route.ts`)**

```typescript
// apps/web/src/app/api/oisha/crm-reports/route.ts
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const baseUrl =
    process.env.OISHA_API_URL ??
    process.env.NEXT_PUBLIC_OISHA_API_URL ??
    "http://127.0.0.1:8080";

  const headers: HeadersInit = {};
  const cookie = request.headers.get("cookie");
  if (cookie) headers["cookie"] = cookie;
  const authHeader = request.headers.get("authorization");
  if (authHeader) headers["authorization"] = authHeader;
  const apiSecret = process.env.OISHA_API_SECRET;
  if (apiSecret && !authHeader) headers["authorization"] = `Bearer ${apiSecret}`;

  const period = request.nextUrl.searchParams.get("period") ?? "daily";

  try {
    const response = await fetch(
      `${baseUrl.replace(/\/$/, "")}/api/crm/reports?period=${encodeURIComponent(period)}`,
      { cache: "no-store", headers }
    );
    const payload = await response.json();
    return NextResponse.json(payload, { status: response.status });
  } catch (error) {
    return NextResponse.json(
      {
        available: false,
        period,
        message: `Oisha API unavailable: ${
          error instanceof Error ? error.message : "unknown error"
        }`,
      },
      { status: 503 }
    );
  }
}
```

- [ ] **Step 2: Type-check**

Run: `cd apps/web && pnpm typecheck` (or repo-root `pnpm run typecheck`).
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/app/api/oisha/crm-reports/route.ts
git commit -m "feat(web): add crm-reports proxy route

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 13: Frontend — "CRM Hisobot" tab in analytics page

**Files:**
- Modify: `apps/web/src/app/(dashboard)/analytics/page.tsx`

**Interfaces:**
- Consumes: `/api/oisha/crm-reports?period=` (Task 12).
- Produces: a new tab `"crm-report"` labelled `"CRM Hisobot"` with `Kunlik | Haftalik | Oylik` period buttons and 4 metric-card groups + a manager table + a collapsible Telegram-text block.

- [ ] **Step 1: Add types + state**

Near the top of the component file, add:

```typescript
interface CrmManagerRow {
  user_id: number;
  name: string;
  won_count: number;
  won_amount: number;
  open_tasks: number;
  overdue_tasks: number;
}

interface CrmMetrics {
  new_leads: number;
  won_count: number;
  won_amount: number;
  lost_count: number;
  lost_amount: number;
  active_count: number;
  active_amount: number;
  pipeline_value: number;
  stagnated_count: number;
  win_rate: number;
  avg_won_deal: number;
  new_contacts: number;
  new_companies: number;
  incoming_calls: number;
  tasks_created: number;
  tasks_completed: number;
  tasks_open: number;
  tasks_overdue: number;
  leads_without_task: number;
  managers: CrmManagerRow[];
}

interface CrmReport {
  available: boolean;
  period: "daily" | "weekly" | "monthly";
  period_start?: string;
  period_end?: string;
  metrics?: CrmMetrics;
  previous?: CrmMetrics | null;
  deltas?: Record<string, number>;
  telegram_text?: string;
}
```

Extend the `activeTab` union with `| "crm-report"` and add:

```typescript
  const [reportPeriod, setReportPeriod] = useState<"daily" | "weekly" | "monthly">("daily");
  const [crmReport, setCrmReport] = useState<CrmReport | null>(null);
  const [crmReportLoading, setCrmReportLoading] = useState(false);
  const [showTgText, setShowTgText] = useState(false);

  useEffect(() => {
    if (activeTab !== "crm-report") return;
    let cancelled = false;
    setCrmReportLoading(true);
    fetch(`/api/oisha/crm-reports?period=${reportPeriod}`)
      .then((r) => r.json())
      .then((d) => { if (!cancelled) setCrmReport(d); })
      .catch(() => { if (!cancelled) setCrmReport(null); })
      .finally(() => { if (!cancelled) setCrmReportLoading(false); });
    return () => { cancelled = true; };
  }, [activeTab, reportPeriod]);
```

- [ ] **Step 2: Add the tab button**

In the tab list array/markup (where other tabs like `overview`, `quality` are declared — around line 33/112), add `{ id: "crm-report", label: "CRM Hisobot" }` (match the existing shape used by `setActiveTab(tab.id)`).

- [ ] **Step 3: Add the tab content block**

After the last `{activeTab === "leads" && ( ... )}` block, add:

```tsx
        {activeTab === "crm-report" && (
          <div className="space-y-6">
            <div className="flex gap-2">
              {(["daily", "weekly", "monthly"] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setReportPeriod(p)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium ${
                    reportPeriod === p
                      ? "bg-blue-600 text-white"
                      : "bg-gray-100 text-gray-700"
                  }`}
                >
                  {p === "daily" ? "Kunlik" : p === "weekly" ? "Haftalik" : "Oylik"}
                </button>
              ))}
            </div>

            {crmReportLoading && <p className="text-gray-500">Yuklanmoqda...</p>}

            {!crmReportLoading && (!crmReport || !crmReport.available) && (
              <div className="rounded-lg border border-dashed border-gray-300 p-8 text-center text-gray-500">
                AmoCRM ulanmagan — hisobot mavjud emas.
              </div>
            )}

            {!crmReportLoading && crmReport?.available && crmReport.metrics && (
              <CrmReportView report={crmReport} />
            )}
          </div>
        )}
```

- [ ] **Step 4: Add the `CrmReportView` component**

At the bottom of the file (module scope, after the default export component or before it):

```tsx
function delta(deltas: Record<string, number> | undefined, key: string) {
  const v = deltas?.[key];
  if (v === undefined || Math.abs(v) < 1e-9) return null;
  const up = v > 0;
  return (
    <span className={up ? "text-green-600 ml-2 text-xs" : "text-red-600 ml-2 text-xs"}>
      {up ? "▲ +" : "▼ "}
      {Math.round(v).toLocaleString("en-US").replace(/,/g, " ")}
    </span>
  );
}

function Stat({
  label,
  value,
  deltas,
  deltaKey,
}: {
  label: string;
  value: string;
  deltas?: Record<string, number>;
  deltaKey?: string;
}) {
  return (
    <div className="rounded-lg bg-white border border-gray-200 p-4">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-lg font-semibold text-gray-900">
        {value}
        {deltaKey ? delta(deltas, deltaKey) : null}
      </div>
    </div>
  );
}

function money(n: number) {
  return `${Math.round(n).toLocaleString("en-US").replace(/,/g, " ")} so'm`;
}

function CrmReportView({ report }: { report: CrmReport }) {
  const m = report.metrics!;
  const d = report.deltas;
  return (
    <div className="space-y-6">
      <section>
        <h3 className="font-semibold text-gray-800 mb-2">Bitimlar</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="Yangi bitimlar" value={String(m.new_leads)} deltas={d} deltaKey="new_leads" />
          <Stat label="Faol bitimlar" value={`${m.active_count} · ${money(m.active_amount)}`} />
          <Stat label="Yutilgan" value={`${m.won_count} · ${money(m.won_amount)}`} deltas={d} deltaKey="won_count" />
          <Stat label="Yutqazilgan" value={`${m.lost_count} · ${money(m.lost_amount)}`} deltas={d} deltaKey="lost_count" />
          <Stat label="Win rate" value={`${m.win_rate.toFixed(0)}%`} deltas={d} deltaKey="win_rate" />
          <Stat label="O'rtacha yutilgan bitim" value={money(m.avg_won_deal)} />
          <Stat label="Pipeline qiymati" value={money(m.pipeline_value)} />
          <Stat label="Stagnatsiya (3+ kun)" value={String(m.stagnated_count)} />
        </div>
      </section>

      <section>
        <h3 className="font-semibold text-gray-800 mb-2">Aloqa</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="Yangi kontaktlar" value={String(m.new_contacts)} deltas={d} deltaKey="new_contacts" />
          <Stat label="Yangi kompaniyalar" value={String(m.new_companies)} />
          <Stat label="Kiruvchi qo'ng'iroqlar" value={String(m.incoming_calls)} deltas={d} deltaKey="incoming_calls" />
        </div>
      </section>

      <section>
        <h3 className="font-semibold text-gray-800 mb-2">Zadachalar</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="Yaratilgan" value={String(m.tasks_created)} deltas={d} deltaKey="tasks_created" />
          <Stat label="Bajarilgan" value={String(m.tasks_completed)} />
          <Stat label="Ochiq" value={String(m.tasks_open)} />
          <Stat label="Muddati o'tgan" value={String(m.tasks_overdue)} />
          <Stat label="Zadachasiz ochiq bitimlar" value={String(m.leads_without_task)} />
        </div>
      </section>

      <section>
        <h3 className="font-semibold text-gray-800 mb-2">Menejerlar</h3>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500">
                <th className="py-2 pr-4">Menejer</th>
                <th className="py-2 pr-4">Yutilgan</th>
                <th className="py-2 pr-4">Summa</th>
                <th className="py-2 pr-4">Ochiq zadacha</th>
                <th className="py-2 pr-4">Muddati o'tgan</th>
              </tr>
            </thead>
            <tbody>
              {m.managers.map((mr) => (
                <tr key={mr.user_id} className="border-t border-gray-100">
                  <td className="py-2 pr-4">{mr.name}</td>
                  <td className="py-2 pr-4">{mr.won_count}</td>
                  <td className="py-2 pr-4">{money(mr.won_amount)}</td>
                  <td className="py-2 pr-4">{mr.open_tasks}</td>
                  <td className="py-2 pr-4">{mr.overdue_tasks}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {report.telegram_text && (
        <section>
          <button
            onClick={() => setShowTgTextOuter((s) => !s)}
            className="text-sm text-blue-600 underline"
          >
            Telegram xabari matni
          </button>
        </section>
      )}
    </div>
  );
}
```

Note: the collapsible needs `showTgText` state — move the toggle up to the page component. Simplest working version: render the `<pre>` unconditionally inside `CrmReportView`:

```tsx
      {report.telegram_text && (
        <section>
          <h3 className="font-semibold text-gray-800 mb-2">Telegram xabari</h3>
          <pre className="whitespace-pre-wrap rounded-lg bg-gray-50 border border-gray-200 p-4 text-xs text-gray-700">
{report.telegram_text}
          </pre>
        </section>
      )}
```

Use this simpler unconditional `<pre>` version and drop the `showTgText` / `setShowTgTextOuter` references.

- [ ] **Step 5: Type-check + build**

Run: `cd apps/web && pnpm typecheck && pnpm build` (or `pnpm run typecheck` at root).
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add "apps/web/src/app/(dashboard)/analytics/page.tsx"
git commit -m "feat(web): add CRM Hisobot tab (daily/weekly/monthly) to analytics

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 14: Manual end-to-end verification + docs

**Files:**
- Modify: `DEV_LOG.md` (prepend a dated entry)

- [ ] **Step 1: Backend endpoint smoke (if a dev API is reachable)**

Run (only if `ALLOW_LOCAL_RUN` dev API is up on `127.0.0.1:8080`):
```bash
curl -s "http://127.0.0.1:8080/api/crm/reports?period=weekly" -H "Authorization: Bearer $OISHA_API_SECRET" | python -m json.tool | head -40
```
Expected: JSON with `available`, `metrics`, `telegram_text`. If no dev API, skip and note it.

- [ ] **Step 2: Dashboard preview**

Start the web app preview (Browser pane / `preview_start` with the web dev server), open `/analytics`, click "CRM Hisobot", switch `Kunlik / Haftalik / Oylik`. Confirm cards render or the "AmoCRM ulanmagan" placeholder shows. Screenshot for the user.

- [ ] **Step 3: DEV_LOG entry**

Prepend to `DEV_LOG.md`:

```markdown
## 2026-09-07 — Unified CRM period reporter

- New `CRMPeriodReporter.build(PeriodType)` powers daily / weekly / monthly
  amoCRM reports from one code path (deal, contact, task, manager metrics).
- Proxy metrics (`contacted`, `qualified`, `avg_response_sec`) removed.
- Telegram: daily 19:30, weekly Mon 09:00, monthly 1st 09:00 -> sales-team
  group `CRM_SALES_REPORT_GROUP_ID` (-1003854308552), topic 115.
- Snapshots persisted to `crm_report_snapshots` for period-over-period deltas.
- New `GET /api/crm/reports?period=` + "CRM Hisobot" tab on `/analytics`.
- Fixes previously-broken `CRMDailyReporter.get_weekly_report()` call.
```

- [ ] **Step 4: Commit**

```bash
git add DEV_LOG.md
git commit -m "docs: DEV_LOG entry for unified CRM period reporter

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage:**

| Spec section | Task |
|---|---|
| Period-agnostic package, module boundaries | Tasks 1-6 |
| `PeriodType`, `period_range`, `previous_range`, `compute_deltas` | Task 1 |
| `PeriodMetrics` / `ManagerRow` / `ReportResult`, compat properties | Task 2 |
| Proxy metrics excluded | Tasks 2, 5 (no fields, no computation) |
| Fetcher — parallel amoCRM calls, aggregation, resilience | Task 5 |
| Formatter — 3-period template, deltas, links, Uzbek months | Task 3 |
| Snapshot DB — `crm_report_snapshots`, save/load/list | Task 4 |
| Backward-compat (`CRMStats`, `format_report(stats,prev)`, `get_history`, `get_weekly_report`) | Tasks 2, 3, 4, 6, 11 |
| Settings `CRM_SALES_REPORT_GROUP_ID/TOPIC_ID` + `.env.example` | Task 7 |
| Scheduler: daily 19:30 / weekly Mon 9:00 / monthly 1st 9:00, sales group, skip-if-unset, idempotent | Task 8 |
| `bg_monitor/jobs_crm.py` weekly path unified | Task 8 |
| `GET /api/crm/reports?period=`, RBAC `DASHBOARD_READ`, `available:false` fallback | Task 9 |
| Router mount in `core.py` | Task 9 |
| Slash commands `/report` `/report_week` `/report_month` `/stats` `/history` | Task 10 |
| Test gate + bandit + legacy import smoke | Task 11 |
| Frontend proxy route | Task 12 |
| Frontend "CRM Hisobot" tab, period buttons, 4 card groups, manager table, telegram text | Task 13 |
| Manual E2E + DEV_LOG | Task 14 |
| `list_snapshots` for future dashboard history | Task 4 (infra only, per spec "kelajak") |

No gaps.

**2. Placeholder scan:** No "TBD"/"TODO"/"handle edge cases"/"similar to Task N". Every code step has concrete code. Error handling is spelled out (`try/except` bodies shown, skip-and-log behavior explicit).

**3. Type consistency:**
- `PeriodType` members `DAILY/WEEKLY/MONTHLY` — consistent Tasks 1-13.
- `PeriodMetrics` field names (`won_count`, `won_amount`, `active_count`, `tasks_open`, `leads_without_task`, `managers`) — identical in Tasks 2, 3, 5, 6, 9, 13.
- `ManagerRow` fields (`user_id`, `name`, `won_count`, `won_amount`, `open_tasks`, `overdue_tasks`) — identical Tasks 2, 3, 5, 13.
- `ReportResult` fields (`period_type`, `period_start`, `period_end`, `metrics`, `previous`, `deltas`, `telegram_text`, `fetch_ok`) — identical Tasks 2, 6, 8, 9, 10.
- `CRMPeriodReporter.build(ptype, anchor=None)` signature — identical Tasks 6, 8, 9, 10.
- `format_period_report(ptype, current, previous)` — identical Tasks 3, 6.
- `save_snapshot(m)` / `load_snapshot(ptype, period_start)` / `list_snapshots(ptype, limit)` — identical Tasks 4, 6, 10.
- `_last_fetch_ok` flag — set in Task 5 code (amended within Task 6 Step 3), read in Task 6.
- Endpoint symbols `_resolve_amocrm`, `_principal_dep`, `CRMPeriodReporter` monkeypatched in Task 9 tests match names defined in Task 9 implementation.

One correction applied inline: Task 6 Step 3 explicitly instructs adding the `self._last_fetch_ok = any([...])` line into Task 5's `fetch_metrics` (Task 5 as written doesn't set it). Implementers doing Task 5 first should add it then; the assignment list matches the nine `_safe(...)` results.
