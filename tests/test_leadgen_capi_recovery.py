"""Synthetic Lead Ads fixtures; no live CRM, Meta, or customer data."""
import asyncio
import sqlite3
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from src.services.core.instagram import leadgen_delivery as delivery
from src.services.core.marketing import meta_capi, meta_capi_store


class SqlitePool:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row

    async def execute(self, query, params=None):
        return [dict(row) for row in self.conn.execute(query, params or []).fetchall()]

    async def commit(self):
        self.conn.commit()


@pytest_asyncio.fixture
async def isolated(monkeypatch, tmp_path):
    from src.services.core.instagram import leadgen_capi as capi
    pool = SqlitePool()
    monkeypatch.setattr(delivery, "_DB_PATH", tmp_path / "delivery.db")
    monkeypatch.setattr(meta_capi_store, "_pool", lambda: pool)
    monkeypatch.setattr(meta_capi_store, "_table_ready", False)
    monkeypatch.setattr(meta_capi, "_config", lambda: {
        "enabled": True, "dataset_id": "synthetic", "token": "synthetic-test-token",
        "test_code": "", "version": "v21.0",
    })
    yield pool
    tasks = list(capi._in_flight.values())
    if capi._recovery_task is not None and not capi._recovery_task.done():
        tasks.append(capi._recovery_task)
    if tasks:
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 10)
    await asyncio.sleep(0)
    pool.conn.close()


def test_checkpoint_persists_capi_intent_atomically(isolated):
    delivery.save_crm_checkpoint("123", 77, queue_capi=True)
    with delivery._connection() as conn:
        assert conn.execute("SELECT lead_id FROM capi_lead_queue WHERE leadgen_id='123'").fetchone() == (77,)


@pytest.mark.asyncio
async def test_watchdog_recovers_capi_with_no_incomplete_channels(monkeypatch, isolated):
    from src.services.core.instagram import leadgen_watchdog as watchdog
    called = asyncio.Event()
    loop = asyncio.get_running_loop()

    def fake_post(cfg, event):
        loop.call_soon_threadsafe(called.set)
        return {"ok": True}

    delivery.save_crm_checkpoint("123", 77, queue_capi=True)
    delivery.record_delivery_status("123", 77, True, True, True)
    monkeypatch.setattr(meta_capi, "_post_events", fake_post)
    assert await watchdog.retry_pending_leadgen_deliveries() == 0
    await asyncio.wait_for(called.wait(), 2)


@pytest.mark.asyncio
async def test_router_finishes_checkpoint_and_channels_while_capi_waits(monkeypatch, isolated):
    from src.services.core.instagram import leadgen_router as router
    from src.services.core.marketing import meta_capi_triggers as triggers
    started, release = asyncio.Event(), asyncio.Event()

    async def slow_capi(*args, **kwargs):
        started.set()
        await release.wait()
        return None

    amo = AsyncMock()
    amo.find_active_lead_by_phone = lambda phone: None
    amo.ensure_lead.return_value = 77
    monkeypatch.setattr(router, "_amocrm_instance", lambda: amo)
    monkeypatch.setattr(router, "is_leadgen_processed", lambda _: False)
    monkeypatch.setattr(router, "mark_leadgen_processed", lambda *a, **k: None)
    monkeypatch.setattr(router, "resolve_ad_name", lambda _: None)
    monkeypatch.setattr(router, "save_attribution", lambda *a: None)
    monkeypatch.setattr(router, "estimate_cost_per_lead", lambda _: None)
    monkeypatch.setattr(router, "_notify_telegram", lambda *a, **k: True)
    monkeypatch.setattr(router, "append_lead_to_sheet", lambda *a, **k: True)
    monkeypatch.setattr(triggers, "on_lead_created", slow_capi)
    event = {"leadgen_id": "123", "field_data": [
        {"name": "full_name", "values": ["Synthetic Test"]},
        {"name": "phone_number", "values": ["+998900000000"]},
    ]}
    try:
        result = await asyncio.wait_for(router.route_leadgen_event(event, "synthetic-token"), 10)
        assert result["ok"]
        assert delivery.get_crm_checkpoint("123") == 77
        assert delivery.is_delivery_complete("123")
        await asyncio.wait_for(started.wait(), 1)
        amo.add_lead_tag.assert_any_await(77, "manba:reklama")
    finally:
        release.set()


