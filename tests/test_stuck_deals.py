"""Tests for Stuck Deals (Qolib ketgan bitimlar) radar service."""
from datetime import datetime, timezone, timedelta

from src.services.command_center.stuck_deals import (
    DealStageRecord,
    StuckDealsRadar,
)


def test_stuck_deals_empty():
    radar = StuckDealsRadar()
    summary = radar.analyze([])
    assert summary.total_stuck_deals == 0
    assert summary.oldest_deal is None
    assert summary.stage_summaries == []


def test_stuck_deals_threshold_and_oldest():
    now = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
    deals = [
        # In qualification for 2 days (threshold 3) -> NOT stuck
        DealStageRecord(
            deal_id="D1",
            deal_name="Artel Korporativ",
            stage_id="qual",
            stage_name="Kvalifikatsiya",
            manager_id="mgr_1",
            manager_name="Aziz",
            amount=50_000_000.0,
            entered_stage_at=now - timedelta(days=2),
        ),
        # In qualification for 4 days (threshold 3) -> STUCK (4 days)
        DealStageRecord(
            deal_id="D2",
            deal_name="Akfa Logistika",
            stage_id="qual",
            stage_name="Kvalifikatsiya",
            manager_id="mgr_2",
            manager_name="Dilnoza",
            amount=30_000_000.0,
            entered_stage_at=now - timedelta(days=4),
        ),
        # In proposal for 10 days (threshold 5) -> STUCK (10 days)
        DealStageRecord(
            deal_id="D3",
            deal_name="Crafers Eksport",
            stage_id="prop",
            stage_name="Taklif yuborildi",
            manager_id="mgr_1",
            manager_name="Aziz",
            amount=120_000_000.0,
            entered_stage_at=now - timedelta(days=10),
        ),
    ]

    custom_thresholds = {"qual": 3, "prop": 5}
    radar = StuckDealsRadar(reference_time=now, stage_thresholds_days=custom_thresholds)
    summary = radar.analyze(deals)

    assert summary.total_stuck_deals == 2
    assert summary.total_stuck_value == 150_000_000.0

    # Oldest deal is D3 (10 days)
    assert summary.oldest_deal is not None
    assert summary.oldest_deal.deal_id == "D3"
    assert summary.oldest_deal.deal_name == "Crafers Eksport"
    assert summary.oldest_deal.stuck_days == 10

    # Verify stage breakdown
    stages = {s.stage_id: s for s in summary.stage_summaries}
    assert "qual" in stages
    assert stages["qual"].stuck_count == 1
    assert stages["qual"].oldest_days == 4
    assert stages["qual"].stuck_amount == 30_000_000.0

    assert "prop" in stages
    assert stages["prop"].stuck_count == 1
    assert stages["prop"].oldest_days == 10
    assert stages["prop"].stuck_amount == 120_000_000.0
