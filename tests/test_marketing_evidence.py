"""Synthetic fixtures: marketing reports must expose missing evidence."""
import pytest

from src.services.core import marketing_attribution as module


def report(monkeypatch, spend, leads):
    monkeypatch.setattr(module, "aggregate_spend", lambda *_: spend)
    monkeypatch.setattr(module, "aggregate_by_campaign", lambda *_: leads)
    return module.MarketingAttributionService(revenue_currency="UZS").get_performance_data("2026-10-01", "2026-10-12")


def test_empty_sources_are_unknown(monkeypatch):
    result = report(monkeypatch, {}, {})
    assert result["totals"]["spend"] is None
    assert result["totals"]["leads"] is None
    assert result["totals"]["roas"] is None
    assert result["status"] == "unavailable"


def test_missing_spend_does_not_become_free_sales(monkeypatch):
    result = report(monkeypatch, {}, {"a": {"leads": 2, "won": 1, "revenue_won": 500}})
    assert result["campaigns"][0]["spend"] is None
    assert result["campaigns"][0]["cost_per_sale"] is None


def test_currency_unknown_blocks_roas(monkeypatch):
    result = report(monkeypatch, {"a": {"spend": 10}}, {"a": {"leads": 2, "won": 1, "revenue_won": 500}})
    assert result["totals"]["roas"] is None


def test_same_currency_calculation_and_cohort_label(monkeypatch):
    result = report(monkeypatch, {"a": {"spend": 100, "currency": "UZS"}}, {"a": {"leads": 2, "won": 1, "lost": 0, "open": 1, "revenue_won": 500}})
    assert result["totals"]["roas"] == 5
    assert result["totals"]["cost_per_lead"] == 50
    assert result["period_basis"] == "lead_created_cohort"


def test_invalid_period_rejected(monkeypatch):
    with pytest.raises(ValueError):
        module.MarketingAttributionService().get_performance_data("2026-10-12", "2026-10-01")


def test_foreign_currency_blocks_roas(monkeypatch):
    result = report(monkeypatch, {"a": {"spend": 10, "currency": "USD"}}, {"a": {"leads": 2, "won": 1, "revenue_won": 500}})
    assert result["totals"]["spend"] == 10
    assert result["totals"]["roas"] is None


def test_legacy_currency_migration_preserves_unknown(tmp_path, monkeypatch):
    import sqlite3
    from src.services.core.marketing import ad_spend_store as store
    path = tmp_path / "synthetic.db"
    monkeypatch.setattr(store, "_DB_PATH", path)
    with sqlite3.connect(path) as conn:
        conn.execute(store._CREATE_TABLE)
        conn.execute("INSERT INTO meta_ad_spend(date,campaign_id,spend) VALUES ('2026-10-01','a',10)")
    assert store.aggregate_spend("2026-10-01", "2026-10-12")["a"]["currency"] is None
    store.upsert_daily_spend([{"date": "2026-10-02", "campaign_id": "a", "spend": 20, "currency": "USD"}], "2026-10-12")
    result = store.aggregate_spend("2026-10-01", "2026-10-12")["a"]
    assert result["spend"] == 30
    assert result["currency"] is None


def test_missing_spend_and_revenue_remain_unknown(tmp_path, monkeypatch):
    from src.services.core.marketing import ad_spend_store as spend, attribution_store as crm
    monkeypatch.setattr(spend, "_DB_PATH", tmp_path / "synthetic-spend.db")
    monkeypatch.setattr(crm, "_DB_PATH", tmp_path / "synthetic-crm.db")
    spend.upsert_daily_spend([{"date": "2026-10-01", "campaign_id": "a", "currency": "UZS"}], "2026-10-12")
    crm.save_attribution("synthetic-1", 1, "a", "Synthetic", "", "", "2026-10-01")
    crm.update_revenue("synthetic-1", None, 1, "2026-10-12")
    assert spend.aggregate_spend("2026-10-01", "2026-10-12")["a"]["spend"] is None
    assert crm.aggregate_by_campaign("2026-10-01", "2026-10-12")["a"]["revenue_won"] is None


def test_api_rejects_invalid_period():
    import asyncio
    from fastapi import HTTPException
    from src.api.routes.marketing_dashboard import get_marketing_performance
    with pytest.raises(HTTPException) as error:
        asyncio.run(get_marketing_performance("invalid", "2026-10-12"))
    assert error.value.status_code == 422


def test_unknown_crm_currency_blocks_roas(monkeypatch):
    monkeypatch.delenv("OISHA_REVENUE_CURRENCY", raising=False)
    monkeypatch.setattr(module, "aggregate_spend", lambda *_: {"a": {"spend": 100, "currency": "UZS"}})
    monkeypatch.setattr(module, "aggregate_by_campaign", lambda *_: {"a": {"leads": 2, "won": 1, "revenue_won": 500}})
    result = module.MarketingAttributionService().get_performance_data("2026-10-01", "2026-10-12")
    assert result["totals"]["revenue_currency"] is None
    assert result["totals"]["roas"] is None
