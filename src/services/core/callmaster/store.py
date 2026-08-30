"""
Callmaster persistence and campaign lifecycle management.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.services.core.callmaster.models import (
    DATA_FILE_ENV,
    CallAttempt,
    Campaign,
    Contact,
    _new_id,
    _safe_int,
    normalize_phone,
    utc_now_iso,
)
from src.services.core.callmaster.actions import build_oisha_action


class CallmasterStore:
    """Small JSON-backed store for the first self-hosted call MVP."""

    def __init__(self, path: Optional[Path | str] = None) -> None:
        raw_path = path or os.getenv(DATA_FILE_ENV) or "data/callmaster_state.json"
        self.path = Path(raw_path)
        self._lock = threading.RLock()
        self._state = self._load()

    def _empty_state(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        return {"campaigns": {}, "contacts": {}, "attempts": {}, "events": {}}

    def _load(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        if not self.path.exists():
            return self._empty_state()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return self._empty_state()
            empty = self._empty_state()
            for key in empty:
                empty[key].update(data.get(key) or {})
            return empty
        except (OSError, json.JSONDecodeError):
            return self._empty_state()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temp_path.write_text(
            json.dumps(self._state, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temp_path.replace(self.path)

    def create_campaign(
        self,
        *,
        name: str,
        audio_url: str,
        description: str = "",
        max_parallel_calls: int = 10,
        retry_limit: int = 1,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not name.strip():
            raise ValueError("campaign_name_required")
        if not audio_url.strip():
            raise ValueError("audio_url_required")
        campaign = Campaign(
            id=_new_id("cmp"),
            name=name.strip(),
            audio_url=audio_url.strip(),
            description=description.strip(),
            max_parallel_calls=max(1, min(int(max_parallel_calls), 1000)),
            retry_limit=max(0, min(int(retry_limit), 10)),
            metadata=metadata or {},
        )
        with self._lock:
            self._state["campaigns"][campaign.id] = asdict(campaign)
            self._save()
        return asdict(campaign)

    def add_contacts(
        self,
        campaign_id: str,
        contacts: Iterable[Dict[str, Any]],
    ) -> Dict[str, Any]:
        self._require_campaign(campaign_id)
        created: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []
        seen = self._campaign_phones(campaign_id)

        with self._lock:
            for item in contacts:
                try:
                    phone = normalize_phone(str(item.get("phone") or ""))
                except ValueError as exc:
                    skipped.append({"phone": item.get("phone"), "reason": str(exc)})
                    continue
                if phone in seen:
                    skipped.append({"phone": phone, "reason": "duplicate_in_campaign"})
                    continue
                contact = Contact(
                    id=_new_id("cnt"),
                    campaign_id=campaign_id,
                    phone=phone,
                    name=str(item.get("name") or "").strip(),
                    lead_id=_safe_int(item.get("lead_id")),
                    metadata=dict(item.get("metadata") or {}),
                )
                seen.add(phone)
                row = asdict(contact)
                self._state["contacts"][contact.id] = row
                created.append(row)
            self._touch_campaign(campaign_id)
            self._save()

        return {"created": created, "skipped": skipped}

    def launch_campaign(self, campaign_id: str, *, provider: str = "local") -> Dict[str, Any]:
        campaign = self._require_campaign(campaign_id)
        queued: List[Dict[str, Any]] = []
        with self._lock:
            for contact in self._contacts_for_campaign(campaign_id):
                if contact["status"] not in {"pending", "failed", "no_answer"}:
                    continue
                if int(contact.get("attempts_count") or 0) > int(campaign.get("retry_limit") or 0):
                    continue
                attempt = CallAttempt(
                    id=_new_id("att"),
                    campaign_id=campaign_id,
                    contact_id=contact["id"],
                    phone=contact["phone"],
                    provider=provider,
                )
                self._state["attempts"][attempt.id] = asdict(attempt)
                contact["status"] = "queued"
                contact["attempts_count"] = int(contact.get("attempts_count") or 0) + 1
                contact["updated_at"] = utc_now_iso()
                queued.append(asdict(attempt))
            campaign["status"] = "running" if queued else campaign.get("status", "draft")
            campaign["updated_at"] = utc_now_iso()
            self._save()
        return {"campaign": campaign, "queued_attempts": queued}

    def record_webhook_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        event_id = _new_id("evt")
        event_name = str(payload.get("event") or payload.get("status") or "").strip()
        digit = str(payload.get("digit") or payload.get("dtmf") or "").strip()
        campaign_id = str(payload.get("campaign_id") or "").strip()
        contact_id = str(payload.get("contact_id") or "").strip()
        attempt_id = str(payload.get("attempt_id") or "").strip()
        phone = str(payload.get("phone") or "").strip()

        with self._lock:
            contact = self._resolve_contact(campaign_id, contact_id, phone)
            attempt = self._resolve_attempt(attempt_id, payload, contact)
            if contact:
                contact["last_event"] = event_name
                contact["last_digit"] = digit
                contact["updated_at"] = utc_now_iso()
                contact["status"] = self._status_from_event(event_name, digit)
                if payload.get("lead_id") and not contact.get("lead_id"):
                    contact["lead_id"] = _safe_int(payload.get("lead_id"))
            if attempt:
                attempt["status"] = self._status_from_event(event_name, digit)
                attempt["digit"] = digit
                attempt["duration_sec"] = _safe_int(payload.get("duration_sec")) or 0
                attempt["provider_call_id"] = str(payload.get("provider_call_id") or attempt.get("provider_call_id") or "")
                attempt["updated_at"] = utc_now_iso()
                attempt["metadata"] = {**dict(attempt.get("metadata") or {}), **dict(payload.get("metadata") or {})}
            event_row = {
                "id": event_id,
                "received_at": utc_now_iso(),
                "payload": payload,
                "contact_id": contact.get("id") if contact else None,
                "attempt_id": attempt.get("id") if attempt else None,
            }
            self._state["events"][event_id] = event_row
            self._save()

        action = build_oisha_action(payload, contact=contact, attempt=attempt)
        return {"event": event_row, "contact": contact, "attempt": attempt, "action": action}

    def get_campaign(self, campaign_id: str) -> Dict[str, Any]:
        campaign = self._require_campaign(campaign_id)
        return {"campaign": campaign, "summary": self.campaign_summary(campaign_id)}

    def campaign_summary(self, campaign_id: str) -> Dict[str, Any]:
        self._require_campaign(campaign_id)
        contacts = self._contacts_for_campaign(campaign_id)
        attempts = [
            item
            for item in self._state["attempts"].values()
            if item.get("campaign_id") == campaign_id
        ]
        by_status: Dict[str, int] = {}
        for contact in contacts:
            by_status[contact.get("status", "unknown")] = by_status.get(contact.get("status", "unknown"), 0) + 1
        return {
            "campaign_id": campaign_id,
            "contacts_total": len(contacts),
            "attempts_total": len(attempts),
            "by_status": by_status,
            "pressed_1": by_status.get("pressed_1", 0),
            "answered": by_status.get("answered", 0) + by_status.get("pressed_1", 0),
        }

    def _require_campaign(self, campaign_id: str) -> Dict[str, Any]:
        campaign = self._state["campaigns"].get(campaign_id)
        if not campaign:
            raise KeyError("campaign_not_found")
        return campaign

    def _touch_campaign(self, campaign_id: str) -> None:
        campaign = self._state["campaigns"].get(campaign_id)
        if campaign:
            campaign["updated_at"] = utc_now_iso()

    def _campaign_phones(self, campaign_id: str) -> set[str]:
        return {
            item["phone"]
            for item in self._state["contacts"].values()
            if item.get("campaign_id") == campaign_id and item.get("phone")
        }

    def _contacts_for_campaign(self, campaign_id: str) -> List[Dict[str, Any]]:
        return [
            item
            for item in self._state["contacts"].values()
            if item.get("campaign_id") == campaign_id
        ]

    def _resolve_contact(
        self, campaign_id: str, contact_id: str, phone: str
    ) -> Optional[Dict[str, Any]]:
        if contact_id and contact_id in self._state["contacts"]:
            return self._state["contacts"][contact_id]
        normalized = None
        if phone:
            try:
                normalized = normalize_phone(phone)
            except ValueError:
                normalized = phone
        for contact in self._state["contacts"].values():
            if campaign_id and contact.get("campaign_id") != campaign_id:
                continue
            if normalized and contact.get("phone") == normalized:
                return contact
        return None

    def _resolve_attempt(
        self,
        attempt_id: str,
        payload: Dict[str, Any],
        contact: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if attempt_id and attempt_id in self._state["attempts"]:
            return self._state["attempts"][attempt_id]
        provider_call_id = str(payload.get("provider_call_id") or "")
        if provider_call_id:
            for attempt in self._state["attempts"].values():
                if attempt.get("provider_call_id") == provider_call_id:
                    return attempt
        if contact:
            for attempt in reversed(list(self._state["attempts"].values())):
                if attempt.get("contact_id") == contact.get("id"):
                    return attempt
        return None

    @staticmethod
    def _status_from_event(event_name: str, digit: str) -> str:
        event_lower = event_name.lower()
        if digit == "1":
            return "pressed_1"
        if event_lower in {"answered", "call_answered"}:
            return "answered"
        if event_lower in {"failed", "busy", "error"}:
            return "failed"
        if event_lower in {"no_answer", "timeout", "missed"}:
            return "no_answer"
        if event_lower in {"queued", "calling", "dialing"}:
            return "calling"
        return event_lower or "updated"
