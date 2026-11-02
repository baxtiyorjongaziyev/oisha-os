"""Tests for Marketing Ad Attribution & ROI (CPL / CAC) engine."""

from src.services.command_center.ad_attribution import (
    AdCampaignRecord,
    AdAttributedLead,
    AdAttributionEngine,
)


def test_ad_attribution_empty():
    engine = AdAttributionEngine()
    summary = engine.calculate(campaigns=[], leads=[])
    assert summary.total_spend == 0.0
    assert summary.total_new_leads == 0
    assert summary.cost_per_lead == 0.0
    assert summary.total_sales == 0
    assert summary.cost_per_sale == 0.0
    assert summary.total_revenue == 0.0
    assert summary.conversion_rate_pct == 0.0


def test_ad_attribution_calculation():
    campaigns = [
        AdCampaignRecord(
            campaign_id="cmp_1",
            campaign_name="Instagram Reels Kurslar",
            platform="instagram",
            post_url="https://instagram.com/p/DB12345",
            spend=2_000_000.0,
            impressions=50_000,
            clicks=1_200,
        ),
        AdCampaignRecord(
            campaign_id="cmp_2",
            campaign_name="Facebook B2B LeadGen",
            platform="facebook",
            post_url="https://facebook.com/ads/post99",
            spend=3_000_000.0,
            impressions=30_000,
            clicks=800,
        ),
    ]

    leads = [
        # cmp_1 leads: 4 leads, 2 won (5M + 5M = 10M)
        AdAttributedLead(lead_id="L1", campaign_id="cmp_1", status="won", won_amount=5_000_000.0),
        AdAttributedLead(lead_id="L2", campaign_id="cmp_1", status="won", won_amount=5_000_000.0),
        AdAttributedLead(lead_id="L3", campaign_id="cmp_1", status="lost", won_amount=0.0),
        AdAttributedLead(lead_id="L4", campaign_id="cmp_1", status="in_progress", won_amount=0.0),
        # cmp_2 leads: 2 leads, 0 won
        AdAttributedLead(lead_id="L5", campaign_id="cmp_2", status="in_progress", won_amount=0.0),
        AdAttributedLead(lead_id="L6", campaign_id="cmp_2", status="lost", won_amount=0.0),
    ]

    engine = AdAttributionEngine()
    summary = engine.calculate(campaigns, leads)

    # Total spend: 2M + 3M = 5,000,000
    assert summary.total_spend == 5_000_000.0
    # Total new leads: 6
    assert summary.total_new_leads == 6
    # Cost per lead (CPL): 5,000,000 / 6 = 833,333.33
    assert round(summary.cost_per_lead, 1) == 833333.3
    # Total sales: 2
    assert summary.total_sales == 2
    # Cost per sale (CAC): 5,000,000 / 2 = 2,500,000.0
    assert summary.cost_per_sale == 2_500_000.0
    # Total revenue: 10,000,000.0
    assert summary.total_revenue == 10_000_000.0
    # Conversion rate: 2 / 6 = 33.3%
    assert round(summary.conversion_rate_pct, 1) == 33.3

    # Check breakdown per campaign
    cmp1_perf = summary.campaign_performances["cmp_1"]
    assert cmp1_perf.spend == 2_000_000.0
    assert cmp1_perf.new_leads == 4
    assert cmp1_perf.cost_per_lead == 500_000.0
    assert cmp1_perf.sales == 2
    assert cmp1_perf.cost_per_sale == 1_000_000.0
    assert cmp1_perf.revenue == 10_000_000.0
    assert cmp1_perf.conversion_rate_pct == 50.0
