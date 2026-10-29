"""
AmoCRM to PostgreSQL / NocoDB Syncer.
Archives closed and historical leads into local PostgreSQL to respect amoCRM's 500 active deal limit.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
from typing import Any, Dict, List, Optional

try:
    import psycopg2
    from psycopg2.extras import Json
except ImportError:
    psycopg2 = None
    Json = lambda x: json.dumps(x)

import src.config as config
from src.services.core.crm.amocrm_sync import AmoCRMSync


logger = logging.getLogger("amocrm_nocodb_syncer")

DEFAULT_PG_CONFIG = {
    "dbname": os.getenv("JB_PG_DB", "jonbranding_core"),
    "user": os.getenv("JB_PG_USER", "jonbranding"),
    "password": os.getenv("JB_PG_PASSWORD", "jb_vault_pg_pass_2026_safe"),
    "host": os.getenv("JB_PG_HOST", "127.0.0.1"),
    "port": int(os.getenv("JB_PG_PORT", "5433")),
}


class AmoCRMNocoDBSyncer:
    """Synchronizes AmoCRM closed/archived deals to PostgreSQL/NocoDB."""

    def __init__(
        self,
        amocrm: Optional[AmoCRMSync] = None,
        pg_config: Optional[Dict[str, Any]] = None,
    ):
        self.amocrm = amocrm or AmoCRMSync(
            config.AMOCRM_SUBDOMAIN,
            config.AMOCRM_CLIENT_ID,
            config.AMOCRM_CLIENT_SECRET,
            config.AMOCRM_REDIRECT_URL,
        )
        self.pg_config = pg_config or DEFAULT_PG_CONFIG

    def get_pg_connection(self):
        return psycopg2.connect(**self.pg_config)

    def init_tables(self) -> None:
        """Create amocrm_archived_leads table in PostgreSQL if not exists."""
        schema_sql = """
        CREATE TABLE IF NOT EXISTS amocrm_archived_leads (
            id BIGINT PRIMARY KEY,
            name VARCHAR(500),
            price NUMERIC(15, 2) DEFAULT 0,
            status_id INTEGER,
            status_category VARCHAR(50),
            pipeline_id INTEGER,
            responsible_user_id INTEGER,
            created_at TIMESTAMP WITH TIME ZONE,
            updated_at TIMESTAMP WITH TIME ZONE,
            closed_at TIMESTAMP WITH TIME ZONE,
            contact_name VARCHAR(255),
            contact_phone VARCHAR(64),
            custom_fields JSONB,
            synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_archived_leads_status ON amocrm_archived_leads(status_id);
        CREATE INDEX IF NOT EXISTS idx_archived_leads_phone ON amocrm_archived_leads(contact_phone);
        CREATE INDEX IF NOT EXISTS idx_archived_leads_synced ON amocrm_archived_leads(synced_at);
        """
        with self.get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(schema_sql)
            conn.commit()
        logger.info("[NOCODB_SYNCER] PostgreSQL amocrm_archived_leads table initialized.")

    def _extract_lead_contact_info(self, lead: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        contact_name = None
        contact_phone = None
        embedded_contacts = lead.get("_embedded", {}).get("contacts", [])
        if embedded_contacts:
            first_c = embedded_contacts[0]
            contact_name = first_c.get("name")
        custom_fields = lead.get("custom_fields_values") or []
        for cf in custom_fields:
            code = cf.get("field_code")
            name = cf.get("field_name", "").lower()
            if code == "PHONE" or "telefon" in name or "phone" in name:
                vals = cf.get("values", [])
                if vals:
                    contact_phone = vals[0].get("value")
                    break
        return contact_name, contact_phone

    def _map_lead_to_row(self, lead: Dict[str, Any]) -> tuple:
        c_name, c_phone = self._extract_lead_contact_info(lead)
        status_id = lead.get("status_id")
        if status_id == 142:
            status_category = "CLOSED_WON"
        elif status_id == 143:
            status_category = "CLOSED_LOST"
        else:
            status_category = "ARCHIVED_STAGNANT"

        created_ts = lead.get("created_at")
        updated_ts = lead.get("updated_at")
        closed_ts = lead.get("closed_at")

        created_dt = (
            datetime.datetime.fromtimestamp(created_ts, datetime.timezone.utc)
            if created_ts
            else None
        )
        updated_dt = (
            datetime.datetime.fromtimestamp(updated_ts, datetime.timezone.utc)
            if updated_ts
            else None
        )
        closed_dt = (
            datetime.datetime.fromtimestamp(closed_ts, datetime.timezone.utc)
            if closed_ts
            else None
        )

        return (
            lead.get("id"),
            lead.get("name") or "Nomsiz bitim",
            lead.get("price") or 0,
            status_id,
            status_category,
            lead.get("pipeline_id"),
            lead.get("responsible_user_id"),
            created_dt,
            updated_dt,
            closed_dt,
            c_name,
            c_phone,
            Json(lead.get("custom_fields_values") or []),
        )

    async def sync_closed_leads(self, statuses: Optional[List[int]] = None, max_pages: int = 5) -> int:
        """Fetch closed/lost/won leads from amoCRM and upsert to PostgreSQL."""
        if statuses is None:
            statuses = [142, 143]  # Standard amoCRM Won and Lost statuses

        if not self.amocrm.access_token:
            self.amocrm._load_token()

        total_synced = 0
        loop = asyncio.get_event_loop()
        upsert_sql = """
        INSERT INTO amocrm_archived_leads (
            id, name, price, status_id, status_category, pipeline_id,
            responsible_user_id, created_at, updated_at, closed_at,
            contact_name, contact_phone, custom_fields, synced_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            price = EXCLUDED.price,
            status_id = EXCLUDED.status_id,
            status_category = EXCLUDED.status_category,
            pipeline_id = EXCLUDED.pipeline_id,
            responsible_user_id = EXCLUDED.responsible_user_id,
            updated_at = EXCLUDED.updated_at,
            closed_at = EXCLUDED.closed_at,
            contact_name = EXCLUDED.contact_name,
            contact_phone = EXCLUDED.contact_phone,
            custom_fields = EXCLUDED.custom_fields,
            synced_at = NOW();
        """

        for status_id in statuses:
            page = 1
            while page <= max_pages:
                leads = await self.amocrm.get_leads(
                    status_id=status_id,
                    limit=250,
                    page=page,
                    with_contacts=True,
                )
                if not leads:
                    break

                rows = [self._map_lead_to_row(lead) for lead in leads if lead.get("id")]
                if rows:
                    def _insert_batch(batch_rows):
                        with self.get_pg_connection() as conn:
                            with conn.cursor() as cur:
                                cur.executemany(upsert_sql, batch_rows)
                            conn.commit()

                    await loop.run_in_executor(None, _insert_batch, rows)
                    total_synced += len(rows)
                    logger.info(
                        "[NOCODB_SYNCER] Synced status=%s page=%s (%s leads)",
                        status_id,
                        page,
                        len(rows),
                    )

                if len(leads) < 250:
                    break
                page += 1

        logger.info("[NOCODB_SYNCER] Synchronization finished. Total synced: %s leads.", total_synced)
        return total_synced
