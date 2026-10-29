"""Call Intelligence Worker — processes call analysis jobs via Redis Streams."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from src.workers.redis_worker import RedisWorker, WorkerConfig, JobProducer, JobPayload
from src.settings import settings

logger = logging.getLogger(__name__)


CALL_INTEL_STREAM = "call_intelligence"
CALL_INTEL_DLQ = "call_intelligence_dlq"
CRM_SYNC_STREAM = "crm_sync"
CRM_SYNC_DLQ = "crm_sync_dlq"


class CallIntelligenceWorker(RedisWorker):
    """Worker for call transcription, scoring, and CRM sync."""

    def __init__(self, redis_client=None):
        config = WorkerConfig(
            stream_name=CALL_INTEL_STREAM,
            consumer_group="call_intel_workers",
            consumer_name=f"call-intel-{os.getpid()}",
            dead_letter_stream=CALL_INTEL_DLQ,
            max_retries=3,
            retry_delay_ms=10000,
        )
        super().__init__(config, redis_client)
        self._register_handlers()

    def _register_handlers(self):
        self.register("transcribe")(self._handle_transcribe)
        self.register("score")(self._handle_score)
        self.register("crm_sync")(self._handle_crm_sync)
        self.register("full_pipeline")(self._handle_full_pipeline)

    async def _handle_transcribe(self, payload: dict) -> dict:
        """Transcribe audio using available STT providers."""
        call_id = payload["call_id"]
        audio_url = payload["audio_url"]
        language = payload.get("language", "uz")

        logger.info("[CallIntel] Transcribing call %s", call_id)

        from src.services.call_analytics.transcriber import CallTranscriberMixin
        transcriber = CallTranscriberMixin()

        transcript = await transcriber.transcribe_url(audio_url, language)

        await self._save_transcript(call_id, transcript)

        return {"call_id": call_id, "transcript_length": len(transcript)}

    async def _handle_score(self, payload: dict) -> dict:
        """Score transcript using rubric + LLM."""
        call_id = payload["call_id"]
        transcript = payload.get("transcript") or await self._get_transcript(call_id)

        logger.info("[CallIntel] Scoring call %s", call_id)

        from src.services.call_analytics.scorer import CallScorerMixin
        from src.services.core.sales_playbook import rubric_prompt_uz

        scorer = CallScorerMixin()
        rubric = rubric_prompt_uz()
        score_result = await scorer.score_transcript(transcript, rubric)

        await self._save_scorecard(call_id, score_result)

        return {"call_id": call_id, "score": score_result.get("overall_score")}

    async def _handle_crm_sync(self, payload: dict) -> dict:
        """Sync call analysis to AmoCRM."""
        call_id = payload["call_id"]
        lead_id = payload.get("lead_id")

        logger.info("[CallIntel] CRM sync for call %s", call_id)

        from src.services.call_analytics.crm_notes import CallCrmNotesMixin
        from src.services.call_analytics.crm_tasks import CallCrmTasksMixin

        notes_mixin = CallCrmNotesMixin()
        tasks_mixin = CallCrmTasksMixin()

        analysis = await self._get_analysis(call_id)

        note_id = await notes_mixin.add_call_analysis_note(call_id, analysis, lead_id)

        if analysis.get("next_action"):
            task_id = await tasks_mixin.create_followup_task(
                call_id=call_id,
                lead_id=lead_id,
                task_text=analysis["next_action"],
                due_hours=24
            )
        else:
            task_id = None

        return {"call_id": call_id, "note_id": note_id, "task_id": task_id}

    async def _handle_full_pipeline(self, payload: dict) -> dict:
        """Run full pipeline: transcribe → score → crm_sync."""
        call_id = payload["call_id"]

        await self._handle_transcribe(payload)
        await self._handle_score({"call_id": call_id})
        await self._handle_crm_sync(payload)

        return {"call_id": call_id, "status": "completed"}

    async def _save_transcript(self, call_id: str, transcript: str):
        from src.db.repositories.intelligence import IntelligenceRepository
        repo = IntelligenceRepository()
        await repo.save_transcript(call_id, transcript)

    async def _get_transcript(self, call_id: str) -> str:
        from src.db.repositories.intelligence import IntelligenceRepository
        repo = IntelligenceRepository()
        return await repo.get_transcript(call_id)

    async def _save_scorecard(self, call_id: str, score: dict):
        from src.db.repositories.intelligence import IntelligenceRepository
        repo = IntelligenceRepository()
        await repo.save_scorecard(call_id, score)

    async def _get_analysis(self, call_id: str) -> dict:
        from src.db.repositories.intelligence import IntelligenceRepository
        repo = IntelligenceRepository()
        return await repo.get_latest_call_analysis(call_id)


class CRMSyncWorker(RedisWorker):
    """Worker for bi-directional AmoCRM sync."""

    def __init__(self, redis_client=None):
        config = WorkerConfig(
            stream_name=CRM_SYNC_STREAM,
            consumer_group="crm_sync_workers",
            consumer_name=f"crm-sync-{os.getpid()}",
            dead_letter_stream=CRM_SYNC_DLQ,
            max_retries=5,
            retry_delay_ms=30000,
        )
        super().__init__(config, redis_client)
        self._register_handlers()

    def _register_handlers(self):
        self.register("lead_create")(self._handle_lead_create)
        self.register("lead_update")(self._handle_lead_update)
        self.register("note_add")(self._handle_note_add)
        self.register("task_create")(self._handle_task_create)
        self.register("status_change")(self._handle_status_change)
        self.register("webhook_process")(self._handle_webhook_process)

    async def _handle_lead_create(self, payload: dict) -> dict:
        from src.services.core.amocrm import AmoCRMClient
        client = AmoCRMClient()
        lead = await client.create_lead(payload)
        return {"lead_id": lead["id"]}

    async def _handle_lead_update(self, payload: dict) -> dict:
        from src.services.core.amocrm import AmoCRMClient
        client = AmoCRMClient()
        await client.update_lead(payload["lead_id"], payload["fields"])
        return {"lead_id": payload["lead_id"], "updated": True}

    async def _handle_note_add(self, payload: dict) -> dict:
        from src.services.core.amocrm import AmoCRMClient
        client = AmoCRMClient()
        note = await client.add_note(payload["lead_id"], payload["text"])
        return {"note_id": note["id"]}

    async def _handle_task_create(self, payload: dict) -> dict:
        from src.services.core.amocrm import AmoCRMClient
        client = AmoCRMClient()
        task = await client.create_task(payload)
        return {"task_id": task["id"]}

    async def _handle_status_change(self, payload: dict) -> dict:
        from src.services.core.amocrm import AmoCRMClient
        client = AmoCRMClient()
        await client.update_lead_status(payload["lead_id"], payload["status_id"], payload["pipeline_id"])
        return {"lead_id": payload["lead_id"], "status_changed": True}

    async def _handle_webhook_process(self, payload: dict) -> dict:
        """Process incoming AmoCRM webhook."""
        from src.api.routes.amocrm_integration import process_amocrm_event
        await process_amocrm_event(payload)
        return {"processed": True}


import os


async def run_call_intel_worker():
    """Entry point for call intelligence worker."""
    worker = CallIntelligenceWorker()
    await worker.start()

    try:
        await asyncio.Event().wait()
    finally:
        await worker.stop()


async def run_crm_sync_worker():
    """Entry point for CRM sync worker."""
    worker = CRMSyncWorker()
    await worker.start()

    try:
        await asyncio.Event().wait()
    finally:
        await worker.stop()


async def enqueue_call_analysis(call_id: str, audio_url: str, lead_id: str = None):
    """Enqueue full call analysis pipeline."""
    producer = JobProducer()
    try:
        await producer.enqueue(
            CALL_INTEL_STREAM,
            "full_pipeline",
            {"call_id": call_id, "audio_url": audio_url, "lead_id": lead_id},
            idempotency_key=f"call_analysis:{call_id}"
        )
    finally:
        await producer.close()


async def enqueue_crm_sync(job_type: str, payload: dict):
    """Enqueue CRM sync job."""
    producer = JobProducer()
    try:
        await producer.enqueue(
            CRM_SYNC_STREAM,
            job_type,
            payload,
            idempotency_key=f"crm_sync:{job_type}:{payload.get('lead_id', 'unknown')}"
        )
    finally:
        await producer.close()