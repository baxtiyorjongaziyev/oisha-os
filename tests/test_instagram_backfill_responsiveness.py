"""Slow Meta HTTP must not block the API event loop."""
import asyncio
import threading
from types import SimpleNamespace

import pytest

from src.services.core.instagram import backfill


@pytest.mark.asyncio
@pytest.mark.parametrize("slow_stage", ["media", "comments", "replies", "send"])
async def test_slow_meta_call_keeps_event_loop_responsive(monkeypatch, slow_stage):
    started = threading.Event()
    release = threading.Event()
    responsiveness = []

    def call(stage, result):
        if stage == slow_stage:
            started.set()
            responsiveness.append(release.wait(timeout=2))
        return result

    client = SimpleNamespace(
        configured=True, access_token="test-token", instagram_account_id="own",
        list_media=lambda **kw: call("media", {"ok": True, "data": [{"id": "m"}]}),
    )
    monkeypatch.setattr(backfill, "InstagramGraphClient", lambda: client)
    monkeypatch.setattr(backfill, "_REPLY_THROTTLE_SEC", 0)
    monkeypatch.setattr(backfill, "_fetch_media_comments", lambda *a: call(
        "comments", [{"id": "c", "text": "hello", "from": {"id": "other"}}],
    ))
    monkeypatch.setattr(backfill, "_fetch_comment_replies", lambda *a: call("replies", []))

    async def reply_text(*args):
        return "test reply"

    async def heartbeat():
        while not started.is_set():
            await asyncio.sleep(0.001)
        release.set()

    tick = asyncio.create_task(heartbeat())
    try:
        result = await backfill.backfill_unanswered_comments(
            generate_reply_fn=reply_text,
            reply_to_comment_fn=lambda *args: call("send", True),
        )
        await tick
    finally:
        release.set()
        tick.cancel()
    assert responsiveness == [True], "Meta I/O blocked the API heartbeat"
    assert result["answered"] == 1
    assert result["errors"] == 0
