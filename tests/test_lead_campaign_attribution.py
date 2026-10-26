import src.services.core.marketing.attribution_store as store
from src.services.core.marketing.attribution_sync import backfill_campaigns
from src.services.core.marketing.meta_ads_client import MetaAdsClient


def _seed(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "_DB_PATH", tmp_path / "attr.db")
    for lg, ad in (("L1", "A1"), ("L2", "A1"), ("L3", "A2"), ("L4", "")):
        store.save_attribution(lg, 1, "", "", ad, "F", "2026-10-26T10:00:00")
    store.save_attribution("L5", 1, "C9", "Old", "A3", "F", "2026-10-26T10:00:00")


def test_backfill_fills_by_ad_with_one_call_per_ad(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    calls = []

    def resolve(ad_id):
        calls.append(ad_id)
        return {"A1": ("C1", "Brend"), "A2": ("", "")}[ad_id]

    assert backfill_campaigns(resolve) == 2
    assert sorted(calls) == ["A1", "A2"]
    remaining = {r["leadgen_id"] for r in store.rows_missing_campaign()}
    assert remaining == {"L3"}  # A2 topilmadi — keyingi siklda qayta; L4 da ad_id yo'q
    with store._connection() as conn:
        row = conn.execute("SELECT campaign_id, campaign_name FROM lead_attribution WHERE leadgen_id='L1'").fetchone()
        old = conn.execute("SELECT campaign_id FROM lead_attribution WHERE leadgen_id='L5'").fetchone()
    assert tuple(row) == ("C1", "Brend")
    assert old[0] == "C9"


class _Resp:
    def __init__(self, status, payload):
        self.status_code, self._payload = status, payload

    def json(self):
        return self._payload


def _client(monkeypatch, resp):
    import src.services.core.marketing.meta_ads_client as mod
    monkeypatch.setattr(mod.requests, "get", lambda *a, **k: resp)
    c = MetaAdsClient.__new__(MetaAdsClient)
    c.api_version = "v19.0"
    monkeypatch.setattr(MetaAdsClient, "access_token", property(lambda self: "t"))
    return c


def test_get_ad_campaign_parses_and_fails_soft(monkeypatch):
    c = _client(monkeypatch, _Resp(200, {"campaign_id": "C1", "campaign": {"id": "C1", "name": "Brend"}}))
    assert c.get_ad_campaign("A1") == ("C1", "Brend")
    c = _client(monkeypatch, _Resp(400, {"error": {"code": 100}}))
    assert c.get_ad_campaign("A1") == ("", "")
    assert c.get_ad_campaign("") == ("", "")
