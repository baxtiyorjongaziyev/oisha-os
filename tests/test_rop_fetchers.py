# tests/test_rop_fetchers.py
from datetime import datetime, timezone
import pytest
from src.services.core.rop.fetchers import RopFetcher, RopFetchError, _tashkent_day_start_epoch
from src.services.core.crm.amocrm_pipeline_config import STATUS_WON, STATUS_LOST


class FakeResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, script):
        # script: list of (url_substr, FakeResp)
        self.script = script
        self.calls = []
    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append((url, params))
        for sub, resp in self.script:
            if sub in url and not getattr(resp, "_used", False):
                resp._used = True
                return resp
        return FakeResp(200, {"_embedded": {}})


class FakeAmo:
    base_url = "https://x.amocrm.ru"
    def _get_headers(self):
        return {}


@pytest.mark.asyncio
async def test_active_leads_filters_terminal_and_counts_requests():
    payload = {"_embedded": {"leads": [
        {"id": 1, "status_id": 111},
        {"id": 2, "status_id": STATUS_WON},
        {"id": 3, "status_id": STATUS_LOST},
    ]}}
    sess = FakeSession([("/api/v4/leads", FakeResp(200, payload))])
    f = RopFetcher(FakeAmo(), session=sess)
    leads = await f.fetch_active_sales_leads()
    assert [l["id"] for l in leads] == [1]
    assert len(sess.calls) == 1

@pytest.mark.asyncio
async def test_active_leads_first_page_failure_raises():
    sess = FakeSession([("/api/v4/leads", FakeResp(500, {}))])
    f = RopFetcher(FakeAmo(), session=sess)
    with pytest.raises(RopFetchError):
        await f.fetch_active_sales_leads()

@pytest.mark.asyncio
async def test_completed_tasks_filtered_by_user_and_grouped():
    payload = {"_embedded": {"tasks": [
        {"id": 9, "entity_id": 1, "responsible_user_id": 101, "task_type_id": 1, "is_completed": True},
        {"id": 10, "entity_id": 2, "responsible_user_id": 999, "task_type_id": 1, "is_completed": True},
    ]}}
    sess = FakeSession([("/api/v4/tasks", FakeResp(200, payload))])
    f = RopFetcher(FakeAmo(), session=sess)
    by_entity, by_user = await f.fetch_today_completed_tasks([101])
    assert 1 in by_entity and 2 not in by_entity
    assert 101 in by_user and 999 not in by_user

@pytest.mark.asyncio
async def test_non_200_returns_empty_not_raise():
    sess = FakeSession([("/api/v4/events", FakeResp(403, {}))])
    f = RopFetcher(FakeAmo(), session=sess)
    assert await f.fetch_today_events([1, 2]) == {}

@pytest.mark.asyncio
async def test_won_leads_first_page_failure_returns_empty_not_raise():
    sess = FakeSession([("/api/v4/leads", FakeResp(500, {}))])
    f = RopFetcher(FakeAmo(), session=sess)
    result = await f.fetch_won_leads_since(0)
    assert result == []


def test_tashkent_day_start_epoch():
    now = datetime(2026, 9, 10, 15, 0, tzinfo=timezone.utc)  # 20:00 Tashkent
    start = _tashkent_day_start_epoch(now)
    # 2026-09-10 00:00 Tashkent == 2026-09-09 19:00 UTC
    assert start == int(datetime(2026, 9, 9, 19, 0, tzinfo=timezone.utc).timestamp())
