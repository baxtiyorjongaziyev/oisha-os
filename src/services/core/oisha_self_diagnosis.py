"""Oisha Self-Diagnosis Engine — O'zini o'zi tahlil qilib, taklif beradigan tizim.

Har kuni avtomatik ravishda 5 ta yo'nalishda tekshiruv o'tkazadi:
1. Error Analysis — Log xatoliklarni guruhlab tahlil qilish
2. Health Check — API/DB/Telegram holatini tekshirish
3. Feature Gap Detection — Yetishmayotgan funksiyalarni aniqlash
4. Code Quality — Dead code, silent exceptions
5. Performance — Og'ir fayllar, sekin joylar

Har bir topilgan muammo ImprovementProposal sifatida saqlanadi va
Telegram orqali owner/jamoaga yuboriladi.
"""

import hashlib
import html
import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.time_utils import get_local_now

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ImprovementProposal:
    """Bir taklif — muammo + yechim + meta."""

    id: str  # "DIAG-2026-07-15-001"
    category: str  # error_fix | health | feature_gap | code_quality | performance
    severity: str  # critical | high | medium | low
    title: str  # Qisqa sarlavha
    problem: str  # Muammo tavsifi
    proposed_solution: str  # Yechim taklifi
    affected_files: List[str] = field(default_factory=list)
    estimated_effort: str = "1h"  # 15min | 30min | 1h | 4h | 1d
    suggested_agent: str = "Coordinator"
    evidence: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    status: str = (
        "proposed"  # proposed | accepted | in_progress | done | rejected | deferred
    )
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    rejection_reason: Optional[str] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = get_local_now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ImprovementProposal":
        data = dict(data)
        # Handle JSON string fields
        if isinstance(data.get("affected_files"), str):
            try:
                data["affected_files"] = json.loads(data["affected_files"])
            except (json.JSONDecodeError, TypeError):
                data["affected_files"] = []
        if isinstance(data.get("evidence"), str):
            try:
                data["evidence"] = json.loads(data["evidence"])
            except (json.JSONDecodeError, TypeError):
                data["evidence"] = {}
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Severity & category constants
# ---------------------------------------------------------------------------

SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"

SEVERITY_EMOJI = {
    SEVERITY_CRITICAL: "🔴",
    SEVERITY_HIGH: "🟡",
    SEVERITY_MEDIUM: "🔵",
    SEVERITY_LOW: "⚪",
}

CATEGORY_ERROR = "error_fix"
CATEGORY_HEALTH = "health"
CATEGORY_FEATURE = "feature_gap"
CATEGORY_CODE = "code_quality"
CATEGORY_PERF = "performance"

_SECRET_PATTERNS = (
    re.compile(r"(?i)(token|secret|password|api[_-]?key)(\s*[:=]\s*)\S+"),
    re.compile(r"\b\d{9,12}:[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/-]+=*"),
)


# ---------------------------------------------------------------------------
# Main diagnosis engine
# ---------------------------------------------------------------------------


