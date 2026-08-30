"""
Facade for SalesCoachTaskWriter.
Delegates to modular subpackage in src.services.core.crm.salescoach_writer.
"""
from src.services.core.crm.salescoach_writer.models import (
    TASHKENT,
    TASK_RULES,
    TaskRule,
    TaskWriteResult,
    _analysis_value,
    _extract_id,
    _next_business_day,
    _normalized_text,
    _note_text,
    task_idempotency_key,
)
from src.services.core.crm.salescoach_writer.writer import SalesCoachTaskWriter

__all__ = [
    "TASHKENT",
    "TASK_RULES",
    "TaskRule",
    "TaskWriteResult",
    "SalesCoachTaskWriter",
    "_analysis_value",
    "_extract_id",
    "_next_business_day",
    "_normalized_text",
    "_note_text",
    "task_idempotency_key",
]
