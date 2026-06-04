from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from requests import RequestException

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.core.amocrm_sync import AmoCRMSync
from src.settings import settings

CONFIRM_TEXT = "NORMALIZE_AMOCRM_DEAL_PHONES"
STATUS_WON = 142
STATUS_LOST = 143


@dataclass
class PhoneNormalization:
    original: str
    normalized: str | None
    status: str
    reason: str


def _digits(value: Any) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def normalize_uz_phone(value: Any) -> PhoneNormalization:
    original = str(value or "").strip()
    digits = _digits(original)
    compact = re.sub(r"[\s\-().]+", "", original)

    if not original:
        return PhoneNormalization(original, None, "skip", "empty")
    if compact.startswith("+998") and len(digits) == 12:
        normalized = f"+{digits}"
        if original == normalized:
            return PhoneNormalization(original, normalized, "ok", "already_plus_998")
        return PhoneNormalization(original, normalized, "update", "format_plus_998")
    if original.startswith("+") and not compact.startswith("+998"):
        return PhoneNormalization(original, None, "skip", "foreign_or_non_uz_international")
    if digits.startswith("998") and len(digits) == 12:
        return PhoneNormalization(original, f"+{digits}", "update", "missing_plus")
    if len(digits) == 9:
        return PhoneNormalization(original, f"+998{digits}", "update", "local_9_digits")
    if len(digits) == 10 and digits.startswith("0"):
        return PhoneNormalization(original, f"+998{digits[1:]}", "update", "local_with_0_prefix")
    if len(digits) == 10 and digits.startswith("8"):
        return PhoneNormalization(original, f"+998{digits[1:]}", "update", "local_with_8_prefix")
    return PhoneNormalization(original, None, "skip", f"ambiguous_digits_len_{len(digits)}")


