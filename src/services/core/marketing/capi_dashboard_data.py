"""Real-data full-funnel & CAPI attribution aggregator for CAPI Platform Dashboard."""
from __future__ import annotations

import datetime as dt
import os
from typing import Any, Dict, List, Optional

from src.services.core.marketing import ad_name_cache, ad_spend_store, attribution_store
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
    142: "Sotuv bo'ldi",
    143: "Rad etildi / Yopildi",
}

NEW_CONTACT_IDS = {87609510, 89067962, 88756946, 86076846, 87609518}
QUALIFICATION_IDS = {87609522}
MEETING_SCHEDULED_IDS = {87609526}
QUALITY_ATTENDED_IDS = {89380154, 88871066}


def _clean_ad_name(raw: str) -> str:
    text = " · ".join(part.strip() for part in str(raw or "").splitlines() if part.strip())
    # Strip trailing 32-char hex hash if auto-appended by Meta Lead Ads
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


def _load_attribution_rows(days: Optional[int] = None, project: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    if project and project.get("id") != "default":
        return []
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


def _load_spend_summary(days: Optional[int] = None, project: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    is_default = not project or project.get("id") in ("default", "")
    account_id = (project.get("ad_account_id") if project else "") or os.getenv("META_AD_ACCOUNT_ID", "").strip()
    if not account_id and is_default:
        account_id = "act_370591433710957"
    try:
        with ad_spend_store._connection() as conn:
            if days and int(days) > 0:
                cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=int(days))).strftime("%Y-%m-%d")
                row = conn.execute(
                    "SELECT COUNT(*) AS cnt, SUM(spend) AS spend, MAX(currency) AS currency "
                    "FROM meta_ad_spend WHERE date >= ?",
                    (cutoff,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) AS cnt, SUM(spend) AS spend, MAX(currency) AS currency FROM meta_ad_spend"
                ).fetchone()
            cnt = int(row["cnt"] or 0) if (row and is_default) else 0
            spend = float(row["spend"]) if (row and row["spend"] is not None and cnt > 0 and is_default) else None
            currency = str(row["currency"] or "") if (row and is_default) else ""
            return {"connected": bool(account_id and cnt > 0), "account_configured": bool(account_id),
                    "rows_count": cnt, "total_spend": spend, "currency": currency or "USD"}
    except Exception:
        return {"connected": False, "account_configured": bool(account_id),
                "rows_count": 0, "total_spend": None, "currency": None}


