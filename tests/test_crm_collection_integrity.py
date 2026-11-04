"""Synthetic CRM responses: incomplete reads must never become report totals."""
import asyncio
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import requests

from src.services.core.crm.daily_report import CRMDailyReporter


def reporter_for(responses):
    request = AsyncMock(side_effect=responses)
    reporter = CRMDailyReporter.__new__(CRMDailyReporter)
    reporter._crm = SimpleNamespace(
        base_url="https://example.amocrm.ru", _request_with_auth=request,
    )
    return reporter


def response(code=200, payload=None):
    return SimpleNamespace(status_code=code, json=lambda: payload)


@pytest.mark.parametrize("failure", [
    response(401), response(500), requests.Timeout("synthetic timeout"),
    response(200, {}), response(200, {"_embedded": {"leads": None}}),
])
@pytest.mark.parametrize("after_page", [False, True])
def test_incomplete_collection_raises(failure, after_page):
    pages = [response(200, {"_embedded": {"leads": [{"id": 1}]}})] if after_page else []
    reporter = reporter_for(pages + [failure])
    with pytest.raises(RuntimeError):
        asyncio.run(reporter._fetch_amocrm_collection("leads", page_size=1))


def test_page_limit_is_not_a_complete_collection():
    reporter = reporter_for([response(200, {"_embedded": {"leads": [{"id": 1}]}})])
    with pytest.raises(RuntimeError):
        asyncio.run(reporter._fetch_amocrm_collection("leads", page_size=1, max_pages=1))


@pytest.mark.parametrize("empty", [response(204), response(200, {"_embedded": {"leads": []}})])
def test_successful_empty_collection_is_zero(empty):
    reporter = reporter_for([empty])
    assert asyncio.run(reporter._fetch_amocrm_collection("leads")) == []


@pytest.mark.parametrize("failed_call", range(5))
def test_weekly_stats_never_aggregates_failed_source(failed_call):
    pages = [response(204) for _ in range(failed_call)] + [response(503)]
    reporter = reporter_for(pages)
    with pytest.raises(RuntimeError):
        asyncio.run(reporter.fetch_weekly_stats(date(2026, 10, 26), date(2026, 10, 26)))


def test_missing_crm_is_unknown():
    reporter = reporter_for([])
    reporter._crm = None
    with pytest.raises(RuntimeError):
        asyncio.run(reporter._fetch_amocrm_collection("leads"))


def test_token_refresh_recovers_without_losing_page():
    reporter = reporter_for([response(401), response(204)])
    reporter._crm.refresh_token = lambda: True
    assert asyncio.run(reporter._fetch_amocrm_collection("leads")) == []
    assert reporter._crm._request_with_auth.await_count == 2


def test_short_page_with_next_link_is_not_complete():
    reporter = reporter_for([
        response(200, {"_embedded": {"leads": [{"id": 1}]},
                       "_links": {"next": {"href": "synthetic-next"}}}),
        response(500),
    ])
    with pytest.raises(RuntimeError):
        asyncio.run(reporter._fetch_amocrm_collection("leads"))


def test_verified_empty_stats_keep_real_zeroes():
    reporter = reporter_for([response(204) for _ in range(5)])
    stats = asyncio.run(reporter.fetch_weekly_stats(date(2026, 10, 26), date(2026, 10, 26)))
    assert stats.active_leads == stats.new_leads == stats.won_leads == 0
    assert stats.active_amount == stats.won_amount == stats.lost_amount == 0


@pytest.mark.parametrize("failed_call", range(9))
def test_period_report_never_persists_partial_totals(tmp_path, failed_call):
    from src.services.core.crm.daily_report import CRMPeriodReporter
    from src.services.core.crm.daily_report.models import PeriodType

    reporter = CRMPeriodReporter(None, str(tmp_path / "report.db"))
    reporter._fetch_amocrm_collection = AsyncMock(
        side_effect=[[] for _ in range(failed_call)]
        + [RuntimeError("synthetic source failure")]
        + [[] for _ in range(8 - failed_call)]
    )
    with pytest.raises(RuntimeError):
        asyncio.run(reporter.build(PeriodType.DAILY, date(2026, 11, 4)))
    assert reporter.load_snapshot(PeriodType.DAILY, date(2026, 11, 4)) is None


def test_verified_empty_period_is_available(tmp_path):
    from src.services.core.crm.daily_report import CRMPeriodReporter
    from src.services.core.crm.daily_report.models import PeriodType

    reporter = CRMPeriodReporter(None, str(tmp_path / "report.db"))
    reporter._fetch_amocrm_collection = AsyncMock(return_value=[])
    result = asyncio.run(reporter.build(PeriodType.DAILY, date(2026, 11, 4)))
    assert result.fetch_ok is True
    assert result.metrics.new_leads == 0
