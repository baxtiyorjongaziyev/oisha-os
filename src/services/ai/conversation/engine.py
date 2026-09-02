"""
Core ConversationEngine orchestrator.
"""
from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional

from src.services.ai.call_analytics import CallAnalytics
from src.services.ai.conversation.models import CallRecord
from src.services.ai.conversation.reporting import ConversationReportingMixin
from src.services.ai.quality_analyzer import ConversationAnalysis, QualityAnalyzer
from src.services.ai.task_manager import AITaskManager
from src.services.utils.db_rows import execute_write

logger = logging.getLogger(__name__)


class ConversationEngine(ConversationReportingMixin):
    """Suhbat tahlili dvigateli."""

    def __init__(self, amocrm_client=None, db_pool=None):
        self.amocrm = amocrm_client
        self.db = db_pool
        self.analyzer = QualityAnalyzer()
        self.analytics = CallAnalytics()
        self.task_manager = AITaskManager(amocrm_client)

        self.analyses: Dict[str, ConversationAnalysis] = {}
        self.call_records: Dict[str, CallRecord] = {}

    async def process_call(
        self,
        call_record: CallRecord,
        auto_analyze: bool = True,
        auto_create_tasks: bool = True,
    ) -> Optional[ConversationAnalysis]:
        logger.info(f"Qo'ng'iroqni qayta ishlash: {call_record.call_id}")
        self.call_records[call_record.call_record.call_id if hasattr(call_record, "call_record") else call_record.call_id] = call_record

        if not call_record.transcript and call_record.audio_url:
            call_record.transcript = await self._transcribe_audio(call_record.audio_url)

        if not call_record.transcript:
            logger.warning("Transkript mavjud emas, tahlil qilinmadi")
            return None

        analysis = None
        if auto_analyze:
            analysis = await self._analyze_call(call_record)
            if analysis:
                self.analyses[call_record.call_id] = analysis
                self.analytics.add_analysis(analysis)
                if self.db:
                    await self._save_analysis_to_db(call_record, analysis)

        if analysis and auto_create_tasks and self.amocrm:
            await self.task_manager.create_tasks_from_analysis(
                analysis, call_record.lead_id, call_record.manager_id
            )

        return analysis

    async def _analyze_call(
        self, call_record: CallRecord
    ) -> Optional[ConversationAnalysis]:
        try:
            return await self.analyzer.analyze_conversation(
                transcript=call_record.transcript,
                manager_name=call_record.manager_name,
                client_name=call_record.lead_name,
                context={
                    "call_id": call_record.call_id,
                    "lead_id": call_record.lead_id,
                    "duration_seconds": call_record.duration_seconds,
                    "started_at": call_record.started_at.isoformat()
                    if hasattr(call_record.started_at, "isoformat")
                    else str(call_record.started_at),
                },
            )
        except Exception as e:
            logger.error(f"Tahlil qilishda xatolik: {e}")
            return None

    async def _transcribe_audio(self, audio_url: str) -> str:
        logger.info(f"Audio transkripsiya qilinmoqda: {audio_url}")
        try:
            from src.services.core.stt_service import STTService

            stt = STTService()
            return await stt.transcribe_url(audio_url)
        except Exception as e:
            logger.error(f"Transkripsiya xatosi: {e}")
            return ""

    async def _save_analysis_to_db(
        self, call_record: CallRecord, analysis: ConversationAnalysis
    ):
        try:
            stages_json = json.dumps(
                [
                    {"stage": s.stage_name.value, "score": s.score}
                    for s in analysis.stages
                ]
            )
            objections_json = json.dumps(
                [
                    {
                        "type": o.objection_type.value,
                        "handled": o.was_handled_well,
                    }
                    for o in analysis.objections_handled
                ]
            )

            await execute_write(
                self.db,
                """
                INSERT INTO conversation_analyses (
                    call_id, lead_id, manager_id, manager_name,
                    overall_score, deal_outcome, stages,
                    objections, strengths, weaknesses, recommendations,
                    analyzed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(call_id) DO UPDATE SET
                    overall_score = excluded.overall_score,
                    deal_outcome = excluded.deal_outcome,
                    stages = excluded.stages,
                    objections = excluded.objections,
                    strengths = excluded.strengths,
                    weaknesses = excluded.weaknesses,
                    recommendations = excluded.recommendations,
                    analyzed_at = excluded.analyzed_at
                """,
                (
                    call_record.call_id,
                    call_record.lead_id,
                    call_record.manager_id,
                    call_record.manager_name,
                    analysis.overall_score,
                    analysis.deal_outcome.value,
                    stages_json,
                    objections_json,
                    json.dumps(analysis.key_strengths),
                    json.dumps(analysis.key_weaknesses),
                    json.dumps(analysis.recommendations),
                    analysis.analyzed_at.isoformat()
                    if hasattr(analysis.analyzed_at, "isoformat")
                    else str(analysis.analyzed_at),
                ),
            )
        except Exception as e:
            logger.error(f"DB ga saqlashda xatolik: {e}")

    async def process_amocrm_lead_calls(
        self, lead_id: int
    ) -> List[ConversationAnalysis]:
        if not self.amocrm:
            return []
        analyses = []
        try:
            notes = await self.amocrm.get_lead_notes(lead_id)
            for note in notes:
                if note.get("note_type") == "call_in" or note.get("note_type") == "call_out":
                    pass
        except Exception as e:
            logger.error(f"AmoCRM qo'ng'iroqlarini olishda xatolik: {e}")
        return analyses
