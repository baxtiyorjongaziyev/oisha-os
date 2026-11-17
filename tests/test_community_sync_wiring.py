from types import SimpleNamespace as NS

from src.services.core.community_sync import wiring


async def test_scheduled_job_without_client():
    assert (await wiring.scheduled_job(NS(client=None)))["status"] == "no_client"


def test_build_deps_defaults_safe(monkeypatch):
    monkeypatch.setattr(wiring, "_adapters", lambda app_ctx, store: [])
    monkeypatch.setattr(wiring, "SyncStore", lambda: object())
    d = wiring.build_deps(NS(client=object(), bot_client=None))
    assert d.enabled is False and d.dry_run is True
    assert (d.folder_id, d.tg_daily_limit, d.bulk_threshold) == (13, 120, 20)
