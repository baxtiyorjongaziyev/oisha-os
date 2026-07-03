"""Oisha Admin Dashboard API — web mini-app backend.

Barcha endpointlar mavjud production servislar ustida ishlaydi:
- Database singleton api_server'dagi bilan bo'lishiladi (circular importdan
  qochish uchun lazy import).
- AirtableSync o'z sozlamalarini settings'dan o'zi o'qiydi.
- Telethon userbot talab qiladigan amallar bot ishlamayotgan jarayonda
  503 qaytaradi (jimgina muvaffaqiyat ko'rsatmaydi).
"""

import asyncio
import logging
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.settings import settings
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

# Bosqich nomida shu so'zlar bo'lsa loyiha yakunlangan deb hisoblanadi
_CLOSED_STAGE_MARKERS = ("yopilgan", "yakunlangan", "done", "completed", "bekor", "cancel")

_TEAM_CACHE_TTL_SECONDS = 300
_team_cache: Dict[str, Any] = {"at": 0.0, "value": None}


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
    manager: Optional[str] = None
    stage: Optional[str] = None
    project_url: Optional[str] = None
    notes: Optional[str] = None


class DeadlineResponse(BaseModel):
    deadlines: List[Deadline]
    total_overdue: int
    total_at_risk: int


async def get_db_instance():
    # api_server'dagi initsializatsiya qilingan singleton'ni qayta ishlatamiz;
    # lazy import — admin.py api_server tomonidan import qilinadi (circular)
    from src.api_server import _get_db_instance

    return await _get_db_instance()


def get_airtable_instance():
    if not settings.AIRTABLE_API_KEY and not settings.AIRTABLE_OAUTH_CLIENT_ID:
        return None
    from src.services.core.airtable_sync import AirtableSync

    # Konstruktor API key / OAuth / base_id'ni settings'dan o'zi o'qiydi
    return AirtableSync()


def _get_admin_bot():
    """Shu jarayonda ishlayotgan AdminBot'ni topadi (main.py global'i)."""
    for mod_name in ("src.main", "main", "__main__"):
        mod = sys.modules.get(mod_name)
        bot = getattr(mod, "admin_bot", None) if mod else None
        if bot is not None:
            return bot
    return None


def _coerce_text(value: Any) -> Optional[str]:
    """Airtable maydonlari list/dict bo'lishi mumkin — matnga keltiradi."""
    if value in (None, ""):
        return None
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if v) or None
    return str(value)


async def _team_efficiency_cached() -> Dict[str, Any]:
    """EnterpriseReporter hisoboti — AmoCRM'ga og'ir so'rov, 5 daqiqa kesh."""
    now = time.time()
    if _team_cache["value"] is not None and now - _team_cache["at"] < _TEAM_CACHE_TTL_SECONDS:
        return _team_cache["value"]
    try:
        from src.api_server import _get_db_instance
        from src.services.core.crm.crm_service import CRMService
        from src.services.core.enterprise_reporter import EnterpriseReporter

        db = await _get_db_instance()
        reporter = EnterpriseReporter(db, CRMService())
        report_html = await reporter.get_team_efficiency_report()
        value: Dict[str, Any] = {"report_html": report_html}
    except Exception as e:
        logger.warning(f"Team efficiency report failed: {e}")
        value = {}
    _team_cache.update(at=now, value=value)
    return value


@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(db=Depends(get_db_instance)):
    """ROI, KPI va jamoa samaradorligi (real DB kalitlari bilan)."""
    today_stats: Dict[str, Any] = {}
    try:
        today_stats = await db.get_today_stats() if db else {}
    except Exception as e:
        logger.warning(f"get_today_stats failed: {e}")

    leads_found = int(today_stats.get("leads_found", 0) or 0)
    messages_synced = int(today_stats.get("messages_synced", 0) or 0)

    roi_metrics = [
        KPIMetric(
            label="Bugungi lidlar",
            value=str(leads_found),
            unit="ta",
            status="success" if leads_found else "warning",
        ),
        KPIMetric(
            label="Sinxronlangan xabarlar",
            value=str(messages_synced),
            unit="ta",
            status="success" if messages_synced else "warning",
        ),
    ]

    team_efficiency = await _team_efficiency_cached()

    return DashboardStats(
        roi_metrics=roi_metrics,
        kpi_metrics=[],
        team_efficiency=team_efficiency,
        updated_at=get_local_now().isoformat(),
    )


