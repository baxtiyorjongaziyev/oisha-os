"""
Facade for CRM Daily & Weekly Reporting.
Delegates to modular subpackage in src.services.core.crm.daily_report.
"""
from src.services.core.crm.daily_report import (
    CRMDailyReporter,
    CRMStats,
    CRMWeeklyStats,
    ReportBot,
    _delta,
    _fmt_duration,
    _ts_today,
    _ts_yesterday,
    build_reportagram_report,
    previous_week_range,
)

__all__ = [
    "CRMStats",
    "CRMWeeklyStats",
    "CRMDailyReporter",
    "ReportBot",
    "build_reportagram_report",
    "_ts_today",
    "_ts_yesterday",
    "_delta",
    "_fmt_duration",
    "previous_week_range",
]
