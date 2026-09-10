"""
Facade for CRM Daily & Weekly Reporting.
Delegates to modular subpackage in src.services.core.crm.daily_report.
"""
from src.services.core.crm.daily_report import (
    CRMDailyReporter,
    CRMPeriodReporter,
    CRMStats,
    CRMWeeklyStats,
    ManagerRow,
    PeriodMetrics,
    PeriodType,
    ReportBot,
    ReportResult,
    _delta,
    _fmt_duration,
    _ts_today,
    _ts_yesterday,
    build_reportagram_report,
    compute_deltas,
    period_range,
    previous_anchor,
    previous_range,
    previous_week_range,
)

__all__ = [
    "CRMStats",
    "CRMWeeklyStats",
    "CRMDailyReporter",
    "CRMPeriodReporter",
    "PeriodType",
    "PeriodMetrics",
    "ManagerRow",
    "ReportResult",
    "period_range",
    "previous_range",
    "previous_anchor",
    "compute_deltas",
    "ReportBot",
    "build_reportagram_report",
    "_ts_today",
    "_ts_yesterday",
    "_delta",
    "_fmt_duration",
    "previous_week_range",
]
