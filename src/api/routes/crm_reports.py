"""CRM davriy hisobotlar API — kunlik / haftalik / oylik.

`GET /api/crm/reports?period=daily|weekly|monthly` bitta manbadan
(`CRMPeriodReporter.build`) to'liq metrika JSON qaytaradi. Telegram matni
va dashboard raqamlari shu yerdan keladi.
"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter

from src.api.rbac import Permission, Principal, require_permissions
from src.api.routes.state import api_state
from src.services.core.crm.daily_report import CRMPeriodReporter
from src.services.core.crm.daily_report.models import PeriodType

router = APIRouter(prefix="/api/crm", tags=["crm-reports"])
logger = logging.getLogger(__name__)

_principal_dep = require_permissions(Permission.DASHBOARD_READ)


def _resolve_amocrm():
    if api_state.amocrm_instance:
        return api_state.amocrm_instance
    try:
        from src.api.routes.amocrm_integration import _get_amocrm_instance
        return _get_amocrm_instance()
    except Exception as exc:
        logger.debug("[crm-reports] amocrm lookup failed: %s", exc)
        return None


@router.get("/reports")
async def crm_reports(
    period: Literal["daily", "weekly", "monthly"] = "daily",
    principal: Principal = _principal_dep,
):
    amocrm = _resolve_amocrm()
    if amocrm is None:
        return {"available": False, "period": period}

    ptype = PeriodType(period)
    result = await CRMPeriodReporter(amocrm=amocrm).build(ptype)
    return {
        "available": result.fetch_ok,
        "period": period,
        "period_start": result.period_start.isoformat(),
        "period_end": result.period_end.isoformat(),
        "metrics": result.metrics.to_dict(),
        "previous": result.previous.to_dict() if result.previous else None,
        "deltas": result.deltas,
        "telegram_text": result.telegram_text,
    }
