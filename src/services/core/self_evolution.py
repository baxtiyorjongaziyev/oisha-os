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
import structlog
import os
import subprocess
import ast
from pathlib import Path
from typing import Any, Dict, List, Optional

from google import genai

from src.database import Database
from src.settings import settings
from src.time_utils import get_local_now

logger = structlog.get_logger()

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

    def __init__(self, db: Database, gemini_api_key: str = "", router: Any = None):
        self.db = db
        self.client = genai.Client(api_key=gemini_api_key) if gemini_api_key else None
        self.model = os.getenv(
            "GEMINI_SELF_EVOLUTION_MODEL", settings.GEMINI_CALL_MODEL
        )
        self.repo_dir = os.environ.get("OISHA_REPO_DIR", "/home/deploy/oisha-os")
        self.github_token = os.environ.get("GITHUB_TOKEN", "")
        self._router = router

    async def _generate_evolution_json(self, prompt: str) -> Optional[Dict[str, Any]]:
        raw_text = ""
        system_inst = "Faqat valid JSON qaytaring. Kod logikasini oʻzgartirmang."
        if self._router is None and self.client is not None:
            try:
                from src.utils.ai_utils import safe_ai_call

                response = await safe_ai_call(
                    client=self.client,
                    prompt=[prompt],
                    system_instruction=system_inst,
                    model=self.model,
                )
                raw_text = getattr(response, "text", "") or ""
            except Exception as exc:
                logger.debug("[EVOLVE] safe_ai_call fallback to free router: %s", exc)
        if not raw_text.strip():
            from src.services.utils.free_ai_router import get_free_ai_router

            router = self._router or get_free_ai_router()
            res = await router.generate_text(
                prompt, system=system_inst, max_tokens=1000, temperature=0.2
            )
            raw_text = getattr(res, "text", "") or ""
        text = raw_text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None
        parsed = json.loads(text[start : end + 1])
        return parsed if isinstance(parsed, dict) else None

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
            proposal = await self._generate_evolution_json(prompt)
            if not proposal or not proposal.get("changes"):
                logger.info("[EVOLVE] AI decided no changes needed")
                return None

            proposal["changes"] = [
                c
                for c in proposal["changes"]
                if isinstance(c, dict) and self._is_safe_file(c.get("file", ""))
            ]
            if not proposal["changes"]:
                return None

            logger.info(f"[EVOLVE] Proposed {len(proposal['changes'])} changes")
            return proposal

        except Exception as exc:
            logger.warning(f"[EVOLVE] Evolution proposal failed: {exc}")
            return None

    def _apply_safe_changes(self, changes: List[Dict[str, Any]]) -> List[str]:
        changed_files: List[str] = []
        root = Path(self.repo_dir).resolve()
        for change in changes:
            file_path = self._resolve_safe_file(change.get("file", ""))
            if file_path is None or not file_path.exists():
                continue
            content = file_path.read_text(encoding="utf-8")
            old_text, new_text = change.get("old_text", ""), change.get("new_text", "")
            if isinstance(old_text, str) and isinstance(new_text, str) and old_text and old_text in content:
                updated = content.replace(old_text, new_text, 1)
                ast.parse(updated, filename=str(file_path))
                file_path.write_text(updated, encoding="utf-8")
                changed_files.append(str(file_path.relative_to(root)))
        return changed_files

    async def create_evolution_pr(self, proposal: Dict[str, Any]) -> Optional[str]:
        """Create a review PR after an explicit owner-approved call."""
        if not self.github_token or not proposal.get("changes"):
            if not self.github_token:
                logger.warning("[EVOLVE] No GITHUB_TOKEN — cannot create PR")
            return None

        branch_name = f"oisha/auto-evolve-{get_local_now().strftime('%Y%m%d-%H%M')}"
        changed_files: List[str] = []
        try:
            if self._git_cmd(["status", "--porcelain"]):
                logger.warning("[EVOLVE] Dirty repository — PR creation blocked")
                return None
            self._git_cmd(["checkout", "-b", branch_name])
            changed_files = self._apply_safe_changes(proposal["changes"])
            if not changed_files:
                self._git_cmd(["checkout", "main"])
                return None
            self._git_cmd(["add", "--", *changed_files])
            self._git_cmd(["commit", "-m", f"feat(ai): self-evolve — {proposal.get('pr_title', 'prompt improvement')}"])
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
                if changed_files:
                    self._git_cmd(["restore", "--staged", "--worktree", "--", *changed_files])
                self._git_cmd(["checkout", "main"])
            except Exception:
                logger.debug("[EVOLVE] Failed to checkout main after error", exc_info=True)
            return None

    def _resolve_safe_file(self, file_path: str) -> Optional[Path]:
        if not file_path or not isinstance(file_path, str):
            return None
        repo_root = Path(self.repo_dir).resolve()
        allowed = {(repo_root / safe).resolve() for safe in SAFE_FILES}
        normalized = file_path.replace("\\", "/")
        if "/" not in normalized:
            basename_matches = [path for path in allowed if path.name == normalized]
            return basename_matches[0] if len(basename_matches) == 1 else None
        candidate = (repo_root / normalized).resolve()
        if candidate not in allowed:
            return None
        return candidate

    def _is_safe_file(self, file_path: str) -> bool:
        return self._resolve_safe_file(file_path) is not None

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
            [
                "gh",
                "pr",
                "create",
                "--title",
                title,
                "--body",
                body,
                "--base",
                "main",
                "--head",
                branch,
            ],
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

        lines.extend(
            [
                "---",
                "🤖 Bu PR Oisha Self-Evolution Engine tomonidan avtomatik yaratilgan.",
                "Owner approve qilganda deploy bo'ladi.",
            ]
        )
        return "\n".join(lines)

    def _read_current_prompt(self) -> str:
        for safe_file in SAFE_FILES:
            path = os.path.join(self.repo_dir, safe_file)
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return f.read()
                except Exception:
                    logger.error("Exception handled in %s", __name__, exc_info=True)
                    continue
        return ""

    @staticmethod
    def _row_val(row: Any, key: str, idx: int) -> Any:
        if isinstance(row, dict) or hasattr(row, "keys"):
            try:
                return row[key]
            except (KeyError, IndexError, TypeError):
                pass
        return row[idx]

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
                {
                    "pattern": self._row_val(r, "pattern", 0),
                    "lesson": self._row_val(r, "lesson", 1),
                    "strategy": self._row_val(r, "strategy", 2),
                    "confidence": self._row_val(r, "confidence", 3),
                    "category": self._row_val(r, "category", 4),
                }
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
                {
                    "rule": self._row_val(r, "rule", 0),
                    "when": self._row_val(r, "trigger_condition", 1),
                    "weight": self._row_val(r, "weight", 2),
                    "success": self._row_val(r, "success_count", 3),
                    "applied": self._row_val(r, "applied_count", 4),
                }
                for r in await rows.fetchall()
            ]

    async def _get_metrics_summary(self) -> Dict[str, Any]:
        async with await self.db.get_connection() as conn:
            quality_row = await conn.execute(
                """SELECT AVG(metric_value) AS val FROM learning_metrics
                   WHERE metric_type = 'response_quality'
                   AND recorded_at > datetime('now', '-7 days')"""
            )
            avg_q = await quality_row.fetchone()

            conversion_row = await conn.execute(
                """SELECT AVG(metric_value) AS val FROM learning_metrics
                   WHERE metric_type = 'lead_conversion'
                   AND recorded_at > datetime('now', '-7 days')"""
            )
            avg_c = await conversion_row.fetchone()

        q_val = self._row_val(avg_q, "val", 0) if avg_q else None
        c_val = self._row_val(avg_c, "val", 0) if avg_c else None
        return {
            "avg_quality": f"{(q_val or 0):.1f}/10" if avg_q else "N/A",
            "conversion_rate": f"{(c_val or 0) * 100:.0f}%" if avg_c else "N/A",
            "top_issue": "data insufficient",
        }
