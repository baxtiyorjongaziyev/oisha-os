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


async def reconcile(mirror, maps) -> dict:
    """Source (mirror) vs target (map) counts; every gap is listed, not hidden."""
    out = {}
    states = await maps.counts()
    for kind, (map_kind, _, _) in KINDS.items():
        rows = await mirror.sql(
            """SELECT COUNT(*) AS n, SUM(CASE WHEN json_extract(payload,'$.is_deleted')
            THEN 1 ELSE 0 END) AS d FROM parallel_crm_entities WHERE kind=?""", [kind])
        total, deleted = rows[0]["n"] or 0, rows[0]["d"] or 0
        synced = states.get(map_kind, {}).get("synced", 0)
        out[kind] = {"source": total, "source_deleted": deleted,
                     "target_synced": synced,
                     "gap": total - deleted - synced,
                     "states": states.get(map_kind, {})}
    out["problems"] = await maps.problems()
    return out


async def run_once(*, pull_amo: bool = True, dry_report: bool = False) -> dict:
    from src.services.core.crm.parallel.runtime import get_remote, get_store
    from src.services.core.crm.parallel.sync import Sync
    from src.database_pool import db_pool

    mirror = await get_store()
    maps = MapStore(db_pool)
    await maps.init()
    result: dict = {}
    if pull_amo:
        remote = get_remote()
        result["amo_pull"] = await Sync(mirror, remote, writeback=False).run()
        result["notes_complete"] = await pull_notes(mirror, remote)
    if not dry_report:
        url, key = config_from_env()
        client = TwentyClient(url, key)
        try:
            projector = Projector(
                mirror, maps, client,
                stage_map=_json_env("TWENTY_STAGE_MAP_JSON"),
                member_map=_json_env("TWENTY_MEMBER_MAP_JSON"))
            result["projection"] = await projector.run()
        finally:
            await client.aclose()
    result["reconcile"] = await reconcile(mirror, maps)
    return result
