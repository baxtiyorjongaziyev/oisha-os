from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.core.amocrm_pipeline_config import (
    CLOSER_TO_SALES_STATUS_NAME,
    FARMER_FINAL_PAYMENT_PENDING_STATUS_NAME,
    FARMER_PIPELINE_ID,
    FARMER_START_STATUS_NAME,
    FARMER_STATUSES,
    FINAL_PAYMENT_TASK_TEXT,
    LEGACY_CLOSER_PIPELINE_ID,
    SALES_ADVANCE_STATUS_NAME,
    SALES_PIPELINE_ID,
    SALES_STATUSES,
    STATUS_LOST,
    STATUS_WON,
    DesiredStatus,
)
from src.services.core.amocrm_sync import AmoCRMSync
from src.settings import settings

CONFIRM_TEXT = "MERGE_HUNTER_CLOSER_TO_SALES"


def _norm(value: Any) -> str:
    return str(value or "").strip().casefold()


class AmoCRMSalesFarmerMigration:
    def __init__(self, *, live: bool = False, confirm: str = "", limit: int | None = None):
        self.live = live
        self.confirm = confirm
        self.limit = limit
        self.now = datetime.now()
        self.report_dir = Path("data/reports")
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.actions: list[dict[str, Any]] = []
        self.errors: list[dict[str, Any]] = []
        self.amocrm = AmoCRMSync(
            subdomain=settings.AMOCRM_SUBDOMAIN,
            client_id=settings.AMOCRM_CLIENT_ID,
            client_secret=(
                settings.AMOCRM_CLIENT_SECRET.get_secret_value()
                if settings.AMOCRM_CLIENT_SECRET
                else ""
            ),
            redirect_url=settings.AMOCRM_REDIRECT_URL,
        )

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
            f"{self.amocrm.base_url}{path}",
            headers=self.amocrm._get_headers(),
            params=params,
            json=json_payload,
            timeout=40,
        )
        if response.status_code == 401 and self.amocrm.refresh_token():
            response = requests.request(
                method,
                f"{self.amocrm.base_url}{path}",
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
        max_pages: int = 120,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        query = {"limit": 250, **(params or {})}
        for page in range(1, max_pages + 1):
            query["page"] = page
            response = self.request("GET", path, params=query)
            response.raise_for_status()
            payload = response.json() if response.text else {}
            batch = payload.get("_embedded", {}).get(item_key, []) or []
            items.extend(batch)
            if not batch or "next" not in (payload.get("_links") or {}):
                break
        return items[: self.limit] if self.limit else items

    def fetch_pipelines(self) -> list[dict[str, Any]]:
        response = self.request("GET", "/api/v4/leads/pipelines")
        response.raise_for_status()
        return response.json().get("_embedded", {}).get("pipelines", []) or []

    @staticmethod
    def statuses_by_name(pipeline: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {
            _norm(status.get("name")): status
            for status in pipeline.get("_embedded", {}).get("statuses", []) or []
        }

    @staticmethod
    def statuses_by_id(pipeline: dict[str, Any]) -> dict[int, dict[str, Any]]:
        return {
            int(status["id"]): status
            for status in pipeline.get("_embedded", {}).get("statuses", []) or []
            if status.get("id")
        }

    def record(self, action: str, **metadata: Any) -> None:
        self.actions.append({"action": action, **metadata})

    def record_error(self, action: str, response: requests.Response, **metadata: Any) -> None:
        self.errors.append(
            {
                "action": action,
                "status_code": response.status_code,
                "body": response.text[:500],
                **metadata,
            }
        )

    def pipeline(self, pipelines: list[dict[str, Any]], pipeline_id: int) -> dict[str, Any]:
        for pipeline in pipelines:
            if int(pipeline.get("id") or 0) == pipeline_id:
                return pipeline
        raise RuntimeError(f"Pipeline topilmadi: {pipeline_id}")

    def save_backup(self, *, pipelines: list[dict[str, Any]], leads: list[dict[str, Any]]) -> str:
        path = self.report_dir / f"amocrm_sales_farmer_pipeline_backup_{self.now:%Y%m%d_%H%M%S}.json"
        payload = {
            "generated_at": self.now.isoformat(),
            "live": self.live,
            "pipelines": pipelines,
            "candidate_leads": leads,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def ensure_pipeline_name(self, pipeline: dict[str, Any], name: str) -> None:
        current = str(pipeline.get("name") or "")
        if current == name:
            self.record("pipeline_name_ok", pipeline_id=pipeline.get("id"), name=name)
            return
        self.record(
            "pipeline_would_rename" if not self.live else "pipeline_rename",
            pipeline_id=pipeline.get("id"),
            old_name=current,
            new_name=name,
        )
        if not self.live:
            return
        response = self.request(
            "PATCH",
            f"/api/v4/leads/pipelines/{int(pipeline['id'])}",
            json_payload={"name": name},
        )
        if response.status_code not in {200, 202}:
            self.record_error("pipeline_rename", response, pipeline_id=pipeline.get("id"))

    def ensure_statuses(self, pipeline: dict[str, Any], desired: tuple[DesiredStatus, ...]) -> dict[str, int]:
        by_id = self.statuses_by_id(pipeline)
        by_name = self.statuses_by_name(pipeline)
        status_ids: dict[str, int] = {}
        updates: list[dict[str, Any]] = []
        creates: list[dict[str, Any]] = []

        for status in desired:
            existing = by_id.get(status.existing_id or -1) or by_name.get(_norm(status.name))
            payload = {"name": status.name, "sort": status.sort, "color": status.color}
            if existing:
                status_ids[status.name] = int(existing["id"])
                if (
                    existing.get("name") != status.name
                    or int(existing.get("sort") or 0) != status.sort
                ):
                    updates.append({"id": int(existing["id"]), **payload})
                else:
                    self.record(
                        "status_ok",
                        pipeline_id=pipeline.get("id"),
                        status_id=existing.get("id"),
                        name=status.name,
                    )
            else:
                creates.append(payload)

        if updates:
            self.record(
                "statuses_would_update" if not self.live else "statuses_update",
                pipeline_id=pipeline.get("id"),
                statuses=updates,
            )
            if self.live:
                response = self.request(
                    "PATCH",
                    f"/api/v4/leads/pipelines/{int(pipeline['id'])}/statuses",
                    json_payload=updates,
                )
                if response.status_code not in {200, 202}:
                    self.record_error("statuses_update", response, pipeline_id=pipeline.get("id"))

        if creates:
            self.record(
                "statuses_would_create" if not self.live else "statuses_create",
                pipeline_id=pipeline.get("id"),
                statuses=creates,
            )
            if self.live:
                response = self.request(
                    "POST",
                    f"/api/v4/leads/pipelines/{int(pipeline['id'])}/statuses",
                    json_payload=creates,
                )
                if response.status_code not in {200, 201, 202}:
                    self.record_error("statuses_create", response, pipeline_id=pipeline.get("id"))

        if self.live and (updates or creates):
            pipeline = self.pipeline(self.fetch_pipelines(), int(pipeline["id"]))
            by_name = self.statuses_by_name(pipeline)
            status_ids = {
                status.name: int(by_name[_norm(status.name)]["id"])
                for status in desired
                if _norm(status.name) in by_name
            }

        return status_ids

    def fetch_active_pipeline_leads(self, pipeline_id: int) -> list[dict[str, Any]]:
        leads = self.fetch_paginated(
            "/api/v4/leads",
            "leads",
            params={"filter[pipeline_id]": pipeline_id, "with": "contacts"},
        )
        return [
            lead
            for lead in leads
            if int(lead.get("status_id") or 0) not in {STATUS_WON, STATUS_LOST}
        ]

    def migrate_lead(self, lead: dict[str, Any], pipeline_id: int, status_id: int, reason: str) -> None:
        self.record(
            "lead_would_move" if not self.live else "lead_move",
            lead_id=lead.get("id"),
            from_pipeline_id=lead.get("pipeline_id"),
            from_status_id=lead.get("status_id"),
            to_pipeline_id=pipeline_id,
            to_status_id=status_id,
            reason=reason,
        )
        if not self.live:
            return
        response = self.request(
            "PATCH",
            f"/api/v4/leads/{int(lead['id'])}",
            json_payload={"pipeline_id": pipeline_id, "status_id": status_id},
        )
        if response.status_code != 200:
            self.record_error("lead_move", response, lead_id=lead.get("id"), reason=reason)
        time.sleep(0.25)

    def record_deferred_lead_move(
        self,
        lead: dict[str, Any],
        *,
        pipeline_id: int,
        target_status_name: str,
        reason: str,
    ) -> None:
        self.record(
            "lead_would_move_after_status_create",
            lead_id=lead.get("id"),
            from_pipeline_id=lead.get("pipeline_id"),
            from_status_id=lead.get("status_id"),
            to_pipeline_id=pipeline_id,
            target_status_name=target_status_name,
            reason=reason,
        )

    def create_final_payment_tasks(self, pending_status_id: int) -> None:
        farmer_leads = self.fetch_active_pipeline_leads(FARMER_PIPELINE_ID)
        pending = [lead for lead in farmer_leads if int(lead.get("status_id") or 0) == pending_status_id]
        open_tasks = self.fetch_paginated(
            "/api/v4/tasks", "tasks", params={"filter[is_completed]": 0}, max_pages=80
        )
        open_by_lead: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for task in open_tasks:
            if task.get("entity_type") == "leads" and task.get("entity_id"):
                open_by_lead[int(task["entity_id"])].append(task)

        for lead in pending:
            lead_id = int(lead["id"])
            already = any(FINAL_PAYMENT_TASK_TEXT[:40] in str(task.get("text") or "") for task in open_by_lead.get(lead_id, []))
            if already:
                self.record("final_payment_task_exists", lead_id=lead_id)
                continue
            payload = [
                {
                    "task_type_id": 1,
                    "text": FINAL_PAYMENT_TASK_TEXT,
                    "complete_till": int((self.now + timedelta(hours=24)).timestamp()),
                    "entity_id": lead_id,
                    "entity_type": "leads",
                }
            ]
            if lead.get("responsible_user_id"):
                payload[0]["responsible_user_id"] = int(lead["responsible_user_id"])
            self.record(
                "task_would_create" if not self.live else "task_create",
                lead_id=lead_id,
                task_text=FINAL_PAYMENT_TASK_TEXT,
            )
            if self.live:
                response = self.request("POST", "/api/v4/tasks", json_payload=payload)
                if response.status_code not in {200, 201}:
                    self.record_error("task_create", response, lead_id=lead_id)

    def run(self) -> dict[str, Any]:
        if self.live and self.confirm != CONFIRM_TEXT:
            raise SystemExit(f"--live uchun --confirm {CONFIRM_TEXT} kerak")

        pipelines = self.fetch_pipelines()
        sales = self.pipeline(pipelines, SALES_PIPELINE_ID)
        closer = self.pipeline(pipelines, LEGACY_CLOSER_PIPELINE_ID)
        farmer = self.pipeline(pipelines, FARMER_PIPELINE_ID)

        closer_leads = self.fetch_active_pipeline_leads(LEGACY_CLOSER_PIPELINE_ID)
        sales_leads = self.fetch_active_pipeline_leads(SALES_PIPELINE_ID)
        backup_path = ""
        if self.live:
            backup_path = self.save_backup(pipelines=pipelines, leads=closer_leads + sales_leads)

        self.ensure_pipeline_name(sales, "Sales pipeline")
        sales_ids = self.ensure_statuses(sales, SALES_STATUSES)
        farmer_ids = self.ensure_statuses(farmer, FARMER_STATUSES)

        if self.live:
            pipelines = self.fetch_pipelines()
            sales = self.pipeline(pipelines, SALES_PIPELINE_ID)
            farmer = self.pipeline(pipelines, FARMER_PIPELINE_ID)
            sales_ids = self.ensure_statuses(sales, SALES_STATUSES)
            farmer_ids = self.ensure_statuses(farmer, FARMER_STATUSES)

        closer_by_id = self.statuses_by_id(closer)
        desired_sales_names = {status.name for status in SALES_STATUSES}
        desired_farmer_names = {status.name for status in FARMER_STATUSES}
        farmer_start_id = farmer_ids.get(FARMER_START_STATUS_NAME)
        for lead in closer_leads:
            old_status = closer_by_id.get(int(lead.get("status_id") or 0), {})
            old_name = str(old_status.get("name") or "")
            target_name = CLOSER_TO_SALES_STATUS_NAME.get(old_name, "Yangi so'rov")
            target_id = sales_ids.get(target_name)
            if target_name == SALES_ADVANCE_STATUS_NAME and farmer_start_id:
                self.migrate_lead(
                    lead,
                    FARMER_PIPELINE_ID,
                    farmer_start_id,
                    f"legacy_advance_to_farmer_start:{old_name}",
                )
            elif (
                target_name == SALES_ADVANCE_STATUS_NAME
                and not self.live
                and FARMER_START_STATUS_NAME in desired_farmer_names
            ):
                self.record_deferred_lead_move(
                    lead,
                    pipeline_id=FARMER_PIPELINE_ID,
                    target_status_name=FARMER_START_STATUS_NAME,
                    reason=f"legacy_advance_to_farmer_start:{old_name}",
                )
            elif target_id:
                self.migrate_lead(lead, SALES_PIPELINE_ID, target_id, f"closer:{old_name}->{target_name}")
            elif not self.live and target_name in desired_sales_names:
                self.record_deferred_lead_move(
                    lead,
                    pipeline_id=SALES_PIPELINE_ID,
                    target_status_name=target_name,
                    reason=f"closer:{old_name}->{target_name}",
                )
            else:
                self.record("lead_move_skipped_missing_sales_status", lead_id=lead.get("id"), target_name=target_name)

        advance_status_id = sales_ids.get(SALES_ADVANCE_STATUS_NAME)
        if advance_status_id and farmer_start_id:
            for lead in sales_leads:
                if int(lead.get("status_id") or 0) == advance_status_id:
                    self.migrate_lead(
                        lead,
                        FARMER_PIPELINE_ID,
                        farmer_start_id,
                        "sales_advance_to_farmer_start",
                    )

        final_payment_pending_id = farmer_ids.get(FARMER_FINAL_PAYMENT_PENDING_STATUS_NAME)
        if final_payment_pending_id:
            self.create_final_payment_tasks(final_payment_pending_id)

        return {
            "success": not self.errors,
            "live": self.live,
            "backup_path": backup_path,
            "actions_count": len(self.actions),
            "errors_count": len(self.errors),
            "actions": self.actions,
            "errors": self.errors,
        }

    def verify(self) -> dict[str, Any]:
        pipelines = self.fetch_pipelines()
        sales = self.pipeline(pipelines, SALES_PIPELINE_ID)
        farmer = self.pipeline(pipelines, FARMER_PIPELINE_ID)
        sales_names = self.statuses_by_name(sales)
        farmer_names = self.statuses_by_name(farmer)
        missing_sales = [s.name for s in SALES_STATUSES if _norm(s.name) not in sales_names]
        missing_farmer = [s.name for s in FARMER_STATUSES if _norm(s.name) not in farmer_names]
        closer_active = self.fetch_active_pipeline_leads(LEGACY_CLOSER_PIPELINE_ID)
        return {
            "success": not missing_sales and not missing_farmer,
            "sales_pipeline_name": sales.get("name"),
            "missing_sales_statuses": missing_sales,
            "missing_farmer_statuses": missing_farmer,
            "legacy_closer_active_count": len(closer_active),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge Hunter/Closer into Sales and configure Farmer final-payment flow.")
    parser.add_argument("--live", action="store_true", help="Apply changes to amoCRM.")
    parser.add_argument("--confirm", default="", help=f"Required for --live: {CONFIRM_TEXT}")
    parser.add_argument("--verify", action="store_true", help="Read-only verification.")
    parser.add_argument("--limit", type=int, default=None, help="Limit fetched leads for testing.")
    args = parser.parse_args()

    migration = AmoCRMSalesFarmerMigration(live=args.live, confirm=args.confirm, limit=args.limit)
    result = migration.verify() if args.verify else migration.run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("success"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
