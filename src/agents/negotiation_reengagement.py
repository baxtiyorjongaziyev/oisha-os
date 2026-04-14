from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List


DEFAULT_MIN_IDLE_HOURS = 48
CLOSED_STATUS_IDS = {142, 143}


@dataclass
class ReengagementCandidate:
    lead_id: int
    lead_name: str
    pipeline_id: int
    status_id: int
    updated_at: int
    idle_hours: int
    price: int
    priority: str
    reason: str
    due_in_hours: int
    task_title: str
    task_details: str
    note: str

    def to_payload(self) -> Dict[str, Any]:
        return asdict(self)


class NegotiationReengagementPlanner:
    @staticmethod
    def plan(
        leads: Iterable[Dict[str, Any]],
        *,
        min_idle_hours: int = DEFAULT_MIN_IDLE_HOURS,
        limit: int = 20,
        now_ts: int | None = None,
    ) -> List[ReengagementCandidate]:
        import time

        now_epoch = int(now_ts or time.time())
        candidates: List[ReengagementCandidate] = []

        for lead in leads:
            lead_id = int(lead.get("id") or 0)
            status_id = int(lead.get("status_id") or 0)
            pipeline_id = int(lead.get("pipeline_id") or 0)
            updated_at = int(lead.get("updated_at") or 0)
            price = int(lead.get("price") or 0)
            lead_name = str(lead.get("name") or f"Lead {lead_id}").strip()

            if not lead_id or status_id in CLOSED_STATUS_IDS:
                continue

            idle_hours = 0
            if updated_at > 0:
                idle_hours = max(0, int((now_epoch - updated_at) / 3600))
            if idle_hours < min_idle_hours:
                continue

            priority = "medium"
            if idle_hours >= 120 or price >= 15_000_000:
                priority = "critical"
            elif idle_hours >= 72 or pipeline_id == 10123314:
                priority = "high"

            if pipeline_id == 10123314:
                reason = "closer_no_response"
            elif idle_hours >= 96:
                reason = "stalled_negotiation"
            else:
                reason = "followup_gap"

            due_in_hours = 24
            if priority == "critical":
                due_in_hours = 4
            elif priority == "high":
                due_in_hours = 12

            task_title = NegotiationReengagementPlanner._build_task_title(lead_name, reason)
            task_details = NegotiationReengagementPlanner._build_task_details(lead_name, idle_hours, price, reason)
            note = NegotiationReengagementPlanner._build_note(lead_name, idle_hours, price, reason)

            candidates.append(
                ReengagementCandidate(
                    lead_id=lead_id,
                    lead_name=lead_name,
                    pipeline_id=pipeline_id,
                    status_id=status_id,
                    updated_at=updated_at,
                    idle_hours=idle_hours,
                    price=price,
                    priority=priority,
                    reason=reason,
                    due_in_hours=due_in_hours,
                    task_title=task_title,
                    task_details=task_details,
                    note=note,
                )
            )

        priority_rank = {"critical": 0, "high": 1, "medium": 2}
        candidates.sort(key=lambda item: (priority_rank.get(item.priority, 3), -item.idle_hours, -item.price))
        return candidates[:limit]

    @staticmethod
    def _build_task_title(lead_name: str, reason: str) -> str:
        if reason == "closer_no_response":
            return f"Closer follow-up: {lead_name}"
        if reason == "stalled_negotiation":
            return f"Restart negotiation: {lead_name}"
        return f"Follow-up commitment: {lead_name}"

    @staticmethod
    def _build_task_details(lead_name: str, idle_hours: int, price: int, reason: str) -> str:
        value_hint = f"Lead qiymati: {price:,} so'm." if price else "Qiymat aniqlanmagan."
        if reason == "closer_no_response":
            return (
                f"{lead_name} closer bosqichida {idle_hours} soat javobsiz qolgan. "
                f"{value_hint} Qaror beruvchi, start sanasi yoki to'lov bo'yicha aniq next stepni yoping."
            )
        if reason == "stalled_negotiation":
            return (
                f"{lead_name} bilan muzokara {idle_hours} soat qotib qolgan. "
                f"{value_hint} E'tirozni aniqlab, qo'ng'iroq yoki strategik sessiya sanasini taklif qiling."
            )
        return (
            f"{lead_name} {idle_hours} soat follow-upsiz qolgan. "
            f"{value_hint} Qaror sanasini mahkamlang yoki nurture holatini aniq yozing."
        )

    @staticmethod
    def _build_note(lead_name: str, idle_hours: int, price: int, reason: str) -> str:
        reason_line = {
            "closer_no_response": "Closer bosqichida no-response kuzatildi.",
            "stalled_negotiation": "Negotiation uzoq pauzada qoldi.",
            "followup_gap": "Follow-up cadence uzilib qolgan.",
        }.get(reason, "Re-engagement kerak.")
        value_line = f"Lead qiymati: {price:,} so'm." if price else "Lead qiymati aniqlanmagan."
        return (
            f"AI re-engagement signal. Lead: {lead_name}. "
            f"Idle: {idle_hours} soat. {reason_line} {value_line} "
            "Keyingi qadam: follow-up task yaratildi va qaror sanasini qayta mahkamlash tavsiya qilindi."
        )
