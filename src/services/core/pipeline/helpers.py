"""
Helpers for Pipeline Auditor intelligence profiles.
"""
from __future__ import annotations

import inspect
import json
from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger()


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _save_user_intelligence(
    db: Any,
    user_id: int,
    psychotype: str,
    pain_points: str,
    objections: str,
    drivers: str,
    negotiation_strategy: str,
    facts_json: dict,
):
    try:
        conn = await db.get_connection()
        now_str = datetime.now(timezone.utc).isoformat()

        query = """
            INSERT INTO user_intelligence (
                user_id, psychotype, pain_points, objections_history, buying_drivers, negotiation_strategy, facts_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                psychotype = excluded.psychotype,
                pain_points = excluded.pain_points,
                objections_history = excluded.objections_history,
                buying_drivers = excluded.buying_drivers,
                negotiation_strategy = excluded.negotiation_strategy,
                facts_json = excluded.facts_json,
                updated_at = excluded.updated_at
        """
        await conn.execute(
            query,
            (
                user_id,
                psychotype,
                pain_points,
                objections,
                drivers,
                negotiation_strategy,
                json.dumps(facts_json),
                now_str,
            ),
        )
        await conn.commit()
        logger.info(f"[AUDITOR] Saved user intelligence for {user_id} in DB.")
    except Exception as e:
        logger.error(f"[AUDITOR] DB write error for user_id {user_id}: {e}")
