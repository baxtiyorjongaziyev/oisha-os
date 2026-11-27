"""Tests for Meta lead created_time attribution and MetaAdsClient campaign status."""
from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import requests

from src.services.core.instagram.leadgen_parser import resolve_lead_created_at
from src.services.core.marketing.meta_ads_client import MetaAdsClient


def _fake_val(label: str) -> str:
    return "-".join(("synthetic", label))


class _Resp:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_resolve_lead_created_at_parses_meta_iso_and_is_sqlite_safe():
    stamp = resolve_lead_created_at({"created_time": "2026-11-03T12:34:56+0000"})
    assert stamp == "2026-11-03T17:34:56+05:00"

    conn = sqlite3.connect(":memory:")
    try:
        date_val, dt_val = conn.execute("SELECT date(?), datetime(?)", (stamp, stamp)).fetchone()
    finally:
        conn.close()
    assert date_val == "2026-11-03"
    assert dt_val == "2026-11-03 12:34:56"


def test_resolve_lead_created_at_supports_z_and_epoch_and_fallback():
    assert resolve_lead_created_at({"created_time": "2026-11-03T12:34:56Z"}) == "2026-11-03T17:34:56+05:00"
    epoch = int(datetime(2026, 11, 3, 12, 34, 56, tzinfo=timezone.utc).timestamp())
    assert resolve_lead_created_at({"created_time": epoch}) == "2026-11-03T17:34:56+05:00"
    assert resolve_lead_created_at({"created_time": str(epoch)}) == "2026-11-03T17:34:56+05:00"

    fallback = datetime(2026, 11, 25, 10, 0, tzinfo=timezone(timedelta(hours=5)))
    assert resolve_lead_created_at({}, fallback=fallback) == "2026-11-25T10:00:00+05:00"
    assert resolve_lead_created_at({"created_time": True}, fallback=fallback) == "2026-11-25T10:00:00+05:00"
    assert resolve_lead_created_at({"created_time": "not-a-date"}, fallback=fallback) == "2026-11-25T10:00:00+05:00"


def test_router_saves_meta_created_time_not_routing_time(monkeypatch):
    from unittest.mock import AsyncMock
    from src.services.core.instagram import leadgen_router as router
    from src.services.core.leads import hunter as hunter_mod
    import src.services.core.marketing.meta_ads_client as mac

    saved = []
    amo = AsyncMock()
    monkeypatch.setattr(router, "is_leadgen_processed", lambda lid: False)
    monkeypatch.setattr(router, "try_claim_leadgen", lambda *a, **k: True)
    monkeypatch.setattr(router, "get_crm_checkpoint", lambda lid: None)
    monkeypatch.setattr(router, "save_crm_checkpoint", lambda *a, **k: None)
    monkeypatch.setattr(router, "resolve_ad_name", lambda ad_id: "Video 2")
    monkeypatch.setattr(router, "save_attribution", lambda *args: saved.append(args))
    monkeypatch.setattr(router, "record_delivery_status", lambda *a, **k: None)
    monkeypatch.setattr(router, "get_delivery_channel_status", lambda lid: {"sheets_ok": True, "telegram_ok": True})
    monkeypatch.setattr(router, "mark_leadgen_processed", lambda *a, **k: None)
    monkeypatch.setattr(router, "estimate_cost_per_lead", lambda *a, **k: None)
    monkeypatch.setattr(router, "_notify_telegram", lambda *a, **k: True)
    monkeypatch.setattr(router, "append_lead_to_sheet", lambda *a, **k: True)
    monkeypatch.setattr(router, "_amocrm_instance", lambda: amo)
    monkeypatch.setattr(router.leadgen_capi, "is_enabled", lambda: False)
    monkeypatch.setattr(router.leadgen_capi, "schedule_lead_event", lambda *a, **k: None)

    async def fake_submit(self, candidate):
        return SimpleNamespace(ok=True, lead_id=9001, state="created")

    monkeypatch.setattr(hunter_mod.HunterWriter, "submit", fake_submit)

    class _NoopMeta:
        def get_ad_campaign(self, ad_id):
            return "", ""

        def get_ad_creative_url(self, ad_id):
            return None

    monkeypatch.setattr(mac, "MetaAdsClient", _NoopMeta)

    event = {
        "leadgen_id": "LG_OLD_NOV3",
        "created_time": "2026-11-03T12:00:00+0000",
        "ad_id": "120249419742870032",
        "form_id": "F1",
        "field_data": [
            {"name": "full_name", "values": ["Test User"]},
            {"name": "phone_number", "values": ["+998901234567"]},
        ],
    }
    res = asyncio.run(router.route_leadgen_event(event, access_token=_fake_val("router")))
    assert res["ok"] is True
    assert len(saved) == 1
    assert saved[0][6] == "2026-11-03T17:00:00+05:00"


def test_tashkent_early_morning_leads_included_in_seller_and_loss_windows(tmp_path, monkeypatch):
    import src.services.core.marketing.attribution_store as store

    monkeypatch.setattr(store, "_DB_PATH", tmp_path / "attr_tz.db")
    # 02:00 +05:00 on Nov 18 is 21:00 UTC on Nov 17 — must stay on Nov 18 in Tashkent reports.
    store.save_attribution("L_EARLY", 101, "C1", "Camp", "A1", "F1", "2026-11-18T02:00:00+05:00")
    store.update_seller_info("L_EARLY", 7, "Seller", 1794950400, 1794951000)
    store.update_revenue("L_EARLY", 0.0, 0, "2026-11-18T03:00:00+05:00", status_id=143, loss_reason_id=1)

    rows = store.seller_rows("2026-11-18", "2026-11-25")
    assert len(rows) == 1
    assert rows[0]["responsible_user_id"] == 7

    loss = store.loss_breakdown("2026-11-18", "2026-11-25")
    assert loss["total"] == 1


