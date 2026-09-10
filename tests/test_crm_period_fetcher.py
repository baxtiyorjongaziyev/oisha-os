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