class OishaSelfDiagnosis:
    """Oishaning ichki diagnostika tizimi.

    Har bir ``diagnose_*`` metodi ``ImprovementProposal`` ro'yxati qaytaradi.
    ``run_full_diagnosis`` barchasini birlashtiradi.
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

    # -- helpers --

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
                        proposed_solution=self._suggest_error_fix(error_msg),
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

    # ----------------------------------------------------------------
    # 2. HEALTH CHECK
    # ----------------------------------------------------------------

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

    # ----------------------------------------------------------------
    # FULL DIAGNOSIS
    # ----------------------------------------------------------------

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

    # ----------------------------------------------------------------
    # TELEGRAM REPORT FORMATTING
    # ----------------------------------------------------------------

    @staticmethod
    def _field(proposal: Any, name: str, default: Any = "") -> Any:
        if isinstance(proposal, dict):
            return proposal.get(name, default)
        return getattr(proposal, name, default)

    @classmethod
    def format_telegram_report(cls, proposals: List[ImprovementProposal]) -> str:
        """Compact, HTML-safe daily digest for the owner."""
        if not proposals:
            return (
                "🧬 <b>OISHA RIVOJLANISH AUDITI</b>\n\n"
                "✅ Hozircha yangi muammo yoki imkoniyat topilmadi."
            )

        by_severity: Dict[str, List[ImprovementProposal]] = {}
        for proposal in proposals:
            severity = str(cls._field(proposal, "severity", SEVERITY_MEDIUM))
            by_severity.setdefault(severity, []).append(proposal)

        lines = [
            "🧬 <b>OISHA RIVOJLANISH AUDITI</b>",
            f"📊 <b>{len(proposals)}</b> ta dalilli taklif topildi.",
            "",
        ]
        shown = 0
        severity_labels = {
            SEVERITY_CRITICAL: "KRITIK",
            SEVERITY_HIGH: "YUQORI",
            SEVERITY_MEDIUM: "O'RTA",
            SEVERITY_LOW: "PAST",
        }
        for severity in (
            SEVERITY_CRITICAL,
            SEVERITY_HIGH,
            SEVERITY_MEDIUM,
            SEVERITY_LOW,
        ):
            items = by_severity.get(severity, [])
            if not items or shown >= 8:
                continue
            lines.append(
                f"{SEVERITY_EMOJI[severity]} <b>{severity_labels[severity]}</b> "
                f"({len(items)})"
            )
            for proposal in items[: 8 - shown]:
                proposal_id = html.escape(str(cls._field(proposal, "id")))
                title = html.escape(str(cls._field(proposal, "title"))[:100])
                agent = html.escape(str(cls._field(proposal, "suggested_agent"))[:40])
                effort = html.escape(str(cls._field(proposal, "estimated_effort"))[:20])
                lines.append(f"• <code>{proposal_id}</code> — {title}")
                lines.append(f"  🤖 {agent} · ⏱ {effort}")
                shown += 1
            lines.append("")

        hidden = len(proposals) - shown
        if hidden > 0:
            lines.append(f"Yana {hidden} ta taklif ro'yxatda.")
        lines.append("Qaror berish: /oisha_takliflar")
        return "\n".join(lines)[:3900]

    @classmethod
    def format_proposal_card(cls, proposal: Any) -> str:
        """Render one proposal for owner approval without leaking raw secrets."""
        proposal_id = html.escape(str(cls._field(proposal, "id")))
        title = html.escape(str(cls._field(proposal, "title"))[:160])
        problem = html.escape(str(cls._field(proposal, "problem"))[:700])
        solution = html.escape(str(cls._field(proposal, "proposed_solution"))[:700])
        agent = html.escape(str(cls._field(proposal, "suggested_agent"))[:80])
        effort = html.escape(str(cls._field(proposal, "estimated_effort"))[:40])
        severity = html.escape(str(cls._field(proposal, "severity", "medium")))
        files = cls._field(proposal, "affected_files", []) or []
        file_text = html.escape(", ".join(str(path) for path in files[:5])[:500])
        return (
            f"🧬 <b>{title}</b>\n"
            f"ID: <code>{proposal_id}</code> · {severity}\n\n"
            f"<b>Muammo:</b> {problem}\n\n"
            f"<b>Taklif:</b> {solution}\n\n"
            f"<b>Agent:</b> {agent} · <b>Vaqt:</b> {effort}\n"
            f"<b>Fayllar:</b> {file_text or 'aniqlanmagan'}"
        )[:3900]

    @staticmethod
    def format_weekly_summary(
        current_proposals: List[ImprovementProposal],
        resolved_count: int = 0,
        total_proposed: int = 0,
    ) -> str:
        """Haftalik progress hisoboti."""
        lines = [
            "📊 <b>OISHA WEEKLY EVOLUTION REPORT</b>",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"📥 Jami takliflar: <b>{total_proposed}</b>",
            f"✅ Hal qilingan: <b>{resolved_count}</b>",
            f"⏳ Kutilmoqda: <b>{len(current_proposals)}</b>",
            "",
        ]

        if total_proposed > 0:
            ratio = resolved_count / total_proposed * 100
            bar_filled = int(ratio / 10)
            bar = "█" * bar_filled + "░" * (10 - bar_filled)
            lines.append(f"📈 Progress: [{bar}] {ratio:.0f}%")

        # Open critical/high items
        urgent = [
            p
            for p in current_proposals
            if p.severity in (SEVERITY_CRITICAL, SEVERITY_HIGH)
        ]
        if urgent:
            lines.append("")
            lines.append(f"⚠️ <b>Ochiq urgent takliflar ({len(urgent)}):</b>")
            for p in urgent[:5]:
                lines.append(f"  • {p.title} ({p.suggested_agent})")

        return "\n".join(lines)
