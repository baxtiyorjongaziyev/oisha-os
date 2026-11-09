"""Synthetic fixtures only: never connect Telegram or a production database."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
import json
import sqlite3

import pytest

from src.services.core.leads.prospect_signals import classify_message
from src.services.core.leads.prospect_store import ProspectStore
from src.services.core.leads.prospect_discovery import scan_prospects
from src.handlers.msg_pipeline.prospect_commands import handle_prospect_command

NOW = datetime(2026, 10, 13, 10, tzinfo=timezone.utc)
CHAT = -1001234567890


def message(text="Yangi mahsulot uchun qadoqlash dizayni kerak", **kwargs):
    return SimpleNamespace(message=text, id=12, date=NOW, sender_id=123, **kwargs)


class Pool:
    """In-memory SQL adapter exercising the production queries."""
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row

    async def execute(self, sql, params=None):
        return [dict(r) for r in self.conn.execute(sql, params or []).fetchall()]

    async def commit(self):
        self.conn.commit()


class Client:
    def is_connected(self):
        return True

    async def iter_messages(self, chat_id, limit):
        yield message()


@pytest.mark.parametrize("text", [
    "Logotip yasaymiz, xizmatlarimizga murojaat qiling",
    "Dizayner kerak. Vakansiya, oylik kelishiladi",
    "Logotip kerak emas",
    "Biz ishlab chiqaruvchimiz. Telefon: +998901234567",
    "Qadoqlash qilamiz. Sizga dizayner kerakmi?",
])
def test_seller_intro_job_and_negated_need_are_not_candidates(text):
    assert classify_message(message(text), CHAT, NOW) == []


def test_evidence_and_unknown_fields():
    result = classify_message(message("Logotip kerak. +998 (90) 123-45-67"), CHAT, NOW)[0]
    assert result.source_url == "https://t.me/c/1234567890/12"
    assert result.phone == "+998901234567"
    assert result.budget is None and result.purchase_timing is None
    assert result.qualification == "needs_review"
    assert result.crm_status == "unchecked"
    assert result.evidence == "Logotip kerak"


@pytest.mark.asyncio
async def test_repeat_and_restart_and_repost_are_deduplicated():
    pool = Pool()
    store = ProspectStore(pool)
    await store.initialize()
    await store.add_source(CHAT, "Synthetic source")
    first = await scan_prospects(Client(), store, now=NOW)
    assert first["new"] == 1
    restarted = ProspectStore(pool)
    second = await scan_prospects(Client(), restarted, now=NOW)
    assert second["new"] == 0
    same = classify_message(message(), CHAT - 1, NOW)
    assert not await restarted.save(same[0])
    assert len(await restarted.recent()) == 1


@pytest.mark.asyncio
async def test_missing_sources_is_unknown_not_zero():
    store = ProspectStore(Pool())
    result = await scan_prospects(Client(), store, now=NOW)
    assert result["status"] == "source_unavailable" and result["new"] is None


@pytest.mark.asyncio
async def test_partial_failure_keeps_good_source_and_records_health():
    class PartialClient(Client):
        async def iter_messages(self, chat_id, limit):
            if chat_id == CHAT - 1:
                raise RuntimeError("synthetic external failure")
            yield message("Sayt kerak")

    store = ProspectStore(Pool())
    await store.initialize()
    await store.add_source(CHAT, "Good synthetic source")
    await store.add_source(CHAT - 1, "Bad synthetic source")
    result = await scan_prospects(PartialClient(), store, now=NOW)
    assert result["status"] == "partial" and result["new"] == 1
    assert {r["last_status"] for r in await store.sources()} == {"ok", "source_unavailable"}
    assert "synthetic external failure" not in json.dumps(result)


@pytest.mark.asyncio
async def test_old_posts_are_ignored_and_limit_is_explicit():
    class OldClient(Client):
        async def iter_messages(self, chat_id, limit):
            old = message()
            old.date = NOW - timedelta(days=8)
            yield old

    class BusyClient(Client):
        async def iter_messages(self, chat_id, limit):
            for _ in range(limit):
                yield message("Synthetic unrelated text")

    store = ProspectStore(Pool())
    await store.initialize()
    await store.add_source(CHAT, "Synthetic source")
    assert (await scan_prospects(OldClient(), store, now=NOW))["new"] == 0
    result = await scan_prospects(BusyClient(), store, now=NOW)
    assert result["sources"][0]["status"] == "window_limited"


@pytest.mark.asyncio
async def test_auto_flag_is_durable_and_default_off():
    pool = Pool()
    store = ProspectStore(pool)
    await store.initialize()
    assert not await store.auto_enabled()
    await store.set_auto(True)
    assert await ProspectStore(pool).auto_enabled()
    await store.set_auto(False)
    assert not await store.auto_enabled()


@pytest.mark.asyncio
async def test_non_owner_cannot_change_sources_or_auto():
    event = SimpleNamespace(respond=AsyncMock())
    assert await handle_prospect_command(event, "/lead_auto on", None, is_owner=False)
    assert "faqat owner" in event.respond.call_args.args[0]
    assert await handle_prospect_command(event, "/lead_sources add @test", None, is_owner=False)


@pytest.mark.asyncio
async def test_command_does_not_echo_post_formatting(monkeypatch):
    store = ProspectStore(Pool())
    await store.initialize()
    prospect = classify_message(message("Logo kerak <script>bad</script>"), CHAT, NOW)[0]
    await store.save(prospect)
    monkeypatch.setattr("src.services.core.leads.prospect_store.get_prospect_store", lambda: store)
    event = SimpleNamespace(respond=AsyncMock())
    assert await handle_prospect_command(event, "/lead_candidates", None, is_owner=True)
    assert event.respond.call_args.kwargs["parse_mode"] is None
    assert "noma’lum" in event.respond.call_args.args[0]


@pytest.mark.asyncio
async def test_source_suggestion_excludes_private_and_unrelated_chats():
    from telethon.tl.types import Channel, User
    from src.services.core.leads.prospect_sources import suggest_sources

    class DialogClient(Client):
        async def iter_dialogs(self, limit):
            for entity in [
                User(id=1, first_name="Biznes"),
                Channel(id=2, title="Biznes yopiq", photo=None, date=NOW),
                Channel(id=3, title="Networking", username="synthetic_network", photo=None, date=NOW),
                Channel(id=4, title="Music", username="synthetic_music", photo=None, date=NOW),
            ]:
                yield SimpleNamespace(entity=entity)

    result = await suggest_sources(DialogClient())
    assert result["status"] == "ok"
    assert [s["title"] for s in result["sources"]] == ["Networking"]
    assert result["sources"][0]["status"] == "needs_review"


@pytest.mark.asyncio
async def test_disabled_source_is_not_scanned():
    store = ProspectStore(Pool())
    await store.initialize()
    await store.add_source(CHAT, "Synthetic source")
    await store.disable_source(CHAT)
    result = await scan_prospects(Client(), store, now=NOW)
    assert result["status"] == "source_unavailable"
    assert await store.recent() == []


@pytest.mark.asyncio
async def test_disconnected_source_records_failure_instead_of_previous_success():
    store = ProspectStore(Pool())
    await store.initialize()
    await store.add_source(CHAT, "Synthetic source")
    await scan_prospects(Client(), store, now=NOW)
    result = await scan_prospects(None, store, now=NOW)
    assert result["new"] is None
    assert (await store.sources())[0]["last_status"] == "source_unavailable"


@pytest.mark.asyncio
async def test_admin_gate_rejects_unauthorized_before_prospect_dispatch(monkeypatch):
    from src import config
    from src.handlers.msg_pipeline.admin_commands import process_admin_commands

    monkeypatch.setattr(config, "OWNER_ID", 1)
    monkeypatch.setattr(config, "WHITELIST_IDS", [])
    event = SimpleNamespace(
        is_private=True, sender_id=2, message=SimpleNamespace(text="/lead_scan"),
        respond=AsyncMock(),
    )
    kwargs = {name: None for name in (
        "client", "bot_client", "msg_controller", "settings", "meeting_scheduler",
        "get_surgical_integration", "_negotiation_int", "lead_scraper", "audit_agent",
        "auto_lead_agent", "admin_bot", "TN5_GROUP_ID", "TN5_TOPIC_ID",
    )}
    assert not await process_admin_commands(event, **kwargs)
    event.respond.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("hour,enabled,expected", [(6, True, False), (23, True, False), (10, False, False), (10, True, True)])
async def test_scheduler_respects_auto_flag_and_quiet_hours(monkeypatch, hour, enabled, expected):
    import asyncio
    from src.schedulers.prospect_discovery_scheduler import prospect_discovery_loop

    store = SimpleNamespace(initialize=AsyncMock(), auto_enabled=AsyncMock(return_value=enabled))
    scan = AsyncMock(return_value={"status": "ok", "new": 0})
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)
        if seconds == 3600:
            raise asyncio.CancelledError

    monkeypatch.setattr("src.schedulers.prospect_discovery_scheduler.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("src.services.core.leads.prospect_store.get_prospect_store", lambda: store)
    monkeypatch.setattr("src.services.core.leads.prospect_discovery.scan_prospects", scan)
    monkeypatch.setattr("src.time_utils.get_local_now", lambda: SimpleNamespace(hour=hour))
    with pytest.raises(asyncio.CancelledError):
        await prospect_discovery_loop()
    assert bool(scan.await_count) == expected
    assert sleeps == [120, 3600]


def test_sender_internal_team_or_provider_is_rejected():
    sender = SimpleNamespace(first_name="Mumtozmaxal", last_name="Normurodova", username="MumtozmaxalJonbranding")
    msg = message("Logotip kerak. +998901234567", sender=sender)
    assert classify_message(msg, CHAT, NOW) == []

    sender2 = SimpleNamespace(first_name="Dilnoza", last_name="Uztelecom", username="uztelecom_dilnoza")
    msg2 = message("Dizayn kerak. +998901234567", sender=sender2)
    assert classify_message(msg2, CHAT, NOW) == []
