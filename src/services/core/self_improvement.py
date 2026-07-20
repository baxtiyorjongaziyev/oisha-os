"""Human-in-the-loop self-improvement flow for Oisha.

Diagnosis is strictly read-only. Oisha persists evidence-backed proposals and
asks the exact owner for a decision; it never changes code or deploys from this
service.
"""

from __future__ import annotations

import datetime
import html
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from src.db.repositories.proposals import ProposalRepository
from src.services.core.oisha_self_diagnosis import (
    ImprovementProposal,
    OishaSelfDiagnosis,
)
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)

DAILY_JOB_NAME = "oisha_self_improvement_daily"
OPEN_STATUSES = ("proposed", "deferred", "failed")


@dataclass
class DiagnosisOutcome:
    proposals: List[ImprovementProposal] = field(default_factory=list)
    skipped: bool = False
    notified: bool = False


class SelfImprovementService:
    """Observe, deduplicate, persist, and request an owner decision."""

    def __init__(
        self,
        db,
        *,
        bot_client=None,
        owner_id: Optional[int] = None,
        project_root: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
    ):
        self.db = db
        self.bot_client = bot_client
        if owner_id is None:
            from src.settings import settings

            owner_id = int(getattr(settings, "OWNER_ID", 0) or 0)
        self.owner_id = int(owner_id or 0)
        default_root = Path(__file__).resolve().parents[3]
        self.project_root = Path(
            project_root or os.environ.get("OISHA_REPO_DIR") or default_root
        ).resolve()
        self.repository = ProposalRepository(db)
        self.diagnosis = OishaSelfDiagnosis(
            db=db,
            project_root=str(self.project_root),
            gemini_api_key=gemini_api_key,
        )
        self._ready = False

    async def ensure_ready(self) -> None:
        if self._ready:
            return
        await self.repository.init_table()
        self._ready = True

    async def run_diagnosis(
        self,
        *,
        force: bool = False,
        notify: bool = True,
    ) -> DiagnosisOutcome:
        """Run at most once per local day unless the owner forces a scan."""
        await self.ensure_ready()
        run_date = get_local_now().strftime("%Y-%m-%d")
        if not force and await self.db.is_job_run(DAILY_JOB_NAME, run_date):
            return DiagnosisOutcome(skipped=True)

        proposals = await self.diagnosis.run_full_diagnosis()
        await self.repository.save_proposals(proposals)
        if not force:
            await self.db.mark_job_run(DAILY_JOB_NAME, run_date)

        notified = False
        if notify:
            notified = await self.notify_digest(proposals)
        logger.info(
            "[SELF-IMPROVEMENT] scan complete: proposals=%d notified=%s force=%s",
            len(proposals),
            notified,
            force,
        )
        return DiagnosisOutcome(
            proposals=proposals,
            skipped=False,
            notified=notified,
        )

    async def notify_digest(self, proposals: List[ImprovementProposal]) -> bool:
        if not self.bot_client or not self.owner_id:
            logger.info(
                "[SELF-IMPROVEMENT] Telegram digest skipped: client/owner missing"
            )
            return False
        message = OishaSelfDiagnosis.format_telegram_report(proposals)
        try:
            await self.bot_client.send_message(
                self.owner_id,
                message,
                parse_mode="html",
                link_preview=False,
            )
            return True
        except Exception:
            logger.warning(
                "[SELF-IMPROVEMENT] Telegram digest delivery failed",
                exc_info=True,
            )
            return False

    async def save_ai_evolution_suggestion(self, payload: dict) -> ImprovementProposal:
        """Store a weekly AI prompt suggestion without mutating the repository."""
        await self.ensure_ready()
        changes = payload.get("changes") or []
        files = sorted(
            {
                str(change.get("file"))
                for change in changes
                if isinstance(change, dict) and change.get("file")
            }
        )
        reasons = [
            str(change.get("reason"))
            for change in changes
            if isinstance(change, dict) and change.get("reason")
        ]
        proposal = ImprovementProposal(
            id="TEMP-EVOLUTION",
            category="ai_evolution",
            severity="medium",
            title=str(payload.get("pr_title") or "AI prompt yaxshilanishi")[:160],
            problem=(
                "Oisha o'rgangan darslar asosida prompt/strategiya yangilanishini "
                "taklif qildi. Owner tasdig'isiz kod o'zgarmaydi."
            ),
            proposed_solution="; ".join(reasons)[:1200]
            or str(payload.get("pr_body") or "Taklifni agent bilan tekshirish")[:1200],
            affected_files=files,
            estimated_effort="1h",
            suggested_agent="Code Quality",
            evidence={"evolution_payload": payload},
        )
        proposal.id = self.diagnosis._stable_id(proposal)
        await self.repository.save_proposal(proposal)
        await self.notify_digest([proposal])
        return proposal

    async def list_actionable(self, limit: int = 10) -> List[dict]:
        await self.ensure_ready()
        return await self.repository.get_proposals(
            statuses=OPEN_STATUSES,
            actionable_only=True,
            limit=limit,
        )

    async def send_proposal_cards(
        self, target: Optional[int] = None, limit: int = 5
    ) -> int:
        """Send owner-only decision cards for currently actionable proposals."""
        if not self.bot_client:
            return 0
        target_id = int(target or self.owner_id or 0)
        if not target_id or target_id != self.owner_id:
            return 0
        proposals = await self.list_actionable(limit=limit)
        if not proposals:
            await self.bot_client.send_message(
                target_id,
                "✅ Hozir qaror kutayotgan rivojlanish taklifi yo'q.",
            )
            return 0

        from telethon import Button

        for proposal in proposals:
            proposal_id = str(proposal["id"])
            buttons = [
                [
                    Button.inline(
                        "✅ AI agentga berish", f"improve:accept:{proposal_id}"
                    ),
                    Button.inline("⏸ 7 kun", f"improve:defer:{proposal_id}"),
                    Button.inline("❌ Rad", f"improve:reject:{proposal_id}"),
                ]
            ]
            await self.bot_client.send_message(
                target_id,
                OishaSelfDiagnosis.format_proposal_card(proposal),
                parse_mode="html",
                link_preview=False,
                buttons=buttons,
            )
        return len(proposals)

    async def decide(
        self,
        proposal_id: str,
        action: str,
        *,
        actor_id: int,
    ) -> tuple[bool, str, Optional[dict]]:
        """Apply an owner decision and return a truthful next-step message."""
        await self.ensure_ready()
        if not self.owner_id or int(actor_id) != self.owner_id:
            return False, "Bu qarorni faqat owner bera oladi.", None

        proposal = await self.repository.get_proposal(proposal_id)
        if not proposal:
            return False, "Taklif topilmadi.", None

        if action == "accept":
            status = "accepted"
            deferred_until = None
            note = "Owner AI agent handoffini tasdiqladi"
        elif action == "defer":
            status = "deferred"
            deferred_until = (
                datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(days=7)
            ).isoformat()
            note = "Owner taklifni 7 kunga kechiktirdi"
        elif action == "reject":
            status = "rejected"
            deferred_until = None
            note = "Owner taklifni rad etdi"
        else:
            return False, "Noma'lum qaror.", proposal

        changed = await self.repository.update_proposal_status(
            proposal_id,
            status,
            resolved_by=str(actor_id),
            rejection_reason="Telegram owner decision"
            if status == "rejected"
            else None,
            deferred_until=deferred_until,
            note=note,
        )
        if not changed:
            return (
                False,
                "Taklif avvalroq qayta ishlangan yoki holati o'zgargan.",
                proposal,
            )

        if status == "accepted":
            return True, self.build_agent_handoff(proposal), proposal
        if status == "deferred":
            return True, "⏸ Taklif 7 kunga kechiktirildi.", proposal
        return True, "❌ Taklif rad etildi.", proposal

    @staticmethod
    def build_agent_handoff(proposal: dict) -> str:
        """Create a ready-to-use brief; acceptance does not fake execution."""
        files = html.escape(
            ", ".join(str(path) for path in proposal.get("affected_files") or [])[:500]
        )
        agent = html.escape(str(proposal.get("suggested_agent", "Coordinator"))[:80])
        title = html.escape(str(proposal.get("title", ""))[:160])
        problem = html.escape(str(proposal.get("problem", ""))[:600])
        solution = html.escape(str(proposal.get("proposed_solution", ""))[:600])
        return (
            "✅ <b>Agent uchun vazifa tayyor</b>\n\n"
            f"<b>Agent:</b> {agent}\n"
            f"<b>Maqsad:</b> {title}\n"
            f"<b>Muammo:</b> {problem}\n"
            f"<b>Yechim:</b> {solution}\n"
            f"<b>Fayllar:</b> {files or 'auditda aniqlanadi'}\n\n"
            "Holat: <b>accepted</b>. Hali kod yozilmadi va deploy qilinmadi; "
            "code-agent executor ulanganda queued bo'ladi."
        )[:3900]
