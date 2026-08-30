"""
AITaskManager main service class.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.services.ai.quality_analyzer import ConversationAnalysis
from src.services.ai.task_creation.builders import (
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    TASK_TYPES,
    create_followup_tasks,
    create_mood_based_tasks,
    create_objection_tasks,
    create_quality_tasks,
    detect_task_type,
    estimate_due_hours,
)
from src.services.ai.task_creation.reporting import (
    generate_task_report,
    get_task_summary,
)

logger = logging.getLogger(__name__)


class AITaskManager:
    """AI tahlil asosida avtomatik vazifa qo'yish."""

    TASK_TYPES = TASK_TYPES
    PRIORITY_HIGH = PRIORITY_HIGH
    PRIORITY_MEDIUM = PRIORITY_MEDIUM
    PRIORITY_LOW = PRIORITY_LOW

    def __init__(self, amocrm_client=None):
        self.amocrm = amocrm_client

    async def create_tasks_from_analysis(
        self, analysis: ConversationAnalysis, auto_create: bool = False
    ) -> List[Dict[str, Any]]:
        tasks = []
        tasks.extend(self._create_quality_tasks(analysis))
        tasks.extend(self._create_objection_tasks(analysis))
        tasks.extend(self._create_followup_tasks(analysis))
        tasks.extend(self._create_mood_based_tasks(analysis))

        if auto_create and self.amocrm:
            created_tasks = []
            for task in tasks:
                created = await self._create_in_amocrm(task, analysis.lead_id)
                if created:
                    task["created_in_crm"] = True
                    created_tasks.append(task)
                    logger.info(
                        f"[AI TASK] AmoCRM da vazifa yaratildi: {task['title']}"
                    )
                else:
                    task["created_in_crm"] = False
                    logger.warning(
                        f"[AI TASK] AmoCRM da vazifa yaratilmadi: {task['title']}"
                    )
            return created_tasks

        return tasks

    def _create_quality_tasks(self, analysis: ConversationAnalysis) -> List[Dict[str, Any]]:
        return create_quality_tasks(analysis)

    def _create_objection_tasks(self, analysis: ConversationAnalysis) -> List[Dict[str, Any]]:
        return create_objection_tasks(analysis)

    def _create_followup_tasks(self, analysis: ConversationAnalysis) -> List[Dict[str, Any]]:
        return create_followup_tasks(analysis)

    def _create_mood_based_tasks(self, analysis: ConversationAnalysis) -> List[Dict[str, Any]]:
        return create_mood_based_tasks(analysis)

    def _detect_task_type(self, text: str) -> int:
        return detect_task_type(text)

    def _estimate_due_hours(self, text: str) -> int:
        return estimate_due_hours(text)

    async def _create_in_amocrm(
        self, task: Dict[str, Any], lead_id: Optional[int]
    ) -> bool:
        from src.utils.task_scheduler import task_deadline

        if not self.amocrm or not lead_id:
            return False

        try:
            due_hours = task.get("due_in_hours", 24)
            complete_till = task_deadline(due_in_hours=due_hours)
            text = task.get("text", task.get("title", "Vazifa"))

            result = await self.amocrm.create_task(
                element_id=lead_id,
                text=text[:500],
                complete_till=complete_till,
            )
            return result
        except Exception as e:
            logger.error(f"[AI TASK] AmoCRM vazifa yaratish xatosi: {e}")
            return False

    async def create_batch_tasks(
        self, analyses: List[ConversationAnalysis], auto_create: bool = False
    ) -> Dict[str, List[Dict[str, Any]]]:
        all_tasks = {}
        for analysis in analyses:
            lead_id = analysis.lead_id
            if not lead_id:
                continue

            tasks = await self.create_tasks_from_analysis(analysis, auto_create)
            if lead_id not in all_tasks:
                all_tasks[lead_id] = []
            all_tasks[lead_id].extend(tasks)

        return all_tasks

    def get_task_summary(self, analyses: List[ConversationAnalysis]) -> Dict[str, Any]:
        return get_task_summary(analyses)

    def generate_task_report(
        self,
        analyses: List[ConversationAnalysis],
        created_tasks: Dict[str, List[Dict[str, Any]]],
    ) -> str:
        return generate_task_report(analyses, created_tasks)
