"""
Self-Evolution Engine — Oisha o'zi kod yozib GitHub PR ochadi.

Loop:
  1. Weekly: learning_journal'dan top lessons → generate prompt improvements
  2. AI generates new prompt/strategy code
  3. Creates branch + PR → owner approve qilganda merge bo'ladi
  4. Merge → auto-deploy (Oracle workflow orqali)

Xavfsizlik:
  - Faqat prompt/strategiya fayllarini o'zgartiradi (src/services/core/persona_hub.py, negotiation_engine.py)
  - Kod logikasini O'ZGARTIRMAYDI
  - PR description'da nima o'zgarganini tushuntiradi
  - Owner approve qilmasdan hech narsa deploy bo'lmaydi
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional

from google import genai

from src.database import Database
from src.settings import settings
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)

EVOLUTION_PROMPT = """Siz AI agent'ning self-improvement moduli siz.

Quyidagi o'rganilgan darslar va strategiyalar asosida, prompt/strategiya yaxshilanishini taklif qiling.

DARSLAR (oxirgi hafta):
{lessons}

HOZIRGI STRATEGIYALAR:
{current_strategies}

HOZIRGI PROMPT FRAGMENTI:
{current_prompt_fragment}

METRIKALAR:
- O'rtacha javob sifati: {avg_quality}
- Lead conversion rate: {conversion_rate}
- Eng ko'p muammo: {top_issue}

Vazifa: Promptni yaxshilang. Quyidagi formatda javob bering:

```json
{{
  "changes": [
    {{
      "file": "persona_hub.py yoki negotiation_engine.py",
      "section": "qaysi qismini o'zgartirish",
      "old_text": "eski matn (exact match)",
      "new_text": "yangi matn",
      "reason": "nima uchun o'zgartirildi"
    }}
  ],
  "pr_title": "qisqa sarlavha",
  "pr_body": "tushuntirish"
}}
```