async def drain_dispatch():
    from src.services.core.instagram import leadgen_capi as capi
    if capi._recovery_task is not None:
        await capi._recovery_task
    if capi._in_flight:
        await asyncio.gather(*list(capi._in_flight.values()))
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_failure_then_watchdog_retry_does_not_redeliver_channels(monkeypatch, isolated):
    from src.services.core.instagram import leadgen_capi as capi, leadgen_watchdog as watchdog
    from src.services.core.instagram import leadgen_router as router
    from src.services.core.instagram import leadgen_capi_outbox as outbox
    posted = []
    results = iter([{"ok": False, "error": "HTTP 500"}, {"ok": True}])
    monkeypatch.setattr(meta_capi, "_post_events", lambda cfg, ev: posted.append(ev) or next(results))
    delivery.save_crm_checkpoint("123", 77, queue_capi=True)
    delivery.record_delivery_status("123", 77, True, True, True)
    capi.schedule_lead_event("123", 77)
    await drain_dispatch()
    assert await meta_capi_store.get_event_status("123", "Lead") == "failed"
    with delivery._connection() as conn:
        assert conn.execute("SELECT count(*) FROM capi_lead_queue").fetchone()[0] == 1
        conn.execute("UPDATE capi_lead_queue SET next_attempt = 0")
    monkeypatch.setattr(router, "mark_leadgen_processed", lambda *a, **k: None)
    amo = AsyncMock()
    monkeypatch.setattr(router, "_amocrm_instance", lambda: amo)
    skipped = await router.route_leadgen_event({"leadgen_id": "123"}, "synthetic", force=True)
    assert skipped["skipped"]
    assert await watchdog.retry_pending_leadgen_deliveries() == 0
    await drain_dispatch()
    assert await meta_capi_store.get_event_status("123", "Lead") == "sent"
    assert outbox.pending() == []
    assert len(posted) == 2
    assert posted[0]["event_id"] == posted[1]["event_id"]
    amo.ensure_lead.assert_not_called()


@pytest.mark.asyncio
async def test_persisted_queue_survives_missing_background_dispatch(monkeypatch, isolated):
    from src.services.core.instagram import leadgen_capi as capi
    from src.services.core.instagram import leadgen_capi_outbox as outbox
    sent = []
    delivery.save_crm_checkpoint("123", 77, queue_capi=True)
    monkeypatch.setattr(meta_capi, "_post_events", lambda cfg, ev: sent.append(ev) or {"ok": True})
    capi.schedule_capi_recovery()
    await drain_dispatch()
    assert [ev["user_data"]["lead_id"] for ev in sent] == ["123"]
    assert outbox.pending() == []


@pytest.mark.asyncio
async def test_pending_duplicate_is_not_treated_as_delivered(monkeypatch, isolated):
    from src.services.core.instagram import leadgen_capi as capi
    delivery.save_crm_checkpoint("123", 77, queue_capi=True)
    assert await meta_capi_store.claim_event("123", "Lead", 77)
    post = lambda *a: pytest.fail("fresh pending claim must not send twice")
    monkeypatch.setattr(meta_capi, "_post_events", post)
    capi.schedule_capi_recovery()
    await drain_dispatch()
    with delivery._connection() as conn:
        assert conn.execute("SELECT count(*) FROM capi_lead_queue").fetchone()[0] == 1


@pytest.mark.asyncio
async def test_sent_duplicate_clears_queue_without_second_graph_request(monkeypatch, isolated):
    from src.services.core.instagram import leadgen_capi as capi
    from src.services.core.instagram import leadgen_capi_outbox as outbox
    delivery.save_crm_checkpoint("123", 77, queue_capi=True)
    assert await meta_capi_store.claim_event("123", "Lead", 77)
    await meta_capi_store.mark_result("123", "Lead", True)
    monkeypatch.setattr(meta_capi, "_post_events", lambda *a: pytest.fail("already sent"))
    capi.schedule_capi_recovery()
    await drain_dispatch()
    assert outbox.pending() == []


@pytest.mark.asyncio
async def test_disabled_capi_keeps_queue_and_sends_nothing(monkeypatch, isolated):
    from src.services.core.instagram import leadgen_capi as capi
    from src.services.core.instagram import leadgen_capi_outbox as outbox
    delivery.save_crm_checkpoint("123", 77, queue_capi=True)
    monkeypatch.setattr(capi, "is_enabled", lambda: False)
    monkeypatch.setattr(meta_capi, "_post_events", lambda *a: pytest.fail("disabled"))
    capi.schedule_lead_event("123", 77)
    capi.schedule_capi_recovery()
    await drain_dispatch()
    assert len(outbox.pending()) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["failed", "stale_pending"])
