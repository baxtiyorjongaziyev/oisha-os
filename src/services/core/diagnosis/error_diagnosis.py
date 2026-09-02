"""
Error log analysis, pattern matching, root-cause deduction, and fix suggestions mixin.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any, List

from src.services.core.diagnosis.models import (
    CATEGORY_ERROR,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    _SECRET_PATTERNS,
    ImprovementProposal,
)

logger = logging.getLogger("OishaSelfDiagnosis")


class ErrorDiagnosisMixin:
    """Handles error log auditing and automated diagnosis proposal creation."""

    def _next_id(self) -> str:
        self._counter += 1
        return f"TEMP-{self._counter:03d}"

    async def _get_connection(self):
        if not self.db:
            raise RuntimeError("database is not configured")
        getter = getattr(self.db, "get_connection", None)
        if getter is not None:
            return await getter()
        manager = getattr(self.db, "conn_manager", None)
        if manager is None:
            raise RuntimeError("database connection factory is unavailable")
        return await manager.get_connection()

    @staticmethod
    def _redact(value: Any, limit: int = 500) -> str:
        text = str(value or "")
        for pattern in _SECRET_PATTERNS:
            text = pattern.sub(
                lambda match: (
                    f"{match.group(1)}{match.group(2)}[REDACTED]"
                    if match.lastindex and match.lastindex >= 2
                    else "[REDACTED]"
                ),
                text,
            )
        return text[:limit]

    @staticmethod
    def _stable_id(proposal: ImprovementProposal) -> str:
        normalized_title = re.sub(r"\d+", "#", proposal.title.casefold())
        seed = {
            "category": proposal.category,
            "title": normalized_title,
            "files": sorted(
                path.replace("\\", "/") for path in proposal.affected_files
            ),
            "agent": proposal.suggested_agent,
        }
        digest = (
            hashlib.sha256(
                json.dumps(seed, ensure_ascii=False, sort_keys=True).encode("utf-8")
            )
            .hexdigest()[:12]
            .upper()
        )
        return f"DIAG-{digest}"

    # ----------------------------------------------------------------
    # 1. ERROR ANALYSIS
    # ----------------------------------------------------------------

    async def diagnose_errors(self) -> List[ImprovementProposal]:
        """agent_actions jadvalidagi so'nggi muvaffaqiyatsiz ishlarni tahlil qiladi."""
        proposals: List[ImprovementProposal] = []
        if not self.db:
            return proposals

        try:
            conn = await self._get_connection()
            cursor = await conn.execute(
                """
                SELECT action_type, action_data, COUNT(*) as cnt
                FROM agent_actions
                WHERE success = 0
                  AND created_at > datetime('now', '-24 hours')
                GROUP BY action_type, action_data
                ORDER BY cnt DESC
                LIMIT 10
                """,
            )
            rows = await cursor.fetchall()

            for row in rows:
                if isinstance(row, dict):
                    action_type = row.get("action_type") or "unknown"
                    raw_data = row.get("action_data")
                    count = int(row.get("cnt") or 0)
                else:
                    action_type = row[0] or "unknown"
                    raw_data = row[1]
                    count = int(row[2] or 0)

                try:
                    action_data = (
                        json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                    )
                except (json.JSONDecodeError, TypeError):
                    action_data = raw_data
                if isinstance(action_data, dict):
                    nested = action_data.get("data")
                    error_msg = (
                        action_data.get("error_message")
                        or action_data.get("error")
                        or action_data.get("reason")
                        or (nested.get("error") if isinstance(nested, dict) else None)
                        or json.dumps(action_data, ensure_ascii=False)
                    )
                else:
                    error_msg = action_data or "Xato tafsiloti yozilmagan"
                error_msg = self._redact(error_msg)

                severity = SEVERITY_HIGH if count >= 5 else SEVERITY_MEDIUM
                if "ImportError" in error_msg or "ModuleNotFound" in error_msg:
                    severity = SEVERITY_CRITICAL

                proposals.append(
                    ImprovementProposal(
                        id=self._next_id(),
                        category=CATEGORY_ERROR,
                        severity=severity,
                        title=f"{action_type} xatosi ({count}x)",
                        problem=f"So'nggi 24 soatda {count} marta xato: {error_msg[:200]}",
                        proposed_solution=await self._get_root_cause_and_solution(error_msg),
                        affected_files=self._guess_files_from_error(error_msg),
                        estimated_effort="30min"
                        if severity == SEVERITY_CRITICAL
                        else "1h",
                        suggested_agent=self._suggest_agent_for_error(error_msg),
                        evidence={"count": count, "error_sample": error_msg},
                    )
                )

        except Exception as exc:
            logger.warning("[SELF-DIAG] Error analysis failed: %s", exc)

        return proposals

    def _suggest_error_fix(self, error_msg: str) -> str:
        if "ModuleNotFound" in error_msg or "ImportError" in error_msg:
            module = re.search(r"No module named '([^']+)'", error_msg)
            mod_name = module.group(1) if module else "unknown"
            return f"Import yo'lini tekshirish: {mod_name}. Fayl ko'chirilgan yoki qayta nomlangan bo'lishi mumkin."
        if "AuthKeyDuplicated" in error_msg:
            return "Telegram userbot session buzilgan. Yangi session string generatsiya qiling."
        if "NoneType" in error_msg:
            return "Ob'ekt None bo'lib qolmoqda — initialization tartibini tekshiring."
        if "timeout" in error_msg.lower():
            return "API so'rov vaqti tugadi — retry logic qo'shing yoki timeout limitini oshiring."
        return "Xatolik logini ko'rib chiqing va tegishli modulda fix qiling."

    async def _get_root_cause_and_solution(self, error_msg: str) -> str:
        base_solution = self._suggest_error_fix(error_msg)
        if not self._gemini_api_key:
            return base_solution
            
        try:
            import google.generativeai as genai
            genai.configure(api_key=self._gemini_api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = f"Ushbu xatolikning ildiz sababi (root cause) nima bo'lishi mumkin va qanday yechim taklif qilasan? 1-2 ta qisqa gap bilan yozing:\n\n{error_msg[:1000]}"
            response = await model.generate_content_async(prompt)
            root_cause = response.text.strip() if response.text else ""
            if root_cause:
                return f"🤖 AI Root Cause:\n{root_cause}\n\nStandart tavsiya: {base_solution}"
        except Exception as e:
            logger.warning("[SELF-DIAG] Gemini root cause failed: %s", e)
        return base_solution

    def _guess_files_from_error(self, error_msg: str) -> List[str]:
        files = re.findall(r'File "([^"]+)"', error_msg)
        if not files:
            # Try module path
            mod = re.search(r"No module named '([^']+)'", error_msg)
            if mod:
                return [mod.group(1).replace(".", "/") + ".py"]
        return [f for f in files if "site-packages" not in f][:3]

    def _suggest_agent_for_error(self, error_msg: str) -> str:
        if "import" in error_msg.lower() or "module" in error_msg.lower():
            return "Coordinator"
        if "auth" in error_msg.lower() or "session" in error_msg.lower():
            return "Security"
        if "amocrm" in error_msg.lower() or "airtable" in error_msg.lower():
            return "Integration"
        return "Parser"

