"""Pure amoCRM mirror payload -> Twenty REST body builders.

Field names were verified against the running Twenty v2.48 workspace schema
(person.name/phones/emails, opportunity.stage/amount/ownerId/pointOfContactId,
task.title/bodyV2/dueAt/status/assigneeId, note.title/bodyV2, *Targets).
``amoId`` is a custom NUMBER field that must exist on person, opportunity,
task and note (see docs/agents/twenty-crm-runbook.md).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone


def normalize_phone(raw) -> str | None:
    digits = re.sub(r"\D", "", str(raw or ""))
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) == 12 and digits.startswith("998"):
        return digits[3:]
    return None


def _field_values(item: dict, code: str) -> list[str]:
    out = []
    for field in item.get("custom_fields_values") or []:
        if isinstance(field, dict) and field.get("field_code") == code:
            out += [str(v.get("value")) for v in field.get("values") or []
                    if isinstance(v, dict) and v.get("value")]
    return out


def _iso(ts) -> str | None:
    if not isinstance(ts, int) or ts <= 0:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def person(item: dict) -> dict:
    name = (item.get("name") or "").strip() or "Nomsiz mijoz"
    first, _, last = name.partition(" ")
    body: dict = {"amoId": item["id"], "name": {"firstName": first, "lastName": last}}
    phone = next(filter(None, map(normalize_phone, _field_values(item, "PHONE"))), None)
    if phone:
        body["phones"] = {"primaryPhoneNumber": phone, "primaryPhoneCountryCode": "UZ",
                          "primaryPhoneCallingCode": "+998"}
    email = next(iter(_field_values(item, "EMAIL")), None)
    if email:
        body["emails"] = {"primaryEmail": email}
    return body


def first_contact_id(lead: dict) -> int | None:
    contacts = (lead.get("_embedded") or {}).get("contacts") or []
    main = [c for c in contacts if isinstance(c, dict) and c.get("is_main")]
    for contact in main or contacts:
        if isinstance(contact, dict) and isinstance(contact.get("id"), int):
            return contact["id"]
    return None


def opportunity(lead: dict, *, stage: str, owner_id: str | None,
                contact_twenty_id: str | None, currency: str | None) -> dict:
    body: dict = {"amoId": lead["id"], "name": (lead.get("name") or "").strip()
                  or f"Bitim #{lead['id']}", "stage": stage,
                  "ownerId": owner_id, "pointOfContactId": contact_twenty_id}
    price = lead.get("price")
    # Always send amount: omitted PATCH fields keep stale values in Twenty.
    body["amount"] = {
        "amountMicros": price * 1_000_000 if isinstance(price, int) and price > 0 else None,
        "currencyCode": (currency or "UZS").upper()}
    return body


def task(item: dict, *, assignee_id: str | None) -> dict:
    text = (item.get("text") or "").strip()
    return {
        "amoId": item["id"],
        "title": (text.splitlines()[0][:200] if text else f"Vazifa #{item['id']}"),
        "bodyV2": {"markdown": text},
        "dueAt": _iso(item.get("complete_till")),
        "status": "DONE" if item.get("is_completed") else "TODO",
        "assigneeId": assignee_id,
    }


def note(item: dict) -> dict:
    params = item.get("params") or {}
    text = str(params.get("text") or "").strip()
    kind = item.get("note_type") or "common"
    title = {"common": "Izoh", "call_in": "Kiruvchi qo'ng'iroq",
             "call_out": "Chiquvchi qo'ng'iroq"}.get(kind, f"Izoh ({kind})")
    if kind in ("call_in", "call_out"):
        mins, secs = divmod(int(params.get("duration") or 0), 60)
        text = f"Davomiyligi: {mins} daq {secs} son\n\n{text}".strip()
    return {"amoId": item["id"], "title": title, "bodyV2": {"markdown": text[:20000]}}
