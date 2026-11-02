"""Marketing Ad Attribution and ROI (CPL / CAC) Engine.

Connects advertising campaigns (Facebook / Instagram Ads) with CRM deal outcomes
to compute acquisition costs, sales conversions, and post-level performance.
"""
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class AdCampaignRecord:
    """Marketing ad campaign or creative post record."""

    campaign_id: str
    campaign_name: str
    platform: str
    post_url: str
    spend: float
    impressions: int = 0
    clicks: int = 0


@dataclass
class AdAttributedLead:
    """Lead attributed to a specific ad campaign with final CRM outcome."""

    lead_id: str
    campaign_id: str
    status: str
    won_amount: float = 0.0


@dataclass
class CampaignPerformance:
    """Performance metrics for an individual ad campaign or creative."""

    campaign_id: str
    campaign_name: str
    platform: str
    post_url: str
    spend: float
    new_leads: int
    cost_per_lead: float
    sales: int
    cost_per_sale: float
    revenue: float
    conversion_rate_pct: float
    roi_pct: float


@dataclass
class AdAttributionSummary:
    """Aggregated marketing performance across all advertising channels."""

    total_spend: float = 0.0
    total_new_leads: int = 0
    cost_per_lead: float = 0.0
    total_sales: int = 0
    cost_per_sale: float = 0.0
    total_revenue: float = 0.0
    conversion_rate_pct: float = 0.0
    overall_roi_pct: float = 0.0
    campaign_performances: Dict[str, CampaignPerformance] = field(default_factory=dict)


class AdAttributionEngine:
    """Computes spend, CPL, CAC, and sales revenue attributed to ad creatives."""

    def calculate(
        self,
        campaigns: List[AdCampaignRecord],
        leads: List[AdAttributedLead],
    ) -> AdAttributionSummary:
        """Compute complete attribution summary linking campaigns and leads."""
        if not campaigns and not leads:
            return AdAttributionSummary()

        total_spend = sum(c.spend for c in campaigns)
        total_leads_count = len(leads)
        cpl = (total_spend / total_leads_count) if total_leads_count > 0 else 0.0

        won_leads = [l for l in leads if l.status == "won"]
        total_sales_count = len(won_leads)
        cac = (total_spend / total_sales_count) if total_sales_count > 0 else 0.0
        total_revenue = sum(l.won_amount for l in won_leads)

        conv_rate = (
            (total_sales_count / total_leads_count * 100.0)
            if total_leads_count > 0
            else 0.0
        )
        overall_roi = (
            ((total_revenue - total_spend) / total_spend * 100.0)
            if total_spend > 0
            else 0.0
        )

        campaign_stats = self._build_campaign_breakdown(campaigns, leads)

        return AdAttributionSummary(
            total_spend=round(total_spend, 2),
            total_new_leads=total_leads_count,
            cost_per_lead=round(cpl, 2),
            total_sales=total_sales_count,
            cost_per_sale=round(cac, 2),
            total_revenue=round(total_revenue, 2),
            conversion_rate_pct=round(conv_rate, 2),
            overall_roi_pct=round(overall_roi, 2),
            campaign_performances=campaign_stats,
        )

    def _build_campaign_breakdown(
        self,
        campaigns: List[AdCampaignRecord],
        leads: List[AdAttributedLead],
    ) -> Dict[str, CampaignPerformance]:
        """Aggregate metrics per individual campaign and post creative."""
        leads_by_camp: Dict[str, List[AdAttributedLead]] = {}
        for lead in leads:
            if lead.campaign_id not in leads_by_camp:
                leads_by_camp[lead.campaign_id] = []
            leads_by_camp[lead.campaign_id].append(lead)

        performances: Dict[str, CampaignPerformance] = {}
        for camp in campaigns:
            camp_leads = leads_by_camp.get(camp.campaign_id, [])
            n_leads = len(camp_leads)
            c_cpl = (camp.spend / n_leads) if n_leads > 0 else 0.0

            won_c_leads = [l for l in camp_leads if l.status == "won"]
            n_sales = len(won_c_leads)
            c_cac = (camp.spend / n_sales) if n_sales > 0 else 0.0
            c_revenue = sum(l.won_amount for l in won_c_leads)

            c_conv = (n_sales / n_leads * 100.0) if n_leads > 0 else 0.0
            c_roi = (
                ((c_revenue - camp.spend) / camp.spend * 100.0)
                if camp.spend > 0
                else 0.0
            )

            performances[camp.campaign_id] = CampaignPerformance(
                campaign_id=camp.campaign_id,
                campaign_name=camp.campaign_name,
                platform=camp.platform,
                post_url=camp.post_url,
                spend=round(camp.spend, 2),
                new_leads=n_leads,
                cost_per_lead=round(c_cpl, 2),
                sales=n_sales,
                cost_per_sale=round(c_cac, 2),
                revenue=round(c_revenue, 2),
                conversion_rate_pct=round(c_conv, 2),
                roi_pct=round(c_roi, 2),
            )
        return performances

    def format_uzbek_summary(self, summary: AdAttributionSummary) -> str:
        """Format an executive marketing ROI summary in Uzbek language."""
        lines = [
            f"Reklama sarfi: {summary.total_spend:,.0f} soʻm",
            f"Yangi lidlar: {summary.total_new_leads} ta",
            f"1 lid narxi (CPL): {summary.cost_per_lead:,.0f} soʻm",
            f"Yutilgan sotuvlar: {summary.total_sales} ta",
            f"1 sotuv narxi (CAC): {summary.cost_per_sale:,.0f} soʻm",
            f"Jami tushum: {summary.total_revenue:,.0f} soʻm",
            f"Konversiya: {summary.conversion_rate_pct:.1f}%",
        ]
        return "\n".join(lines)