async def test_legacy_failed_or_abandoned_claim_gets_recovered(monkeypatch, isolated, status):
    from src.services.core.instagram import leadgen_capi as capi
    from src.services.core.instagram import leadgen_capi_outbox as outbox
    assert await meta_capi_store.claim_event("123", "Lead", 77)
    if status == "failed":
        await meta_capi_store.mark_result("123", "Lead", False, "HTTP 500")
    else:
        await isolated.execute("UPDATE capi_events SET updated_at='2000-01-01T00:00:00+00:00'")
        await isolated.commit()
    sent = []
    monkeypatch.setattr(meta_capi, "_post_events", lambda cfg, ev: sent.append(ev) or {"ok": True})
    capi.schedule_capi_recovery()
    await drain_dispatch()
    assert len(outbox.pending()) == 1
    capi.schedule_capi_recovery()
    await drain_dispatch()
    assert len(sent) == 1
    assert outbox.pending() == []


@pytest.mark.asyncio
async def test_legacy_scan_respects_outbox_backoff(monkeypatch, isolated):
    from src.services.core.instagram import leadgen_capi as capi
    delivery.save_crm_checkpoint("123", 77, queue_capi=True)
    sent = []
    monkeypatch.setattr(meta_capi, "_post_events", lambda cfg, ev: sent.append(ev) or {"ok": False})
    capi.schedule_capi_recovery()
    await drain_dispatch()
    capi.schedule_capi_recovery()
    await drain_dispatch()
    assert len(sent) == 1


@pytest.mark.asyncio
async def test_dispatch_is_bounded_and_repeated_scans_do_not_duplicate(monkeypatch, isolated):
    from src.services.core.instagram import leadgen_capi as capi
    from src.services.core.marketing import meta_capi_triggers as triggers
    started = []
    release = asyncio.Event()

    async def slow_send(leadgen_id, *args, **kwargs):
        started.append(leadgen_id)
        await release.wait()
        return None

    monkeypatch.setattr(triggers, "on_lead_created", slow_send)
    for i in range(6):
        delivery.save_crm_checkpoint(str(i + 100), i + 1, queue_capi=True)
    try:
        capi.schedule_capi_recovery()
        await capi._recovery_task
        capi.schedule_capi_recovery()
        await capi._recovery_task
        assert len(capi._in_flight) == 4
        assert len(set(started)) == len(started) == 4
    finally:
        release.set()
        await drain_dispatch()


@pytest.mark.asyncio
async def test_completed_historical_deliveries_are_not_backfilled(monkeypatch, isolated):
    from src.services.core.instagram import leadgen_capi as capi
    delivery.save_crm_checkpoint("123", 77)
    delivery.record_delivery_status("123", 77, True, True, True)
    monkeypatch.setattr(meta_capi, "_post_events", lambda *a: pytest.fail("no historical backfill"))
    capi.schedule_capi_recovery()
    await drain_dispatch()


def test_checkpoint_and_intent_rollback_together(monkeypatch, isolated):
    from src.services.core.instagram import leadgen_capi_outbox as outbox

    def unavailable(*args):
        raise sqlite3.OperationalError("synthetic queue failure")

    monkeypatch.setattr(outbox, "enqueue_in_checkpoint", unavailable)
    with pytest.raises(sqlite3.OperationalError):
        delivery.save_crm_checkpoint("123", 77, queue_capi=True)
    assert delivery.get_crm_checkpoint("123") is None


@pytest.mark.asyncio
async def test_cancelled_claim_is_recovered_after_restart_grace(monkeypatch, isolated):
    from src.services.core.instagram import leadgen_capi as capi
    from src.services.core.instagram import leadgen_capi_outbox as outbox
    from src.services.core.marketing import meta_capi_triggers as triggers
    original = triggers.on_lead_created
    started = asyncio.Event()
    release = asyncio.Event()

    async def interrupted(leadgen_id, lead_id, **kwargs):
        assert await meta_capi_store.claim_event(leadgen_id, "Lead", lead_id)
        started.set()
        await release.wait()

    delivery.save_crm_checkpoint("123", 77, queue_capi=True)
    monkeypatch.setattr(triggers, "on_lead_created", interrupted)
    capi.schedule_lead_event("123", 77)
    await asyncio.wait_for(started.wait(), 5)
    task = capi._in_flight["123"]
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await asyncio.sleep(0)
    assert len(outbox.pending()) == 1
    monkeypatch.setattr(triggers, "on_lead_created", original)
    await isolated.execute("UPDATE capi_events SET updated_at='2000-01-01T00:00:00+00:00'")
    await isolated.commit()
    sent = []
    monkeypatch.setattr(meta_capi, "_post_events", lambda cfg, ev: sent.append(ev) or {"ok": True})
    capi.schedule_capi_recovery()
    await drain_dispatch()
    assert len(sent) == 1
    assert outbox.pending() == []
