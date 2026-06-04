"""Safe amoCRM cleanup based on the expert audit.

The script is intentionally conservative:
- never deletes leads;
- never auto-closes leads as Lost;
- creates tasks only for active leads that do not already have an open task;
- tags leads into operational buckets;
- optionally moves clearly stale Hunter backlog into the Reactivation pipeline.

Run:
  python scripts/amocrm_expert_cleanup.py --dry-run
  python scripts/amocrm_expert_cleanup.py --live --move-reactivation
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.core.amocrm_sync import AmoCRMSync
from src.services.core.amocrm_pipeline_config import (
    FARMER_PIPELINE_ID,
    FINAL_PAYMENT_TASK_TEXT,
    LEGACY_CLOSER_PIPELINE_ID,
    SALES_PIPELINE_ID,
)
from src.settings import settings


HUNTER_PIPELINE_ID = SALES_PIPELINE_ID
CLOSER_PIPELINE_ID = LEGACY_CLOSER_PIPELINE_ID
REACTIVATION_PIPELINE_ID = 10947042

STATUS_WON = 142
STATUS_LOST = 143

HUNTER_YANGI_SOROV = 80178230
HUNTER_BOGLANIB_BOLMADI = 80178226
HUNTER_MULOQOT_BOSHLANDI = 80178222
HUNTER_UCHRASHUV = 80178218
REACTIVATION_SOVUQ_BAZA = 86076846

TAG_REVIVE = "OISHA_REVIVE_24H"
TAG_REACTIVATE = "OISHA_REACTIVATE"
TAG_LOST_CANDIDATE = "OISHA_LOST_CANDIDATE"
TAG_MEETING_REVIEW = "OISHA_MEETING_REVIEW"
TAG_NEEDS_CONTACT = "OISHA_NEEDS_CONTACT"
TAG_TASK_CREATED = "OISHA_TASK_CREATED"
TAG_OVERDUE_TASK = "OISHA_OVERDUE_TASK"


@dataclass(frozen=True)
class CleanupDecision:
    bucket: str
    tag: str
    task_text: str
    due_hours: int
    move_pipeline_id: int | None = None
    move_status_id: int | None = None


class AmoCRMExpertCleanup:
    def __init__(self, *, dry_run: bool, move_reactivation: bool, limit: int | None = None):
        self.dry_run = dry_run
        self.move_reactivation = move_reactivation
        self.limit = limit
        self.tz = ZoneInfo(settings.APP_TIMEZONE or "Asia/Tashkent")
        self.now = datetime.now(self.tz)
        self.now_ts = int(self.now.timestamp())
        self.started_stamp = self.now.strftime("%Y%m%d_%H%M%S")
        self.report_dir = Path("data/reports")
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir = Path("data")

        self.amocrm = AmoCRMSync(
            subdomain=settings.AMOCRM_SUBDOMAIN,
            client_id=settings.AMOCRM_CLIENT_ID,
            client_secret=(
                settings.AMOCRM_CLIENT_SECRET.get_secret_value()
                if settings.AMOCRM_CLIENT_SECRET
                else None
            ),
            redirect_url=settings.AMOCRM_REDIRECT_URL,
        )
        self.base_url = self.amocrm.base_url

        self.actions: list[dict[str, Any]] = []
        self.errors: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_payload: Any = None,
    ) -> requests.Response:
        response = requests.request(
            method,
            f"{self.base_url}{path}",
            headers=self.amocrm._get_headers(),
            params=params,
            json=json_payload,
            timeout=40,
        )
        if response.status_code == 401 and self.amocrm.refresh_token():
            response = requests.request(
                method,
                f"{self.base_url}{path}",
                headers=self.amocrm._get_headers(),
                params=params,
                json=json_payload,
                timeout=40,
            )
        return response

    def fetch_paginated(
        self,
        path: str,
        item_key: str,
        *,
        params: dict[str, Any] | None = None,
        limit: int = 250,
        max_pages: int = 120,
    ) -> list[dict[str, Any]]:
        query = dict(params or {})
        query.setdefault("limit", limit)
        items: list[dict[str, Any]] = []

        for page in range(1, max_pages + 1):
            query["page"] = page
            response = self.request("GET", path, params=query)
            response.raise_for_status()
            payload = response.json() if response.text else {}
            batch = payload.get("_embedded", {}).get(item_key, []) or []
            items.extend(batch)
            if not batch or "next" not in (payload.get("_links") or {}):
                break

        return items

    def lead_url(self, lead_id: int) -> str:
        return f"https://{settings.AMOCRM_SUBDOMAIN}.amocrm.ru/leads/detail/{lead_id}"

    def lead_tags(self, lead: dict[str, Any]) -> set[str]:
        return {
            str(tag.get("name") or "")
            for tag in lead.get("_embedded", {}).get("tags", []) or []
            if tag.get("name")
        }

    def lead_contacts_count(self, lead: dict[str, Any]) -> int:
        return len(lead.get("_embedded", {}).get("contacts", []) or [])

    def age_hours(self, lead: dict[str, Any]) -> float:
        updated_at = int(lead.get("updated_at") or lead.get("created_at") or self.now_ts)
        return max(0.0, (self.now_ts - updated_at) / 3600)

    def decide(self, lead: dict[str, Any], has_open_task: bool) -> CleanupDecision | None:
        status_id = int(lead.get("status_id") or 0)
        pipeline_id = int(lead.get("pipeline_id") or 0)
        age = self.age_hours(lead)
        contacts_count = self.lead_contacts_count(lead)

        if status_id in {STATUS_WON, STATUS_LOST}:
            return None

        if contacts_count == 0:
            return CleanupDecision(
                bucket="lost_candidate_needs_contact",
                tag=TAG_LOST_CANDIDATE,
                task_text=(
                    "Oisha audit: kontakt yo'q. Telefon/Telegramni toping; "
                    "topilmasa Lost reason bilan yoping."
                ),
                due_hours=24,
            )

        if pipeline_id == HUNTER_PIPELINE_ID and status_id in {
            HUNTER_YANGI_SOROV,
            HUNTER_BOGLANIB_BOLMADI,
            HUNTER_MULOQOT_BOSHLANDI,
        }:
            if age >= 24 * 7:
                return CleanupDecision(
                    bucket="reactivation",
                    tag=TAG_REACTIVATE,
                    task_text=(
                        "Oisha audit: eski lead. Bugun qayta aloqa qiling, "
                        "natijani yozing: qiziqish qaytdi / rad etdi / raqam noto'g'ri."
                    ),
                    due_hours=24,
                    move_pipeline_id=(
                        REACTIVATION_PIPELINE_ID if self.move_reactivation else None
                    ),
                    move_status_id=(
                        REACTIVATION_SOVUQ_BAZA if self.move_reactivation else None
                    ),
                )
            if age >= 24 or not has_open_task:
                return CleanupDecision(
                    bucket="revive_24h",
                    tag=TAG_REVIVE,
                    task_text=(
                        "Oisha audit: leadni 24 soat ichida tiriltiring. "
                        "Mijozga yozing/qo'ng'iroq qiling va keyingi statusni belgilang."
                    ),
                    due_hours=24,
                )

        if pipeline_id == HUNTER_PIPELINE_ID and status_id == HUNTER_UCHRASHUV:
            if age >= 24:
                return CleanupDecision(
                    bucket="meeting_review",
                    tag=TAG_MEETING_REVIEW,
                    task_text=(
                        "Oisha audit: uchrashuv statusi eskirgan. "
                        "Uchrashuv bo'lganini tekshiring: Closer/Farmerga o'tkazing "
                        "yoki Lost/Reactivation qarorini qo'ying."
                    ),
                    due_hours=24,
                )

        if has_open_task:
            return None

        if pipeline_id == CLOSER_PIPELINE_ID:
            return CleanupDecision(
                bucket="closer_next_step",
                tag=TAG_TASK_CREATED,
                task_text=(
                    "Oisha audit: Closer lead uchun keyingi qadamni belgilang: "
                    "brief, KP, follow-up yoki shartnoma."
                ),
                due_hours=24,
            )

        if pipeline_id == FARMER_PIPELINE_ID:
            return CleanupDecision(
                bucket="farmer_final_payment_next_step",
                tag=TAG_TASK_CREATED,
                task_text=FINAL_PAYMENT_TASK_TEXT,
                due_hours=48,
            )

        if pipeline_id == 10427390:
            return CleanupDecision(
                bucket="quality_next_step",
                tag=TAG_TASK_CREATED,
                task_text="Oisha audit: NPS/review/case keyingi qadamini belgilang.",
                due_hours=72,
            )

        return CleanupDecision(
            bucket="generic_next_step",
            tag=TAG_TASK_CREATED,
            task_text="Oisha audit: lead uchun aniq keyingi qadam va deadline belgilang.",
            due_hours=24,
        )

    def record(self, action: str, lead: dict[str, Any], **metadata: Any) -> None:
        self.actions.append(
            {
                "action": action,
                "lead_id": int(lead["id"]),
                "lead_name": lead.get("name"),
                "pipeline_id": lead.get("pipeline_id"),
                "status_id": lead.get("status_id"),
                "url": self.lead_url(int(lead["id"])),
                **metadata,
            }
        )

    def record_error(self, action: str, lead: dict[str, Any], response: requests.Response) -> None:
        self.errors.append(
            {
                "action": action,
                "lead_id": int(lead["id"]),
                "status_code": response.status_code,
                "body": response.text[:500],
                "url": self.lead_url(int(lead["id"])),
            }
        )

    def add_tag(self, lead: dict[str, Any], tag: str) -> None:
        if tag in self.lead_tags(lead):
            self.record("tag_skipped_exists", lead, tag=tag)
            return

        self.record("tag_would_add" if self.dry_run else "tag_add", lead, tag=tag)
        if self.dry_run:
            return

        response = self.request(
            "PATCH",
            f"/api/v4/leads/{int(lead['id'])}",
            json_payload={"_embedded": {"tags": [{"name": tag}]}},
        )
        if response.status_code != 200:
            self.record_error("tag_add", lead, response)

    def create_task(
        self,
        lead: dict[str, Any],
        decision: CleanupDecision,
        has_open_task: bool,
    ) -> None:
        if has_open_task:
            self.record("task_skipped_open_exists", lead, bucket=decision.bucket)
            return

        complete_till = int((self.now + timedelta(hours=decision.due_hours)).timestamp())
        payload = [
            {
                "task_type_id": 1,
                "text": decision.task_text,
                "complete_till": complete_till,
                "entity_id": int(lead["id"]),
                "entity_type": "leads",
            }
        ]
        if lead.get("responsible_user_id"):
            payload[0]["responsible_user_id"] = int(lead["responsible_user_id"])

        self.record(
            "task_would_create" if self.dry_run else "task_create",
            lead,
            bucket=decision.bucket,
            due_hours=decision.due_hours,
            task_text=decision.task_text,
        )
        if self.dry_run:
            return

        response = self.request("POST", "/api/v4/tasks", json_payload=payload)
        if response.status_code not in {200, 201}:
            self.record_error("task_create", lead, response)

    def move_lead(self, lead: dict[str, Any], decision: CleanupDecision) -> None:
        if not decision.move_pipeline_id or not decision.move_status_id:
            return

        self.record(
            "status_would_move" if self.dry_run else "status_move",
            lead,
            bucket=decision.bucket,
            to_pipeline_id=decision.move_pipeline_id,
            to_status_id=decision.move_status_id,
        )
        if self.dry_run:
            return

        response = self.request(
            "PATCH",
            f"/api/v4/leads/{int(lead['id'])}",
            json_payload={
                "pipeline_id": int(decision.move_pipeline_id),
                "status_id": int(decision.move_status_id),
            },
        )
        if response.status_code != 200:
            self.record_error("status_move", lead, response)

    def add_note(self, lead: dict[str, Any], decision: CleanupDecision) -> None:
        if decision.bucket not in {
            "reactivation",
            "lost_candidate_needs_contact",
            "meeting_review",
        }:
            return

        note_text = (
            "Oisha expert cleanup:\n"
            f"- Segment: {decision.bucket}\n"
            f"- Action: {decision.task_text}\n"
            "- Auto-delete yoki auto-Lost qilinmadi. Mas'ul tekshirishi kerak."
        )
        payload = [{"note_type": "common", "params": {"text": note_text}}]

        self.record(
            "note_would_add" if self.dry_run else "note_add",
            lead,
            bucket=decision.bucket,
        )
        if self.dry_run:
            return

        response = self.request(
            "POST",
            f"/api/v4/leads/{int(lead['id'])}/notes",
            json_payload=payload,
        )
        if response.status_code not in {200, 201}:
            self.record_error("note_add", lead, response)

    def mark_overdue_task_leads(
        self,
        leads_by_id: dict[int, dict[str, Any]],
        overdue_tasks: list[dict[str, Any]],
    ) -> None:
        seen: set[int] = set()
        for task in overdue_tasks:
            if task.get("entity_type") != "leads" or not task.get("entity_id"):
                continue
            lead_id = int(task["entity_id"])
            if lead_id in seen or lead_id not in leads_by_id:
                continue
            seen.add(lead_id)
            self.add_tag(leads_by_id[lead_id], TAG_OVERDUE_TASK)

    def backup_snapshot(
        self,
        *,
        pipelines: list[dict[str, Any]],
        leads: list[dict[str, Any]],
        open_tasks: list[dict[str, Any]],
    ) -> Path:
        backup_path = self.backup_dir / f"amocrm_cleanup_backup_{self.started_stamp}.json"
        backup_payload = {
            "generated_at": self.now.isoformat(),
            "dry_run": self.dry_run,
            "move_reactivation": self.move_reactivation,
            "pipelines": pipelines,
            "leads": leads,
            "open_tasks": open_tasks,
        }
        backup_path.write_text(
            json.dumps(backup_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return backup_path

    def save_report(
        self,
        *,
        backup_path: Path,
        leads_total: int,
        active_total: int,
        open_tasks_total: int,
        overdue_tasks_total: int,
    ) -> tuple[Path, Path]:
        counts = defaultdict(int)
        for action in self.actions:
            counts[action["action"]] += 1
            if action.get("bucket"):
                counts[f"bucket:{action['bucket']}"] += 1

        report = {
            "ok": not self.errors,
            "generated_at": self.now.isoformat(),
            "dry_run": self.dry_run,
            "move_reactivation": self.move_reactivation,
            "backup_path": str(backup_path.resolve()),
            "summary": {
                "leads_total": leads_total,
                "active_total": active_total,
                "open_tasks_total": open_tasks_total,
                "overdue_tasks_total": overdue_tasks_total,
                "actions_total": len(self.actions),
                "errors_total": len(self.errors),
                **dict(sorted(counts.items())),
            },
            "actions": self.actions,
            "errors": self.errors,
        }

        mode = "dry_run" if self.dry_run else "live"
        json_path = self.report_dir / f"amocrm_expert_cleanup_{mode}_{self.started_stamp}.json"
        md_path = self.report_dir / f"amocrm_expert_cleanup_{mode}_{self.started_stamp}.md"
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        lines = [
            f"# amoCRM Expert Cleanup - {mode} - {self.now.strftime('%Y-%m-%d %H:%M')}",
            "",
            f"Backup: `{backup_path.resolve()}`",
            "",
            "## Summary",
        ]
        for key, value in report["summary"].items():
            lines.append(f"- {key}: **{value}**")
        if self.errors:
            lines.extend(["", "## Errors"])
            for error in self.errors[:30]:
                lines.append(
                    f"- {error['action']} lead {error['lead_id']}: "
                    f"HTTP {error['status_code']} - {error['body'][:120]}"
                )
        lines.extend(["", "## First Actions"])
        for action in self.actions[:50]:
            lines.append(
                f"- {action['action']} lead {action['lead_id']} "
                f"{action.get('bucket', '')} {action.get('tag', '')}"
            )
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return json_path, md_path

    def run(self) -> dict[str, Any]:
        account = self.request("GET", "/api/v4/account")
        account.raise_for_status()

        pipelines_payload = self.request("GET", "/api/v4/leads/pipelines")
        pipelines_payload.raise_for_status()
        pipelines = pipelines_payload.json().get("_embedded", {}).get("pipelines", []) or []

        leads = self.fetch_paginated(
            "/api/v4/leads",
            "leads",
            params={"with": "contacts"},
        )
        if self.limit:
            leads = leads[: self.limit]

        open_tasks = self.fetch_paginated(
            "/api/v4/tasks",
            "tasks",
            params={"filter[is_completed]": 0},
            max_pages=80,
        )

        backup_path = self.backup_snapshot(
            pipelines=pipelines,
            leads=leads,
            open_tasks=open_tasks,
        )

        active_leads = [
            lead for lead in leads if int(lead.get("status_id") or 0) not in {STATUS_WON, STATUS_LOST}
        ]
        leads_by_id = {int(lead["id"]): lead for lead in leads if lead.get("id")}
        open_tasks_by_lead: dict[int, list[dict[str, Any]]] = defaultdict(list)
        overdue_tasks: list[dict[str, Any]] = []

        for task in open_tasks:
            if task.get("entity_type") == "leads" and task.get("entity_id"):
                open_tasks_by_lead[int(task["entity_id"])].append(task)
            if task.get("complete_till") and int(task["complete_till"]) < self.now_ts:
                overdue_tasks.append(task)

        for lead in active_leads:
            has_open_task = bool(open_tasks_by_lead.get(int(lead["id"])))
            decision = self.decide(lead, has_open_task)
            if not decision:
                continue

            self.add_tag(lead, decision.tag)
            self.create_task(lead, decision, has_open_task)
            self.add_note(lead, decision)
            self.move_lead(lead, decision)

            if not self.dry_run:
                time.sleep(0.12)

        self.mark_overdue_task_leads(leads_by_id, overdue_tasks)

        json_path, md_path = self.save_report(
            backup_path=backup_path,
            leads_total=len(leads),
            active_total=len(active_leads),
            open_tasks_total=len(open_tasks),
            overdue_tasks_total=len(overdue_tasks),
        )

        return {
            "ok": not self.errors,
            "dry_run": self.dry_run,
            "move_reactivation": self.move_reactivation,
            "backup_path": str(backup_path.resolve()),
            "json_path": str(json_path.resolve()),
            "md_path": str(md_path.resolve()),
            "actions_total": len(self.actions),
            "errors_total": len(self.errors),
            "errors": self.errors[:10],
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safe amoCRM expert cleanup")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Only plan actions")
    mode.add_argument("--live", action="store_true", help="Apply actions to amoCRM")
    parser.add_argument(
        "--move-reactivation",
        action="store_true",
        help="Move clearly stale Hunter backlog into Reactivation/Sovuq baza",
    )
    parser.add_argument("--limit", type=int, default=None, help="Limit fetched leads for testing")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cleanup = AmoCRMExpertCleanup(
        dry_run=args.dry_run,
        move_reactivation=args.move_reactivation,
        limit=args.limit,
    )
    result = cleanup.run()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
