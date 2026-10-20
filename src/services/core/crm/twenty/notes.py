"""Paginated, checkpointed pull of ALL amoCRM lead notes into the mirror.

PR #923 reads only the latest 50 notes per lead for display. Migration needs the
full history, so this walks /api/v4/leads/notes page by page and stores each
note as mirror kind ``notes`` (resumable via ``progress_notes`` meta).
"""
from __future__ import annotations

import time


async def pull_notes(store, remote, *, clock=time.time, max_pages: int = 40) -> bool:
    progress = await store.meta("progress_notes")
    if progress is None:
        progress = {"page": 1, "start": await store.meta("cursor_notes", 0),
                    "end": int(clock())}
    for _ in range(max_pages):
        data = await remote.request("get", "/api/v4/leads/notes", params={
            "page": progress["page"], "limit": 250,
            "filter[updated_at][from]": max(0, progress["start"] - 120),
            "order[id]": "asc",
        })
        embedded = data.get("_embedded")
        rows = embedded.get("notes", []) if isinstance(embedded, dict) else None
        if not isinstance(rows, list):
            raise ValueError("invalid_notes_page")
        for note in rows:
            if not isinstance(note, dict) or not isinstance(note.get("id"), int):
                raise ValueError("invalid_note")
            note = dict(note, entity_type="leads")
            await store.upsert("notes", note, int(clock()))
        if not (data.get("_links") or {}).get("next"):
            await store.set_meta("cursor_notes", progress["end"])
            await store.set_meta("progress_notes", None)
            return True
        if not rows:
            raise ValueError("empty_page_with_next")
        progress["page"] += 1
        await store.set_meta("progress_notes", progress)
    return False
