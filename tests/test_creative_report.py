"""Kreativlar solishtiruvi: ad kesimidagi xarajat + CRM natijasi."""
from __future__ import annotations

import datetime as dt

from src.services.core.marketing import ad_spend_store, attribution_store, creative_report


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(ad_spend_store, "_DB_PATH", tmp_path / "s.db")
    monkeypatch.setattr(attribution_store, "_DB_PATH", tmp_path / "a.db")
    monkeypatch.setenv("META_CAPI_QUALIFIED_STATUS_IDS", "87609526")
    ad_spend_store.upsert_daily_ad_spend([
        {"date": "2026-10-06", "ad_id": "A", "ad_name": "Video 1", "spend": 500_000, "meta_leads": 10},
        {"date": "2026-10-06", "ad_id": "B", "ad_name": "Video 2", "spend": 300_000, "meta_leads": 6},
    ], "x")
    for i in range(6):
        attribution_store.save_attribution(f"a{i}", i + 1, "c", "C", "A", "", "2026-10-06T10:00:00")
        attribution_store.update_revenue(f"a{i}", 0, None, "x", 87609526 if i < 2 else 87609518)
    attribution_store.update_revenue("a0", 4_000_000, 1, "x", 142)
    for i in range(5):
        attribution_store.save_attribution(f"b{i}", 100 + i, "c", "C", "B", "", "2026-10-06T10:00:00")


def test_rows_and_report(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    rows = {r["ad_id"]: r for r in creative_report.build_rows("2026-10-05", "2026-10-11")}
    a = rows["A"]
    assert (a["leads"], a["qualified"], a["won"]) == (6, 2, 1)
    assert a["cpql"] == 250_000 and a["roas"] == 8.0
    text = creative_report.format_report("2026-10-05", "2026-10-11", list(rows.values()))
    assert "Eng arzon sifatli lid: <b>Video 1</b>" in text
    assert "Sifatli lid bermayapti: <b>Video 2</b>" in text


def test_weekly_only_monday_once(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    sent = []

    def send(text):
        sent.append(text)
        return True

    assert not creative_report.send_weekly_if_due(dt.date(2026, 10, 13), send)  # Seshanba
    assert creative_report.send_weekly_if_due(dt.date(2026, 10, 12), send)
    assert not creative_report.send_weekly_if_due(dt.date(2026, 10, 12), send)
    assert len(sent) == 1


def test_weekly_pdf_builds(monkeypatch, tmp_path):
    from src.services.core.marketing import pdf_report

    _setup(monkeypatch, tmp_path)
    attribution_store.update_seller_info("a1", 7, "Rayxon", 1_791_000_000, 1_791_000_600)
    path = pdf_report.weekly_pdf(dt.date(2026, 10, 12), tmp_path / "reports")
    data = path.read_bytes()
    assert data.startswith(b"%PDF") and len(data) > 1500


def test_weekly_sends_pdf_after_text(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    sent = []
    assert creative_report.send_weekly_if_due(
        dt.date(2026, 10, 12), lambda t: sent.append("text") or True,
        lambda p: sent.append(p.endswith(".pdf")) or True,
    )
    assert sent == ["text", True]
