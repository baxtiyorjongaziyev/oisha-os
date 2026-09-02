"""
OishaSelfDiagnosis main engine orchestrating full audit passes across all submodules.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from src.services.core.diagnosis.error_diagnosis import ErrorDiagnosisMixin
from src.services.core.diagnosis.health_quality import HealthQualityMixin
from src.services.core.diagnosis.models import (
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    ImprovementProposal,
)
from src.services.core.diagnosis.reporting import ReportingMixin

logger = logging.getLogger("OishaSelfDiagnosis")


class OishaSelfDiagnosis(ErrorDiagnosisMixin, HealthQualityMixin, ReportingMixin):
    """
    Oisha-OS o'z-o'zini tashxislash va takomillashtirish tizimi.
    """

    def __init__(
        self,
        db=None,
        project_root: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
    ):
        self.db = db
        configured_root = (
            project_root or os.environ.get("OISHA_REPO_DIR") or os.getcwd()
        )
        self.project_root = Path(configured_root).resolve()
        self._src_root = self.project_root / "src"
        self._counter = 0
        self._gemini_api_key = gemini_api_key

    async def run_full_diagnosis(self) -> List[ImprovementProposal]:
        """Barcha 5 ta diagnostikani ishga tushiradi va natijalarni birlashtiradi."""
        self._counter = 0
        all_proposals: List[ImprovementProposal] = []

        diagnostics = [
            ("errors", self.diagnose_errors),
            ("health", self.diagnose_health),
            ("code_quality", self.diagnose_code_quality),
            ("feature_gaps", self.diagnose_feature_gaps),
            ("performance", self.diagnose_performance),
        ]

        for name, method in diagnostics:
            try:
                results = await method()
                all_proposals.extend(results)
                logger.info("[SELF-DIAG] %s: %d ta taklif topildi", name, len(results))
            except Exception as exc:
                logger.error("[SELF-DIAG] %s diagnostikasi xato: %s", name, exc)

        # Stable semantic IDs prevent reruns from overwriting another finding and
        # let the repository preserve a prior owner decision.
        deduplicated: Dict[str, ImprovementProposal] = {}
        for proposal in all_proposals:
            proposal.id = self._stable_id(proposal)
            deduplicated.setdefault(proposal.id, proposal)
        all_proposals = list(deduplicated.values())

        # Sort by severity
        severity_order = {
            SEVERITY_CRITICAL: 0,
            SEVERITY_HIGH: 1,
            SEVERITY_MEDIUM: 2,
            SEVERITY_LOW: 3,
        }
        all_proposals.sort(key=lambda p: severity_order.get(p.severity, 99))

        logger.info(
            "[SELF-DIAG] To'liq diagnostika tugadi: %d ta taklif",
            len(all_proposals),
        )
        return all_proposals

