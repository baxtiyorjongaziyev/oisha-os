"""Tests for Speed to Lead (SLA) metrics calculation."""
from datetime import datetime, timezone, timedelta

from src.services.command_center.speed_to_lead import (
    LeadInteraction,
    SpeedToLeadCalculator,
)


def test_speed_to_lead_empty():
    calc = SpeedToLeadCalculator()
    metrics = calc.calculate([])
    assert metrics.total_leads == 0
    assert metrics.sla_rate_pct == 0.0
    assert metrics.avg_response_minutes == 0.0
    assert metrics.longest_wait is None


def test_speed_to_lead_bucketing_and_sla():
    now = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)
    interactions = [
        # 10 min response -> <15m
        LeadInteraction(
            lead_id="L1",
            customer_name="Alisher",
            channel="telegram",
            manager_id="mgr_1",
            created_at=now - timedelta(minutes=60),
            first_response_at=now - timedelta(minutes=50),
        ),
        # 25 min response -> 15-30m
        LeadInteraction(
            lead_id="L2",
            customer_name="Malika",
            channel="instagram",
            manager_id="mgr_1",
            created_at=now - timedelta(minutes=50),
            first_response_at=now - timedelta(minutes=25),
        ),
        # 45 min response -> 30-60m
        LeadInteraction(
            lead_id="L3",
            customer_name="Jasur",
            channel="telegram",
            manager_id="mgr_2",
            created_at=now - timedelta(minutes=80),
            first_response_at=now - timedelta(minutes=35),
        ),
        # Unanswered lead, created 90 mins ago -> unanswered
        LeadInteraction(
            lead_id="L4",
            customer_name="Zilola",
            channel="telegram",
            manager_id="mgr_2",
            created_at=now - timedelta(minutes=90),
            first_response_at=None,
        ),
    ]

    calc = SpeedToLeadCalculator(reference_time=now, target_sla_minutes=30)
    metrics = calc.calculate(interactions)

    assert metrics.total_leads == 4
    assert metrics.answered_leads == 3
    assert metrics.unanswered_leads == 1

    # SLA compliant (<= 30 min): L1 (10m) and L2 (25m) -> 2 out of 4 leads = 50.0%
    assert metrics.sla_rate_pct == 50.0

    # Buckets verification
    assert metrics.buckets["within_15m"] == 1
    assert metrics.buckets["within_30m"] == 1
    assert metrics.buckets["within_1h"] == 1
    assert metrics.buckets["within_2h"] == 0
    assert metrics.buckets["over_2h"] == 0
    assert metrics.buckets["unanswered"] == 1

    # Longest wait should be Zilola (90 minutes unanswered)
    assert metrics.longest_wait is not None
    assert metrics.longest_wait.customer_name == "Zilola"
    assert metrics.longest_wait.wait_minutes == 90.0


def test_speed_to_lead_channel_breakdown():
    now = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
    interactions = [
        LeadInteraction(
            lead_id="T1",
            customer_name="Botir",
            channel="telegram",
            manager_id="mgr_1",
            created_at=now - timedelta(minutes=10),
            first_response_at=now,
        ),
        LeadInteraction(
            lead_id="I1",
            customer_name="Dilnoza",
            channel="instagram",
            manager_id="mgr_2",
            created_at=now - timedelta(minutes=40),
            first_response_at=now,
        ),
    ]
    calc = SpeedToLeadCalculator(reference_time=now)
    metrics = calc.calculate(interactions)
    channels = metrics.channel_breakdown
    assert "telegram" in channels
    assert "instagram" in channels
    assert channels["telegram"]["count"] == 1
    assert channels["telegram"]["avg_minutes"] == 10.0
    assert channels["instagram"]["count"] == 1
    assert channels["instagram"]["avg_minutes"] == 40.0
