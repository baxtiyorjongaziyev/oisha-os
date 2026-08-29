"""
AmoCRMDealHygieneAgent orchestrator class.
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from src.services.core.hygiene.classifier import ClassifierMixin
from src.services.core.hygiene.identity import IdentityMixin
from src.services.core.hygiene.models import (
    SYSTEM_TAGS,
    DealHygieneFinding,
    DealSignal,
    DuplicateDealFinding,
    LeadIdentity,
    extract_phones,
    extract_usernames,
    normalize_phone,
)

logger = logging.getLogger("AmoCRMDealHygiene")


class AmoCRMDealHygieneAgent(IdentityMixin, ClassifierMixin):
    """
    AmoCRM deal hygiene agent.
    """

    def __init__(self, amocrm: AmoCRMSync, db: Any = None):
        self.amocrm = amocrm
        self.db = db


    async def audit(self, limit: int = 100) -> Dict[str, Any]:
        leads = await self.amocrm.get_leads_detailed(limit=min(max(limit, 1), 250))
        active_leads = [lead for lead in leads if lead.get("status_id") not in (142, 143)]
        telegram_profiles = await self._load_telegram_profiles()

        identities: List[LeadIdentity] = []
        unnecessary: List[DealHygieneFinding] = []

        for lead in active_leads:
            identity = await self._build_identity(lead, telegram_profiles)
            identities.append(identity)

            finding = await self._classify_unnecessary(lead, identity)
            if finding:
                unnecessary.append(finding)

        duplicates = self._find_duplicates(identities)

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "checked_leads": len(active_leads),
            "unnecessary_count": len(unnecessary),
            "duplicate_group_count": len(duplicates),
            "unnecessary_deals": [asdict(item) for item in unnecessary],
            "duplicate_suspects": [asdict(item) for item in duplicates],
            "safety": {
                "auto_delete": False,
                "auto_merge": False,
                "apply_mode": "tags_notes_tasks_only",
            },
        }

    async def apply_report(
        self,
        report: Dict[str, Any],
        create_tasks: bool = True,
    ) -> Dict[str, Any]:
        """Apply safe AmoCRM annotations only: tags, notes, optional tasks."""
        actions: List[Dict[str, Any]] = []

        for item in report.get("unnecessary_deals", []):
            lead_id = int(item["lead_id"])
            tag = item.get("tag") or SYSTEM_TAGS["needs_review"]
            note = self._format_unnecessary_note(item)
            actions.append(await self._tag_and_note(lead_id, tag, note))
            if create_tasks:
                task_text = (
                    "Oisha: sdelka sifati shubhali. Dalillarni tekshirib, "
                    "keraksiz bo'lsa Lost/keraksiz segmentga ajrating."
                )
                actions.append(await self._create_review_task(lead_id, task_text))

        for group in report.get("duplicate_suspects", []):
            note = self._format_duplicate_note(group)
            for lead_id in group.get("lead_ids", []):
                actions.append(
                    await self._tag_and_note(int(lead_id), SYSTEM_TAGS["duplicate"], note)
                )
            if create_tasks and group.get("lead_ids"):
                lead_id = int(group["lead_ids"][0])
                actions.append(
                    await self._create_review_task(
                        lead_id,
                        "Oisha: duplikat sdelka ehtimoli yuqori. "
                        "Telefon/Telegram mosligini tekshirib, bitta asosiy sdelkani qoldiring.",
                    )
                )

        return {
            "attempted": len(actions),
            "success": sum(1 for action in actions if action.get("success")),
            "failed": sum(1 for action in actions if not action.get("success")),
            "actions": actions,
        }
