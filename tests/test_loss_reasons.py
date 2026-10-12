"""Rad etish sabablari: reklama vs sotuv toifasi va lead_attribution yig'indisi."""
from __future__ import annotations

from src.services.core.marketing import attribution_store, loss_reasons


def test_classify_defaults_and_env(monkeypatch):
    assert loss_reasons.classify(24237406) == "reklama"
    assert loss_reasons.classify(21860106) == "sotuv"
    assert loss_reasons.classify(None) == "noma'lum"
    assert loss_reasons.classify(0) == "noma'lum"
    monkeypatch.setenv("META_LOSS_AD_REASON_IDS", "21860106")
    assert loss_reasons.classify(21860106) == "reklama"
    assert loss_reasons.classify(24237406) == "sotuv"


def test_loss_breakdown_and_backfill(monkeypatch, tmp_path):
    monkeypatch.setattr(attribution_store, "_DB_PATH", tmp_path / "a.db")
    for i, (cid, reason) in enumerate([("c1", 24237406), ("c1", 21860102), ("c2", None)]):
        attribution_store.save_attribution(f"g{i}", 100 + i, cid, f"Camp {cid}", "", "", "2026-10-10T10:00:00")
        attribution_store.update_revenue(f"g{i}", 0, 0, "x", 143 if reason else None, reason)
    data = attribution_store.loss_breakdown("2026-10-01", "2026-10-12")
    assert data["total"] == 3
    assert data["by_category"] == {"reklama": 1, "sotuv": 1, "noma'lum": 1}
    assert data["by_campaign"]["c1"]["reklama"] == 1
    # status_id yo'q yo'qotilgan lid sabab olish uchun qayta tekshiriladi
    pending = attribution_store.pending_revenue_sync(days=10_000)
    assert [p["leadgen_id"] for p in pending] == ["g2"]
