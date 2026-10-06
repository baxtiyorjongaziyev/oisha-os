"""Suhbat tahlilidan AmoCRM amallarini rejalashtirish (sof, I/O yo'q).

Chegaralar (Owner tasdiqlagan, 2026-10-06):
- faqat bo'sh maydon to'ldiriladi; to'la maydon uchun faqat taklif
- etap faqat oldinga va ishonch >= min_confidence bo'lsa
- orqaga / terminal (Lost/Won) natija -> menejerga task
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Union


@dataclass(frozen=True)
class FieldFillAction:
    field_id: int
    value: str


@dataclass(frozen=True)
class FieldSuggestion:
    field_id: int
    current: str
    proposed: str


@dataclass(frozen=True)
class StageAction:
    from_status: int
    to_status: int


@dataclass(frozen=True)
class TaskAction:
    text: str


_PLACEHOLDERS = {"", "n/a", "na", "-", "noaniq", "yo'q", "yoq", "null", "none", "mavjud emas"}

CrmAction = Union[FieldFillAction, FieldSuggestion, StageAction, TaskAction]


def _current_field_values(lead: Mapping[str, Any]) -> Dict[int, str]:
    result: Dict[int, str] = {}
    for field in lead.get("custom_fields_values") or []:
        values = field.get("values") or []
        if not values:
            continue
        value = str(values[0].get("value") or "").strip()
        if value:
            result[int(field.get("field_id"))] = value
    return result


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class CrmActionPlanner:
    def __init__(self, field_map: Mapping[str, int], stage_rules: Mapping[str, Any]):
        self.field_map = dict(field_map)
        self.pipeline_order: List[int] = [int(s) for s in stage_rules.get("pipeline_order") or []]
        self.outcome_to_status: Dict[str, int] = {
            str(k): int(v) for k, v in (stage_rules.get("outcome_to_status") or {}).items()
        }
        self.terminal_outcomes = {str(o) for o in stage_rules.get("terminal_outcomes") or []}
        self.closed_statuses = {int(s) for s in stage_rules.get("closed_statuses") or []}
        self.min_confidence = _safe_float(stage_rules.get("min_confidence", 0.8))

    def plan(self, analysis: Mapping[str, Any], lead: Mapping[str, Any]) -> List[CrmAction]:
        if int(lead.get("status_id") or 0) in self.closed_statuses:
            return []  # Won/Lost lid — AI tegmaydi
        actions: List[CrmAction] = list(self._plan_fields(analysis, lead))
        stage_action = self._plan_stage(analysis, lead)
        if stage_action is not None:
            actions.append(stage_action)
        return actions

    def _plan_fields(self, analysis: Mapping[str, Any], lead: Mapping[str, Any]) -> List[CrmAction]:
        current = _current_field_values(lead)
        actions: List[CrmAction] = []
        for key, field_id in self.field_map.items():
            proposed = str(analysis.get(key) or "").strip()
            if proposed.casefold() in _PLACEHOLDERS:
                continue
            existing = current.get(int(field_id))
            if existing is None:
                actions.append(FieldFillAction(field_id=int(field_id), value=proposed))
            elif existing.casefold() != proposed.casefold():
                actions.append(FieldSuggestion(field_id=int(field_id), current=existing, proposed=proposed))
        return actions

    def _plan_stage(self, analysis: Mapping[str, Any], lead: Mapping[str, Any]) -> Optional[CrmAction]:
        outcome = str(analysis.get("natija") or "").strip()
        if not outcome:
            return None
        if outcome in self.terminal_outcomes:
            return TaskAction(text=f"Etapni tekshiring: AI natijasi '{outcome}' (Lost/Won qarori menejerda)")

        target = self.outcome_to_status.get(outcome)
        current = int(lead.get("status_id") or 0)
        if target is None or current not in self.pipeline_order or target not in self.pipeline_order:
            return None
        if _safe_float(analysis.get("natija_ishonch")) < self.min_confidence:
            return None

        current_idx = self.pipeline_order.index(current)
        target_idx = self.pipeline_order.index(target)
        if target_idx > current_idx:
            return StageAction(from_status=current, to_status=target)
        if target_idx < current_idx:
            return TaskAction(text=f"Etapni tekshiring: AI natijasi '{outcome}' joriy etapdan orqada")
        return None
