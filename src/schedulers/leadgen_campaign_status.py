"""Campaign delivery status helpers for the daily Meta Lead Ads report."""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("LeadgenStatusReporter")


def fetch_campaign_status(client_factory: Optional[Callable[[], Any]] = None) -> Optional[Dict[str, Any]]:
    """Fetch read-only campaign delivery snapshot via MetaAdsClient.

    Returns None when META_AD_ACCOUNT_ID/token is not configured.
    """
    try:
        if client_factory is None:
            from src.services.core.marketing.meta_ads_client import MetaAdsClient
            client = MetaAdsClient()
        else:
            client = client_factory()
        getter = getattr(client, "get_campaign_statuses", None)
        if not callable(getter):
            return None
        return getter()
    except Exception as exc:
        logger.warning("[LEADGEN REPORTER] Campaign status check failed: %s", type(exc).__name__)
        return {"ok": False, "error_code": None, "error": type(exc).__name__}


def format_campaign_status_lines(
    status: Optional[Dict[str, Any]],
    *,
    no_leads: bool = False,
) -> list[str]:
    """Render concise HTML line(s) describing Meta Ads campaign activity."""
    if status is None:
        if no_leads:
            return [
                "• ℹ️ <b>Meta kampaniyalari:</b> tekshirilmadi "
                "(<code>META_AD_ACCOUNT_ID</code> sozlanmagan)"
            ]
        return []

    if not status.get("ok"):
        return [
            "• ⚠️ <b>Meta kampaniyalari:</b> API tekshirib boʻlmadi "
            "(<code>ads_read</code> / tokenni tekshiring)"
        ]

    active = int(status.get("active") or 0)
    active_lead = int(status.get("active_lead") or 0)
    paused = int(status.get("paused") or 0)
    issues = int(status.get("issues") or 0)

    if active == 0:
        details = []
        if paused:
            details.append(f"{paused} ta pauza")
        if issues:
            details.append(f"{issues} ta xato")
        suffix = f" ({', '.join(details)})" if details else ""
        return [
            f"• 🔴 <b>Meta kampaniyalari:</b> 0 ta faol — barcha kampaniyalar toʻxtatilgan{suffix}"
        ]

    if active_lead > 0:
        lead_note = f" (lid kampaniyalari: {active_lead} ta)"
    elif no_leads:
        lead_note = " — faol Lead Ads kampaniyasi yoʻq"
    else:
        lead_note = ""

    issue_note = f", ⚠️ {issues} ta xatoli" if issues else ""
    return [f"• 🟢 <b>Meta kampaniyalari:</b> {active} ta faol{lead_note}{issue_note}"]


def campaign_no_leads_footer(status: Optional[Dict[str, Any]]) -> str:
    """Choose the most accurate warning footer when 0 leads arrived in 24h."""
    if status and status.get("ok"):
        active = int(status.get("active") or 0)
        active_lead = int(status.get("active_lead") or 0)
        if active == 0:
            return (
                "⚠️ <i>Oxirgi 24 soatda Meta formalaridan lid tushmadi — "
                "Ads Managerʼda faol kampaniya yoʻq (barchasi toʻxtatilgan).</i>"
            )
        if active_lead == 0:
            return (
                "⚠️ <i>Oxirgi 24 soatda Meta formalaridan lid tushmadi — "
                "faol kampaniyalar bor, lekin Lead Ads kampaniyasi faol emas.</i>"
            )
    return (
        "⚠️ <i>Oxirgi 24 soatda Meta formalaridan lid tushmadi. "
        "Reklama kampaniyalari faolligi, byudjet va lid formasini tekshiring.</i>"
    )
