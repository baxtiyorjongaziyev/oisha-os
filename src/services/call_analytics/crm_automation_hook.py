"""Suhbat tahlilidan keyin CRM avtomatikasini ishga tushirish (runner uchun kirish nuqtasi).

Hech qachon exception tashlamaydi — asosiy qo'ng'iroq pipeline'ini to'xtatmasligi kerak.

Boshqaruv (agent_state):
- crm_automation:enabled  — default off: hech narsa qilinmaydi
- crm_automation:dry_run  — default on: faqat audit, AmoCRM'ga yozilmaydi
"""

import logging
from typing import Any, Dict, Optional

from src.services.call_analytics.crm_actions import CrmActionPlanner
from src.services.call_analytics.crm_automation_config import FIELD_MAP, STAGE_RULES
from src.services.call_analytics.crm_automation_store import DbCrmAutomationStore
from src.services.call_analytics.crm_executor import CrmActionExecutor, ExecutionResult
from src.services.core.salescoach_store.models import _maybe_await

logger = logging.getLogger(__name__)

DRY_RUN_KEY = "crm_automation:dry_run"
_OFF_VALUES = {"0", "false", "no", "off", "disabled"}


async def _is_dry_run(db: Any) -> bool:
    raw = await _maybe_await(db.get_state(DRY_RUN_KEY, "true"))
    return str(raw or "").strip().lower() not in _OFF_VALUES


async def run_crm_automation(
    db: Any,
    amocrm: Any,
    lead_id: int,
    analysis: Dict[str, Any],
    responsible_user_id: Optional[int] = None,
) -> Optional[ExecutionResult]:
    if db is None or amocrm is None or not lead_id:
        return None
    try:
        store = DbCrmAutomationStore(db)
        if not await store.is_enabled():
            return None
        await store.initialize()
        lead = await _maybe_await(amocrm.get_lead(int(lead_id)))
        if not lead:
            return None
        actions = CrmActionPlanner(FIELD_MAP, STAGE_RULES).plan(analysis, lead)
        if not actions:
            return None
        executor = CrmActionExecutor(
            amocrm,
            store,
            dry_run=await _is_dry_run(db),
            responsible_user_id=responsible_user_id,
        )
        result = await executor.execute(int(lead_id), actions)
        logger.info(
            "[CRM AUTO] lead=%s dry_run=%s audits=%s skipped=%s suggestions=%s",
            lead_id, executor.dry_run, result.audit_ids, result.skipped_reason, result.suggestions,
        )
        return result
    except Exception as exc:  # noqa: BLE001 — pipeline'ni himoya qilish
        logger.error("[CRM AUTO] lead %s failed: %s", lead_id, exc)
        return None
