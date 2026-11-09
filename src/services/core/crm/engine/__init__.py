"""Oisha CRM — Native amoCRM Replacement Engine."""
from src.services.core.crm.engine.ai_coach import CrmAiCoach
from src.services.core.crm.engine.automation import CrmAutomationEngine
from src.services.core.crm.engine.intake import LeadIntakeService, normalize_phone_number
from src.services.core.crm.engine.schema import (
    CompanyModel,
    ContactModel,
    DealCreate,
    DealModel,
    DealUpdate,
    IntakeLeadPayload,
    PipelineModel,
    StageModel,
    TaskCreate,
    TaskModel,
    TimelineEventCreate,
    TimelineEventModel,
)
from src.services.core.crm.engine.store import OishaCrmStore

__all__ = [
    "CrmAiCoach",
    "CrmAutomationEngine",
    "LeadIntakeService",
    "OishaCrmStore",
    "normalize_phone_number",
    "CompanyModel",
    "ContactModel",
    "DealCreate",
    "DealModel",
    "DealUpdate",
    "IntakeLeadPayload",
    "PipelineModel",
    "StageModel",
    "TaskCreate",
    "TaskModel",
    "TimelineEventCreate",
    "TimelineEventModel",
]
