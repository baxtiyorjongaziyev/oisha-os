"""
Database schema and persistence for CRM archiver.
"""
from __future__ import annotations

import datetime
import logging
from typing import Any, Dict

logger = logging.getLogger("crm_archiver")


async def init_archiver_tables(db: Any) -> None:
    logger.info("[ARCHIVER] Archive jadvallarini tekshirish/yaratish...")
    async with await db.get_connection() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS amocrm_archived_leads (
                lead_id INTEGER PRIMARY KEY,
                name TEXT,
                price INTEGER,
                status_id INTEGER,
                pipeline_id INTEGER,
                responsible_user_id INTEGER,
                created_at INTEGER,
                updated_at INTEGER,
                phone TEXT,
                contact_id INTEGER,
                contact_name TEXT,
                notes TEXT,
                custom_fields TEXT,
                archived_at TEXT
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS amocrm_archived_campaigns (
                lead_id INTEGER PRIMARY KEY,
                campaign_step1 TEXT,
                campaign_step2 TEXT,
                campaign_step3 TEXT,
                generated_at TEXT,
                status TEXT,
                FOREIGN KEY(lead_id) REFERENCES amocrm_archived_leads(lead_id)
            )
            """
        )
        await conn.commit()
    logger.info("[ARCHIVER] Archive jadvallari tayyor.")


async def save_archived_lead_and_campaign(
    db: Any, payload: Dict[str, Any], campaign: Dict[str, str]
) -> None:
    async with await db.get_connection() as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO amocrm_archived_leads
            (lead_id, name, price, status_id, pipeline_id, responsible_user_id, created_at, updated_at, phone, contact_id, contact_name, notes, custom_fields, archived_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["lead_id"],
                payload["name"],
                payload["price"],
                payload["status_id"],
                payload["pipeline_id"],
                payload["responsible_user_id"],
                payload["created_at"],
                payload["updated_at"],
                payload["phone"],
                payload["contact_id"],
                payload["contact_name"],
                payload["notes"],
                payload["custom_fields"],
                payload["archived_at"],
            ),
        )
        await conn.execute(
            """
            INSERT OR REPLACE INTO amocrm_archived_campaigns
            (lead_id, campaign_step1, campaign_step2, campaign_step3, generated_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload["lead_id"],
                campaign["step1"],
                campaign["step2"],
                campaign["step3"],
                datetime.datetime.now().isoformat(),
                "pending",
            ),
        )
        await conn.commit()
