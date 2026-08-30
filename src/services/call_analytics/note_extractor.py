"""
Note inspection and metadata extraction helpers for Call Analytics.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List

import structlog
from src.services.call_analytics.helpers import ANALYSIS_MARKER, _CALL_NOTE_TYPES

logger = structlog.get_logger()


class NoteExtractorMixin:
    """Methods for extracting metadata and call info from AmoCRM notes."""

    @staticmethod
    def _lead_has_analysis(notes: List[Dict[str, Any]]) -> bool:
        return any(
            ANALYSIS_MARKER in str((note.get("params") or {}).get("text") or "")
            for note in notes
        )

    @staticmethod
    def _note_has_analysis_for_call(notes: List[Dict[str, Any]], call_id: str) -> bool:
        if not call_id:
            return False
        return any(
            ANALYSIS_MARKER in str((note.get("params") or {}).get("text") or "")
            and f"Call ID: {call_id}"
            in str((note.get("params") or {}).get("text") or "")
            for note in notes
        )

    def _looks_like_call_note(self, note: Dict[str, Any]) -> bool:
        note_type = str(note.get("note_type") or "").lower()
        if note_type in _CALL_NOTE_TYPES:
            return True
        return (
            self._find_audio_url(note.get("params") or {}, strict=True)
            is not None
        )

    def _extract_call_id(
        self, note: Dict[str, Any], lead_id: int, audio_url: str
    ) -> str:
        params = note.get("params") or {}
        for key in (
            "uniq",
            "call_id",
            "record_id",
            "recording_id",
            "phone_call_id",
        ):
            value = params.get(key) if isinstance(params, dict) else None
            if value:
                return str(value)
        if note.get("id"):
            return str(note["id"])
        digest = hashlib.sha1(
            f"{lead_id}:{audio_url}".encode("utf-8"),
            usedforsecurity=False,
        ).hexdigest()[:16]
        return f"lead-{lead_id}-{digest}"

    @staticmethod
    def _extract_call_duration_seconds(note: Dict[str, Any]) -> int:
        params = note.get("params") or {}
        if not isinstance(params, dict):
            return 0
        for key in (
            "duration",
            "duration_seconds",
            "duration_sec",
            "call_duration",
        ):
            value = params.get(key)
            if value is None:
                continue
            try:
                return max(0, int(float(value)))
            except (TypeError, ValueError):
                continue
        return 0

    def _extract_phone_from_note(self, note: Dict[str, Any]) -> str:
        params = note.get("params") or {}
        if not isinstance(params, dict):
            return ""
        for key in ("phone", "caller_phone", "source_phone", "from", "to"):
            value = params.get(key)
            if value:
                return str(value)
        return ""

    @staticmethod
    def _extract_lead_phone(lead: Dict[str, Any]) -> str:
        try:
            contacts = (
                lead.get("_embedded", {}).get("contacts", [])
                or lead.get("contacts", [])
            )
            for contact in contacts:
                for field in contact.get("custom_fields_values") or []:
                    if str(field.get("field_code", "")).upper() == "PHONE":
                        values = field.get("values") or []
                        if values:
                            return str(values[0].get("value", ""))
        except Exception as exc:
            logger.error("[CALL] Failed to extract lead phone: %s", exc)
        return ""
