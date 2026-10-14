"""Synthetic regression scenarios from the actual Claude Code review."""
import asyncio

from tests.test_capi_platform import client, isolated, payload  # noqa: F401
from src.services.core.marketing import capi_platform as platform
from src.services.core.marketing import capi_platform_store as store
from src.services.core.marketing.capi_platform_schema import Conversion


def test_website_credential_cannot_forge_crm_purchase(isolated, monkeypatch):  # noqa: F811
    monkeypatch.setenv("OISHA_CAPI_INGEST_SECRET", "synthetic-ingest")
    http = client()
    forged = payload(source="crm", event_name="Purchase", leadgen_id="123",
                     event_id="crm-123-Purchase", value=999, currency="UZS")
    response = http.post("/api/marketing/capi/events", json=forged,
                         headers={"Authorization": "Bearer synthetic-ingest"})
    assert response.status_code == 403


def test_conflicting_event_reuse_is_rejected(isolated):  # noqa: F811
    async def scenario():
        original = Conversion(**payload())
        changed = Conversion(**payload(event_time=original.event_time, email="other@example.test"))
        await platform.accept(original)
        try:
            await platform.accept(changed)
        except ValueError as exc:
            assert str(exc) == "event_id_conflict"
        else:
            raise AssertionError("Changed conversion silently discarded")
    asyncio.run(scenario())


def test_permanent_meta_rejection_is_terminal(isolated, monkeypatch):  # noqa: F811
    pool, _ = isolated
    monkeypatch.setattr(platform.meta_capi, "_post_events", lambda *_: {
        "ok": False, "error": "HTTP 400"
    })
    async def scenario():
        await platform.accept(Conversion(**payload()))
        response = (await platform.dispatch_due())[0]
        assert response["status"] == "rejected"
        assert (await store.events())[0]["status"] == "rejected"
        await pool.execute("UPDATE capi_platform_events SET next_attempt_at='2000'")
        assert await platform.dispatch_due() == []
    asyncio.run(scenario())


def test_cookie_mutation_requires_origin(isolated, monkeypatch):  # noqa: F811
    import jwt
    import time
    secret = "synthetic-session-secret-for-test-only-32bytes"
    monkeypatch.setenv("JWT_SECRET", secret)
    http = client()
    http.cookies.set("oisha_token", jwt.encode(
        {"sub": "synthetic-owner", "role": "owner", "exp": int(time.time()) + 60},
        secret, algorithm="HS256"))
    assert http.post("/api/marketing/capi/dispatch").status_code == 403
