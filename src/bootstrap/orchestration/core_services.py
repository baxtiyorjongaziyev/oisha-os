"""
Core services, credentials, and database initialization for bootstrap.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Tuple

from src.api.routes.state import api_state
from src.controllers.message_controller import MessageController
from src.database import Database
from src.settings import settings

logger = logging.getLogger("OishaBootstrap")


async def _warm_hisobchi_cache(store: Any, spreadsheet_id: str) -> None:
    """Populate Hisobchi in-memory sheet cache without blocking bot startup."""
    try:
        await asyncio.wait_for(store.init(), timeout=45.0)
        logger.info("[HISOBCHI] Google Sheets cache warmed (spreadsheet: %s)", spreadsheet_id)
    except Exception as exc:
        logger.warning("[HISOBCHI] Background cache warmup skipped/deferred: %s", exc)


async def init_core_services() -> Tuple[Dict[str, Any], Database, Any, MessageController]:
    api_keys = {
        "gemini": settings.GEMINI_API_KEY.get_secret_value(),
        "deepseek": settings.DEEPSEEK_API_KEY.get_secret_value() if settings.DEEPSEEK_API_KEY else None,
        "aws_access_key": settings.AWS_ACCESS_KEY_ID.get_secret_value() if settings.AWS_ACCESS_KEY_ID else None,
        "aws_secret_key": settings.AWS_SECRET_ACCESS_KEY.get_secret_value() if settings.AWS_SECRET_ACCESS_KEY else None,
        "aws_region": settings.AWS_REGION,
        "bedrock_model_id": settings.BEDROCK_MODEL_ID,
    }
    db = Database()
    await db.init_instance()
    api_state.db_instance = db
    from src.context import app_ctx
    app_ctx.db_instance = db
    app_ctx.db = db
    from src.services.core.finance.hisobchi_schema import init_hisobchi_tables

    hisobchi_gs_id = getattr(settings, "HISOBCHI_GSHEET_ID", None)
    hisobchi_gs_creds = getattr(settings, "HISOBCHI_GSHEET_CREDS_FILE", None) or getattr(settings, "GSHEET_CREDS_FILE", "service_account.json")
    if hisobchi_gs_id:
        from src.services.core.hisobchi_gsheets import HisobchiGsheetStore

        hisobchi_gs_store = await asyncio.to_thread(
            HisobchiGsheetStore, hisobchi_gs_id, hisobchi_gs_creds
        )
        from src.services.core.finance.finance_source import GoogleSheetsFinanceSource

        api_state.finance_source = GoogleSheetsFinanceSource(
            hisobchi_gs_store,
            tracking_start_date=settings.HISOBCHI_TRACKING_START_DATE,
        )
        asyncio.create_task(
            _warm_hisobchi_cache(hisobchi_gs_store, str(hisobchi_gs_id)),
            name="hisobchi_gs_cache_warmup",
        )
        logger.info("[HISOBCHI] Google Sheets backend is ready (spreadsheet: %s)", hisobchi_gs_id)
    else:
        hisobchi_gs_store = None
        from src.services.core.finance.finance_source import DatabaseFinanceSource
        api_state.finance_source = DatabaseFinanceSource(
            db,
            tracking_start_date=settings.HISOBCHI_TRACKING_START_DATE,
        )
        await init_hisobchi_tables(db)
        logger.info("[HISOBCHI] Database schema is ready & DatabaseFinanceSource is active.")
    
    msg_controller = MessageController(api_keys=api_keys, db=db)
    return api_keys, db, hisobchi_gs_store, msg_controller
