"""Tool-calling AI Sales Chat engine over real call_analyses and leaderboard data.

Executes read-only analytical tools (call fetch, leaderboard, micro-checklist,
and seller stage-gap diagnosis), records every action for UI transparency
('> N ta amal bajarildi'), enforces RBAC seller isolation, and never fabricates
metrics when the database has no matching records.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence

from src.api.rbac import Principal, Role, scope_owned_rows
from src.services.core.metasell.checklist import evaluate_manager_checklist
from src.services.core.metasell.diagnostics import _most_common, diagnose_seller
from src.services.core.metasell.leaderboard import build_manager_leaderboard
from src.services.core.metasell.models import _row_get

logger = logging.getLogger(__name__)

_CHAT_COLUMNS = (
    "call_id",
    "lead_id",
    "manager_id",
    "manager_name",
    "client_name",
    "duration_seconds",
    "overall_score",
    "scores",
    "summary",
    "strengths",
    "weaknesses",
    "objections",
    "outcome",
    "converted",
    "lead_price",
    "lead_won",
    "breakdown_at",
    "breakdown_reason",
    "longest_pause_seconds",
    "next_steps",
    "analyzed_at",
    "created_at",
)

_SELECT_CHAT_WINDOW_SQL = (
    "SELECT call_id, lead_id, manager_id, manager_name, client_name, "
    "duration_seconds, overall_score, scores, summary, strengths, "
    "weaknesses, objections, outcome, converted, lead_price, lead_won, "
    "breakdown_at, breakdown_reason, longest_pause_seconds, next_steps, "
    "analyzed_at, created_at "
    "FROM call_analyses "
    "WHERE created_at >= datetime('now', ?) "
    "ORDER BY created_at DESC LIMIT 500"
)

_SYSTEM_PROMPT = (
    "Siz Jon Branding agentligining Oisha-OS AI Sotuv Tahlilchisisiz. "
    "FAQAT berilgan JSON faktlardagi haqiqiy raqam, menejer ismlari va foizlardan "
    "foydalanib javob bering. Hech qachon mavjud boʻlmagan raqam yoki ism toʻqimang. "
    "Javobni oʻzbek tilida aniq boʻlimlar (Kuchli tomonlari, Kuchsiz tomonlari, "
    "Eʼtirozlar va Tavsiya) bilan qisqa va tushunarli yozing."
)


def _norm_text(value: str) -> str:
    return re.sub(r"[ʻʼ`'\u2018\u2019]", "ʻ", (value or "").strip().lower())


def _parse_days_window(question: str, explicit_days: Optional[int] = None) -> tuple[int, str]:
    if explicit_days is not None and explicit_days > 0:
        clamped = max(1, min(int(explicit_days), 365))
        return clamped, f"oxirgi {clamped} kun"
    q = _norm_text(question)
    if any(w in q for w in ("bugun", "kecha", "24 soat")):
        return 2, "oxirgi 2 kun"
    if any(w in q for w in ("hafta", "7 kun")):
        return 7, "oxirgi 7 kun"
    if any(w in q for w in ("chorak", "90 kun", "uch oy")):
        return 90, "oxirgi 90 kun"
    if "oʻtgan oy" in q or "otgan oy" in q:
        return 30, "oxirgi 30 kun"
    return 30, "oxirgi 30 kun"


def _row_to_mapping(row: Any) -> Dict[str, Any]:
    if isinstance(row, Mapping):
        return dict(row)
    return {col: _row_get(row, col) for col in _CHAT_COLUMNS}


def _resolve_focus_manager(
    question: str,
    managers: Sequence[Dict[str, Any]],
    history: Sequence[Mapping[str, Any]],
) -> Optional[str]:
    if not managers:
        return None
    q = _norm_text(question)
    for mgr in managers:
        full_name = str(mgr.get("manager_name") or "").strip()
        if full_name and _norm_text(full_name) in q:
            return full_name
    for mgr in managers:
        full_name = str(mgr.get("manager_name") or "").strip()
        tokens = [t for t in _norm_text(full_name).split() if len(t) >= 4]
        if any(tok in q for tok in tokens):
            return full_name

    pronouns = ("uning", "unda", "u haqida", "shu sotuvchi", "shu menejer")
    if any(p in q for p in pronouns) and history:
        for turn in reversed(history):
            prev_mgr = str(turn.get("focus_manager") or "").strip()
            if prev_mgr and any(m["manager_name"] == prev_mgr for m in managers):
                return prev_mgr
            prev_text = _norm_text(str(turn.get("content") or ""))
            for mgr in managers:
                if _norm_text(mgr["manager_name"]) in prev_text:
                    return mgr["manager_name"]

    if any(w in q for w in ("faqat gaplash", "sotmayap", "0 sotuv", "eng kuchsiz")):
        talkers = [m for m in managers if m.get("diagnostic_tag") == "faqat_gaplashyapti"]
        return talkers[0]["manager_name"] if talkers else managers[-1]["manager_name"]

    if any(w in q for w in ("eng yaxshi", "yetakchi", "kim koʻp sot", "lider", "birinchi")):
        return managers[0]["manager_name"]
    return None


def _render_deterministic_answer(
    *,
    window_label: str,
    leaderboard: Dict[str, Any],
    focus_manager: Optional[str],
    checklist: Dict[str, Any],
    top_objections: Sequence[str],
    diagnosis_note: str,
) -> str:
    managers = leaderboard.get("managers") or []
    lines: List[str] = []
    if focus_manager:
        mgr_stats = next((m for m in managers if m["manager_name"] == focus_manager), None)
        if mgr_stats:
            lines.append(
                f"Tanlangan davrda ({window_label}) **{focus_manager}** koʻrsatkichlari: "
                f"**{mgr_stats['sales_count']} ta sotuv**, lid konversiyasi "
                f"**{mgr_stats['lead_conversion_pct']:.2f}%**, suhbat sifati "
                f"**{mgr_stats['call_quality_pct']:.2f}%**, oʻrtacha davomiylik "
                f"**{mgr_stats['avg_duration_label']}** ({mgr_stats['diagnostic_label']})."
            )
        else:
            lines.append(f"Tanlangan davrda ({window_label}) **{focus_manager}** tahlili:")
    else:
        leader = managers[0]
        talkers = [m["manager_name"] for m in managers if m["diagnostic_tag"] == "faqat_gaplashyapti"]
        lines.append(
            f"Tanlangan davrda ({window_label}) jamoa yetakchisi: **{leader['manager_name']}** "
            f"(**{leader['sales_count']} ta sotuv**, konversiya **{leader['lead_conversion_pct']:.2f}%**, "
            f"sifat **{leader['call_quality_pct']:.2f}%**)."
        )
        if talkers:
            lines.append(
                f"Faqat gaplashib sotuv yopmaganlar: **{', '.join(talkers[:3])}**."
            )

    strengths = checklist.get("strengths") or []
    if strengths:
        lines.append("\n**Kuchli tomonlari**")
        for item in strengths[:4]:
            lines.append(f"- **{item['title']} ({item['pct']:.0f}%)**: {item['description']}")

    weaknesses = checklist.get("weaknesses") or []
    if weaknesses:
        lines.append("\n**Kuchsiz tomonlari**")
        for item in weaknesses[:4]:
            lines.append(f"- **{item['title']} ({item['pct']:.0f}%)**: {item['description']}")

    if top_objections:
        lines.append(f"\n**Eng koʻp uchragan eʼtirozlar:** {', '.join(top_objections)}.")
    if diagnosis_note:
        lines.append(f"**Diagnostika:** {diagnosis_note}")
    return "\n".join(lines)


class MetasellSalesChatEngine:
    """Agentic tool-calling analytical chat over Oisha-OS call_analyses."""

    def __init__(self, db: Any, ai_router: Any = None) -> None:
        self.db = db
        self.ai_router = ai_router

    async def _fetch_rows(self, days: int, principal: Optional[Principal]) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        conn = await self.db.get_connection()
        result = conn.execute(_SELECT_CHAT_WINDOW_SQL, (f"-{int(days)} days",))
        if hasattr(result, "__await__"):
            result = await result
        rows = result.fetchall() if hasattr(result, "fetchall") else []
        if hasattr(rows, "__await__"):
            rows = await rows
        mapped = [_row_to_mapping(r) for r in (rows or [])]
        if principal and principal.role is Role.SELLER:
            return list(scope_owned_rows(principal, mapped, owner_field="manager_id"))
        return mapped

    async def _maybe_polish_with_llm(self, question: str, facts: Dict[str, Any], fallback: str) -> str:
        if self.ai_router is None:
            return fallback
        try:
            prompt = (
                f"Foydalanuvchi savoli: {question}\n\n"
                f"Tekshirilgan baza faktlari (JSON):\n"
                f"{json.dumps(facts, ensure_ascii=False)}\n\n"
                "Shu faktlar asosida javob bering."
            )
            res = await self.ai_router.generate_text(
                prompt,
                system=_SYSTEM_PROMPT,
                max_tokens=900,
                temperature=0.1,
            )
            cleaned = str(getattr(res, "text", "") or "").strip()
            return cleaned if cleaned else fallback
        except Exception as exc:
            logger.info("[SALES CHAT] LLM fallback to deterministic report: %s", exc)
            return fallback

    @staticmethod
    def _empty_reply(win_days: int, win_label: str, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "real_data": False,
            "window_days": win_days,
            "window_label": win_label,
            "actions_count": len(actions),
            "actions": actions,
            "focus_manager": None,
            "checklist": None,
            "leaderboard": [],
            "top_objections": [],
            "answer": (
                f"Tanlangan davrda ({win_label}) call_analyses bazasida baholangan "
                "qoʻngʻiroqlar topilmadi. Uydirma raqam ishlatilmadi."
            ),
        }

    def _run_analysis_tools(
        self,
        clean_q: str,
        rows: List[Dict[str, Any]],
        history: Sequence[Mapping[str, Any]],
        actions: List[Dict[str, Any]],
    ) -> tuple[Dict[str, Any], Optional[str], Dict[str, Any], List[str], str]:
        q_norm = _norm_text(clean_q)
        sort_mode = "sifat" if ("sifat" in q_norm and "sotuv" not in q_norm) else "natija"
        leaderboard = build_manager_leaderboard(rows, sort_by=sort_mode)
        managers = leaderboard["managers"]
        actions.append(
            {
                "tool": "build_manager_leaderboard",
                "label": f"Menejerlar reytingi hisoblandi ({len(managers)} nafar)",
                "records": len(managers),
            }
        )
        focus_mgr = _resolve_focus_manager(clean_q, managers, history)
        checklist = evaluate_manager_checklist(rows, manager_name=focus_mgr)
        actions.append(
            {
                "tool": "evaluate_manager_checklist",
                "label": f"{checklist['manager_name']} mikro-mezonlar (% da) tahlil qilindi",
                "records": checklist["evaluated_calls"],
            }
        )
        scoped = [
            r for r in rows if not focus_mgr or focus_mgr.lower() in str(r.get("manager_name") or "").lower()
        ]
        top_obj = _most_common(scoped, "objections", top=4)
        diag_note = diagnose_seller(focus_mgr, scoped).reason if (focus_mgr and scoped) else ""
        return leaderboard, focus_mgr, checklist, top_obj, diag_note

    async def ask(
        self,
        question: str,
        *,
        days: Optional[int] = None,
        history: Optional[Sequence[Mapping[str, Any]]] = None,
        principal: Optional[Principal] = None,
    ) -> Dict[str, Any]:
        """Execute read-only sales analytics tools and return grounded answer."""
        clean_q = (question or "").strip()
        win_days, win_label = _parse_days_window(clean_q, days)
        rows = await self._fetch_rows(win_days, principal)
        actions: List[Dict[str, Any]] = [
            {
                "tool": "query_call_analyses",
                "label": f"Qoʻngʻiroq tahlillari bazadan oʻqildi ({win_label})",
                "records": len(rows),
            }
        ]
        if not rows:
            return self._empty_reply(win_days, win_label, actions)

        leaderboard, focus_mgr, checklist, top_objections, diag_note = self._run_analysis_tools(
            clean_q, rows, history or (), actions
        )
        deterministic = _render_deterministic_answer(
            window_label=win_label,
            leaderboard=leaderboard,
            focus_manager=focus_mgr,
            checklist=checklist,
            top_objections=top_objections,
            diagnosis_note=diag_note,
        )
        facts_payload = {
            "window": win_label,
            "focus_manager": focus_mgr,
            "leaderboard_top5": leaderboard["managers"][:5],
            "checklist_strengths": checklist["strengths"][:4],
            "checklist_weaknesses": checklist["weaknesses"][:4],
            "top_objections": top_objections,
            "diagnosis": diag_note,
        }
        final_answer = await self._maybe_polish_with_llm(clean_q, facts_payload, deterministic)
        return {
            "real_data": True,
            "window_days": win_days,
            "window_label": win_label,
            "actions_count": len(actions),
            "actions": actions,
            "focus_manager": focus_mgr,
            "checklist": checklist,
            "leaderboard": leaderboard["managers"][:10],
            "top_objections": top_objections,
            "answer": final_answer,
        }
