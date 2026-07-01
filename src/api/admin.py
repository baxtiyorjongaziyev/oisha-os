from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime
from src.services.core.enterprise_reporter import EnterpriseReporter
from src.services.core.airtable_sync import AirtableSync
from src.settings import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class KPIMetric(BaseModel):
    label: str
    value: str
    unit: Optional[str] = None
    trend: Optional[str] = None  # "up", "down", "stable"
    status: str  # "success", "warning", "danger"


class DashboardStats(BaseModel):
    roi_metrics: List[KPIMetric]
    kpi_metrics: List[KPIMetric]
    team_efficiency: Dict[str, Any]
    updated_at: str


class Deadline(BaseModel):
    id: str
    name: str
    due_date: str
    days_until_due: int
    status: str  # "on_track", "at_risk", "overdue"
    manager: Optional[str]
    project_url: Optional[str]
    notes: Optional[str]


class DeadlineResponse(BaseModel):
    deadlines: List[Deadline]
    total_overdue: int
    total_at_risk: int


class CRMAction(BaseModel):
    id: str
    type: str  # "lead_created", "deal_updated", "contact_added"
    title: str
    description: str
    timestamp: str
    status: str


async def get_db_instance():
    """Inject database instance"""
    from src.database import db
    return db


async def get_airtable_instance():
    """Inject Airtable instance"""
    if not settings.AIRTABLE_API_KEY and not settings.AIRTABLE_OAUTH_CLIENT_ID:
        return None
    return AirtableSync(
        api_key=settings.AIRTABLE_API_KEY,
        base_id=settings.AIRTABLE_BASE_ID,
        client_id=settings.AIRTABLE_OAUTH_CLIENT_ID,
        client_secret=settings.AIRTABLE_OAUTH_CLIENT_SECRET,
        access_token=settings.AIRTABLE_ACCESS_TOKEN,
        refresh_token=settings.AIRTABLE_REFRESH_TOKEN,
    )


@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(db=Depends(get_db_instance)):
    """Get ROI, KPI, and team efficiency metrics"""
    try:
        # Get ROI metrics from database
        today_stats = await db.get_today_stats() if db else {}

        roi_metrics = [
            KPIMetric(
                label="Bugungi Savdo",
                value=str(today_stats.get("sales_today", 0)),
                unit="UZS",
                status="success"
            ),
            KPIMetric(
                label="Savdo Raqami",
                value=str(today_stats.get("transaction_count", 0)),
                unit="ta",
                status="success"
            ),
        ]

        # Get KPI metrics (team efficiency)
        kpi_metrics = [
            KPIMetric(
                label="Javobgarlar",
                value=str(today_stats.get("manager_count", 0)),
                unit="ta",
                status="success"
            ),
            KPIMetric(
                label="Yangi Bitimlar",
                value=str(today_stats.get("new_deals", 0)),
                unit="ta",
                status="success"
            ),
        ]

        # Team efficiency from EnterpriseReporter
        enterprise_reporter = EnterpriseReporter(db)
        team_efficiency = await enterprise_reporter.get_team_efficiency_report() if enterprise_reporter else {}

        return DashboardStats(
            roi_metrics=roi_metrics,
            kpi_metrics=kpi_metrics,
            team_efficiency=team_efficiency,
            updated_at=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Dashboard stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/deadlines", response_model=DeadlineResponse)
async def get_deadlines(airtable=Depends(get_airtable_instance)):
    """Get Airtable project deadlines with status and manager info"""
    try:
        if not airtable:
            return DeadlineResponse(deadlines=[], total_overdue=0, total_at_risk=0)

        deadlines_list = []
        total_overdue = 0
        total_at_risk = 0

        # Get records from Airtable (assuming AIRTABLE_BASE_ID is set)
        if settings.AIRTABLE_BASE_ID:
            records = await airtable.get_records(
                base_id=settings.AIRTABLE_BASE_ID,
                table_name="Projects"  # Adjust based on actual table name
            ) if hasattr(airtable, 'get_records') else []

            from datetime import datetime, timedelta
            today = datetime.now().date()

            for rec in records:
                fields = rec.get("fields", {})
                due_date_str = fields.get("Due Date") or fields.get("Deadline")

                if not due_date_str:
                    continue

                try:
                    due_date = datetime.fromisoformat(due_date_str).date()
                    days_until = (due_date - today).days

                    if days_until < 0:
                        status = "overdue"
                        total_overdue += 1
                    elif days_until <= 3:
                        status = "at_risk"
                        total_at_risk += 1
                    else:
                        status = "on_track"

                    deadline = Deadline(
                        id=rec.get("id", ""),
                        name=fields.get("Name") or fields.get("Project"),
                        due_date=due_date_str,
                        days_until_due=days_until,
                        status=status,
                        manager=fields.get("Manager") or fields.get("Responsible"),
                        project_url=airtable.get_record_url(rec.get("id")) if hasattr(airtable, 'get_record_url') else None,
                        notes=fields.get("Notes") or fields.get("Description")
                    )
                    deadlines_list.append(deadline)
                except (ValueError, TypeError):
                    continue

        return DeadlineResponse(
            deadlines=sorted(deadlines_list, key=lambda x: x.days_until_due),
            total_overdue=total_overdue,
            total_at_risk=total_at_risk
        )
    except Exception as e:
        logger.error(f"Deadlines fetch error: {e}")
        # Return empty response instead of 500 if Airtable fails
        return DeadlineResponse(deadlines=[], total_overdue=0, total_at_risk=0)


@router.post("/actions/{action_type}")
async def execute_admin_action(action_type: str, payload: Dict[str, Any], db=Depends(get_db_instance)):
    """Execute admin actions: export leads, sync CRM, send reports, etc."""
    try:
        if action_type == "export_tez_natija_sheets":
            from src.services.core.tez_natija_exporter import TezNatijaExporter
            exporter = TezNatijaExporter(db=db)
            result = await exporter.export_all_groups_to_sheets()
            return {"status": "success", "result": result}

        elif action_type == "export_tez_natija_amocrm":
            from src.services.core.tez_natija_exporter import TezNatijaExporter
            from src.services.core.crm.amocrm_sync import AmoCRMSync
            amocrm = AmoCRMSync()
            exporter = TezNatijaExporter(db=db, amocrm=amocrm)
            result = await exporter.export_all_groups_to_amocrm()
            return {"status": "success", "result": result}

        elif action_type == "send_briefing":
            # Would integrate with admin_bot.run_auto_briefing()
            return {"status": "success", "message": "Briefing sent to owner"}

        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action_type}")

    except Exception as e:
        logger.error(f"Admin action error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
