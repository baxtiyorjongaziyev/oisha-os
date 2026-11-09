"""Oisha CRM — Mahalliy maʼlumotlar bazasi (SQLite Store).

Ushbu modul amoCRMʼga bogʻliq boʻlmagan toʻliq mahalliy CRM
jadvallari (Voronkalar, Bosqichlar, Bitimlar, Vazifalar va Tarix)
boshqaruvini amalga oshiradi.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

from src.services.core.crm.engine.schema import (
    DealCreate,
    DealModel,
    DealUpdate,
    PipelineModel,
    StageModel,
    TaskCreate,
    TaskModel,
    TimelineEventCreate,
    TimelineEventModel,
)
from src.services.core.crm.engine.store_ddl import (
    init_database_schema,
    seed_default_pipeline,
)

logger = logging.getLogger(__name__)
DEFAULT_NATIVE_DB_PATH = "data/oisha_crm.db"


class OishaCrmStore:
    """Mustaqil Oisha CRM maʼlumotlar qatlami."""

    def __init__(self, db_path: str = DEFAULT_NATIVE_DB_PATH) -> None:
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn_cache: Optional[sqlite3.Connection] = None
        with self._get_conn() as conn:
            init_database_schema(conn)
            seed_default_pipeline(conn)

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn_cache is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            self._conn_cache = conn
        return self._conn_cache

    def get_pipelines(self) -> List[PipelineModel]:
        """Barcha savdo voronkalari va ularning bosqichlarini qaytarish."""
        with self._get_conn() as conn:
            pipes = conn.execute("SELECT * FROM crm_pipelines WHERE is_archive = 0 ORDER BY is_main DESC, id ASC").fetchall()
            result: List[PipelineModel] = []
            for p in pipes:
                stages_rows = conn.execute(
                    "SELECT * FROM crm_stages WHERE pipeline_id = ? ORDER BY sort_order ASC",
                    (p["id"],),
                ).fetchall()
                stages = [
                    StageModel(
                        id=s["id"],
                        pipeline_id=s["pipeline_id"],
                        name=s["name"],
                        slug=s["slug"],
                        color=s["color"],
                        sort_order=s["sort_order"],
                        is_won=bool(s["is_won"]),
                        is_lost=bool(s["is_lost"]),
                    )
                    for s in stages_rows
                ]
                result.append(
                    PipelineModel(
                        id=p["id"],
                        name=p["name"],
                        slug=p["slug"],
                        is_main=bool(p["is_main"]),
                        is_archive=bool(p["is_archive"]),
                        stages=stages,
                    )
                )
            return result

    def create_deal(self, payload: DealCreate) -> DealModel:
        """Yangi bitim yaratish."""
        with self._get_conn() as conn:
            tags_str = json.dumps(payload.tags, ensure_ascii=False)
            cf_str = json.dumps(payload.custom_fields, ensure_ascii=False)
            cur = conn.execute(
                """
                INSERT INTO crm_deals (
                    name, pipeline_id, stage_id, price, responsible_user_id,
                    responsible_name, phone, email, source, tags_json, custom_fields_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.name, payload.pipeline_id, payload.stage_id, payload.price,
                    payload.responsible_user_id, payload.responsible_name,
                    payload.phone, payload.email, payload.source, tags_str, cf_str,
                ),
            )
            deal_id = cur.lastrowid
            conn.commit()

        self.add_timeline_event(
            TimelineEventCreate(
                deal_id=deal_id,
                event_type="deal_created",
                author="Tizim",
                text=f"Yangi bitim yaratildi: \"{payload.name}\" (Manba: {payload.source})",
            )
        )
        return self.get_deal(deal_id)  # type: ignore

    def get_deal(self, deal_id: int) -> Optional[DealModel]:
        """Bitimni toʻliq maʼlumotlari bilan olish."""
        with self._get_conn() as conn:
            row = conn.execute(
                """
                SELECT d.*, s.name as stage_name
                FROM crm_deals d
                LEFT JOIN crm_stages s ON d.stage_id = s.id
                WHERE d.id = ?
                """,
                (deal_id,),
            ).fetchone()
            if not row:
                return None

            return DealModel(
                id=row["id"],
                name=row["name"],
                pipeline_id=row["pipeline_id"],
                stage_id=row["stage_id"],
                stage_name=row["stage_name"],
                price=float(row["price"] or 0.0),
                responsible_user_id=row["responsible_user_id"],
                responsible_name=row["responsible_name"],
                contact_id=row["contact_id"],
                contact_name=row["phone"],
                company_id=row["company_id"],
                phone=row["phone"],
                email=row["email"],
                source=row["source"],
                tags=json.loads(row["tags_json"] or "[]"),
                custom_fields=json.loads(row["custom_fields_json"] or "{}"),
                is_active=bool(row["is_active"]),
                next_task_at=row["next_task_at"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def update_deal(self, deal_id: int, patch: DealUpdate) -> Optional[DealModel]:
        """Mavjud bitimni tahrirlash."""
        existing = self.get_deal(deal_id)
        if not existing:
            return None

        updates: List[str] = []
        params: List[Any] = []

        if patch.name is not None:
            updates.append("name = ?")
            params.append(patch.name)
        if patch.stage_id is not None and patch.stage_id != existing.stage_id:
            updates.append("stage_id = ?")
            params.append(patch.stage_id)
            self.add_timeline_event(
                TimelineEventCreate(
                    deal_id=deal_id,
                    event_type="stage_change",
                    author=patch.responsible_name or "Menejer",
                    text=f"Bosqich oʻzgartirildi: #{existing.stage_id} ➔ #{patch.stage_id}",
                )
            )
        if patch.price is not None:
            updates.append("price = ?")
            params.append(patch.price)
        if patch.responsible_name is not None:
            updates.append("responsible_name = ?")
            params.append(patch.responsible_name)
        if patch.phone is not None:
            updates.append("phone = ?")
            params.append(patch.phone)
        if patch.email is not None:
            updates.append("email = ?")
            params.append(patch.email)
        if patch.tags is not None:
            updates.append("tags_json = ?")
            params.append(json.dumps(patch.tags, ensure_ascii=False))
        if patch.custom_fields is not None:
            merged_cf = {**existing.custom_fields, **patch.custom_fields}
            updates.append("custom_fields_json = ?")
            params.append(json.dumps(merged_cf, ensure_ascii=False))
        if patch.is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if patch.is_active else 0)

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            sql = f"UPDATE crm_deals SET {', '.join(updates)} WHERE id = ?"  # nosec B608
            params.append(deal_id)
            with self._get_conn() as conn:
                conn.execute(sql, params)
                conn.commit()

        return self.get_deal(deal_id)

    def get_kanban_deals(self, pipeline_id: int = 1) -> Dict[str, Any]:
        """Kanban koʻrinishi uchun barcha bosqichlar va ulardagi bitimlarni jamlash."""
        with self._get_conn() as conn:
            stages = conn.execute(
                "SELECT * FROM crm_stages WHERE pipeline_id = ? ORDER BY sort_order ASC",
                (pipeline_id,),
            ).fetchall()
            deals_rows = conn.execute(
                "SELECT * FROM crm_deals WHERE pipeline_id = ? AND is_active = 1 ORDER BY id DESC",
                (pipeline_id,),
            ).fetchall()

        stage_columns = []
        for st in stages:
            st_deals = [
                {
                    "id": d["id"],
                    "name": d["name"],
                    "price": float(d["price"] or 0),
                    "phone": d["phone"] or "",
                    "responsible_name": d["responsible_name"] or "",
                    "source": d["source"] or "",
                    "tags": json.loads(d["tags_json"] or "[]"),
                    "updated_at": d["updated_at"],
                }
                for d in deals_rows
                if d["stage_id"] == st["id"]
            ]
            total_sum = sum(d["price"] for d in st_deals)
            stage_columns.append(
                {
                    "id": st["id"],
                    "name": st["name"],
                    "slug": st["slug"],
                    "color": st["color"],
                    "count": len(st_deals),
                    "total_sum": total_sum,
                    "deals": st_deals,
                }
            )

        return {
            "pipeline_id": pipeline_id,
            "total_deals": len(deals_rows),
            "columns": stage_columns,
        }

    def create_task(self, payload: TaskCreate) -> TaskModel:
        """Bitim uchun yangi vazifa belgilash."""
        with self._get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO crm_tasks (deal_id, title, task_type, responsible_name, due_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (payload.deal_id, payload.title, payload.task_type, payload.responsible_name, payload.due_at),
            )
            task_id = cur.lastrowid
            conn.execute("UPDATE crm_deals SET next_task_at = ? WHERE id = ?", (payload.due_at, payload.deal_id))
            conn.commit()

        self.add_timeline_event(
            TimelineEventCreate(
                deal_id=payload.deal_id,
                event_type="task",
                author=payload.responsible_name,
                text=f"📌 Vazifa qoʻshildi ({payload.task_type}, muddat: {payload.due_at}): {payload.title}",
            )
        )
        return TaskModel(
            id=task_id,
            deal_id=payload.deal_id,
            title=payload.title,
            task_type=payload.task_type,
            responsible_name=payload.responsible_name,
            due_at=payload.due_at,
            is_completed=False,
        )

    def complete_task(self, task_id: int, result_text: str = "Bajarildi") -> bool:
        """Vazifani bajarilgan deb belgilash."""
        with self._get_conn() as conn:
            task = conn.execute("SELECT * FROM crm_tasks WHERE id = ?", (task_id,)).fetchone()
            if not task:
                return False
            conn.execute(
                "UPDATE crm_tasks SET is_completed = 1, result_text = ? WHERE id = ?",
                (result_text, task_id),
            )
            conn.commit()

        self.add_timeline_event(
            TimelineEventCreate(
                deal_id=task["deal_id"],
                event_type="task_done",
                author=task["responsible_name"] or "Xodim",
                text=f"✅ Vazifa bajarildi ({task['title']}): {result_text}",
            )
        )
        return True

    def add_timeline_event(self, payload: TimelineEventCreate) -> TimelineEventModel:
        """Bitim kartochkasi tasmaga xabar yoki hodisa qoʻshish."""
        meta_str = json.dumps(payload.metadata, ensure_ascii=False)
        with self._get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO crm_timeline (deal_id, event_type, author, text, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (payload.deal_id, payload.event_type, payload.author, payload.text, meta_str),
            )
            event_id = cur.lastrowid
            conn.commit()

        return TimelineEventModel(
            id=event_id,
            deal_id=payload.deal_id,
            event_type=payload.event_type,
            author=payload.author,
            text=payload.text,
            metadata=payload.metadata,
            created_at="hozir",
        )

    def get_timeline(self, deal_id: int, limit: int = 50) -> List[TimelineEventModel]:
        """Bitim kartochkasi tarixini olish."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM crm_timeline WHERE deal_id = ? ORDER BY id DESC LIMIT ?",
                (deal_id, limit),
            ).fetchall()
            return [
                TimelineEventModel(
                    id=r["id"],
                    deal_id=r["deal_id"],
                    event_type=r["event_type"],
                    author=r["author"],
                    text=r["text"],
                    metadata=json.loads(r["metadata_json"] or "{}"),
                    created_at=str(r["created_at"]),
                )
                for r in rows
            ]
