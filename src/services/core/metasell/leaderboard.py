"""Manager Leaderboard ('Kim sotyapti, kim faqat gaplashyapti') & CSV exporter.

Builds real-data rankings by closed sales (`natija`) or call quality (`sifat`)
without synthetic rows, and sanitizes CSV cells against formula injection.
"""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from typing import Any, Dict, List, Sequence

from src.services.core.metasell.diagnostics import _is_converted
from src.services.core.metasell.models import _mean, _row_get
from src.services.core.sales_playbook import OUTCOME_PAYMENT, normalise_outcome

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _avatar_initials(name: str) -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        return "??"
    parts = [p for p in cleaned.split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return cleaned[:2].upper()


def _format_mm_ss(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    return f"{total // 60}:{total % 60:02d}"


def _is_closed_sale(row: Any) -> bool:
    won_flag = _row_get(row, "lead_won", None)
    if won_flag is not None:
        try:
            if int(won_flag) == 1:
                return True
        except (TypeError, ValueError):
            pass
    norm = normalise_outcome(_row_get(row, "outcome", ""))
    return norm == OUTCOME_PAYMENT


def _diagnostic_tag(
    sales_count: int,
    lead_conversion_pct: float,
    call_quality_pct: float,
    avg_duration_seconds: int,
) -> tuple[str, str]:
    if sales_count > 0 and lead_conversion_pct >= 25.0:
        return "sotyapti", "Sotyapti"
    if sales_count == 0 and (call_quality_pct >= 50.0 or avg_duration_seconds >= 180):
        return "faqat_gaplashyapti", "Faqat gaplashyapti"
    if sales_count > 0:
        return "rivojlanmoqda", "Sotuv bor (konversiya past)"
    return "past_samaradorlik", "Natija yoʻq"


def _count_leads_and_revenue(mgr_rows: Sequence[Any]) -> tuple[int, int, int, float]:
    lead_keys: set[str] = set()
    won_lead_keys: set[str] = set()
    converted_steps = 0
    revenue_by_lead: Dict[str, float] = {}
    for idx, row in enumerate(mgr_rows):
        raw_lead = _row_get(row, "lead_id", None)
        call_key = str(_row_get(row, "call_id", "") or f"row-{idx}")
        entity_key = f"lead:{raw_lead}" if raw_lead not in (None, 0, "") else f"call:{call_key}"
        lead_keys.add(entity_key)
        if _is_converted(row):
            converted_steps += 1
        if _is_closed_sale(row):
            won_lead_keys.add(entity_key)
            price = float(_row_get(row, "lead_price", 0) or 0.0)
            revenue_by_lead[entity_key] = max(revenue_by_lead.get(entity_key, 0.0), price)
    return len(lead_keys), len(won_lead_keys), converted_steps, sum(revenue_by_lead.values())


def _aggregate_single_manager(mgr_rows: Sequence[Any]) -> Dict[str, Any]:
    name = next(
        (str(_row_get(r, "manager_name", "") or "").strip() for r in mgr_rows if _row_get(r, "manager_name")),
        "Nomaʼlum menejer",
    )
    manager_id = next(
        (_row_get(r, "manager_id") for r in mgr_rows if _row_get(r, "manager_id") is not None),
        None,
    )
    qualified_leads, sales_count, converted_steps, rev_won = _count_leads_and_revenue(mgr_rows)
    lead_conv = round((sales_count / qualified_leads * 100.0) if qualified_leads else 0.0, 2)

    scored_vals = [
        float(_row_get(r, "overall_score", 0) or 0)
        for r in mgr_rows
        if float(_row_get(r, "overall_score", 0) or 0) > 0
    ]
    quality_pct = round(_mean(scored_vals), 2)

    durations = [
        float(_row_get(r, "duration_seconds", 0) or 0)
        for r in mgr_rows
        if float(_row_get(r, "duration_seconds", 0) or 0) > 0
    ]
    avg_dur = int(round(_mean(durations))) if durations else 0
    tag_key, tag_label = _diagnostic_tag(sales_count, lead_conv, quality_pct, avg_dur)

    return {
        "manager_id": manager_id,
        "manager_name": name,
        "avatar": _avatar_initials(name),
        "sales_count": sales_count,
        "qualified_leads": qualified_leads,
        "lead_conversion_pct": lead_conv,
        "call_quality_pct": quality_pct,
        "avg_duration_seconds": avg_dur,
        "avg_duration_label": _format_mm_ss(avg_dur),
        "total_calls": len(mgr_rows),
        "converted_calls": converted_steps,
        "revenue_won": round(rev_won),
        "diagnostic_tag": tag_key,
        "diagnostic_label": tag_label,
    }


def build_manager_leaderboard(
    rows: Sequence[Any],
    *,
    sort_by: str = "natija",
) -> Dict[str, Any]:
    """Build manager ranking table supporting 'natija' and 'sifat' sort modes."""
    mode = "sifat" if str(sort_by or "").strip().lower() == "sifat" else "natija"
    if not rows:
        return {
            "has_data": False,
            "sort_by": mode,
            "refresh_interval_minutes": 60,
            "last_analyzed_at": None,
            "managers": [],
        }

    grouped: Dict[str, List[Any]] = defaultdict(list)
    timestamps: List[str] = []
    for row in rows:
        mgr_name = str(_row_get(row, "manager_name", "") or "").strip()
        mgr_id = _row_get(row, "manager_id", None)
        if not mgr_name and mgr_id is None:
            continue
        key = mgr_name.lower() if mgr_name else f"id:{mgr_id}"
        grouped[key].append(row)
        ts = str(_row_get(row, "analyzed_at", "") or _row_get(row, "created_at", "") or "").strip()
        if ts:
            timestamps.append(ts)

    managers = [_aggregate_single_manager(items) for items in grouped.values()]
    if mode == "sifat":
        managers.sort(
            key=lambda m: (m["call_quality_pct"], m["avg_duration_seconds"], m["sales_count"]),
            reverse=True,
        )
    else:
        managers.sort(
            key=lambda m: (m["sales_count"], m["lead_conversion_pct"], m["revenue_won"], m["call_quality_pct"]),
            reverse=True,
        )

    return {
        "has_data": bool(managers),
        "sort_by": mode,
        "refresh_interval_minutes": 60,
        "last_analyzed_at": max(timestamps) if timestamps else None,
        "managers": managers,
    }


def _safe_csv_cell(value: Any) -> str:
    text = str(value if value is not None else "")
    if text and text[0] in _FORMULA_PREFIXES:
        return "'" + text
    return text


def export_leaderboard_csv(managers: Sequence[Dict[str, Any]]) -> str:
    """Serialize manager leaderboard to UTF-8 CSV with formula-injection protection."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(
        [
            "Menejer",
            "Sotuvlar",
            "Lid konversiyasi (%)",
            "Suhbat sifati (%)",
            "Oʻrtacha davomiylik",
            "Jami qoʻngʻiroqlar",
            "Tushum (soʻm)",
            "Holat",
        ]
    )
    for item in managers:
        writer.writerow(
            [
                _safe_csv_cell(item.get("manager_name", "")),
                int(item.get("sales_count", 0) or 0),
                f"{float(item.get('lead_conversion_pct', 0.0) or 0.0):.2f}%",
                f"{float(item.get('call_quality_pct', 0.0) or 0.0):.2f}%",
                _safe_csv_cell(item.get("avg_duration_label", "0:00")),
                int(item.get("total_calls", 0) or 0),
                int(item.get("revenue_won", 0) or 0),
                _safe_csv_cell(item.get("diagnostic_label", "")),
            ]
        )
    return buf.getvalue()
