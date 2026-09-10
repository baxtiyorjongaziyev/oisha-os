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


import pytest
from src.services.core.crm.daily_report.reporter import CRMPeriodReporter


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _StubAmo:
    base_url = "https://jonbrandingagency.amocrm.ru"
    access_token = "token"

    def __init__(self, per_collection):
        # per_collection: dict[str, list[dict]] keyed by amocrm collection name
        # ("leads", "contacts", "companies", "calls", "tasks")
        self._pc = per_collection

    def _get_headers(self):
        return {"Authorization": "Bearer token"}

    def get_user_name(self, uid):
        return f"U{uid}"

    async def _request_with_auth(self, request_fn, url, **kwargs):
        collection = url.rsplit("/", 1)[-1]
        return FakeResponse(200, {"_embedded": {collection: self._pc.get(collection, [])}})


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
