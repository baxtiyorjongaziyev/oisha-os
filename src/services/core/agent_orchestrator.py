"""
Bots Managed by Bots — Telegram AI Bot Revolution feature #5.

An autonomous orchestration layer where one "master" agent (OishaBrain)
creates task pipelines and dispatches them to specialized sub-agents via
bot-to-bot messaging. No human involvement required.

Pipeline example:
  OishaBrain detects a stagnated lead
    → instructs SurgicalNegotiator bot to draft revival message
    → SurgicalNegotiator returns proposed text
    → OishaBrain sends to auto_reply_gate for approval decision
    → if approved, sends via userbot

Design:
  - Tasks are defined as AgentTask objects (reuses agent_loop.py schema)
  - Orchestrator routes by task.kind → target agent
  - Sub-agents report results back via bot-to-bot reply
  - All steps are logged to agent_actions table
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PipelineStep:
    name: str
    agent: str          # bot username or internal agent id
    instruction: str    # what to tell the agent
    depends_on: Optional[str] = None   # step name to wait for
    timeout: float = 30.0


@dataclass
class Pipeline:
    id: str
    goal: str
    steps: List[PipelineStep] = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending | running | done | failed
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def add_step(
        self,
        name: str,
        agent: str,
        instruction: str,
        depends_on: Optional[str] = None,
        timeout: float = 30.0,
    ) -> "Pipeline":
        self.steps.append(PipelineStep(name, agent, instruction, depends_on, timeout))
        return self


class AgentOrchestrator:
    """
    Master orchestrator — creates and executes multi-step agent pipelines.

    Each step can be:
      - An internal Python agent (called directly via agent registry)
      - An external bot (messaged via BotMessenger)
    """

    def __init__(
        self,
        agent_registry: Optional[Dict[str, Any]] = None,
        bot_messenger=None,
        db=None,
    ):
        self.agents = agent_registry or {}   # agent_id → agent instance
        self.messenger = bot_messenger
        self.db = db
        self._active_pipelines: Dict[str, Pipeline] = {}

    def register_agent(self, agent_id: str, agent: Any) -> None:
        self.agents[agent_id] = agent

    async def run_pipeline(self, pipeline: Pipeline) -> Pipeline:
        """Execute all steps in a pipeline, respecting dependencies."""
        logger.info(f"[orchestrator] Pipeline {pipeline.id}: {pipeline.goal}")
        self._active_pipelines[pipeline.id] = pipeline
        pipeline.status = "running"

        for step in pipeline.steps:
            # Wait for dependency result
            if step.depends_on and step.depends_on not in pipeline.results:
                logger.warning(f"[orchestrator] Step {step.name} skipped — dep {step.depends_on} missing")
                continue

            dep_result = pipeline.results.get(step.depends_on, "") if step.depends_on else ""
            instruction = step.instruction
            if dep_result:
                instruction = f"{instruction}\n\nPrevious step result:\n{dep_result}"

            try:
                result = await asyncio.wait_for(
                    self._run_step(step, instruction),
                    timeout=step.timeout,
                )
                pipeline.results[step.name] = result
                logger.info(f"[orchestrator] Step {step.name} → {str(result)[:80]}")
            except asyncio.TimeoutError:
                pipeline.results[step.name] = f"timeout after {step.timeout}s"
                logger.warning(f"[orchestrator] Step {step.name} timed out")
            except Exception as e:
                pipeline.results[step.name] = f"error: {e}"
                logger.error(f"[orchestrator] Step {step.name} failed: {e}")

        pipeline.status = "done"
        await self._log_pipeline(pipeline)
        return pipeline

    async def _run_step(self, step: PipelineStep, instruction: str) -> str:
        """Route step to internal agent or external bot."""
        # Internal agent
        if step.agent in self.agents:
            agent = self.agents[step.agent]
            if hasattr(agent, "process_task"):
                return await agent.process_task(0, instruction)
            elif hasattr(agent, "evolve"):
                result = await agent.evolve(instruction)
                return str(result)
            return f"agent {step.agent} has no process_task/evolve method"

        # External bot via bot-to-bot messaging
        if self.messenger and step.agent.startswith("@"):
            msg = await self.messenger.request(step.agent, instruction, timeout=step.timeout)
            return msg.reply_text or (f"no reply from {step.agent}" if msg.success else msg.error or "failed")

        return f"no handler for agent: {step.agent}"

    async def _log_pipeline(self, pipeline: Pipeline) -> None:
        if not self.db or not hasattr(self.db, "log_agent_action"):
            return
        try:
            await self.db.log_agent_action(
                user_id=0,
                action_type="orchestrator_pipeline",
                data={
                    "id": pipeline.id,
                    "goal": pipeline.goal,
                    "status": pipeline.status,
                    "results": pipeline.results,
                    "created_at": pipeline.created_at,
                },
                success=pipeline.status == "done",
            )
        except Exception as e:
            logger.error(f"[orchestrator] log error: {e}")

    # ── Pre-built pipeline factories ──────────────────────────────────────────

    def stagnated_lead_pipeline(self, user_id: str, lead_name: str) -> Pipeline:
        """
        Stagnated lead → draft revival → risk check → auto-send if approved.
        """
        p = Pipeline(
            id=f"stagnant_{user_id}_{datetime.now().strftime('%H%M%S')}",
            goal=f"Revive stagnated lead: {lead_name}",
        )
        p.add_step(
            "draft_revival",
            "sales",
            f"Draft a revival message for lead '{lead_name}' who hasn't responded in 3+ days. Be direct, 2 sentences max.",
        )
        p.add_step(
            "risk_check",
            "brain",
            f"Is it safe to auto-send this revival message to '{lead_name}'? Reply YES or NO with reason.",
            depends_on="draft_revival",
        )
        return p

    def call_to_crm_pipeline(self, call_id: str, scorecard_summary: str) -> Pipeline:
        """
        Call scored → extract CRM data → update AmoCRM → notify manager.
        """
        p = Pipeline(
            id=f"call_crm_{call_id}",
            goal=f"Push call {call_id} scorecard to CRM",
        )
        p.add_step(
            "extract_crm_fields",
            "sales",
            f"From this call scorecard, extract: lead_quality (1-10), next_action, commitment_made (yes/no).\nScorecard: {scorecard_summary[:500]}",
        )
        p.add_step(
            "update_crm",
            "sales",
            f"Update AmoCRM lead with extracted fields for call {call_id}.",
            depends_on="extract_crm_fields",
        )
        return p


# Singleton
_orchestrator: Optional[AgentOrchestrator] = None


def get_orchestrator(
    agent_registry: Optional[Dict] = None,
    bot_messenger=None,
    db=None,
) -> AgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator(agent_registry, bot_messenger, db)
    return _orchestrator
