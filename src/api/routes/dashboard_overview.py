"""Dashboard overview — bitta endpointda kirim, voronka, sifat, kassa.

`/api/dashboard/overview` frontend Analitika sahifasining "Umumiy ko'rinish"
kartalarini boqadi. Har bir metrika real manbadan keladi:
  - kirim/kassa/sof foyda -> ERPDashboard (Hisobchi + Turso), FINANCE_READ talab
  - voronka qiymati/lid soni -> AmoCRM (barcha sahifalar), FINANCE_READ talab
  - suhbat sifati -> `call_analyses` jadvali (sales_quality bilan bir xil manba)

DASHBOARD_READ (Seller/Viewer) faqat sifat bo'limini ko'radi — moliya va
voronka umumiy (org-wide) raqam, shuning uchun FINANCE_READ shart. Manba
ulanmagan yoki so'rov muvaffaqiyatsiz bo'lsa `available: false` bilan
qaytadi — frontend fake raqam ko'rsatmasin.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests
from fastapi import APIRouter

from src.api.rbac import Permission, Principal, has_permission, require_permissions
from src.api.routes.state import api_state

router = APIRouter(prefix="/api/dashboard", tags=["dashboard-overview"])
logger = logging.getLogger(__name__)

_MAX_LEAD_PAGES = 20  # AmoCRM limit=250/page -> 5000 lidgacha; undan keyin to'xtatamiz


async def _fetch_all_leads(amocrm) -> tuple[list[dict], bool]:
    """Barcha faol lidlarni sahifalab olish. Returns (leads, ok)."""
    leads: list[dict] = []
    url = f"{amocrm.base_url}/api/v4/leads"
    params: list[tuple[str, object]] = [("limit", 250)]
    page = 1
    while page <= _MAX_LEAD_PAGES:
        page_params = [*params, ("page", page)]
        try:
            response = await amocrm._request_with_auth(
                requests.get, url, params=page_params, timeout=30
            )
        except Exception as exc:
            logger.warning("[dashboard-overview] amocrm page %d fetch failed: %s", page, exc)
            return leads, False

        if response.status_code == 401:
            try:
                import asyncio

                refreshed = await asyncio.to_thread(amocrm.refresh_token)
            except Exception:
                refreshed = False
            if not refreshed:
                return leads, False
            continue

        if response.status_code == 204:
            break
        if response.status_code != 200:
            return leads, False

        payload = response.json()
        page_leads = payload.get("_embedded", {}).get("leads", [])
        leads.extend(item for item in page_leads if isinstance(item, dict))
        if not payload.get("_links", {}).get("next"):
            break
        page += 1

    return leads, True


@router.get("/overview")
async def dashboard_overview(
    principal: Principal = require_permissions(Permission.DASHBOARD_READ),
):
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "finance": {"available": False},
        "pipeline": {"available": False},
        "quality": {"available": False},
    }

    can_see_finance = has_permission(principal, Permission.FINANCE_READ)

    # --- Finance: kirim, sof foyda, kassa holati (org-wide -> FINANCE_READ) ---
    if can_see_finance and api_state.db_instance is not None:
        try:
            from src.services.core.finance.erp_dashboard import ERPDashboard

            snap = await ERPDashboard(db=api_state.db_instance).get_snapshot()
            result["finance"] = {
                "available": True,
                "period": snap.period,
                "revenue": snap.total_revenue,
                "expenses": snap.total_expenses,
                "net_profit": snap.net_profit,
                "cash_flow_status": snap.cash_flow_status,  # type: ignore[attr-defined]
                "outstanding_invoices": snap.outstanding_invoices,
                "outstanding_amount": snap.outstanding_amount,
            }
        except Exception as exc:
            logger.warning("[dashboard-overview] finance snapshot failed: %s", exc)

    # --- Pipeline: AmoCRM lead/deal qiymati (org-wide -> FINANCE_READ) ---
    if can_see_finance:
        amocrm = api_state.amocrm_instance
        if amocrm is None and api_state.db_instance is not None:
            try:
                from src.api.routes.amocrm_integration import _get_amocrm_instance

                amocrm = _get_amocrm_instance()
            except Exception as exc:
                logger.debug("[dashboard-overview] amocrm lookup failed: %s", exc)

        if amocrm is not None:
            leads, ok = await _fetch_all_leads(amocrm)
            if ok:
                total_leads = len(leads)
                pipeline_value = sum(int(lead.get("price") or 0) for lead in leads)
                avg_deal = pipeline_value / total_leads if total_leads else 0
                result["pipeline"] = {
                    "available": True,
                    "leads_total": total_leads,
                    "pipeline_value": pipeline_value,
                    "avg_deal_value": round(avg_deal),
                }
            else:
                logger.warning("[dashboard-overview] amocrm leads fetch incomplete/failed")

    # --- Quality: suhbat sifati (call_analyses) ---
    if api_state.db_instance is not None:
        try:
            from src.api.routes.sales_quality import (
                _build_sales_quality_payload,
                _fetch_call_analysis_rows,
            )

            rows = await _fetch_call_analysis_rows()
            payload = _build_sales_quality_payload(rows)
            team = payload.get("team", {})
            result["quality"] = {
                "available": True,
                "calls_total": team.get("calls_total", 0),
                "quality_score": team.get("quality_score", 0),
            }
        except Exception as exc:
            logger.warning("[dashboard-overview] quality payload failed: %s", exc)

    return result
