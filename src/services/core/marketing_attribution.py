"""Marketing attribution service.

Meta Ads spend (`meta_ad_spend`, `ad_spend_sync.py`) va AmoCRM natijasi
(`lead_attribution`, `attribution_sync.py`) ni campaign_id bo'yicha birlashtirib,
Vena AI uslubidagi "Lid narxi / Lid soni / Sotuv narxi / Sotuv soni" ko'rinishini
beradi. Ikkala manba ham background scheduler orqali (`marketing_attribution_scheduler.py`)
muntazam yangilanadi — bu servis faqat allaqachon sinxronlangan mahalliy
keshni o'qiydi (tezkor, Meta/AmoCRM'ga so'rov yubormaydi).
"""
from __future__ import annotations

from typing import Any, Dict, List

from src.services.core.marketing.ad_spend_store import aggregate_spend
from src.services.core.marketing.attribution_store import aggregate_by_campaign


def _safe_div(numerator: float, denominator: float) -> float:
    return (numerator / denominator) if denominator else 0.0


class MarketingAttributionService:
    def __init__(self, amocrm_sync: Any = None, db: Any = None):
        self.amo = amocrm_sync
        self.db = db

    def get_performance_data(self, start_date: str, end_date: str) -> Dict[str, Any]:
        spend_by_campaign = aggregate_spend(start_date, end_date)
        leads_by_campaign = aggregate_by_campaign(start_date, end_date)

        campaign_ids = set(spend_by_campaign) | set(leads_by_campaign)
        campaigns: List[Dict[str, Any]] = []
        totals = {
            "spend": 0.0,
            "leads": 0,
            "won": 0,
            "lost": 0,
            "open": 0,
            "revenue_won": 0.0,
        }

        for cid in campaign_ids:
            spend_row = spend_by_campaign.get(cid, {})
            lead_row = leads_by_campaign.get(cid, {})

            spend = float(spend_row.get("spend", 0.0))
            leads = int(lead_row.get("leads", 0))
            won = int(lead_row.get("won", 0))
            lost = int(lead_row.get("lost", 0))
            open_deals = int(lead_row.get("open", 0))
            revenue_won = float(lead_row.get("revenue_won", 0.0))

            campaign_name = lead_row.get("campaign_name") or spend_row.get("campaign_name") or cid

            campaigns.append(
                {
                    "campaign_id": cid,
                    "campaign_name": campaign_name,
                    "spend": round(spend),
                    "impressions": int(spend_row.get("impressions", 0)),
                    "clicks": int(spend_row.get("clicks", 0)),
                    "leads": leads,
                    "cost_per_lead": round(_safe_div(spend, leads)),
                    "deals_won": won,
                    "deals_lost": lost,
                    "deals_open": open_deals,
                    "revenue_won": round(revenue_won),
                    "cost_per_sale": round(_safe_div(spend, won)),
                    "roas": round(_safe_div(revenue_won, spend), 2),
                }
            )

            totals["spend"] += spend
            totals["leads"] += leads
            totals["won"] += won
            totals["lost"] += lost
            totals["open"] += open_deals
            totals["revenue_won"] += revenue_won

        campaigns.sort(key=lambda c: c["spend"], reverse=True)

        return {
            "start_date": start_date,
            "end_date": end_date,
            "campaigns": campaigns,
            "totals": {
                "spend": round(totals["spend"]),
                "leads": totals["leads"],
                "cost_per_lead": round(_safe_div(totals["spend"], totals["leads"])),
                "deals_won": totals["won"],
                "deals_lost": totals["lost"],
                "deals_open": totals["open"],
                "revenue_won": round(totals["revenue_won"]),
                "cost_per_sale": round(_safe_div(totals["spend"], totals["won"])),
                "roas": round(_safe_div(totals["revenue_won"], totals["spend"]), 2),
            },
        }
