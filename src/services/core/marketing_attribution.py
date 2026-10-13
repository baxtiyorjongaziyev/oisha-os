"""Campaign spend versus revenue of leads created in the requested cohort."""
from __future__ import annotations
from datetime import date
import os
from typing import Any, Dict
from src.services.core.marketing.ad_spend_store import aggregate_spend
from src.services.core.marketing.attribution_store import aggregate_by_campaign


def _ratio(numerator, denominator):
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return round(numerator / denominator, 2)


def _metrics(spend, leads, currency, revenue_currency):
    crm = leads or {}
    amount = spend.get("spend") if spend else None
    return {
        "spend": amount,
        "impressions": spend.get("impressions") if spend else None,
        "clicks": spend.get("clicks") if spend else None,
        "leads": crm.get("leads"),
        "deals_won": crm.get("won"),
        "deals_lost": crm.get("lost"),
        "deals_open": crm.get("open"),
        "revenue_won": crm.get("revenue_won"),
        "cost_per_lead": _ratio(amount, crm.get("leads")),
        "cost_per_sale": _ratio(amount, crm.get("won")),
        "roas": _ratio(crm.get("revenue_won"), amount) if currency and currency == revenue_currency else None,
        "spend_currency": currency,
        "revenue_currency": revenue_currency,
    }


def _total(rows, key):
    values = [row[key] for row in rows]
    return sum(values) if values and all(v is not None for v in values) else None


class MarketingAttributionService:
    def __init__(self, amocrm_sync: Any = None, db: Any = None, revenue_currency=None):
        self.amo = amocrm_sync
        self.db = db
        self.revenue_currency = revenue_currency or os.getenv("OISHA_REVENUE_CURRENCY", "").strip().upper() or None

    def get_performance_data(self, start_date: str, end_date: str) -> Dict[str, Any]:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
        if start > end:
            raise ValueError("start_date must not exceed end_date")
        spend = aggregate_spend(start_date, end_date)
        leads = aggregate_by_campaign(start_date, end_date)
        rows = []
        for cid in sorted(set(spend) | set(leads)):
            ad, crm = spend.get(cid), leads.get(cid)
            row = _metrics(ad, crm, ad.get("currency") if ad else None, self.revenue_currency)
            row.update(campaign_id=cid, campaign_name=(crm or {}).get("campaign_name")
                       or (ad or {}).get("campaign_name") or cid,
                       spend_synced_at=(ad or {}).get("synced_at"),
                       crm_synced_at=(crm or {}).get("synced_at"))
            rows.append(row)
        rows.sort(key=lambda row: row["spend"] or 0, reverse=True)
        currencies = {row["spend_currency"] for row in rows}
        currency = next(iter(currencies)) if len(currencies) == 1 else None
        totals = {key: _total(rows, key) for key in (
            "spend", "leads", "deals_won", "deals_lost", "deals_open", "revenue_won")}
        if currency is None:
            totals["spend"] = None
        totals.update(cost_per_lead=_ratio(totals["spend"], totals["leads"]),
                      cost_per_sale=_ratio(totals["spend"], totals["deals_won"]),
                      roas=_ratio(totals["revenue_won"], totals["spend"]) if currency and currency == self.revenue_currency else None,
                      spend_currency=currency, revenue_currency=self.revenue_currency)
        return {
            "start_date": start_date, "end_date": end_date,
            "period_basis": "lead_created_cohort", "timezone": "Asia/Tashkent",
            "status": "partial" if rows else "unavailable",
            "scope": "tracked_meta_lead_ads",
            "limitations": ["Revenue belongs to leads created in this period, not sales closed in it.",
                            "Cache coverage and current source health are not verified.",
                            "ROAS requires matching Meta and configured CRM currencies; no FX conversion is applied."],
            "campaigns": rows, "totals": totals,
        }
