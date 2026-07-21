"""Finance Dashboard — Moliya (Hisobchi AI) ma'lumotlari API."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from src.api.routes.state import api_state

router = APIRouter(tags=["finance-dashboard"])
logger = logging.getLogger(__name__)

@router.get("/api/finance/dashboard")
async def finance_dashboard():
    """Barcha Moliya ma'lumotlarini bitta endpointdan olish."""
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "balance": 0,
        "monthly_income": 0,
        "monthly_expense": 0,
    }

    if api_state.db_instance:
        try:
            conn = await api_state.db_instance.get_connection()
            # Hisobchi table exists or we can mock for now until GSheets logic is solid
            # If the user wants to use Google Sheets, we will pull from GSheets. For now, mock data from DB if available.
            
            # TODO: Pull real data from Google Sheets or Airtable
            result["balance"] = 18450
            result["monthly_income"] = 8200
            result["monthly_expense"] = 2150
            
        except Exception as exc:
            logger.debug("[finance-dashboard] stats query failed: %s", exc)

    return result


@router.get("/api/finance/transactions")
async def finance_transactions():
    """Oxirgi tranzaksiyalar ro'yxati."""
    transactions = []
    
    if api_state.db_instance:
        try:
            # TODO: Fetch from Google Sheets or Airtable
            transactions = [
                { "id": 1, "type": "Kirim", "amount": "+$5,000", "description": "Websayt loyihasi uchun avans", "date": "Bugun, 10:30" },
                { "id": 2, "type": "Chiqim", "amount": "-$120", "description": "Server xarajatlari", "date": "Kecha, 14:15" },
                { "id": 3, "type": "Kirim", "amount": "+$2,300", "description": "Marketing xizmati to'lovi", "date": "2 kun oldin" },
            ]
        except Exception as exc:
            logger.debug("[finance-dashboard] transactions query failed: %s", exc)

    return {"transactions": transactions, "total": len(transactions)}
