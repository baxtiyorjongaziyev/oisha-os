"""
Marketing Attribution Dashboard Routes
Oisha-OS v5.0 - /api/marketing/
"""

from fastapi import APIRouter, HTTPException, Query
from src.api.rbac import Permission, require_permissions
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from src.services.core.marketing_attribution import MarketingAttributionService


router = APIRouter(
    prefix="/api/marketing",
    tags=["Marketing Analytics"],
    dependencies=[require_permissions(Permission.DASHBOARD_READ)],
)

@router.get("/performance", response_model=Dict[str, Any])
async def get_marketing_performance(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    # amocrm = Depends(get_amocrm_sync) # TODO: uncomment when fully injecting
):
    """
    Meta Ads xarajatlari va AmoCRM savdolarini birlashtirilgan ko'rinishda (ROAS, CAC bilan) qaytaradi.
    Hozircha demo datani beradi.
    """
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
        
    service = MarketingAttributionService(amocrm_sync=None) # Pass amocrm when available
    try:
        return service.get_performance_data(start_date=start_date, end_date=end_date)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
