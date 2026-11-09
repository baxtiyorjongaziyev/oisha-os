from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.services.reporter.reconciliation import ReconciliationService
from src.services.reporter.pivot_builder import (
    AgencyPivotBuilder,
    AgencyRecord,
    PivotQuery,
)

router = APIRouter(prefix="/api/v1/agency-dashboard", tags=["Agency Dashboard"])


class PivotRecordInput(BaseModel):
    client: str
    service_type: str
    manager: str
    designer: str
    month: str
    revenue: float
    cost: float
    status: str = "bajarildi"


class PivotRequest(BaseModel):
    row_dimension: str
    sort_by: str = "revenue"
    sort_asc: bool = False
    top_n: Optional[int] = None
    records: List[PivotRecordInput] = Field(default_factory=list)


class ReconciliationRequest(BaseModel):
    client_name: str
    period_start: str
    period_end: str
    initial_balance: float = 0.0
    entries: List[Dict[str, Any]] = Field(default_factory=list)


AGENCY_WIDGETS: List[Dict[str, Any]] = [
    {"id": "total_revenue", "label": "Jami tushum", "category": "moliya"},
    {"id": "gross_profit", "label": "Yalpi foyda", "category": "moliya"},
    {"id": "bank_balance", "label": "Bank va kassa balansi", "category": "moliya"},
    {"id": "operating_expenses", "label": "Operatsion xarajatlar", "category": "moliya"},
    {"id": "pipeline_deals", "label": "Aktiv bitimlar soni", "category": "savdo"},
    {"id": "conversion_rate", "label": "Konversiya foizi", "category": "savdo"},
    {"id": "avg_contract_value", "label": "Oʻrtacha shartnoma qiymati", "category": "savdo"},
    {"id": "sales_dynamics", "label": "Savdo oʻsish dinamikasi", "category": "savdo"},
    {"id": "receivables", "label": "Mijozlar qarzdorligi", "category": "qarz"},
    {"id": "overdue_debts", "label": "Muddati oʻtgan toʻlovlar", "category": "qarz"},
    {"id": "top_debtors", "label": "Top qarzdor mijozlar", "category": "qarz"},
    {"id": "payables", "label": "Frilanserlarga qarzimiz", "category": "qarz"},
    {"id": "active_projects", "label": "Jarayondagi brending loyihalari", "category": "loyihalar"},
    {"id": "deadline_risks", "label": "Deadline xavfi ostidagi ishlar", "category": "loyihalar"},
    {"id": "project_health", "label": "Loyihalar rentabellik holati", "category": "loyihalar"},
    {"id": "team_attendance", "label": "Jamoa bugungi davomati", "category": "jamoa"},
    {"id": "team_utilization", "label": "Dizaynerlar bandlik foizi", "category": "jamoa"},
    {"id": "pending_missions", "label": "Bajarilishi kutilayotgan AI missiyalar", "category": "jamoa"},
    {"id": "top_ltv_clients", "label": "Top mijozlar", "category": "mijozlar"},
    {"id": "cooling_clients", "label": "Soviyotgan mijozlar", "category": "mijozlar"},
]


@router.get("/widgets")
def get_widgets_metadata() -> Dict[str, Any]:
    return {"total": len(AGENCY_WIDGETS), "widgets": AGENCY_WIDGETS}


@router.get("/summary")
def get_dashboard_summary(period: str = Query("month")) -> Dict[str, Any]:
    return {
        "period": period,
        "as_of": "2026-11-01 10:00",
        "categories": {
            "moliya": {
                "total_revenue": 345000000.0,
                "gross_profit": 230000000.0,
                "bank_balance": 85000000.0,
                "operating_expenses": 115000000.0,
                "currency": "soʻm",
            },
            "savdo": {
                "pipeline_deals": 24,
                "conversion_rate": 28.5,
                "avg_contract_value": 45000000.0,
                "growth_vs_prev_period": 14.2,
            },
            "qarz": {
                "receivables": 68000000.0,
                "overdue_debts": 18000000.0,
                "debtors_count": 4,
                "payables": 12000000.0,
            },
            "loyihalar": {
                "active_projects": 12,
                "deadline_risks": 2,
                "profitable_pct": 83.3,
            },
            "jamoa": {
                "team_attendance": "18/20 hozir",
                "team_utilization": 87.5,
                "pending_missions": 6,
            },
            "mijozlar": {
                "active_count": 48,
                "cooling_count": 5,
                "top_ltv_client": "Artel Electronics",
            },
        },
    }


@router.post("/pivot")
def build_pivot_table(request: PivotRequest) -> Dict[str, Any]:
    builder = AgencyPivotBuilder()
    records = [
        AgencyRecord(
            client=r.client,
            service_type=r.service_type,
            manager=r.manager,
            designer=r.designer,
            month=r.month,
            revenue=r.revenue,
            cost=r.cost,
            status=r.status,
        )
        for r in request.records
    ]
    try:
        query = PivotQuery(
            row_dimension=request.row_dimension,
            sort_by=request.sort_by,
            sort_asc=request.sort_asc,
            top_n=request.top_n,
        )
        res = builder.build(records, query)
        return {
            "row_dimension": res.row_dimension,
            "total_count": res.total_count,
            "total_revenue": res.total_revenue,
            "total_cost": res.total_cost,
            "total_profit": res.total_profit,
            "average_margin_pct": res.average_margin_pct,
            "rows": [
                {
                    "dimension_value": r.dimension_value,
                    "count": r.count,
                    "revenue": r.revenue,
                    "cost": r.cost,
                    "profit": r.profit,
                    "margin_pct": r.margin_pct,
                }
                for r in res.rows
            ],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reconciliation")
def generate_reconciliation(request: ReconciliationRequest) -> Dict[str, Any]:
    service = ReconciliationService()
    stmt = service.generate_statement(
        client_name=request.client_name,
        period_start=request.period_start,
        period_end=request.period_end,
        initial_balance=request.initial_balance,
        entries=request.entries,
    )
    return {
        "client_name": stmt.client_name,
        "period": f"{stmt.period_start} — {stmt.period_end}",
        "initial_balance": stmt.initial_balance,
        "total_debit": stmt.total_debit,
        "total_credit": stmt.total_credit,
        "closing_balance": stmt.closing_balance,
        "status": stmt.status,
        "text_document": stmt.to_text(),
    }
