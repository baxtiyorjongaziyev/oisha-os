"""Synthetic replay boundary; no live providers or CRM calls."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.call_analytics.quality_backfill import backfill_quality
from src.services.sales_quality.reviews import QualityReviews


@pytest.mark.asyncio
async def test_replay_bounded_deduplicated_and_does_not_fake_scores(tmp_path, monkeypatch):
    store = QualityReviews(tmp_path / "quality.sqlite3")
    row = {"call_id": "call", "lead_id": 1, "manager_id": 7, "transcript": "Synthetic transcript " * 4}
    db = SimpleNamespace(execute=AsyncMock(return_value=[row, row, {**row, "call_id": "second"}]))
    evaluate = AsyncMock(return_value={"review_ready": False, "score": None, "criteria": [], "kpi_eligible": False})
    monkeypatch.setattr("src.services.call_analytics.quality_backfill.contextual_review", evaluate)
    result = await backfill_quality(db, object(), limit=1, store=store)
    assert result["processed"] == 1
    assert result["unknown"] == 1
    assert store.get("call")["score"] is None
    assert store.get("second") is None
    result = await backfill_quality(db, object(), limit=1, store=store)
    assert result["processed"] == 1
    assert store.get("second") is not None
    assert evaluate.await_count == 2
