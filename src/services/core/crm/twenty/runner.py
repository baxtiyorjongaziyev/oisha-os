"""Wiring + reconciliation report for the amoCRM -> Twenty projection."""
from __future__ import annotations

import json
import os

from .client import TwentyClient, config_from_env
from .mapping import MapStore
from .notes import pull_notes
from .projector import KINDS, Projector


def enabled() -> bool:
    return os.getenv("TWENTY_SYNC_ENABLED", "0") == "1"


def _json_env(name: str) -> dict:
    value = json.loads(os.getenv(name, "{}") or "{}")
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    return value


async def reconcile(mirror, maps, client=None) -> dict:
    """Source (mirror) vs local map vs live Twenty counts; gaps are explicit.

    ``target_remote`` is read from Twenty (records with amoId set) when a client
    is available, so a record lost in Twenty shows up as ``remote_gap``.
    """
    out = {}
    states = await maps.counts()
    for kind, (map_kind, plural, _) in KINDS.items():
        rows = await mirror.sql(
            """SELECT COUNT(*) AS n, SUM(CASE WHEN json_extract(payload,'$.is_deleted')
            THEN 1 ELSE 0 END) AS d FROM parallel_crm_entities WHERE kind=?""", [kind])
        total, deleted = rows[0]["n"] or 0, rows[0]["d"] or 0
        synced = states.get(map_kind, {}).get("synced", 0)
        out[kind] = {"source": total, "source_deleted": deleted,
                     "target_synced": synced,
                     "gap": total - deleted - synced,
                     "states": states.get(map_kind, {})}
        if client is not None:
            try:
                remote = await client.count(plural, "amoId[is]:NOT_NULL")
                out[kind]["target_remote"] = remote
                out[kind]["remote_gap"] = synced - remote
            except Exception as exc:  # report, never hide
                out[kind]["target_remote"] = f"unavailable: {exc}"
    out["problems"] = await maps.problems()
    return out


async def run_once(*, pull_amo: bool = True, dry_report: bool = False) -> dict:
    from src.services.core.crm.parallel.runtime import get_remote, get_store
    from src.services.core.crm.parallel.sync import Sync
    from src.database_pool import db_pool

    mirror = await get_store()
    maps = MapStore(db_pool)
    await maps.init()
    result: dict = {"source_complete": True}
    if pull_amo:
        remote = get_remote()
        pull = await Sync(mirror, remote, writeback=False).run()
        result["amo_pull"] = pull
        if pull.get("state") not in ("ready", "partial"):
            # Account mismatch / unavailable: never read notes or project.
            result["source_complete"] = False
            return result
        result["notes_complete"] = await pull_notes(mirror, remote)
        result["source_complete"] = pull["state"] == "ready" and result["notes_complete"]
    try:
        url, key = config_from_env()
        client = TwentyClient(url, key)
    except Exception:
        client = None
    try:
        if not dry_report:
            if client is None:
                raise RuntimeError("twenty_not_configured")
            projector = Projector(
                mirror, maps, client,
                stage_map=_json_env("TWENTY_STAGE_MAP_JSON"),
                member_map=_json_env("TWENTY_MEMBER_MAP_JSON"))
            result["projection"] = await projector.run()
        result["reconcile"] = await reconcile(mirror, maps, client)
    finally:
        if client is not None:
            await client.aclose()
    return result
