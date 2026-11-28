"""Unit tests for Autonomous Cockpit Engine (Proactive Sales Automation)."""
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.command_center.ad_attribution import (
    AdAttributedLead,
    AdCampaignRecord,
)
from src.services.command_center.autonomous_engine import (
    AutonomousCockpitEngine,
)
from src.services.command_center.speed_to_lead import LeadInteraction
from src.services.command_center.stuck_deals import DealStageRecord


@pytest.fixture
def mock_bridge():
    """Create a mock LiveDataBridge with sample baseline test records."""
    bridge = MagicMock()
    now = datetime(2026, 11, 7, 10, 0, tzinfo=UTC)

    # 3 leads: one responded, one waiting 18m, one waiting 45m
    bridge.fetch_recent_lead_interactions = AsyncMock(
        return_value=[
            LeadInteraction(
                lead_id="L1",
                customer_name="Alisher aka",
                channel="instagram",
                manager_id="mgr_dilshod",
                created_at=now - timedelta(minutes=5),
                first_response_at=now - timedelta(minutes=2),
            ),
            LeadInteraction(
                lead_id="L2",
                customer_name="Barno opa",
                channel="telegram",
                manager_id="mgr_nozima",
                created_at=now - timedelta(minutes=18),
                first_response_at=None,
            ),
            LeadInteraction(
                lead_id="L3",
                customer_name="Sardor",
                channel="call",
                manager_id="mgr_bobur",
                created_at=now - timedelta(minutes=45),
                first_response_at=None,
            ),
        ]
    )

    # Sample deals
    bridge.fetch_active_deal_records = AsyncMock(
        return_value=[
            DealStageRecord(
                deal_id="D1",
                deal_name="Artel Korporativ",
                stage_id="s1",
                stage_name="Muzokara",
                manager_id="mgr_bobur",
                manager_name="Bobur",
                amount=15_000_000.0,
                entered_stage_at=now - timedelta(days=5),
            )
        ]
    )

    # Sample ad campaigns: one normal, one high CPL anomaly
    bridge.fetch_ad_attribution_data = AsyncMock(
        return_value=(
            [
                AdCampaignRecord(
                    campaign_id="CAMP_OK",
                    campaign_name="Target B2B",
                    platform="instagram",
                    post_url="https://ig.me/1",
                    spend=100_000.0,
                    impressions=1000,
                    clicks=50,
                ),
                AdCampaignRecord(
                    campaign_id="CAMP_EXPENSIVE",
                    campaign_name="Target VIP",
                    platform="instagram",
                    post_url="https://ig.me/2",
                    spend=300_000.0,
                    impressions=500,
                    clicks=10,
                ),
            ],
            [
                AdAttributedLead(lead_id="L101", campaign_id="CAMP_OK", status="won", won_amount=50_000_000.0),
                AdAttributedLead(lead_id="L102", campaign_id="CAMP_EXPENSIVE", status="in_progress", won_amount=0.0),
            ],
        )
    )
    return bridge


@pytest.mark.asyncio
async def test_scan_speed_to_lead_alerts(mock_bridge):
    engine = AutonomousCockpitEngine(bridge=mock_bridge)
    now = datetime(2026, 11, 7, 10, 0, tzinfo=UTC)
    seller_map = {"mgr_nozima": "9998881", "mgr_bobur": "9998882"}

    alerts = await engine.scan_speed_to_lead_alerts(
        now=now,
        remind_min=15,
        escalate_min=30,
        seller_map=seller_map,
        escalation_chat_id="-1001234567",
    )

    # L2 is at 18 min -> sla_nudge to mgr_nozima (9998881)
    # L3 is at 45 min -> sla_nudge (to mgr_bobur) AND sla_escalation to -1001234567
    assert len(alerts) >= 2
    types = [a.alert_type for a in alerts]
    assert "sla_nudge" in types
    assert "sla_escalation" in types

    nudge_alert = next(a for a in alerts if a.alert_type == "sla_nudge" and a.metadata["lead_id"] == "L2")
    assert nudge_alert.recipient_chat_id == "9998881"
    assert "Barno opa" in nudge_alert.message_text

    esc_alert = next(a for a in alerts if a.alert_type == "sla_escalation")
    assert esc_alert.recipient_chat_id == "-1001234567"
    assert "SLA BUZILIShI" in esc_alert.message_text

    # Re-scan at the same time: should produce 0 alerts due to deduplication cache
    dup_alerts = await engine.scan_speed_to_lead_alerts(
        now=now,
        remind_min=15,
        escalate_min=30,
        seller_map=seller_map,
    )
    assert len(dup_alerts) == 0