@router.get("/deadlines", response_model=DeadlineResponse)
async def get_deadlines(airtable=Depends(get_airtable_instance)):
    """Airtable 'Loyihalar' jadvalidan deadline holati (status + link bilan)."""
    if airtable is None:
        return DeadlineResponse(deadlines=[], total_overdue=0, total_at_risk=0)

    from src.services.core.airtable_sync import AirtableSync

    try:
        # requests asosidagi sync metod — event loop'ni bloklamaslik uchun thread'da
        records = await asyncio.to_thread(airtable.get_projects)
    except Exception as e:
        logger.error(f"Airtable get_projects failed: {e}")
        return DeadlineResponse(deadlines=[], total_overdue=0, total_at_risk=0)

    today = get_local_now().date()
    deadlines: List[Deadline] = []
    url_prefix: Optional[str] = None

    for rec in records or []:
        fields = rec.get("fields", {}) or {}
        rec_id = str(rec.get("id", ""))

        # Lookup/rollup maydonlari list qaytarishi mumkin — matnga keltiramiz
        due_str = _coerce_text(AirtableSync._get_field(fields, "deadline"))
        if not due_str:
            continue
        try:
            due_date = datetime.fromisoformat(due_str[:10]).date()
        except (ValueError, TypeError):
            continue

        stage = _coerce_text(AirtableSync._get_field(fields, "stage"))
        if stage and any(m in stage.lower() for m in _CLOSED_STAGE_MARKERS):
            continue

        days = (due_date - today).days
        status = "overdue" if days < 0 else ("at_risk" if days <= 3 else "on_track")

        # Record URL: bitta probe bilan prefiksni aniqlab, qolganiga qo'llaymiz
        # (get_record_url har chaqiriqda jadvallar bo'ylab HTTP qidiradi)
        project_url = None
        if rec_id:
            if url_prefix is None:
                try:
                    first_url = await asyncio.to_thread(airtable.get_record_url, rec_id)
                    if first_url and first_url.endswith(rec_id):
                        url_prefix = first_url[: -len(rec_id)]
                    project_url = first_url
                except Exception:
                    url_prefix = ""  # qayta urinmaymiz
            elif url_prefix:
                project_url = f"{url_prefix}{rec_id}"

        deadlines.append(
            Deadline(
                id=rec_id,
                name=_coerce_text(AirtableSync._get_field(fields, "project_name")) or "Nomsiz loyiha",
                due_date=due_str,
                days_until_due=days,
                status=status,
                manager=_coerce_text(AirtableSync._get_field(fields, "manager")),
                stage=stage,
                project_url=project_url,
                notes=_coerce_text(AirtableSync._get_field(fields, "summary")),
            )
        )

    deadlines.sort(key=lambda d: d.days_until_due)
    return DeadlineResponse(
        deadlines=deadlines,
        total_overdue=sum(1 for d in deadlines if d.status == "overdue"),
        total_at_risk=sum(1 for d in deadlines if d.status == "at_risk"),
    )


@router.post("/actions/{action_type}")
async def execute_admin_action(action_type: str, payload: Optional[Dict[str, Any]] = None):
    """Admin amallari. Telethon userbot talab qilinadigan amallar bot
    ishlamayotgan jarayonda halol 503 qaytaradi."""
    try:
        if action_type == "send_briefing":
            bot = _get_admin_bot()
            if bot is None:
                raise HTTPException(
                    status_code=503,
                    detail="Admin bot bu jarayonda ishlamayapti — briefing VM'dagi asosiy bot orqali yuboriladi",
                )
            await bot.run_auto_briefing()
            return {"status": "success", "message": "Briefing owner'ga yuborildi"}

        if action_type in ("export_tez_natija_sheets", "export_tez_natija_amocrm"):
            # Eksport jonli Telethon client bilan guruhlarni skan qiladi —
            # API jarayonida client yo'q, Telegram buyrug'iga yo'naltiramiz
            raise HTTPException(
                status_code=503,
                detail=(
                    "Bu eksport jonli Telethon userbot talab qiladi. "
                    "Telegram'da /teznatija (Sheets) yoki /teznatija_amo (AmoCRM) "
                    "buyrug'ini ishlating."
                ),
            )

        raise HTTPException(status_code=400, detail=f"Noma'lum amal: {action_type}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin action '{action_type}' failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
