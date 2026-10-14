from datetime import datetime
from zoneinfo import ZoneInfo

import src.schedulers.daily_insights_scheduler as sched
from src.services.core.crm.amocrm_pipeline_config import STATUS_LOST, STATUS_WON
from src.services.core.rop.sales_intel import (
    NO_SOURCE, build_intel, build_managers, build_sources, build_upsell,
    build_warnings, collect, lead_source, render,
)
from src.services.core.rop.targets import SellerTarget

TZ = ZoneInfo("Asia/Tashkent")
MON_10 = datetime(2026, 9, 14, 10, 0, tzinfo=TZ)
DAY = 86400
ROSTER = [SellerTarget(1, "Rayxon", None, 1, 10, 20, 2, 0, 1, 0),
          SellerTarget(2, "Aziz", None, 1, 10, 20, 2, 0, 1, 0)]


def _lead(uid, price, tag=None, idle=0, status=STATUS_WON, lid=1):
    l = {"id": lid, "name": f"L{lid}", "responsible_user_id": uid, "price": price,
         "status_id": status, "updated_at": int(MON_10.timestamp() - idle * DAY)}
    if tag:
        l["_embedded"] = {"tags": [{"name": tag}]}
    return l


def _proj(name, stage, end, remaining=0, budget=0, seller="Rayxon"):
    return {"fields": {"Loyihani nomi?": name, "Loyiha bosqichi": stage, "END sana": end,
                       "Qoldiq to'lov $": remaining, "Kelishgan narx": budget,
                       "Sotuvchi": seller}}


def test_lead_source_uses_first_tag():
    assert lead_source(_lead(1, 0, "Instagram")) == "Instagram"
    assert lead_source(_lead(1, 0)) == NO_SOURCE


def test_sources_conversion_and_order():
    won = [_lead(1, 5, "IG"), _lead(1, 20, "Sayt")]
    lost = [_lead(1, 0, "IG", status=STATUS_LOST)]
    rows = build_sources(won, lost)
    assert [r.source for r in rows] == ["Sayt", "IG"]
    assert rows[1].conversion == 50.0


def test_manager_score_weights_revenue_conversion_calls():
    won = [_lead(1, 100)]
    calls = {"rayxon": {"total": 60, "solid_calls": 10}}
    rows = build_managers(ROSTER, won, [], calls)
    assert rows[0].name == "Rayxon" and rows[0].score == 100
    assert rows[1].score == 0


def test_warnings_silent_deal_and_overdue_payment():
    active = [_lead(2, 9, idle=7, status=0), _lead(1, 9, idle=1, status=0, lid=2)]
    projects = [_proj("P1", "Dizayn", "2026-09-01", remaining=500),
                _proj("P2", "Yakunlangan", "2026-09-01", remaining=500)]
    ws = build_warnings(ROSTER, active, {}, projects, MON_10)
    kinds = sorted(w.kind for w in ws)
    assert kinds == ["deal", "payment"]
    assert any("0 qo'ng'iroq" in w.detail for w in ws)


def test_upsell_window():
    projects = [_proj("Old", "Yakunlangan", "2026-06-01", budget=10),
                _proj("Recent", "Yakunlangan", "2026-09-01"),
                _proj("Active", "Dizayn", "2026-06-01")]
    assert [u.name for u in build_upsell(projects, MON_10)] == ["Old"]


def test_render_all_sections():
    si = build_intel(ROSTER, [_lead(1, 7_000_000, "IG")], [], [], {}, [], MON_10)
    text = render(si)
    for marker in ("1. Qaysi manba", "2. Menejer skori", "3. Erta", "4. Qayta"):
        assert marker in text
    assert "IG: 1 sotuv" in text


class FakeFetcher:
    async def fetch_closed_leads_since(self, status, since):
        return [_lead(1, 1, "IG")] if status == STATUS_WON else []
    async def fetch_active_sales_leads(self):
        return []
    async def fetch_calls_between(self, a, b, now):
        return {}


class FakeAirtable:
    def get_projects(self):
        return [_proj("Old", "Yakunlangan", "2026-06-01", budget=10)]


class FakeRepo:
    async def list_active_targets(self):
        return [{"responsible_user_id": 1, "seller_name": "Rayxon"}]


class FakeBot:
    def __init__(self): self.sent = []
    async def send_message(self, chat_id, text, parse_mode=None):
        self.sent.append((chat_id, text))


async def test_collect_joins_sources():
    si = await collect(FakeFetcher(), FakeAirtable(), ROSTER, MON_10)
    assert si.sources[0].source == "IG" and si.upsell[0].name == "Old"


async def test_run_sales_intel_gated(monkeypatch):
    bot = FakeBot()
    monkeypatch.setenv("ROP_CEO_CHAT_ID", "7")
    kw = dict(now_fn=lambda: MON_10, fetcher=FakeFetcher(), repo=FakeRepo(),
              airtable=FakeAirtable())
    monkeypatch.delenv("SALES_INTEL_ENABLED", raising=False)
    assert not await sched.run_sales_intel(bot, **kw)
    monkeypatch.setenv("SALES_INTEL_ENABLED", "1")
    assert await sched.run_sales_intel(bot, **kw)
    assert bot.sent[0][0] == 7 and "Sales Intel" in bot.sent[0][1]