@pytest.mark.asyncio
async def test_build_morning_executive_card(mock_bridge):
    engine = AutonomousCockpitEngine(bridge=mock_bridge)
    card_text, keyboard = await engine.build_morning_executive_card(base_url="https://oisha.example.com")

    assert keyboard is not None
    assert "Tonggi Boshqaruv va Savdo Pulsi" in card_text
    assert "Speed to Lead SLA" in card_text
    assert "Qotib qolgan bitimlar" in card_text
    assert "Reklama CPL" in card_text


@pytest.mark.asyncio
async def test_scan_ad_spend_anomalies(mock_bridge, monkeypatch):
    from src.settings import settings
    monkeypatch.setattr(settings, "OWNER_ID", "150074828")

    engine = AutonomousCockpitEngine(bridge=mock_bridge)
    # Both CAMP_OK (100k) and CAMP_EXPENSIVE (300k) have CPL > threshold 45,000
    alerts = await engine.scan_ad_spend_anomalies(cpl_alert_threshold=45_000.0)

    assert len(alerts) >= 2
    assert any("Target VIP" in a.message_text for a in alerts)
    assert any("Target B2B" in a.message_text for a in alerts)
    for a in alerts:
        assert a.alert_type == "ad_anomaly"
        assert a.recipient_chat_id == "150074828"
        assert "REKLAMA BYUDJETI XAVFI" in a.message_text


@pytest.mark.asyncio
async def test_build_evening_closing_card(mock_bridge):
    engine = AutonomousCockpitEngine(bridge=mock_bridge)
    wrapup_text = await engine.build_evening_closing_card()

    assert "Kunlik Savdo Sarhisobi (19:30)" in wrapup_text
    assert "Qayta ishlangan lidlar" in wrapup_text
    assert "Kunlik SLA foizi" in wrapup_text
    assert "Muddati oʻtgan ochiq vazifalar" in wrapup_text
    assert "trijaj navbatiga biriktirildi" not in wrapup_text


@pytest.mark.asyncio
async def test_stale_leads_and_unmapped_sellers_are_guarded(tmp_path):
    now = datetime(2026, 11, 7, 10, 0, tzinfo=UTC)
    bridge = MagicMock()
    bridge.fetch_recent_lead_interactions = AsyncMock(
        return_value=[
            LeadInteraction(
                lead_id="STALE_1",
                customer_name="Eski Mijoz",
                channel="telegram",
                manager_id="mgr_1",
                created_at=now - timedelta(days=3),
                first_response_at=None,
            ),
            LeadInteraction(
                lead_id="FRESH_1",
                customer_name="Yangi Mijoz",
                channel="telegram",
                manager_id="mgr_unmapped",
                created_at=now - timedelta(minutes=35),
                first_response_at=None,
            ),
        ]
    )

    state_file = tmp_path / "autopilot_state.json"
    engine = AutonomousCockpitEngine(bridge=bridge, state_path=state_file)
    alerts = await engine.scan_speed_to_lead_alerts(
        now=now,
        seller_map={},
        escalation_chat_id="-1001234567",
    )
    # STALE_1 ignored (> 24h), FRESH_1 does not emit invalid nudge to "mgr_unmapped", only valid escalation
    assert len(alerts) == 1
    assert alerts[0].alert_type == "sla_escalation"
    assert alerts[0].metadata["lead_id"] == "FRESH_1"

    # Restart simulation: reloaded engine must NOT re-emit the same escalation
    restarted = AutonomousCockpitEngine(bridge=bridge, state_path=state_file)
    replay_alerts = await restarted.scan_speed_to_lead_alerts(
        now=now + timedelta(minutes=2),
        seller_map={},
        escalation_chat_id="-1001234567",
    )
    assert replay_alerts == []


@pytest.mark.asyncio
async def test_ad_anomalies_skip_non_uzs_spend(mock_bridge, monkeypatch):
    from src.settings import settings
    monkeypatch.setattr(settings, "OWNER_ID", "150074828")
    mock_bridge.last_spend_currency = "USD"

    engine = AutonomousCockpitEngine(bridge=mock_bridge)
    alerts = await engine.scan_ad_spend_anomalies(cpl_alert_threshold=45_000.0)
    assert alerts == []
