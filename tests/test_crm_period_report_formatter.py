import json
from datetime import date
from pathlib import Path

import pytest

from src.services.core.crm.daily_report.formatter import FormatMixin
from src.services.core.crm.daily_report.models import ManagerRow, PeriodMetrics, PeriodType

SNAPSHOT = Path(__file__).parent / "fixtures" / "snapshots" / "crm_period_reports.json"


class _Crm:
    base_url = "https://jon.amocrm.ru"


class _Reporter(FormatMixin):
    DEFAULT_REPORT_PIPELINE_IDS = ["111", "222"]
    WON_STATUS = 142
    LOST_STATUS = 143
    _crm = _Crm()


def _full(ptype, start, end):
    managers = [
        ManagerRow(1, "Ali", won_count=5, won_amount=12_500_000, open_tasks=3, overdue_tasks=1),
        ManagerRow(2, "Vali", won_count=3, won_amount=4_000_000),
        ManagerRow(3, "Gani", won_count=2, won_amount=1_000_000.4, overdue_tasks=2),
        ManagerRow(4, "Sobir", won_count=1, won_amount=500_000),
    ]
    calls = [ManagerRow(1, "Ali", calls_count=20, calls_answered=15), ManagerRow(2, "Vali", calls_count=4)]
    return PeriodMetrics(
        ptype, start, end, new_leads=40, won_count=11, won_amount=18_000_000.5,
        lost_count=6, lost_amount=2_500_000, active_count=25, active_amount=90_000_000,
        pipeline_value=120_000_000, stagnated_count=7, win_rate=64.7, avg_won_deal=1_636_363.68,
        new_contacts=33, new_companies=4, incoming_calls=50, tasks_created=60,
        tasks_completed=41, tasks_open=19, tasks_overdue=5, leads_without_task=2,
        calls_total=80, calls_answered=61, managers=managers, call_managers=calls,
    )


def _prev(ptype, start, end):
    return PeriodMetrics(
        ptype, start, end, new_leads=30, won_count=11, lost_count=9, win_rate=70.2,
        new_contacts=40, incoming_calls=50, calls_total=1_200, calls_answered=70, tasks_created=55,
    )


D = (date(2026, 10, 2), date(2026, 10, 2))
W = (date(2026, 9, 28), date(2026, 10, 4))
M = (date(2026, 9, 1), date(2026, 9, 30))

CASES = {
    "daily_full_with_prev": (PeriodType.DAILY, _full(PeriodType.DAILY, *D), _prev(PeriodType.DAILY, *D)),
    "weekly_full_no_prev": (PeriodType.WEEKLY, _full(PeriodType.WEEKLY, *W), None),
    "monthly_empty": (PeriodType.MONTHLY, PeriodMetrics(PeriodType.MONTHLY, *M), None),
    "monthly_empty_with_prev": (
        PeriodType.MONTHLY, PeriodMetrics(PeriodType.MONTHLY, *M), _prev(PeriodType.MONTHLY, *M),
    ),
}


@pytest.fixture(autouse=True)
def _no_pipeline_env(monkeypatch):
    monkeypatch.delenv("CRM_REPORT_PIPELINE_IDS", raising=False)


def render(name):
    return _Reporter().format_period_report(*CASES[name])


@pytest.mark.parametrize("name", sorted(CASES))
def test_format_period_report_matches_snapshot(name):
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert render(name) == expected[name]


def test_format_report_dispatches_period_type():
    ptype, cur, prev = CASES["daily_full_with_prev"]
    assert _Reporter().format_report(ptype, cur, prev) == render("daily_full_with_prev")