class AmoCRMDealPhoneNormalizer:
    def __init__(
        self,
        *,
        live: bool = False,
        confirm: str = "",
        limit: int | None = None,
        include_closed: bool = False,
    ):
        self.live = live
        self.confirm = confirm
        self.limit = limit
        self.include_closed = include_closed
        self.actions: list[dict[str, Any]] = []
        self.errors: list[dict[str, Any]] = []
        self.now = datetime.now()
        self.report_dir = Path("data/reports")
        self.report_dir.mkdir(parents=True, exist_ok=True)
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
        response = self._request_once(method, path, params=params, json_payload=json_payload)
        if response.status_code == 401 and self.amocrm.refresh_token():
            response = self._request_once(method, path, params=params, json_payload=json_payload)
        return response

    def _request_once(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_payload: Any = None,
    ) -> requests.Response:
        last_exc: RequestException | None = None
        for attempt in range(1, 4):
            try:
                return requests.request(
                    method,
                    f"{self.amocrm.base_url}{path}",
                    headers=self.amocrm._get_headers(),
                    params=params,
                    json=json_payload,
                    timeout=(10, 60),
                )
            except RequestException as exc:
                last_exc = exc
                self.record(
                    "request_retry",
                    method=method,
                    path=path,
                    attempt=attempt,
                    error=type(exc).__name__,
                )
                time.sleep(min(2 * attempt, 6))
        raise last_exc or RuntimeError(f"request failed: {method} {path}")

    def fetch_paginated(
        self,
        path: str,
        item_key: str,
        *,
        params: dict[str, Any] | None = None,
        max_pages: int = 160,
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

    def fetch_deal_contact_ids(self) -> tuple[list[dict[str, Any]], dict[int, set[int]]]:
        leads = self.fetch_paginated("/api/v4/leads", "leads", params={"with": "contacts"})
        by_contact: dict[int, set[int]] = {}
        kept_leads: list[dict[str, Any]] = []
        for lead in leads:
            status_id = int(lead.get("status_id") or 0)
            if not self.include_closed and status_id in {STATUS_WON, STATUS_LOST}:
                continue
            kept_leads.append(lead)
            for ref in lead.get("_embedded", {}).get("contacts", []) or []:
                contact_id = int(ref.get("id") or 0)
                if contact_id:
                    by_contact.setdefault(contact_id, set()).add(int(lead.get("id") or 0))
        return kept_leads, by_contact

    def fetch_contact(self, contact_id: int) -> dict[str, Any] | None:
        try:
            response = self.request("GET", f"/api/v4/contacts/{contact_id}", params={"with": "leads"})
        except RequestException as exc:
            self.errors.append(
                {
                    "action": "contact_fetch",
                    "contact_id": contact_id,
                    "error": type(exc).__name__,
                    "body": str(exc)[:500],
                }
            )
            return None
        if response.status_code == 404:
            self.record("contact_missing", contact_id=contact_id)
            return None
        response.raise_for_status()
        return response.json()

    def fetch_contacts_by_ids(self, contact_ids: list[int]) -> dict[int, dict[str, Any]]:
        contacts: dict[int, dict[str, Any]] = {}
        for start in range(0, len(contact_ids), 200):
            chunk = contact_ids[start : start + 200]
            params: list[tuple[str, Any]] = [("limit", 250), ("with", "leads")]
            params.extend(("filter[id][]", contact_id) for contact_id in chunk)
            try:
                response = self.request("GET", "/api/v4/contacts", params=params)  # type: ignore[arg-type]
            except RequestException as exc:
                self.errors.append(
                    {
                        "action": "contacts_batch_fetch",
                        "contact_ids": chunk[:20],
                        "contact_ids_count": len(chunk),
                        "error": type(exc).__name__,
                        "body": str(exc)[:500],
                    }
                )
                for contact_id in chunk:
                    contact = self.fetch_contact(contact_id)
                    if contact:
                        contacts[contact_id] = contact
                continue
            if response.status_code == 400:
                for contact_id in chunk:
                    contact = self.fetch_contact(contact_id)
                    if contact:
                        contacts[contact_id] = contact
                continue
            response.raise_for_status()
            batch = response.json().get("_embedded", {}).get("contacts", []) or []
            for contact in batch:
                contact_id = int(contact.get("id") or 0)
                if contact_id:
                    contacts[contact_id] = contact
            found = set(contacts).intersection(chunk)
            for missing_id in sorted(set(chunk) - found):
                self.record("contact_missing_from_batch", contact_id=missing_id)
        return contacts

    @staticmethod
    def phone_field_values(contact: dict[str, Any]) -> list[dict[str, Any]]:
        for field in contact.get("custom_fields_values") or []:
            if field.get("field_code") == "PHONE":
                return field.get("values") or []
        return []

    def build_phone_values(self, values: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[PhoneNormalization]]:
        new_values: list[dict[str, Any]] = []
        results: list[PhoneNormalization] = []
        seen: set[str] = set()
        for value in values:
            result = normalize_uz_phone(value.get("value"))
            results.append(result)
            patched = dict(value)
            if result.status in {"update", "ok"} and result.normalized:
                patched["value"] = result.normalized
            if patched.get("value") in seen:
                results[-1] = PhoneNormalization(
                    result.original,
                    result.normalized,
                    "skip",
                    "duplicate_after_normalization",
                )
                continue
            seen.add(str(patched.get("value") or ""))
            new_values.append(patched)
        return new_values, results

    def save_backup(self, contacts: list[dict[str, Any]]) -> str:
        path = self.report_dir / f"amocrm_phone_normalization_backup_{self.now:%Y%m%d_%H%M%S}.json"
        path.write_text(
            json.dumps(
                {
                    "generated_at": self.now.isoformat(),
                    "live": self.live,
                    "contacts": contacts,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return str(path)

    def patch_contact_phone(
        self,
        *,
        contact: dict[str, Any],
        lead_ids: set[int],
        new_values: list[dict[str, Any]],
        results: list[PhoneNormalization],
    ) -> None:
        contact_id = int(contact["id"])
        updates = [asdict(result) for result in results if result.status == "update"]
        skips = [asdict(result) for result in results if result.status == "skip"]
        if not updates:
            if skips:
                self.record("contact_skipped_phone", contact_id=contact_id, lead_ids=sorted(lead_ids), skips=skips)
            else:
                self.record("contact_phone_ok", contact_id=contact_id, lead_ids=sorted(lead_ids))
            return

        self.record(
            "contact_phone_would_update" if not self.live else "contact_phone_update",
            contact_id=contact_id,
            contact_name=contact.get("name"),
            lead_ids=sorted(lead_ids),
            updates=updates,
            skipped=skips,
        )
        if not self.live:
            return
        payload = {"custom_fields_values": [{"field_code": "PHONE", "values": new_values}]}
        response = self.request("PATCH", f"/api/v4/contacts/{contact_id}", json_payload=payload)
        if response.status_code not in {200, 202}:
            self.record_error("contact_phone_update", response, contact_id=contact_id, lead_ids=sorted(lead_ids))
        time.sleep(0.15)

    def run(self) -> dict[str, Any]:
        if self.live and self.confirm != CONFIRM_TEXT:
            raise SystemExit(f"--live uchun --confirm {CONFIRM_TEXT} kerak")

        leads, contact_to_leads = self.fetch_deal_contact_ids()
        contacts_by_id = self.fetch_contacts_by_ids(sorted(contact_to_leads))
        contacts: list[dict[str, Any]] = []
        backup_path = self.save_backup(list(contacts_by_id.values())) if self.live else ""
        for contact_id, lead_ids in sorted(contact_to_leads.items()):
            contact = contacts_by_id.get(contact_id)
            if not contact:
                continue
            contacts.append(contact)
            values = self.phone_field_values(contact)
            if not values:
                self.record("contact_skipped_no_phone", contact_id=contact_id, lead_ids=sorted(lead_ids))
                continue
            new_values, results = self.build_phone_values(values)
            self.patch_contact_phone(
                contact=contact,
                lead_ids=lead_ids,
                new_values=new_values,
                results=results,
            )

        return {
            "success": not self.errors,
            "live": self.live,
            "include_closed": self.include_closed,
            "backup_path": backup_path,
            "checked_leads": len(leads),
            "checked_contacts": len(contact_to_leads),
            "actions_count": len(self.actions),
            "errors_count": len(self.errors),
            "actions": self.actions,
            "errors": self.errors,
        }

    def verify(self) -> dict[str, Any]:
        self.live = False
        result = self.run()
        remaining = [
            action
            for action in result["actions"]
            if action["action"] == "contact_phone_would_update"
        ]
        skipped = [
            action
            for action in result["actions"]
            if action["action"] == "contact_skipped_phone"
        ]
        return {
            "success": not remaining and not self.errors,
            "checked_leads": result["checked_leads"],
            "checked_contacts": result["checked_contacts"],
            "remaining_updates": len(remaining),
            "skipped_ambiguous_or_foreign": len(skipped),
            "errors": self.errors,
        }


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Normalize amoCRM deal contact phones to +998 format.")
    parser.add_argument("--live", action="store_true", help="Apply contact PHONE updates.")
    parser.add_argument("--confirm", default="", help=f"Required for --live: {CONFIRM_TEXT}")
    parser.add_argument("--verify", action="store_true", help="Read-only verification after live update.")
    parser.add_argument("--limit", type=int, default=None, help="Limit fetched leads for testing.")
    parser.add_argument("--include-closed", action="store_true", help="Also scan Won/Lost deals.")
    args = parser.parse_args()

    normalizer = AmoCRMDealPhoneNormalizer(
        live=args.live,
        confirm=args.confirm,
        limit=args.limit,
        include_closed=args.include_closed,
    )
    result = normalizer.verify() if args.verify else normalizer.run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("success"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
