"""Drilldown analytics engine for CAPI Console.

Provides atomic lead-level drilldown records for any clicked KPI metric,
funnel stage, creative, or loss category, matching CRM data with attribution.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional

from src.services.core.marketing import ad_name_cache, attribution_store
from src.services.core.marketing.loss_reasons import classify, reason_name

AMO_STATUS_LABELS: Dict[int, str] = {
    87609510: "Неразобранное",
    89067962: "Yangi LEads",
    88756946: "Yangi murojaat (UTC)",
    86076846: "Birlamchi aloqa",
    87609518: "Qayta aloqa",
    87609522: "Kvalifikatsiya",
    87609526: "Uchrashuv belgilandi",
    89380154: "Uchrashuvga keldi",
    88871066: "Kelishuv / Yopish",
    142: "Sotuv bo'ldi (Won)",
    143: "Rad etildi (Lost)",
}

QUALIFICATION_IDS = {87609522}
MEETING_SCHEDULED_IDS = {87609526}
QUALITY_ATTENDED_IDS = {89380154, 88871066, 142}


def _clean_ad_name(raw: str) -> str:
    text = " · ".join(part.strip() for part in str(raw or "").splitlines() if part.strip())
    if len(text) > 45 and "-" in text:
        head, tail = text.rsplit("-", 1)
        if len(tail) == 32 and all(c in "0123456789abcdef" for c in tail.lower()):
            text = head.strip()
    return text[:95] + ("…" if len(text) > 95 else "")


def _load_ad_names() -> Dict[str, str]:
    try:
        with ad_name_cache._connection() as conn:
            rows = conn.execute("SELECT ad_id, ad_name FROM ad_names").fetchall()
        return {str(r["ad_id"]): _clean_ad_name(r["ad_name"]) for r in rows if r["ad_id"] and r["ad_name"]}
    except Exception:
        return {}


def _load_attribution(days: Optional[int] = None) -> List[Dict[str, Any]]:
    try:
        with attribution_store._connection() as conn:
            if days and int(days) > 0:
                cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=int(days))).strftime("%Y-%m-%d")
                rows = conn.execute(
                    "SELECT * FROM lead_attribution WHERE date(created_at) >= date(?) ORDER BY created_at DESC",
                    (cutoff,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM lead_attribution ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _match_metric(row: Dict[str, Any], metric: str, filter_val: Optional[str]) -> bool:
    sid = int(row.get("status_id") or 0)
    won = row.get("lead_won")
    ad_id = str(row.get("ad_id") or "").strip()
    is_won = won == 1 or sid == 142
    is_lost = won == 0 or sid == 143

    if metric in ("total_leads", "meta_leads"):
        return True
    if metric == "won":
        return is_won
    if metric == "lost":
        return is_lost
    if metric == "contacted":
        return not is_lost
    if metric == "new_contact":
        return not is_won and not is_lost and sid not in (
            QUALIFICATION_IDS | MEETING_SCHEDULED_IDS | QUALITY_ATTENDED_IDS
        )
    if metric == "quality_attended":
        return sid in QUALITY_ATTENDED_IDS or is_won
    if metric == "meeting_scheduled":
        return not is_won and not is_lost and sid in MEETING_SCHEDULED_IDS
    if metric == "qualification":
        return not is_won and not is_lost and sid in QUALIFICATION_IDS
    if metric == "creative":
        target = (filter_val or "").strip()
        if target in ("unknown", "unattributed", ""):
            return not ad_id
        return ad_id == target
    if metric == "loss_category":
        if not is_lost:
            return False
        lrid = row.get("loss_reason_id")
        cat = classify(lrid) if lrid else "noma'lum"
        return cat == (filter_val or "").strip()
    if metric == "loss_reason":
        if not is_lost:
            return False
        lrid = row.get("loss_reason_id")
        rname = reason_name(lrid) if lrid else "Sabab ko'rsatilmagan"
        return rname == (filter_val or "").strip()
    return True


def get_drilldown_leads(
    metric: str,
    days: Optional[int] = None,
    filter_val: Optional[str] = None,
    limit: int = 200,
    project_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieve filtered individual lead records for modal/drawer drilldown."""
    if project_id and project_id != "default":
        from src.services.core.marketing import capi_projects
        proj = capi_projects.get_project(project_id)
        if not proj or str(proj.get("crm_pipeline_id") or "").strip() != "11162698":
            return {"metric": metric, "filter": filter_val, "count": 0, "total_value": 0.0, "leads": []}

    all_rows = _load_attribution(days=days)
    ad_names = _load_ad_names()

    matched: List[Dict[str, Any]] = []
    for r in all_rows:
        if not _match_metric(r, metric, filter_val):
            continue

        aid = str(r.get("ad_id") or "").strip()
        ad_label = ad_names.get(aid) or (f"Reklama #{aid[-6:]}" if aid else "Meta Lead Ads")
        sid = int(r.get("status_id") or 0)
        lid = r.get("lead_id")
        lrid = r.get("loss_reason_id")

        matched.append({
            "lead_id": lid,
            "leadgen_id": r.get("leadgen_id"),
            "created_at": str(r.get("created_at") or "")[:19].replace("T", " "),
            "ad_id": aid or None,
            "ad_name": ad_label,
            "campaign_name": r.get("campaign_name") or "Meta Reklama",
            "status_id": sid,
            "status_name": AMO_STATUS_LABELS.get(sid, f"Status #{sid}" if sid else "Yangi"),
            "lead_price": float(r.get("lead_price") or 0.0),
            "lead_won": r.get("lead_won"),
            "loss_reason": reason_name(lrid) if lrid else (None if sid != 143 else "Sabab ko'rsatilmagan"),
            "loss_category": classify(lrid) if lrid else None,
            "responsible_name": r.get("responsible_name") or "Menejer",
            "crm_url": f"https://jonbranding.amocrm.ru/leads/detail/{lid}" if lid else None,
        })
        if len(matched) >= limit:
            break

    total_value = sum(item["lead_price"] for item in matched)
    return {
        "metric": metric,
        "filter": filter_val,
        "count": len(matched),
        "total_value": total_value,
        "leads": matched,
    }
