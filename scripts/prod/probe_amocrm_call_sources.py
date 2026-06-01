"""Read-only amoCRM call source inventory without printing customer data."""

import json
import os
import sys
from collections import Counter
from typing import Any, Dict, List

import requests

sys.path.insert(0, os.getcwd())

from src.services.core.amocrm_sync import AmoCRMSync
from src.settings import settings


def _secret_text(value: Any) -> str:
    getter = getattr(value, "get_secret_value", None)
    return str(getter() if callable(getter) else value or "")


def _new_client() -> AmoCRMSync:
    return AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=_secret_text(settings.AMOCRM_CLIENT_SECRET),
        redirect_url=settings.AMOCRM_REDIRECT_URL,
    )


def _fetch_notes(client: AmoCRMSync, entity_type: str) -> Dict[str, Any]:
    url = f"{client.base_url}/api/v4/{entity_type}/notes"
    params: List[tuple[str, Any]] = [
        ("limit", 250),
        ("order[updated_at]", "desc"),
        ("filter[note_type][]", "call_in"),
        ("filter[note_type][]", "call_out"),
    ]
    response = requests.get(url, headers=client._get_headers(), params=params, timeout=30)
    notes = (
        response.json().get("_embedded", {}).get("notes", [])
        if response.status_code == 200
        else []
    )
    sources = Counter(
        str((note.get("params") or {}).get("source") or "unknown") for note in notes
    )
    result = {
        "http_status": response.status_code,
        "count": len(notes),
        "with_link": sum(
            1 for note in notes if (note.get("params") or {}).get("link")
        ),
        "note_types": dict(Counter(str(note.get("note_type") or "") for note in notes)),
        "sources": dict(sources.most_common(10)),
    }
    if entity_type == "contacts":
        linked_lead_counts = Counter()
        sampled = 0
        for note in notes:
            if sampled >= 25 or not (note.get("params") or {}).get("link"):
                continue
            contact_id = note.get("entity_id")
            if not contact_id:
                continue
            contact_response = requests.get(
                f"{client.base_url}/api/v4/contacts/{contact_id}",
                headers=client._get_headers(),
                params={"with": "leads"},
                timeout=30,
            )
            leads = (
                contact_response.json().get("_embedded", {}).get("leads", [])
                if contact_response.status_code == 200
                else []
            )
            linked_lead_counts[str(len(leads))] += 1
            sampled += 1
        result["linked_lead_sample"] = {
            "sampled": sampled,
            "counts": dict(linked_lead_counts),
        }
    return result


def _fetch_call_events(client: AmoCRMSync) -> Dict[str, Any]:
    params: List[tuple[str, Any]] = [
        ("limit", 250),
        ("filter[type][]", "incoming_call"),
        ("filter[type][]", "outgoing_call"),
    ]
    response = requests.get(
        f"{client.base_url}/api/v4/events",
        headers=client._get_headers(),
        params=params,
        timeout=30,
    )
    events = (
        response.json().get("_embedded", {}).get("events", [])
        if response.status_code == 200
        else []
    )
    return {
        "http_status": response.status_code,
        "count": len(events),
        "event_types": dict(Counter(str(event.get("type") or "") for event in events)),
        "entity_types": dict(
            Counter(str(event.get("entity_type") or "") for event in events)
        ),
    }


def main() -> None:
    client = _new_client()
    print(
        json.dumps(
            {
                "leads": _fetch_notes(client, "leads"),
                "contacts": _fetch_notes(client, "contacts"),
                "companies": _fetch_notes(client, "companies"),
                "events": _fetch_call_events(client),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