QOIDALAR:
1. Faqat prompt matnlarini o'zgartiring — kod logikasini TEGMANG
2. O'zgarishlar kichik va aniq bo'lsin
3. Har bir o'zgarish sababini yozing
4. Agar yaxshilanish kerak emas deb hisoblasangiz, bo'sh changes qaytaring
"""

SAFE_FILES = [
    "src/services/core/persona_hub.py",
    "src/services/core/negotiation_engine.py",
]


class SelfEvolutionEngine:
    """AI-driven prompt evolution with GitHub PR workflow."""

    def __init__(self, db: Database, gemini_api_key: str):
        self.db = db
        self.client = genai.Client(api_key=gemini_api_key)
        self.model = os.getenv("GEMINI_SELF_EVOLUTION_MODEL", settings.GEMINI_CALL_MODEL)
        self.repo_dir = os.environ.get("OISHA_REPO_DIR", "/home/ubuntu/oisha-os")
        self.github_token = os.environ.get("GITHUB_TOKEN", "")

    async def propose_evolution(self) -> Optional[Dict[str, Any]]:
        """Darslar asosida prompt yaxshilanishini taklif qilish."""
        lessons = await self._get_recent_lessons()
        if len(lessons) < 3:
            logger.info("[EVOLVE] Not enough lessons yet for evolution")
            return None

        strategies = await self._get_current_strategies()
        metrics = await self._get_metrics_summary()
        current_prompt = self._read_current_prompt()

        prompt = EVOLUTION_PROMPT.format(
            lessons=json.dumps(lessons, ensure_ascii=False, indent=2),
            current_strategies=json.dumps(strategies, ensure_ascii=False, indent=2),
            current_prompt_fragment=current_prompt[:2000],
            avg_quality=metrics.get("avg_quality", "N/A"),
            conversion_rate=metrics.get("conversion_rate", "N/A"),
            top_issue=metrics.get("top_issue", "N/A"),
        )

        try:
            from src.utils.ai_utils import safe_ai_call
            response = await safe_ai_call(
                client=self.client,
                prompt=[prompt],
                system_instruction="Faqat valid JSON qaytaring. Kod logikasini o'zgartirmang.",
                model=self.model,
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            proposal = json.loads(text)
            if not proposal.get("changes"):
                logger.info("[EVOLVE] AI decided no changes needed")
                return None

            for change in proposal["changes"]:
                if not self._is_safe_file(change.get("file", "")):
                    logger.warning(f"[EVOLVE] Unsafe file rejected: {change.get('file')}")
                    proposal["changes"] = [
                        c for c in proposal["changes"]
                        if self._is_safe_file(c.get("file", ""))
                    ]

            if not proposal["changes"]:
                return None

            logger.info(f"[EVOLVE] Proposed {len(proposal['changes'])} changes")
            return proposal

        except Exception as exc:
            logger.warning(f"[EVOLVE] Evolution proposal failed: {exc}")
            return None

    async def create_evolution_pr(self, proposal: Dict[str, Any]) -> Optional[str]:
        """Taklif asosida GitHub PR ochish."""
        if not self.github_token:
            logger.warning("[EVOLVE] No GITHUB_TOKEN — cannot create PR")
            return None

        if not proposal.get("changes"):
            return None

        branch_name = f"oisha/auto-evolve-{get_local_now().strftime('%Y%m%d-%H%M')}"

        try:
            self._git_cmd(["checkout", "-b", branch_name])

            for change in proposal["changes"]:
                file_path = os.path.join(self.repo_dir, change["file"])
                if not os.path.exists(file_path):
                    continue

                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                old_text = change.get("old_text", "")
                new_text = change.get("new_text", "")
                if old_text and old_text in content:
                    content = content.replace(old_text, new_text, 1)
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)

            self._git_cmd(["add", "-A"])

            commit_msg = f"feat(ai): self-evolve — {proposal.get('pr_title', 'prompt improvement')}"
            self._git_cmd(["commit", "-m", commit_msg])
            self._git_cmd(["push", "-u", "origin", branch_name])

            pr_url = self._create_pr(
                branch=branch_name,
                title=proposal.get("pr_title", "AI Self-Evolution"),
                body=self._format_pr_body(proposal),
            )

            self._git_cmd(["checkout", "main"])
            logger.info(f"[EVOLVE] PR created: {pr_url}")
            return pr_url

        except Exception as exc:
            logger.error(f"[EVOLVE] PR creation failed: {exc}")
            try:
                self._git_cmd(["checkout", "main"])
            except Exception:
                pass
            return None

    def _is_safe_file(self, file_path: str) -> bool:
        normalized = file_path.replace("\\", "/")
        return any(normalized.endswith(safe) or normalized == safe for safe in SAFE_FILES)

    def _git_cmd(self, args: List[str]) -> str:
        result = subprocess.run(
            ["git"] + args,
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
        return result.stdout.strip()

    def _create_pr(self, branch: str, title: str, body: str) -> str:
        result = subprocess.run(
            ["gh", "pr", "create", "--title", title, "--body", body, "--base", "main", "--head", branch],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"gh pr create failed: {result.stderr}")
        return result.stdout.strip()

    def _format_pr_body(self, proposal: Dict[str, Any]) -> str:
        lines = [
            "## AI Self-Evolution PR",
            "",
            proposal.get("pr_body", "Prompt yaxshilanishi"),
            "",
            "### O'zgarishlar:",
            "",
        ]
        for change in proposal.get("changes", []):
            lines.append(f"- **{change.get('file')}** ({change.get('section', '')})")
            lines.append(f"  Sabab: {change.get('reason', '')}")
            lines.append("")

        lines.extend([
            "---",
            "🤖 Bu PR Oisha Self-Evolution Engine tomonidan avtomatik yaratilgan.",
            "Owner approve qilganda deploy bo'ladi.",
        ])
        return "\n".join(lines)

    def _read_current_prompt(self) -> str:
        for safe_file in SAFE_FILES:
            path = os.path.join(self.repo_dir, safe_file)
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return f.read()
                except Exception:
                    continue
        return ""

    async def _get_recent_lessons(self) -> List[Dict[str, Any]]:
        async with await self.db.get_connection() as conn:
            rows = await conn.execute(
                """SELECT pattern, lesson, strategy, confidence, category
                   FROM learning_journal
                   WHERE confidence > 0.4
                   ORDER BY created_at DESC
                   LIMIT 20"""
            )
            return [
                {"pattern": r[0], "lesson": r[1], "strategy": r[2], "confidence": r[3], "category": r[4]}
                for r in await rows.fetchall()
            ]

    async def _get_current_strategies(self) -> List[Dict[str, Any]]:
        async with await self.db.get_connection() as conn:
            rows = await conn.execute(
                """SELECT rule, trigger_condition, weight, success_count, applied_count
                   FROM strategy_rules WHERE active = 1
                   ORDER BY weight DESC LIMIT 10"""
            )
            return [
                {"rule": r[0], "when": r[1], "weight": r[2], "success": r[3], "applied": r[4]}
                for r in await rows.fetchall()
            ]

    async def _get_metrics_summary(self) -> Dict[str, Any]:
        async with await self.db.get_connection() as conn:
            quality_row = await conn.execute(
                """SELECT AVG(metric_value) FROM learning_metrics
                   WHERE metric_type = 'response_quality'
                   AND recorded_at > datetime('now', '-7 days')"""
            )
            avg_q = await quality_row.fetchone()

            conversion_row = await conn.execute(
                """SELECT AVG(metric_value) FROM learning_metrics
                   WHERE metric_type = 'lead_conversion'
                   AND recorded_at > datetime('now', '-7 days')"""
            )
            avg_c = await conversion_row.fetchone()

        return {
            "avg_quality": f"{(avg_q[0] or 0):.1f}/10" if avg_q else "N/A",
            "conversion_rate": f"{(avg_c[0] or 0)*100:.0f}%" if avg_c else "N/A",
            "top_issue": "data insufficient",
        }
