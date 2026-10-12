"""CPL / xarajat anomaliya monitori."""
from __future__ import annotations

from src.services.core.marketing import ad_spend_store, cpl_monitor


def _row(date, spend, leads, cid="c1"):
    return {"date": date, "campaign_id": cid, "campaign_name": "Kampaniya", "spend": spend, "meta_leads": leads}


BASE = [_row(f"2026-10-0{d}", 200_000, 10) for d in range(4, 11)]  # CPL 20k


def test_cpl_spike():
    alerts = cpl_monitor.detect_anomalies("2026-10-11", BASE + [_row("2026-10-11", 200_000, 4)])
    assert [a["kind"] for a in alerts] == ["cpl_spike"]
    assert alerts[0]["cpl"] == 50_000


def test_normal_day_no_alert():
    assert cpl_monitor.detect_anomalies("2026-10-11", BASE + [_row("2026-10-11", 210_000, 10)]) == []


def test_no_leads_and_spend_stop():
    no_leads = cpl_monitor.detect_anomalies("2026-10-11", BASE + [_row("2026-10-11", 200_000, 0)])
    assert no_leads[0]["kind"] == "no_leads"
    stopped = cpl_monitor.detect_anomalies("2026-10-11", BASE)
    assert stopped[0]["kind"] == "spend_stop"


def test_small_spend_ignored():
    base = [_row(f"2026-10-0{d}", 10_000, 1) for d in range(4, 11)]
    assert cpl_monitor.detect_anomalies("2026-10-11", base + [_row("2026-10-11", 10_000, 0)]) == []


def test_check_and_alert_dedupes(monkeypatch, tmp_path):
    monkeypatch.setattr(ad_spend_store, "_DB_PATH", tmp_path / "s.db")
    ad_spend_store.upsert_daily_spend(BASE + [_row("2026-10-11", 200_000, 0)], "x")
    sent = []
    assert cpl_monitor.check_and_alert("2026-10-11", lambda t: sent.append(t) or True) == 1
    assert cpl_monitor.check_and_alert("2026-10-11", lambda t: sent.append(t) or True) == 0
    assert len(sent) == 1 and "0 lid" in sent[0]


def test_failed_send_retries_later(monkeypatch, tmp_path):
    monkeypatch.setattr(ad_spend_store, "_DB_PATH", tmp_path / "s.db")
    ad_spend_store.upsert_daily_spend(BASE + [_row("2026-10-11", 200_000, 0)], "x")
    assert cpl_monitor.check_and_alert("2026-10-11", lambda t: False) == 0
    assert cpl_monitor.check_and_alert("2026-10-11", lambda t: True) == 1
