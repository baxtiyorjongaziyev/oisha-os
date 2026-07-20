"""
Evolution Scheduler — Self-learning va self-evolution loop'larini boshqaradi.

Scheduled tasks:
  - Every conversation end: extract lessons (real-time)
  - Every 6 hours: synthesize strategies from lessons
  - Weekly (Sunday 03:00): persist an owner-reviewed evolution proposal
  - Daily (10:00): run read-only self-diagnosis and send a Telegram digest
  - Every hour: record metrics snapshot
"""

from __future__ import annotations

import asyncio
import structlog
from datetime import datetime, timedelta
from typing import Optional

from src.database import Database
from src.time_utils import get_local_now

logger = structlog.get_logger()


class EvolutionScheduler:
    """Coordinates self-learning and self-evolution on schedule."""

    def __init__(
        self,
        db: Database,
        gemini_api_key: str,
        bot_client=None,
        owner_id: Optional[int] = None,
    ):
        self.db = db
        self.gemini_api_key = gemini_api_key
        self.bot_client = bot_client
        self.owner_id = owner_id
        self._learning_engine = None
        self._evolution_engine = None
        self._improvement_service = None
        self._running = False
        self._task: Optional[asyncio.Task] = None

    @property
    def learning(self):
        if self._learning_engine is None:
            from src.services.core.self_learning import SelfLearningEngine

            self._learning_engine = SelfLearningEngine(self.db, self.gemini_api_key)
        return self._learning_engine

    @property
    def evolution(self):
        if self._evolution_engine is None:
            from src.services.core.self_evolution import SelfEvolutionEngine

            self._evolution_engine = SelfEvolutionEngine(self.db, self.gemini_api_key)
        return self._evolution_engine

    @property
    def improvement(self):
        if self._improvement_service is None:
            from src.services.core.self_improvement import SelfImprovementService

            self._improvement_service = SelfImprovementService(
                self.db,
                bot_client=self.bot_client,
                owner_id=self.owner_id,
                gemini_api_key=self.gemini_api_key,
            )
        return self._improvement_service

    async def start(self):
        """Start the evolution scheduler loop."""
        if self._running:
            return
        self._running = True
        await self.learning.ensure_tables()
        try:
            await self.improvement.ensure_ready()
        except Exception as exc:
            logger.warning(f"[SCHEDULER] Self-improvement init failed: {exc}")
        self._task = asyncio.create_task(self._run_loop())
        logger.info("[SCHEDULER] Evolution scheduler started")

    async def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[SCHEDULER] Evolution scheduler stopped")

    async def on_conversation_end(
        self,
        conversation: str,
        client_type: str = "unknown",
        outcome: str = "unknown",
        manager_name: str = "",
        chat_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ):
        """Call this when a conversation ends — extracts lessons in background."""
        asyncio.create_task(
            self.learning.extract_lessons(
                conversation=conversation,
                client_type=client_type,
                outcome=outcome,
                manager_name=manager_name,
                chat_id=chat_id,
                user_id=user_id,
            )
        )

    async def get_learning_context(self, category: Optional[str] = None) -> str:
        """Get learning context string to inject into prompts."""
        lessons = await self.learning.get_relevant_lessons(
            context="", category=category
        )
        strategies = await self.learning.get_active_strategies()
        return self.learning.build_learning_context(lessons, strategies)

    async def _run_loop(self):
        """Main scheduler loop."""
        last_synthesis: Optional[datetime] = None
        last_metrics: Optional[datetime] = None

        while self._running:
            try:
                now = get_local_now()

                if last_synthesis is None or (now - last_synthesis) > timedelta(
                    hours=6
                ):
                    await self._do_synthesis()
                    last_synthesis = now

                # Daily read-only diagnosis. Persistent scheduled_jobs state in
                # SelfImprovementService prevents duplicates after restarts.
                if now.hour == 10:
                    await self.improvement.run_diagnosis()

                # Weekly AI suggestion is now proposal-only. Code/PR mutation is
                # blocked until the owner explicitly accepts the proposal.
                if now.weekday() == 6 and now.hour == 3:
                    run_date = now.strftime("%Y-%m-%d")
                    if not await self.db.is_job_run("oisha_weekly_evolution", run_date):
                        completed = await self._do_evolution()
                        if completed:
                            await self.db.mark_job_run(
                                "oisha_weekly_evolution", run_date
                            )

                if last_metrics is None or (now - last_metrics) > timedelta(hours=1):
                    await self._record_metrics_snapshot()
                    last_metrics = now

                await asyncio.sleep(300)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"[SCHEDULER] Loop error: {exc}")
                await asyncio.sleep(60)

    async def _do_synthesis(self):
        """Synthesize strategies from accumulated lessons."""
        try:
            strategies = await self.learning.synthesize_strategies()
            if strategies:
                logger.info(f"[SCHEDULER] Synthesized {len(strategies)} strategies")
        except Exception as exc:
            logger.warning(f"[SCHEDULER] Synthesis failed: {exc}")

    async def _do_evolution(self) -> bool:
        """Persist an AI evolution proposal without changing code or Git state."""
        try:
            proposal = await self.evolution.propose_evolution()
            if proposal:
                saved = await self.improvement.save_ai_evolution_suggestion(proposal)
                logger.info(f"[SCHEDULER] Evolution suggestion saved: {saved.id}")
            return True
        except Exception as exc:
            logger.warning(f"[SCHEDULER] Evolution failed: {exc}")
            return False

    async def _record_metrics_snapshot(self):
        """Record hourly metrics."""
        try:
            async with await self.db.get_connection() as conn:
                row = await conn.execute(
                    "SELECT COUNT(*) FROM learning_journal WHERE created_at > datetime('now', '-1 hour')"
                )
                count = (await row.fetchone())[0]
                await self.learning.record_metric("lessons_per_hour", float(count))
        except Exception as exc:
            logger.debug(f"[SCHEDULER] Metrics snapshot failed: {exc}")
