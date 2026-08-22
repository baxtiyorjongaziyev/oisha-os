"""Dashboard overview — bitta endpointda kirim, voronka, sifat, kassa.

`/api/dashboard/overview` frontend Analitika sahifasining "Umumiy ko'rinish"
kartalarini boqadi. Har bir metrika real manbadan keladi:
  - kirim/kassa/sof foyda -> ERPDashboard (Hisobchi + Turso)
  - voronka qiymati/lid soni -> AmoCRM `get_leads()`
  - suhbat sifati -> `call_analyses` jadvali (sales_quality bilan bir xil manba)

Manba ulanmagan bo'lsa metrika `null` va `available: false` bilan qaytadi —
frontend fake raqam ko'rsatmasin.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from src.api.rbac import Permission, require_permissions
from src.api.routes.state import api_state

router = APIRouter(prefix="/api/dashboard", tags=["dashboard-overview"])
logger = logging.getLogger(__name__)


@router.get("/overview")
async def dashboard_overview(
    principal=require_permissions(Permission.DASHBOARD_READ),
):
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "finance": {"available": False},
        "pipeline": {"available": False},
        "quality": {"available": False},
    }

    # --- Finance: kirim, sof foyda, kassa holati ---
    if api_state.db_instance is not None:
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

    # --- Pipeline: AmoCRM lead/deal qiymati ---
    amocrm = api_state.amocrm_instance
    if amocrm is None and api_state.db_instance is not None:
        try:
            from src.api.routes.amocrm_integration import _get_amocrm_instance

            amocrm = _get_amocrm_instance()
        except Exception as exc:
            logger.debug("[dashboard-overview] amocrm lookup failed: %s", exc)

    if amocrm is not None:
        try:
            leads = await amocrm.get_leads()
            total_leads = len(leads)
            pipeline_value = sum(int(lead.get("price") or 0) for lead in leads)
            avg_deal = pipeline_value / total_leads if total_leads else 0
            result["pipeline"] = {
                "available": True,
                "leads_total": total_leads,
                "pipeline_value": pipeline_value,
                "avg_deal_value": round(avg_deal),
            }
        except Exception as exc:
            logger.warning("[dashboard-overview] amocrm leads fetch failed: %s", exc)

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
