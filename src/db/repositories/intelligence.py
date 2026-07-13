"""Intelligence repository for user intelligence and call analysis."""
from __future__ import annotations

import json
import structlog
from typing import Any, Dict, Optional

from src.db.repositories.base import BaseRepository

logger = structlog.get_logger()


class IntelligenceRepository(BaseRepository):
    """Repository for user intelligence and call analysis."""

    async def init_tables(self) -> None:
        """Create intelligence-related tables."""
        await self._execute("""
            CREATE TABLE IF NOT EXISTS user_intelligence (
                user_id INTEGER PRIMARY KEY,
                psychotype TEXT,
                pain_points TEXT,
                objections_history TEXT,
                buying_drivers TEXT,
                communication_style TEXT,
                negotiation_strategy TEXT,
                facts_json TEXT,
                updated_at DATETIME
            )
        """)
        await self._execute("""
            CREATE TABLE IF NOT EXISTS call_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER,
                call_id TEXT,
                duration INTEGER,
                transcript TEXT,
                sentiment TEXT,
                scores TEXT,
                strengths TEXT,
                weaknesses TEXT,
                objections TEXT,
                next_steps TEXT,
                recommended_tasks TEXT,
                created_at DATETIME
            )
        """)

    async def get_user_intelligence(self, user_id: int) -> Dict[str, Any]:
        """Get user intelligence data."""
        conn = await self._get_conn()
        async with conn.execute(
            "SELECT psychotype, pain_points, objections_history, buying_drivers, "
            "communication_style, negotiation_strategy, facts_json "
            "FROM user_intelligence WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "psychotype": row[0],
                    "pain_points": row[1],
                    "objections_history": row[2],
                    "buying_drivers": row[3],
                    "communication_style": row[4],
                    "negotiation_strategy": row[5],
                    "facts_json": json.loads(row[6]) if row[6] else {},
                }
            return {}

    async def upsert_user_intelligence(
        self, user_id: int, intel_data: Dict[str, Any]
    ) -> bool:
        """Insert or update user intelligence."""
        import datetime
        conn = await self._get_conn()
        now = datetime.datetime.now().isoformat()
        existing = await self.get_user_intelligence(user_id)
        facts = existing.get("facts_json", {})
        if "facts" in intel_data:
            facts.update(intel_data["facts"])
        await conn.execute(
            """
            INSERT INTO user_intelligence (
                user_id, psychotype, pain_points, objections_history,
                buying_drivers, communication_style, negotiation_strategy,
                facts_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                psychotype = COALESCE(excluded.psychotype, user_intelligence.psychotype),
                pain_points = COALESCE(excluded.pain_points, user_intelligence.pain_points),
                objections_history = COALESCE(excluded.objections_history, user_intelligence.objections_history),
                buying_drivers = COALESCE(excluded.buying_drivers, user_intelligence.buying_drivers),
                communication_style = COALESCE(excluded.communication_style, user_intelligence.communication_style),
                negotiation_strategy = COALESCE(excluded.negotiation_strategy, user_intelligence.negotiation_strategy),
                facts_json = excluded.facts_json,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                intel_data.get("psychotype"),
                intel_data.get("pain_points"),
                intel_data.get("objections_history"),
                intel_data.get("buying_drivers"),
                intel_data.get("communication_style"),
                intel_data.get("negotiation_strategy"),
                json.dumps(facts),
                now,
            ),
        )
        await conn.commit()
        return True

    async def get_latest_call_analysis(
        self, lead_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get latest call analysis for a lead."""
        if not lead_id:
            return None

        conn = await self._get_conn()
        if not conn:
            logger.error("[DB] Connection failed while fetching call analysis")
            return None

        query = """
            SELECT * FROM call_analyses
            WHERE lead_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """
        try:
            async with conn.execute(query, (lead_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    if isinstance(row, dict):
                        data = dict(row)
                    else:
                        cols = [description[0] for description in cursor.description]
                        data = dict(zip(cols, row))
                    json_fields = [
                        "scores", "strengths", "weaknesses",
                        "objections", "next_steps", "recommended_tasks",
                    ]
                    for json_col in json_fields:
                        val = data.get(json_col)
                        if val and isinstance(val, str):
                            try:
                                data[json_col] = json.loads(val)
                            except (json.JSONDecodeError, TypeError) as e:
                                logger.warning(
                                    f"[DB] JSON parse error for {json_col} in lead {lead_id}: {e}"
                                )
                    return data
        except Exception as e:
            logger.error(f"[DB] Error fetching call analysis for lead {lead_id}: {e}")

        return None