def _load_ad_spend_by_ad(days: Optional[int] = None, project: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
    is_default = not project or project.get("id") in ("default", "")
    if not is_default:
        return {}
    try:
        with ad_spend_store._connection() as conn:
            if days and int(days) > 0:
                cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=int(days))).strftime("%Y-%m-%d")
                rows = conn.execute(
                    "SELECT ad_id, SUM(spend) AS spend FROM meta_ad_spend_by_ad WHERE date >= ? GROUP BY ad_id",
                    (cutoff,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT ad_id, SUM(spend) AS spend FROM meta_ad_spend_by_ad GROUP BY ad_id"
                ).fetchall()
            return {
                str(r["ad_id"]).strip(): round(float(r["spend"] or 0.0), 2)
                for r in rows
                if r["ad_id"] and r["spend"] is not None
            }
    except Exception:
        return {}


def _enrich_crm_events(
    crm_events: List[Dict[str, Any]],
    all_by_leadgen: Dict[str, Dict[str, Any]],
    ad_names: Dict[str, str],
) -> tuple[int, int, int, int]:
    capi_qual_sent = capi_purch_sent = capi_lead_sent = capi_failed = 0
    for ev in crm_events:
        st = str(ev.get("status") or "")
        en = str(ev.get("event_name") or "")
        if st == "sent":
            if en == "QualifiedLead":
                capi_qual_sent += 1
            elif en == "Purchase":
                capi_purch_sent += 1
            elif en == "Lead":
                capi_lead_sent += 1
        elif st in ("failed", "rejected"):
            capi_failed += 1

        attr = all_by_leadgen.get(str(ev.get("leadgen_id") or ""))
        ev["lead_id"] = ev.get("lead_id") or ev.get("amo_lead_id") or (attr.get("lead_id") if attr else None)
        if attr:
            aid = str(attr.get("ad_id") or "").strip()
            ev["ad_id"] = aid or None
            ev["ad_name"] = ad_names.get(aid) or (f"Reklama #{aid[-6:]}" if aid else "Meta Lead Ads")
            ev["lead_price"] = float(attr["lead_price"]) if attr.get("lead_price") is not None else None
            sid = int(attr["status_id"]) if attr.get("status_id") is not None else None
            ev["amo_status_id"] = sid
            ev["amo_status_name"] = AMO_STATUS_LABELS.get(sid or 0, f"Status #{sid}" if sid else "Yangi")
        else:
            ev["ad_id"] = None
            ev["ad_name"] = "Meta Lead Ads"
            ev["lead_price"] = None
            ev["amo_status_id"] = None
            ev["amo_status_name"] = "amoCRM"
    return capi_qual_sent, capi_purch_sent, capi_lead_sent, capi_failed


def _build_funnel_stages(
    total_leads: int, new_contact_cnt: int, qual_cnt: int, qual_val: float,
    meet_sched_cnt: int, meet_sched_val: float, quality_total: int, closing_val: float,
    won_cnt: int, won_revenue: float, lost_cnt: int, loss_cat: Dict[str, int],
) -> List[Dict[str, Any]]:
    pct = lambda n: round((n * 100.0 / total_leads), 1) if total_leads > 0 else 0.0
    return [
        {"key": "meta_leads", "step": "1. Meta Reklama Jami Lidlari", "count": total_leads,
         "pct": 100.0 if total_leads else 0.0, "amount_uzs": None, "capi_event": "Lead",
         "stage_hint": "Instagram / Facebook Lead Ads formasi"},
        {"key": "new_contact", "step": "2. Yangi LEads & Qayta Aloqa", "count": new_contact_cnt,
         "pct": pct(new_contact_cnt), "amount_uzs": 0.0, "capi_event": None,
         "stage_hint": "amoCRM #89067962 / #88756946 / #87609518"},
        {"key": "qualification", "step": "3. Kvalifikatsiya", "count": qual_cnt,
         "pct": pct(qual_cnt), "amount_uzs": qual_val, "capi_event": None,
         "stage_hint": "amoCRM #87609522 (Ehtiyoj va byudjet aniqlanmoqda)"},
        {"key": "meeting_scheduled", "step": "4. Uchrashuv Belgilandi", "count": meet_sched_cnt,
         "pct": pct(meet_sched_cnt), "amount_uzs": meet_sched_val, "capi_event": "Kutish (Hali kelmagan)",
         "stage_hint": "amoCRM #87609526 (Belgilangan, CAPI yuborilmaydi)"},
        {"key": "quality_attended", "step": "5. Uchrashuvga Keldi & Kelishuv", "count": quality_total,
         "pct": pct(quality_total), "amount_uzs": closing_val + won_revenue, "capi_event": "QualifiedLead",
         "stage_hint": "amoCRM #89380154 (Uchrashuvga keldi) & #88871066 (Kelishuv)"},
        {"key": "won", "step": "6. Sotuv Bo'ldi (Xarid)", "count": won_cnt,
         "pct": pct(won_cnt), "amount_uzs": won_revenue, "capi_event": "Purchase",
         "stage_hint": "amoCRM #142 (Shartnoma va to'lov tasdiqlandi)"},
        {"key": "lost", "step": "7. Rad Etildi / Yo'qotildi", "count": lost_cnt,
         "pct": pct(lost_cnt), "amount_uzs": 0.0, "capi_event": "Yuborilmaydi",
         "stage_hint": f"amoCRM #143 (Reklama sababli: {loss_cat['reklama']} ta, Sotuv: {loss_cat['sotuv']} ta)"},
    ]


def build_dashboard_analytics(
    crm_events: List[Dict[str, Any]],
    site_events: List[Dict[str, Any]],
    days: Optional[int] = None,
    project: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute real end-to-end funnel, creative attribution, loss analysis, and enriched CAPI events."""
    ad_names = _load_ad_names()
    attr_rows = _load_attribution_rows(days=days, project=project)
    spend_info = _load_spend_summary(days=days, project=project)
    ad_spend_map = _load_ad_spend_by_ad(days=days, project=project)

    by_leadgen = {str(r.get("leadgen_id") or ""): r for r in attr_rows if r.get("leadgen_id")}
    all_by_leadgen = by_leadgen if not days else {str(r.get("leadgen_id") or ""): r for r in _load_attribution_rows(None)}

    total_leads = len(attr_rows)
    new_contact_cnt = qual_cnt = meet_sched_cnt = meet_attend_cnt = closing_cnt = won_cnt = lost_cnt = 0
    qual_val = meet_sched_val = closing_val = won_revenue = active_pipeline_val = 0.0
    won_deals: List[Dict[str, Any]] = []
    creative_map: Dict[str, Dict[str, Any]] = {}
    loss_cat: Dict[str, int] = {"reklama": 0, "sotuv": 0, "noma'lum": 0}
    loss_reasons_map: Dict[str, Dict[str, Any]] = {}

    for r in attr_rows:
        sid = int(r["status_id"]) if r.get("status_id") is not None else 0
        won = r.get("lead_won")
        price = float(r["lead_price"] or 0.0)
        ad_id = str(r.get("ad_id") or "").strip()
        ad_label = ad_names.get(ad_id) or (f"Reklama #{ad_id[-6:]}" if ad_id else "Sayt / Organik / Eski")

        c_key = ad_id or "unattributed"
        c_bucket = creative_map.setdefault(c_key, {
            "ad_id": ad_id or None, "ad_name": ad_label, "total_leads": 0, "qualification": 0,
            "meeting_scheduled": 0, "quality_attended": 0, "won": 0, "lost": 0, "marketing_lost": 0,
            "active": 0, "spend_usd": ad_spend_map.get(ad_id), "revenue_won": 0.0, "pipeline_value": 0.0,
        })
        c_bucket["total_leads"] += 1

        if won == 1 or sid == 142:
            won_cnt += 1
            won_revenue += price
            c_bucket["won"] += 1
            c_bucket["quality_attended"] += 1
            c_bucket["revenue_won"] += price
            won_deals.append({"lead_id": r.get("lead_id"), "leadgen_id": r.get("leadgen_id"),
                              "ad_id": ad_id or None, "ad_name": ad_label, "price": price, "created_at": r.get("created_at")})
        elif won == 0 or sid == 143:
            lost_cnt += 1
            c_bucket["lost"] += 1
            lrid = r.get("loss_reason_id")
            cat = classify(lrid)
            if cat == "reklama":
                c_bucket["marketing_lost"] += 1
            rname = reason_name(lrid) if lrid else "Sabab ko'rsatilmagan"
            loss_cat[cat] = loss_cat.get(cat, 0) + 1
            loss_reasons_map.setdefault(rname, {"name": rname, "category": cat, "count": 0})["count"] += 1
        else:
            c_bucket["active"] += 1
            active_pipeline_val += price
            c_bucket["pipeline_value"] += price
            if sid in QUALIFICATION_IDS:
                qual_cnt += 1; qual_val += price; c_bucket["qualification"] += 1
            elif sid in MEETING_SCHEDULED_IDS:
                meet_sched_cnt += 1; meet_sched_val += price; c_bucket["meeting_scheduled"] += 1
            elif sid == 89380154:
                meet_attend_cnt += 1; closing_val += price; c_bucket["quality_attended"] += 1
            elif sid == 88871066:
                closing_cnt += 1; closing_val += price; c_bucket["quality_attended"] += 1
            else:
                new_contact_cnt += 1

    capi_qual_sent, capi_purch_sent, capi_lead_sent, capi_failed = _enrich_crm_events(crm_events, all_by_leadgen, ad_names)
    quality_total = meet_attend_cnt + closing_cnt + won_cnt
    funnel_stages = _build_funnel_stages(
        total_leads, new_contact_cnt, qual_cnt, qual_val, meet_sched_cnt, meet_sched_val,
        quality_total, closing_val, won_cnt, won_revenue, lost_cnt, loss_cat,
    )
    creatives_sorted = sorted(creative_map.values(), key=lambda x: (x["won"], x["quality_attended"], x["total_leads"]), reverse=True)[:100]
    reasons_sorted = sorted(loss_reasons_map.values(), key=lambda x: x["count"], reverse=True)
    for item in reasons_sorted:
        item["pct"] = round(item["count"] * 100.0 / lost_cnt, 1) if lost_cnt else 0.0

    return {
        "cohort_days": days or "all",
        "overview": {
            "total_leads": total_leads,
            "total_meta_leads": total_leads,
            "active_in_pipeline": total_leads - won_cnt - lost_cnt,
            "active_pipeline_value": active_pipeline_val,
            "qualification_count": qual_cnt,
            "meeting_scheduled_count": meet_sched_cnt,
            "meeting_scheduled_value": meet_sched_val,
            "quality_attended_count": quality_total,
            "won_count": won_cnt,
            "revenue_won": won_revenue,
            "lost_count": lost_cnt,
            "capi_qualified_sent": capi_qual_sent,
            "capi_purchase_sent": capi_purch_sent,
            "capi_lead_sent": capi_lead_sent,
            "capi_failed_count": capi_failed,
            "capi_website_events": len(site_events),
            "spend_connected": bool(spend_info.get("connected")),
            "total_spend_usd": spend_info.get("total_spend"),
            "spend": spend_info,
        },
        "funnel_stages": funnel_stages,
        "creatives": creatives_sorted,
        "loss_analysis": {
            "total": lost_cnt,
            "ad_fault": loss_cat["reklama"],
            "sales_fault": loss_cat["sotuv"],
            "unknown_fault": loss_cat["noma'lum"],
            "reasons": reasons_sorted,
        },
        "won_deals": won_deals,
    }
