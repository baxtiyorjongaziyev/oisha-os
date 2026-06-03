from datetime import date, datetime

import pytest

from src.services.core.crm_daily_report import (
    CRMDailyReporter,
    CRMWeeklyStats,
    previous_week_range,
)


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class FakeAmoCRM:
    base_url = "https://jonbrandingagency.amocrm.ru"
    access_token = "token"

    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def _get_headers(self):
        return {"Authorization": "Bearer token"}

    async def _request_with_auth(self, request_fn, url, **kwargs):
        collection = url.rsplit("/", 1)[-1]
        params = kwargs.get("params", {})
        page = int(params.get("page", 1))
        key = (
            collection,
            params.get("filter[created_at][from]"),
            params.get("filter[closed_at][from]"),
            page,
        )
        self.calls.append((collection, page, params))
        payload = self.pages.get(key, [])
        return FakeResponse(200, {"_embedded": {collection: payload}})


def test_previous_week_range_matches_monday_to_sunday():
    start, end = previous_week_range(date(2026, 6, 3))

    assert start == date(2026, 5, 25)
    assert end == date(2026, 5, 31)


def test_format_weekly_report_uz_contains_reportagram_style_fields(tmp_path):
    reporter = CRMDailyReporter(amocrm=FakeAmoCRM({}), db_path=str(tmp_path / "r.db"))
    stats = CRMWeeklyStats(
        period_start=date(2026, 5, 25),
        period_end=date(2026, 5, 31),
        active_leads=527,
        active_amount=276_644_000,
        won_leads=0,
        won_amount=0,
        lost_leads=0,
        lost_amount=0,
        new_leads=65,
        new_companies=3,
        new_contacts=71,
    )

    text = reporter.format_weekly_report_uz(stats)

    assert "AmoCRM Haftalik Hisobot | 25.05.2026 - 31.05.2026" in text
    assert "Aktiv bitimlar davr oxirida: 527" in text
    assert "Aktiv bitimlar summasi: 276 644 000 so'm" in text
    assert "Yangi bitimlar: 65" in text
    assert "Yangi kompaniyalar: 3" in text
    assert "Yangi kontaktlar: 71" in text
    assert "jonbrandingagency.amocrm.ru/gtd/leads/list/" in text


@pytest.mark.asyncio
async def test_fetch_weekly_stats_paginates_and_counts_entities(tmp_path):
    start = date(2026, 5, 25)
    end = date(2026, 5, 31)
    created_from = int(datetime(2026, 5, 25, 0, 0, 0).timestamp())
    closed_from = created_from

    active_page_1 = [{"status_id": 1, "price": 1000} for _ in range(250)]
    active_page_2 = [{"status_id": 1, "price": 2000} for _ in range(2)]
    closed_page = [
        {"status_id": 142, "price": 3000},
        {"status_id": 143, "price": 4000},
        {"status_id": 1, "price": 5000},
    ]

    pages = {
        ("leads", None, None, 1): active_page_1,
        ("leads", None, None, 2): active_page_2,
        ("leads", created_from, None, 1): [{"id": i} for i in range(65)],
        ("leads", None, closed_from, 1): closed_page,
        ("contacts", created_from, None, 1): [{"id": i} for i in range(71)],
        ("companies", created_from, None, 1): [{"id": i} for i in range(3)],
    }
    reporter = CRMDailyReporter(amocrm=FakeAmoCRM(pages), db_path=str(tmp_path / "r.db"))

    stats = await reporter.fetch_weekly_stats(start, end)

    assert stats.active_leads == 252
    assert stats.active_amount == 254000
    assert stats.new_leads == 65
    assert stats.won_leads == 1
    assert stats.won_amount == 3000
    assert stats.lost_leads == 1
    assert stats.lost_amount == 4000
    assert stats.new_contacts == 71
    assert stats.new_companies == 3