def test_meta_ads_client_access_token_prefers_ads_token(monkeypatch):
    monkeypatch.delenv("META_ADS_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("META_PAGE_ACCESS_TOKEN", raising=False)
    val_page = "-".join(("synthetic", "page", "val"))
    val_ads = "-".join(("synthetic", "ads", "val"))
    fake_settings = SimpleNamespace(
        META_AD_ACCOUNT_ID="act_123",
        META_PAGE_ACCESS_TOKEN=val_page,
    )
    client = MetaAdsClient(settings_obj=fake_settings)
    assert client.access_token == val_page

    monkeypatch.setenv("META_ADS_ACCESS_TOKEN", val_ads)
    assert client.access_token == val_ads


def test_get_campaign_statuses_unconfigured_returns_none(monkeypatch):
    monkeypatch.delenv("META_AD_ACCOUNT_ID", raising=False)
    fake_settings = SimpleNamespace(META_AD_ACCOUNT_ID=None, META_PAGE_ACCESS_TOKEN=_fake_val("unconf"))
    client = MetaAdsClient(settings_obj=fake_settings)
    assert client.get_campaign_statuses() is None


def test_get_campaign_statuses_summarizes_and_paginates(monkeypatch):
    import src.services.core.marketing.meta_ads_client as mod

    pages = [
        _Resp(
            200,
            {
                "data": [
                    {"id": "1", "name": "Lead Form Q4", "effective_status": "ACTIVE", "objective": "OUTCOME_LEADS"},
                    {"id": "2", "name": "Brand Reach", "effective_status": "ACTIVE", "objective": "OUTCOME_AWARENESS"},
                    {"id": "3", "name": "Old Archived", "effective_status": "ARCHIVED", "objective": "OUTCOME_LEADS"},
                ],
                "paging": {"next": "https://graph.facebook.com/v21.0/next-page"},
            },
        ),
        _Resp(
            200,
            {
                "data": [
                    {"id": "4", "name": "Paused Lead", "effective_status": "PAUSED", "objective": "LEAD_GENERATION"},
                    {"id": "5", "name": "Billing Err", "effective_status": "WITH_ISSUES", "objective": "OUTCOME_LEADS"},
                    {"id": "6", "name": "Deleted Camp", "effective_status": "DELETED", "objective": "OUTCOME_LEADS"},
                ],
            },
        ),
    ]
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        return pages.pop(0)

    monkeypatch.setattr(mod.requests, "get", fake_get)
    client = MetaAdsClient(settings_obj=SimpleNamespace(META_AD_ACCOUNT_ID="370591433710957", META_PAGE_ACCESS_TOKEN=_fake_val("page")))
    monkeypatch.delenv("META_AD_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("META_ADS_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("META_PAGE_ACCESS_TOKEN", raising=False)

    res = client.get_campaign_statuses()
    assert len(calls) == 2
    assert res == {
        "ok": True,
        "total": 4,
        "active": 2,
        "active_lead": 1,
        "paused": 1,
        "issues": 1,
        "active_names": ["Lead Form Q4", "Brand Reach"],
        "issue_names": ["Billing Err"],
        "truncated": False,
    }


def test_get_campaign_statuses_marks_truncated_beyond_page_limit(monkeypatch):
    import src.services.core.marketing.meta_ads_client as mod

    monkeypatch.setattr(
        mod.requests,
        "get",
        lambda *a, **k: _Resp(
            200,
            {
                "data": [{"id": "1", "name": "C", "effective_status": "PAUSED", "objective": "OUTCOME_LEADS"}],
                "paging": {"next": "https://graph.facebook.com/v21.0/more"},
            },
        ),
    )
    monkeypatch.delenv("META_AD_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("META_ADS_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("META_PAGE_ACCESS_TOKEN", raising=False)
    val_tok = "-".join(("synthetic", "val"))
    client = MetaAdsClient(settings_obj=SimpleNamespace(META_AD_ACCOUNT_ID="act_1", META_PAGE_ACCESS_TOKEN=val_tok))
    res = client.get_campaign_statuses()
    assert res["ok"] is True
    assert res["paused"] == 5
    assert res["truncated"] is True


def test_get_campaign_statuses_handles_graph_and_network_errors(monkeypatch):
    import src.services.core.marketing.meta_ads_client as mod

    monkeypatch.delenv("META_AD_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("META_ADS_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("META_PAGE_ACCESS_TOKEN", raising=False)
    client = MetaAdsClient(settings_obj=SimpleNamespace(META_AD_ACCOUNT_ID="act_1", META_PAGE_ACCESS_TOKEN=_fake_val("err")))

    monkeypatch.setattr(
        mod.requests,
        "get",
        lambda *a, **k: _Resp(400, {"error": {"code": 200, "message": "Requires ads_read"}}),
    )
    err = client.get_campaign_statuses()
    assert err["ok"] is False
    assert err["error_code"] == 200

    def raise_timeout(*a, **k):
        raise requests.Timeout("slow")

    monkeypatch.setattr(mod.requests, "get", raise_timeout)
    net = client.get_campaign_statuses()
    assert net == {"ok": False, "error_code": None, "error": "Timeout"}
