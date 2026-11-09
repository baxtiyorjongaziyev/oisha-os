"""
Korporativ sotuvchilar va Telegram suhbatlari uchun maʼlumotlar ombori.
SQLite / Turso bazasi bilan xavfsiz va asinxron ishlash.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.services.corporate_sales.models import CorporateSeller

logger = logging.getLogger("CorporateSalesRepository")


class CorporateSalesRepository:
    """Korporativ sotuvchilar va muloqot tahlillari ombori."""

    def __init__(self, db_manager: Any = None):
        self.db = db_manager

    async def _get_conn(self) -> Any:
        """Maʼlumotlar bazasi ulanishini olish."""
        if hasattr(self.db, "get_connection"):
            return await self.db.get_connection()
        if hasattr(self.db, "connection"):
            return self.db.connection
        return self.db

    async def init_tables(self) -> None:
        """Zaruriy jadvallarni yaratish."""
        conn = await self._get_conn()
        if not conn:
            logger.warning("[CORP_SALES_REPO] DB ulanishi yoʻq, init_tables oʻtkazib yuborildi")
            return

        create_sellers_table = """
        CREATE TABLE IF NOT EXISTS corporate_sellers (
            seller_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL UNIQUE,
            session_string TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
        create_analyses_table = """
        CREATE TABLE IF NOT EXISTS conversation_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id TEXT UNIQUE,
            lead_id INTEGER,
            manager_id INTEGER,
            manager_name TEXT,
            overall_score INTEGER,
            deal_outcome TEXT,
            status TEXT,
            stages TEXT,
            objections TEXT,
            strengths TEXT,
            weaknesses TEXT,
            recommendations TEXT,
            analyzed_at TEXT,
            updated_at TEXT
        )
        """
        try:
            await conn.execute(create_sellers_table)
            await conn.execute(create_analyses_table)
            if hasattr(conn, "commit"):
                await conn.commit()
            logger.info("[CORP_SALES_REPO] Jadvallar muvaffaqiyatli tekshirildi/yaratildi")
        except Exception as exc:
            logger.error("[CORP_SALES_REPO] Jadvallarni yaratishda xato: %s", exc)

    async def get_all_active_sellers(self) -> List[CorporateSeller]:
        """Barcha faol korporativ sotuvchilarni olish."""
        conn = await self._get_conn()
        if not conn:
            return []

        query = """
        SELECT seller_id, name, phone, session_string, is_active, created_at, updated_at
        FROM corporate_sellers
        WHERE is_active = 1
        ORDER BY seller_id ASC
        """
        try:
            cursor = await conn.execute(query)
            rows = await cursor.fetchall()
            return [CorporateSeller.from_row(r) for r in (rows or [])]
        except Exception as exc:
            logger.error("[CORP_SALES_REPO] Sotuvchilarni oʻqishda xato: %s", exc)
            return []

    async def get_seller_by_phone(self, phone: str) -> Optional[CorporateSeller]:
        """Telefon raqami boʻyicha sotuvchini topish."""
        conn = await self._get_conn()
        if not conn:
            return None

        query = """
        SELECT seller_id, name, phone, session_string, is_active, created_at, updated_at
        FROM corporate_sellers
        WHERE phone = ?
        LIMIT 1
        """
        try:
            cursor = await conn.execute(query, (phone,))
            row = await cursor.fetchone()
            if row:
                return CorporateSeller.from_row(row)
            return None
        except Exception as exc:
            logger.error("[CORP_SALES_REPO] Sotuvchini izlashda xato: %s", exc)
            return None

    async def upsert_seller(
        self, name: str, phone: str, session_string: str
    ) -> Optional[CorporateSeller]:
        """Sotuvchini qoʻshish yoki sessiyasini yangilash."""
        conn = await self._get_conn()
        if not conn:
            return None

        now = datetime.now(timezone.utc).isoformat()
        query = """
        INSERT INTO corporate_sellers (name, phone, session_string, is_active, created_at, updated_at)
        VALUES (?, ?, ?, 1, ?, ?)
        ON CONFLICT(phone) DO UPDATE SET
            name = excluded.name,
            session_string = excluded.session_string,
            is_active = 1,
            updated_at = excluded.updated_at
        RETURNING seller_id, name, phone, session_string, is_active, created_at, updated_at
        """
        try:
            cursor = await conn.execute(
                query, (name, phone, session_string, now, now)
            )
            row = await cursor.fetchone()
            if hasattr(conn, "commit"):
                await conn.commit()
            if row:
                return CorporateSeller.from_row(row)
            return await self.get_seller_by_phone(phone)
        except Exception as exc:
            logger.error("[CORP_SALES_REPO] Sotuvchini saqlashda xato: %s", exc)
            return None

    async def deactivate_seller(self, seller_id: int) -> bool:
        """Sotuvchini nofaol qilish."""
        conn = await self._get_conn()
        if not conn:
            return False

        now = datetime.now(timezone.utc).isoformat()
        query = """
        UPDATE corporate_sellers
        SET is_active = 0, updated_at = ?
        WHERE seller_id = ?
        """
        try:
            await conn.execute(query, (now, seller_id))
            if hasattr(conn, "commit"):
                await conn.commit()
            return True
        except Exception as exc:
            logger.error("[CORP_SALES_REPO] Sotuvchini oʻchirishda xato: %s", exc)
            return False

    async def save_conversation_analysis(
        self,
        *,
        conversation_id: str,
        manager_id: int,
        manager_name: str,
        overall_score: int,
        deal_outcome: str,
        lead_id: Optional[int] = None,
        stages: Optional[List[Dict[str, Any]]] = None,
        objections: Optional[List[str]] = None,
        strengths: Optional[List[str]] = None,
        weaknesses: Optional[List[str]] = None,
        recommendations: Optional[List[str]] = None,
    ) -> bool:
        """Tahlil natijalarini conversation_analyses jadvaliga saqlash."""
        conn = await self._get_conn()
        if not conn:
            return False

        now = datetime.now(timezone.utc).isoformat()
        query = """
        INSERT INTO conversation_analyses (
            call_id, lead_id, manager_id, manager_name,
            overall_score, deal_outcome, status, stages,
            objections, strengths, weaknesses, recommendations,
            analyzed_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(call_id) DO UPDATE SET
            overall_score = excluded.overall_score,
            deal_outcome = excluded.deal_outcome,
            status = excluded.status,
            stages = excluded.stages,
            objections = excluded.objections,
            strengths = excluded.strengths,
            weaknesses = excluded.weaknesses,
            recommendations = excluded.recommendations,
            updated_at = excluded.updated_at
        """
        try:
            await conn.execute(
                query,
                (
                    conversation_id,
                    lead_id,
                    manager_id,
                    manager_name,
                    overall_score,
                    deal_outcome,
                    deal_outcome,
                    json.dumps(stages or []),
                    json.dumps(objections or []),
                    json.dumps(strengths or []),
                    json.dumps(weaknesses or []),
                    json.dumps(recommendations or []),
                    now,
                    now,
                ),
            )
            if hasattr(conn, "commit"):
                await conn.commit()
            return True
        except Exception as exc:
            logger.error("[CORP_SALES_REPO] Tahlilni saqlashda xato: %s", exc)
            return False
