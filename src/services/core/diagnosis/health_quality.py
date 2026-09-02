"""
Health metrics, code quality auditing, feature gaps, and performance bottlenecks mixin.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from src.services.core.diagnosis.models import (
    CATEGORY_CODE,
    CATEGORY_FEATURE,
    CATEGORY_HEALTH,
    CATEGORY_PERF,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    ImprovementProposal,
)

logger = logging.getLogger("OishaSelfDiagnosis")


class HealthQualityMixin:
    """Handles system health checks, static code quality, and feature gap auditing."""

    async def diagnose_health(self) -> List[ImprovementProposal]:
        """API kalitlari, DB ulanishi, muhim fayllar holatini tekshiradi."""
        proposals: List[ImprovementProposal] = []

        # -- 2a. Required env vars --
        required_vars = {
            "BOT_TOKEN": ("Telegram Bot API token", SEVERITY_CRITICAL),
            "GEMINI_API_KEY": ("Google Gemini AI kaliti", SEVERITY_HIGH),
            "AMOCRM_CLIENT_ID": ("AmoCRM OAuth client ID", SEVERITY_HIGH),
            "AMOCRM_CLIENT_SECRET": ("AmoCRM OAuth secret", SEVERITY_HIGH),
            "TURSO_DATABASE_URL": ("Turso bulutli DB manzili", SEVERITY_MEDIUM),
        }
        for var, (desc, severity) in required_vars.items():
            val = os.environ.get(var, "")
            if not val:
                proposals.append(
                    ImprovementProposal(
                        id=self._next_id(),
                        category=CATEGORY_HEALTH,
                        severity=severity,
                        title=f"Env var yo'q: {var}",
                        problem=f"{desc} sozlanmagan. Bu funksiyalar ishlamaydi.",
                        proposed_solution=f".env yoki GitHub Secrets ga {var} ni qo'shing.",
                        suggested_agent="Coordinator",
                        estimated_effort="15min",
                    )
                )

        # -- 2b. Required files --
        required_files = {
            "data/service_account.json": (
                "Google Sheets/Calendar/Drive uchun kerak",
                SEVERITY_HIGH,
                "Integration",
            ),
        }
        for rel_path, (desc, severity, agent) in required_files.items():
            abs_path = self.project_root / rel_path
            if not abs_path.exists():
                proposals.append(
                    ImprovementProposal(
                        id=self._next_id(),
                        category=CATEGORY_HEALTH,
                        severity=severity,
                        title=f"Fayl topilmadi: {rel_path}",
                        problem=f"{desc}. Fayl mavjud emas: {abs_path}",
                        proposed_solution=f"{rel_path} faylini serverga yuklang.",
                        affected_files=[rel_path],
                        suggested_agent=agent,
                        estimated_effort="15min",
                    )
                )

        # -- 2c. Database connectivity --
        if self.db:
            try:
                conn = await self._get_connection()
                await conn.execute("SELECT 1")
            except Exception as exc:
                logger.error("Exception handled in %s", __name__, exc_info=True)
                proposals.append(
                    ImprovementProposal(
                        id=self._next_id(),
                        category=CATEGORY_HEALTH,
                        severity=SEVERITY_CRITICAL,
                        title="Database ulanish xatosi",
                        problem=(
                            "SQLite/Turso bazaga ulanib bo'lmaydi: "
                            f"{self._redact(exc, limit=240)}"
                        ),
                        proposed_solution="Database fayl yo'lini va Turso URL ni tekshiring.",
                        suggested_agent="Database",
                        estimated_effort="30min",
                        evidence={"error": self._redact(exc)},
                    )
                )

        return proposals

    # ----------------------------------------------------------------
    # 3. CODE QUALITY
    # ----------------------------------------------------------------

    async def diagnose_code_quality(self) -> List[ImprovementProposal]:
        """Silent except, katta fayllar, va boshqa code quality muammolarini topadi."""
        proposals: List[ImprovementProposal] = []

        if not self._src_root.exists():
            return proposals

        silent_excepts: List[Dict[str, Any]] = []

        for py_file in self._src_root.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()
            except Exception:
                logger.error("Exception handled in %s", __name__, exc_info=True)
                continue

            rel_path = str(py_file.relative_to(self.project_root))

            # -- 3a. Silent except blocks --
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped in (
                    "except Exception:",
                    "except Exception as e:",
                    "except:",
                ):
                    # Check if next non-empty line is pass or ...
                    for j in range(i, min(i + 3, len(lines))):
                        next_line = lines[j].strip()
                        if not next_line:
                            continue
                        if next_line in ("pass", "..."):
                            silent_excepts.append(
                                {
                                    "file": rel_path,
                                    "line": i,
                                    "code": stripped,
                                }
                            )
                            break
                        break

        # Group silent excepts
        if silent_excepts:
            by_file: Dict[str, int] = {}
            for se in silent_excepts:
                by_file[se["file"]] = by_file.get(se["file"], 0) + 1

            top_files = sorted(by_file.items(), key=lambda x: -x[1])[:5]
            desc_parts = [f"{f}: {c} ta" for f, c in top_files]

            proposals.append(
                ImprovementProposal(
                    id=self._next_id(),
                    category=CATEGORY_CODE,
                    severity=SEVERITY_MEDIUM,
                    title=f"Silent except: {len(silent_excepts)} ta topildi",
                    problem=(
                        f"Loyihada {len(silent_excepts)} ta `except: pass` mavjud. "
                        f"Xatoliklar yashirinmoqda. Top fayllar: {', '.join(desc_parts)}"
                    ),
                    proposed_solution=(
                        "Har bir `except: pass` ni `except Exception as e: logger.warning(...)` "
                        "bilan almashtiring. Xatolik loglanishi kerak."
                    ),
                    affected_files=[f for f, _ in top_files],
                    estimated_effort="2h",
                    suggested_agent="Code Quality",
                    evidence={"total": len(silent_excepts), "by_file": by_file},
                )
            )

        return proposals

    # ----------------------------------------------------------------
    # 4. FEATURE GAP DETECTION
    # ----------------------------------------------------------------

    async def diagnose_feature_gaps(self) -> List[ImprovementProposal]:
        """Mavjud handler/scheduler/command larni tahlil qilib, yetishmayotganlarni aniqlaydi."""
        proposals: List[ImprovementProposal] = []

        # -- 4a. Check broken imports in known patterns --
        # Look for files that import from moved locations
        moved_modules = {
            "src.services.core.amocrm_sync": "src.services.core.crm.amocrm_sync",
            "src.services.core.crm_file_offloader": "src.services.core.crm.crm_file_offloader",
        }
        for old_path, new_path in moved_modules.items():
            old_import = f"from {old_path} import"
            matches = []
            if self._src_root.exists():
                for py_file in self._src_root.rglob("*.py"):
                    if "__pycache__" in str(py_file):
                        continue
                    try:
                        content = py_file.read_text(encoding="utf-8", errors="replace")
                        if old_import in content:
                            rel = str(py_file.relative_to(self.project_root))
                            matches.append(rel)
                    except Exception:
                        logger.error("Exception handled in %s", __name__, exc_info=True)
                        continue

            if matches:
                proposals.append(
                    ImprovementProposal(
                        id=self._next_id(),
                        category=CATEGORY_FEATURE,
                        severity=SEVERITY_HIGH,
                        title=f"Eskirgan import: {old_path.rsplit('.', 1)[-1]}",
                        problem=(
                            f"{len(matches)} ta faylda eskirgan import bor: `{old_path}`. "
                            f"Modul `{new_path}` ga ko'chirilgan."
                        ),
                        proposed_solution=f"Barcha `{old_import}` → `from {new_path} import` ga o'zgartiring.",
                        affected_files=matches,
                        estimated_effort="30min",
                        suggested_agent="Coordinator",
                        evidence={"old": old_path, "new": new_path, "files": matches},
                    )
                )

        # -- 4b. Implemented roadmap modules that are not connected to runtime --
        capability_modules = (
            (
                "AI Voice Agent",
                "src/services/core/voice_agent.py",
                "src.services.core.voice_agent",
                "AmoCRM webhookdan VoiceAgent chaqiruvini ulang va feature flag bilan boshqaring.",
                "Integration",
            ),
            (
                "Case Study Publisher",
                "src/services/core/sanity_publisher.py",
                "src.services.core.sanity_publisher",
                "Yakunlangan AmoCRM loyiha hodisasini SanityPublisher ga ulang.",
                "Integration",
            ),
            (
                "Predictive LTV",
                "src/services/core/ltv_trainer.py",
                "src.services.core.ltv_trainer",
                "LTV train scheduleri va yangi lead scoring hookini runtimega ulang.",
                "Data/ML",
            ),
            (
                "Edge Personalization",
                "src/services/edge/edge_personalizer.py",
                "src.services.edge.edge_personalizer",
                "Segment endpointini API yoki Worker event oqimiga ulang va deploy holatini kuzating.",
                "Performance",
            ),
        )
        for name, rel_path, module_path, solution, agent in capability_modules:
            module_file = self.project_root / rel_path
            if not module_file.exists():
                continue
            references: List[str] = []
            import_markers = (f"from {module_path} import", f"import {module_path}")
            for py_file in self._src_root.rglob("*.py"):
                if py_file.resolve() == module_file.resolve() or "__pycache__" in str(
                    py_file
                ):
                    continue
                try:
                    content = py_file.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                if any(marker in content for marker in import_markers):
                    references.append(str(py_file.relative_to(self.project_root)))
            if not references:
                proposals.append(
                    ImprovementProposal(
                        id=self._next_id(),
                        category=CATEGORY_FEATURE,
                        severity=SEVERITY_MEDIUM,
                        title=f"Runtimega ulanmagan: {name}",
                        problem=(
                            f"{rel_path} implement qilingan, ammo src runtime ichida "
                            "uni ishga tushiradigan import/hook topilmadi."
                        ),
                        proposed_solution=solution,
                        affected_files=[rel_path],
                        estimated_effort="4h",
                        suggested_agent=agent,
                        evidence={"runtime_references": references},
                    )
                )

        return proposals

    # ----------------------------------------------------------------
    # 5. PERFORMANCE AUDIT (lightweight, no profiling)
    # ----------------------------------------------------------------

    async def diagnose_performance(self) -> List[ImprovementProposal]:
        """Og'ir fayllar, ortiqcha import, va boshqa performance muammolarini topadi."""
        proposals: List[ImprovementProposal] = []

        # Check for very large Python files that might cause slow imports
        if self._src_root.exists():
            huge_files = []
            for py_file in self._src_root.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                size = py_file.stat().st_size
                if size > 50_000:  # > 50KB
                    rel = str(py_file.relative_to(self.project_root))
                    huge_files.append({"file": rel, "size_kb": size // 1024})

            if huge_files:
                huge_files.sort(key=lambda x: -x["size_kb"])
                proposals.append(
                    ImprovementProposal(
                        id=self._next_id(),
                        category=CATEGORY_PERF,
                        severity=SEVERITY_MEDIUM,
                        title=f"{len(huge_files)} ta og'ir fayl (>50KB)",
                        problem=(
                            "Katta Python fayllar import vaqtini oshiradi va xotirani ko'p sarflaydi. "
                            + ", ".join(
                                f"{hf['file']}({hf['size_kb']}KB)"
                                for hf in huge_files[:3]
                            )
                        ),
                        proposed_solution="Fayllarni kichik modullarga ajrating. Lazy import qo'llang.",
                        affected_files=[hf["file"] for hf in huge_files],
                        estimated_effort="4h",
                        suggested_agent="Performance",
                        evidence={"files": huge_files},
                    )
                )

        return proposals

