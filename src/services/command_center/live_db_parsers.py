"""Row parsing and normalization helpers for LiveDataBridge."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.services.command_center.ad_attribution import (
    AdAttributedLead,
    AdCampaignRecord,
)
from src.services.command_center.speed_to_lead import LeadInteraction
from src.services.command_center.stuck_deals import DealStageRecord


def safe_parse_dt(val: str | None, default: datetime | None) -> datetime | None:
    """Safely parse ISO timestamp string with UTC timezone awareness."""
    if not val:
        return default
    try:
        dt = datetime.fromisoformat(val)
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except (ValueError, TypeError, OverflowError):
        return default


def parse_deal_row(row: Any) -> DealStageRecord:
    """Parse tuple or dictionary row into DealStageRecord."""
    if isinstance(row, (tuple, list)):
        d_id, name, s_id, s_name, m_id, m_name, amount, entered_str = row[:8]
        dt = safe_parse_dt(str(entered_str), datetime.now(UTC))
        return DealStageRecord(
            deal_id=str(d_id),
            deal_name=str(name),
            stage_id=str(s_id),
            stage_name=str(s_name),
            manager_id=str(m_id),
            manager_name=str(m_name),
            amount=float(amount or 0.0),
            entered_stage_at=dt or datetime.now(UTC),
        )

    d_id = str(row.get("deal_id") or row.get("id") or "")
    slug = str(row.get("stage_id") or row.get("status_slug") or "open")
    entered_raw = row.get("entered_stage_at") or row.get("updated_at") or row.get("created_at")
    dt = safe_parse_dt(str(entered_raw) if entered_raw else None, datetime.now(UTC))
    return DealStageRecord(
        deal_id=d_id,
        deal_name=str(row.get("deal_name") or row.get("name") or f"Bitim #{d_id}"),
        stage_id=slug,
        stage_name=str(row.get("stage_name") or slug.replace("_", " ").title()),
        manager_id=str(row.get("manager_id") or row.get("responsible_user_id") or ""),
        manager_name=str(row.get("manager_name") or row.get("responsible_name") or "Belgilanmagan"),
        amount=float(row.get("amount") or row.get("price") or 0.0),
        entered_stage_at=dt or datetime.now(UTC),
    )


def parse_call_rows(rows: list[Any], cutoff_dt: datetime) -> list[LeadInteraction]:
    """Parse inbound call_events rows into LeadInteraction records."""
    parsed: list[LeadInteraction] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        dt = safe_parse_dt(str(row.get("created_at") or ""), None)
        if dt is None or dt < cutoff_dt:
            continue
        answered = int(row.get("answered") or 0)
        dur = int(row.get("duration_seconds") or 0)
        resp = dt if (answered == 1 or dur > 0) else None
        parsed.append(
            LeadInteraction(
                lead_id=f"call_{row.get('lead_id') or row.get('call_id') or ''}",
                customer_name=str(row.get("phone") or "Qoʻngʻiroq"),
                channel="call",
                manager_id=str(row.get("manager_name") or row.get("manager_id") or "Belgilanmagan"),
                created_at=dt,
                first_response_at=resp,
            )
        )
    return parsed


def parse_legacy_rows(rows: list[Any], cutoff_dt: datetime) -> list[LeadInteraction]:
    """Parse tuple or dict rows from crm_interactions fixtures."""
    parsed: list[LeadInteraction] = []
    for row in rows:
        if isinstance(row, (tuple, list)):
            l_id, cust_name, chan, m_id, created_str, resp_str = row[:6]
            dt = safe_parse_dt(str(created_str), None)
            if dt is None or dt < cutoff_dt:
                continue
            parsed.append(
                LeadInteraction(
                    lead_id=str(l_id),
                    customer_name=str(cust_name),
                    channel=str(chan),
                    manager_id=str(m_id),
                    created_at=dt,
                    first_response_at=safe_parse_dt(str(resp_str), None) if resp_str else None,
                )
            )
            continue
        dt = safe_parse_dt(str(row.get("created_at") or ""), None)
        if dt is None or dt < cutoff_dt:
            continue
        resp = safe_parse_dt(str(row.get("first_response_at") or ""), None)
        parsed.append(
            LeadInteraction(
                lead_id=str(row.get("lead_id") or row.get("id") or ""),
                customer_name=str(row.get("customer_name") or row.get("phone") or "Mijoz"),
                channel=str(row.get("channel") or "telegram"),
                manager_id=str(row.get("manager_id") or "Belgilanmagan"),
                created_at=dt,
                first_response_at=resp,
            )
        )
    return parsed


def parse_chat_rows(rows: list[dict[str, Any]], cutoff_dt: datetime) -> list[LeadInteraction]:
    """Parse omnichannel crm_chat_threads rows into LeadInteraction records."""
    parsed: list[LeadInteraction] = []
    for row in rows:
        in_raw = row.get("first_in_at") or row.get("created_at")
        in_dt = safe_parse_dt(str(in_raw or ""), None)
        if in_dt is None or in_dt < cutoff_dt:
            continue
        out_dt = safe_parse_dt(str(row.get("first_out_at") or ""), None)
        unread = int(row.get("unread_count") or 0)
        if out_dt and out_dt >= in_dt:
            resp: datetime | None = out_dt
        elif unread > 0:
            resp = None
        else:
            resp = in_dt
        parsed.append(
            LeadInteraction(
                lead_id=f"chat_{row.get('thread_id') or row.get('lead_id') or ''}",
                customer_name=str(row.get("contact_name") or "Mijoz"),
                channel=str(row.get("channel") or "telegram").lower(),
                manager_id=str(row.get("responsible_name") or "Belgilanmagan"),
                created_at=in_dt,
                first_response_at=resp,
            )
        )
    return parsed


def parse_campaign_row(row: Any) -> AdCampaignRecord:
    """Parse tuple or dictionary into AdCampaignRecord."""
    if isinstance(row, (tuple, list)):
        cid, name, platform, url, spend, imp, clk = row[:7]
        return AdCampaignRecord(
            str(cid), str(name), str(platform), str(url),
            float(spend or 0.0), int(imp or 0), int(clk or 0),
        )
    return AdCampaignRecord(
        campaign_id=str(row.get("campaign_id") or ""),
        campaign_name=str(row.get("campaign_name") or row.get("campaign_id") or "Reklama"),
        platform=str(row.get("platform") or "meta"),
        post_url=str(row.get("post_url") or ""),
        spend=float(row.get("spend") or 0.0),
        impressions=int(row.get("impressions") or 0),
        clicks=int(row.get("clicks") or 0),
    )


def parse_ad_lead_row(row: Any) -> AdAttributedLead:
    """Parse tuple or dictionary into AdAttributedLead."""
    if isinstance(row, (tuple, list)):
        lid, cid, status, won_amt = row[:4]
        return AdAttributedLead(str(lid), str(cid), str(status), float(won_amt or 0.0))
    if "status" in row:
        status = str(row.get("status") or "in_progress")
        won_amt = float(row.get("won_amount") or 0.0)
    else:
        lead_won = row.get("lead_won")
        status_id = row.get("status_id")
        if lead_won == 1 or status_id == 142:
            status = "won"
        elif status_id == 143:
            status = "lost"
        else:
            status = "in_progress"
        won_amt = float(row.get("lead_price") or 0.0) if status == "won" else 0.0
    return AdAttributedLead(
        lead_id=str(row.get("lead_id") or ""),
        campaign_id=str(row.get("campaign_id") or ""),
        status=status,
        won_amount=won_amt,
    )
