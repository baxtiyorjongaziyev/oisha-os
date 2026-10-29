"""Persistent SQLite mapping and checkpoint store for CRM synchronization."""
from __future__ import annotations

import os
import sqlite3
from typing import Any, Optional, Tuple


class SyncMappingStore:
    """Idempotent mapping va checkpointlarni SQLite'da mustahkam saqlovchi ombor."""

    def __init__(self, db_path: str = "data/crm_twenty_sync.db") -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_db()

    def _execute(self, query: str, params: tuple = (), fetchone: bool = False):
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                cur = conn.cursor()
                cur.execute(query, params)
                if fetchone:
                    return cur.fetchone()
        finally:
            conn.close()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS entity_mappings (
                        entity_type TEXT NOT NULL,
                        source_id TEXT NOT NULL,
                        destination_id TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (entity_type, source_id)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sync_checkpoints (
                        pipeline_id INTEGER PRIMARY KEY,
                        last_lead_id INTEGER,
                        processed_count INTEGER,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
        finally:
            conn.close()

    def get_mapping(self, entity_type: str, source_id: Any) -> Optional[str]:
        row = self._execute(
            "SELECT destination_id FROM entity_mappings WHERE entity_type = ? AND source_id = ?",
            (entity_type, str(source_id)),
            fetchone=True,
        )
        return row[0] if row else None

    def save_mapping(self, entity_type: str, source_id: Any, destination_id: str) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO entity_mappings (entity_type, source_id, destination_id)
            VALUES (?, ?, ?)
            """,
            (entity_type, str(source_id), str(destination_id)),
        )

    def get_checkpoint(self, pipeline_id: int) -> Optional[Tuple[int, int]]:
        row = self._execute(
            "SELECT last_lead_id, processed_count FROM sync_checkpoints WHERE pipeline_id = ?",
            (pipeline_id,),
            fetchone=True,
        )
        return (row[0], row[1]) if row else None

    def save_checkpoint(self, pipeline_id: int, last_lead_id: int, count: int) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO sync_checkpoints (pipeline_id, last_lead_id, processed_count, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (pipeline_id, last_lead_id, count),
        )
