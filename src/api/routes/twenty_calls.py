"""Call recordings -> Twenty notes, deduplicated by call_id.

Fail-closed: no secret configured => 503; wrong secret => 401;
Twenty not configured => 503; Twenty write failed => 502 (caller retries);
unknown outcome => 502 and the call stays ``uncertain`` until reconciled by
``callId`` lookup, so a retry never creates a second note.
"""
from __future__ import annotations

import hmac
import os
from typing import Literal, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from src.services.core.crm.twenty import builders
from src.services.core.crm.twenty.client import (
    TwentyClient, TwentyError, TwentyNotConfigured, TwentyUncertain, config_from_env,
)
from src.services.core.crm.twenty.mapping import MapStore, digest

router = APIRouter(prefix="/api/twenty", tags=["twenty"])
SYSTEM, KIND = "moizvonki", "call"


class CallEvent(BaseModel):
    call_id: str = Field(min_length=1, max_length=128)
    phone: str = Field(min_length=7, max_length=32)
    direction: Literal["in", "out"]
    duration: int = Field(ge=0, le=86400)
    recording_url: Optional[str] = Field(default=None, max_length=1000)
    manager: Optional[str] = Field(default=None, max_length=100)
    started_at: Optional[int] = Field(default=None, ge=0)


def _check_secret(provided: Optional[str]) -> None:
    expected = os.getenv("TWENTY_CALLS_WEBHOOK_SECRET", "").strip()
    if not expected:
        raise HTTPException(503, "webhook_secret_not_configured")
    if not provided or not hmac.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(401, "unauthorized")


def call_note(event: CallEvent) -> dict:
    mins, secs = divmod(event.duration, 60)
    title = "Kiruvchi qo'ng'iroq" if event.direction == "in" else "Chiquvchi qo'ng'iroq"
    lines = [f"Telefon: +998{builders.normalize_phone(event.phone) or event.phone}",
             f"Davomiyligi: {mins} daq {secs} son"]
    if event.manager:
        lines.append(f"Mas'ul: {event.manager}")
    if event.recording_url:
        lines.append(f"[Yozuvni tinglash]({event.recording_url})")
    return {"title": title, "callId": event.call_id, "bodyV2": {"markdown": "\n\n".join(lines)}}


async def _existing_note(client, call_id: str):
    rows = await client.find("notes", f'callId[eq]:"{call_id}"')
    if len(rows) > 1:
        raise TwentyError("duplicate_call_notes")
    return rows[0]["id"] if rows else None


async def record_call(event: CallEvent, client, maps) -> dict:
    current = await maps.get(KIND, event.call_id, SYSTEM)
    if current and current["state"] == "synced":
        # Re-link on retry: a previous attempt may have failed after the note was created.
        linked = await _link_person(client, current["twenty_id"], event.phone)
        return {"status": "duplicate", "note_id": current["twenty_id"], "linked": linked}
    note_id = None
    if current and current["state"] in ("uncertain", "pending"):
        note_id = await _existing_note(client, event.call_id)
    body = call_note(event)
    if note_id is None:
        await maps.put(KIND, event.call_id, state="pending", system=SYSTEM)
        try:
            note_id = (await client.create("notes", "note", body))["id"]
        except TwentyUncertain as exc:
            await maps.fail(KIND, event.call_id, str(exc), uncertain=True, system=SYSTEM)
            raise
        except TwentyError as exc:
            await maps.fail(KIND, event.call_id, str(exc), system=SYSTEM)
            raise
    await maps.put(KIND, event.call_id, state="synced", twenty_id=note_id,
                   dig=digest(body), system=SYSTEM)
    linked = await _link_person(client, note_id, event.phone)
    return {"status": "recorded", "note_id": note_id, "linked": linked}


async def _link_person(client, note_id: str, phone: str) -> bool:
    number = builders.normalize_phone(phone)
    if not number:
        return False
    people = await client.find("people", f'phones.primaryPhoneNumber[eq]:"{number}"')
    if len(people) != 1:
        return False  # 0 = unknown caller, >1 = ambiguous; never guess
    existing = await client.find(
        "noteTargets", f'and(noteId[eq]:"{note_id}",targetPersonId[eq]:"{people[0]["id"]}")')
    if not existing:
        await client.create("noteTargets", "noteTarget",
                            {"noteId": note_id, "targetPersonId": people[0]["id"]})
    return True


@router.post("/calls")
async def call_webhook(event: CallEvent,
                       x_webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret")):
    _check_secret(x_webhook_secret)
    try:
        url, key = config_from_env()
    except TwentyNotConfigured:
        raise HTTPException(503, "twenty_not_configured")
    from src.database_pool import db_pool
    maps = MapStore(db_pool)
    await maps.init()
    client = TwentyClient(url, key)
    try:
        return await record_call(event, client, maps)
    except TwentyError as exc:
        raise HTTPException(502, str(exc))
    finally:
        await client.aclose()
