"""Tests for Live DB & CRM data bridge."""
import pytest
from datetime import datetime, timezone

from src.services.command_center.live_db_bridge import LiveDataBridge


@pytest.mark.asyncio
async def test_live_data_bridge_fallback_when_db_empty():
    bridge = LiveDataBridge(db_connection=None)
    
    # 1. Deals
    deals = await bridge.fetch_active_deal_records()
    assert len(deals) >= 2
    assert deals[0].deal_id is not None
    assert deals[0].amount > 0

    # 2. Lead Interactions
    interactions = await bridge.fetch_recent_lead_interactions()
    assert len(interactions) >= 3
    assert any(i.channel == "telegram" for i in interactions)

    # 3. Ad attribution
    campaigns, leads = await bridge.fetch_ad_attribution_data()
    assert len(campaigns) >= 1
    assert len(leads) >= 2
    assert campaigns[0].platform in ["instagram", "facebook"]


@pytest.mark.asyncio
async def test_live_data_bridge_with_mock_cursor():
    class FakeCursor:
        async def fetchall(self):
            now_iso = datetime.now(timezone.utc).isoformat()
            return [
                ("deal_99", "Real Mijoz B2B", "prop", "Taklif", "mgr_1", "Aziz", 150_000_000.0, now_iso)
            ]

    class FakeConn:
        async def execute(self, query, params=None):
            return FakeCursor()

    bridge = LiveDataBridge(db_connection=FakeConn())
    deals = await bridge.fetch_active_deal_records()
    assert len(deals) == 1
    assert deals[0].deal_id == "deal_99"
    assert deals[0].deal_name == "Real Mijoz B2B"
    assert deals[0].amount == 150_000_000.0
