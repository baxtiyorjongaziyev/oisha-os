"""Persistent SQLite store for Jon CRM (9 Pipelines, Kanban, Focus Dialer, BANT/SPIN, Files & AI Call Analysis)."""
from __future__ import annotations

import json
import logging
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "data/crm_dialer.db"


class DialerStore:
    """SQLite data access layer for Jon CRM leads, custom fields, tags, files, and call logs."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn_cache: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn_cache is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA temp_store=MEMORY;")
            conn.execute("PRAGMA cache_size=-16000;")
            self._conn_cache = conn
        return self._conn_cache

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dialer_leads (
                    id INTEGER PRIMARY KEY,
                    pipeline_id INTEGER NOT NULL DEFAULT 11162698,
                    name TEXT NOT NULL,
                    contact_name TEXT,
                    company_name TEXT,
                    phone TEXT,
                    email TEXT,
                    price REAL DEFAULT 0,
                    status_id INTEGER NOT NULL,
                    status_slug TEXT NOT NULL,
                    responsible_user_id INTEGER,
                    responsible_name TEXT,
                    source TEXT,
                    tags_json TEXT DEFAULT '[]',
                    custom_fields_json TEXT DEFAULT '{}',
                    files_json TEXT DEFAULT '[]',
                    ai_analysis_json TEXT DEFAULT '{}',
                    notes_json TEXT DEFAULT '[]',
                    last_called_at TIMESTAMP,
                    calls_count INTEGER DEFAULT 0,
                    next_call_at TIMESTAMP,
                    last_audio_url TEXT,
                    last_audio_duration INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            alter_statements = (
                "ALTER TABLE dialer_leads ADD COLUMN company_name TEXT DEFAULT '';",
                "ALTER TABLE dialer_leads ADD COLUMN email TEXT DEFAULT '';",
                "ALTER TABLE dialer_leads ADD COLUMN tags_json TEXT DEFAULT '[]';",
                "ALTER TABLE dialer_leads ADD COLUMN custom_fields_json TEXT DEFAULT '{}';",
                "ALTER TABLE dialer_leads ADD COLUMN files_json TEXT DEFAULT '[]';",
                "ALTER TABLE dialer_leads ADD COLUMN ai_analysis_json TEXT DEFAULT '{}';",
                "ALTER TABLE dialer_leads ADD COLUMN last_audio_url TEXT;",
                "ALTER TABLE dialer_leads ADD COLUMN last_audio_duration INTEGER DEFAULT 0;",
            )
            for stmt in alter_statements:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    pass

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dialer_call_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lead_id INTEGER NOT NULL,
                    seller_name TEXT,
                    old_status TEXT,
                    new_status TEXT NOT NULL,
                    note TEXT,
                    next_call_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_dialer_leads_pipe ON dialer_leads (pipeline_id, status_slug);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_dialer_leads_active ON dialer_leads (is_active, status_slug);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_dialer_leads_rep ON dialer_leads (responsible_user_id);")

    def _deserialize_row(self, row: sqlite3.Row, slim: bool = False) -> Dict[str, Any]:
        d = dict(row)
        pairs = [("tags", "tags_json", [])] if slim else [
            ("tags", "tags_json", []),
            ("custom_fields", "custom_fields_json", {}),
            ("files", "files_json", []),
            ("ai_analysis", "ai_analysis_json", {}),
            ("notes", "notes_json", []),
        ]
        for field_key, json_col, default in pairs:
            raw = d.get(json_col)
            try:
                d[field_key] = json.loads(raw) if raw else default
            except Exception:
                d[field_key] = default
        return d

    def upsert_lead(self, lead_data: Dict[str, Any]) -> None:
        """Insert or update lead in Jon CRM store."""
        tags_str = json.dumps(lead_data["tags"], ensure_ascii=False) if "tags" in lead_data else None
        cf_str = json.dumps(lead_data["custom_fields"], ensure_ascii=False) if "custom_fields" in lead_data else None
        files_str = json.dumps(lead_data["files"], ensure_ascii=False) if "files" in lead_data else None
        ai_str = json.dumps(lead_data["ai_analysis"], ensure_ascii=False) if "ai_analysis" in lead_data else None
        notes_str = json.dumps(lead_data["notes"], ensure_ascii=False) if "notes" in lead_data else None

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO dialer_leads (
                    id, pipeline_id, name, contact_name, company_name, phone, email, price,
                    status_id, status_slug, responsible_user_id, responsible_name,
                    source, tags_json, custom_fields_json, files_json, ai_analysis_json,
                    notes_json, last_audio_url, last_audio_duration, is_active, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    pipeline_id = COALESCE(excluded.pipeline_id, dialer_leads.pipeline_id),
                    name = CASE WHEN excluded.name != ('Lid #' || excluded.id) THEN excluded.name ELSE dialer_leads.name END,
                    contact_name = CASE WHEN excluded.contact_name != '' THEN excluded.contact_name ELSE dialer_leads.contact_name END,
                    company_name = CASE WHEN excluded.company_name != '' THEN excluded.company_name ELSE dialer_leads.company_name END,
                    phone = CASE WHEN excluded.phone != '' THEN excluded.phone ELSE dialer_leads.phone END,
                    email = CASE WHEN excluded.email != '' THEN excluded.email ELSE dialer_leads.email END,
                    price = CASE WHEN excluded.price > 0 THEN excluded.price ELSE dialer_leads.price END,
                    status_id = CASE WHEN excluded.status_id != 0 THEN excluded.status_id ELSE dialer_leads.status_id END,
                    status_slug = COALESCE(excluded.status_slug, dialer_leads.status_slug),
                    responsible_user_id = COALESCE(excluded.responsible_user_id, dialer_leads.responsible_user_id),
                    responsible_name = CASE WHEN excluded.responsible_name != '' THEN excluded.responsible_name ELSE dialer_leads.responsible_name END,
                    source = CASE WHEN excluded.source != '' THEN excluded.source ELSE dialer_leads.source END,
                    tags_json = COALESCE(excluded.tags_json, dialer_leads.tags_json),
                    custom_fields_json = COALESCE(excluded.custom_fields_json, dialer_leads.custom_fields_json),
                    files_json = COALESCE(excluded.files_json, dialer_leads.files_json),
                    ai_analysis_json = COALESCE(excluded.ai_analysis_json, dialer_leads.ai_analysis_json),
                    notes_json = COALESCE(excluded.notes_json, dialer_leads.notes_json),
                    last_audio_url = COALESCE(excluded.last_audio_url, dialer_leads.last_audio_url),
                    last_audio_duration = CASE WHEN excluded.last_audio_duration > 0 THEN excluded.last_audio_duration ELSE dialer_leads.last_audio_duration END,
                    is_active = excluded.is_active,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (
                    lead_data["id"],
                    lead_data.get("pipeline_id", 11162698),
                    lead_data.get("name") or f"Lid #{lead_data['id']}",
                    lead_data.get("contact_name") or "",
                    lead_data.get("company_name") or "",
                    lead_data.get("phone") or "",
                    lead_data.get("email") or "",
                    float(lead_data.get("price") or 0.0),
                    int(lead_data.get("status_id") or 0),
                    lead_data.get("status_slug") or "yangi",
                    lead_data.get("responsible_user_id"),
                    lead_data.get("responsible_name") or "",
                    lead_data.get("source") or "",
                    tags_str,
                    cf_str,
                    files_str,
                    ai_str,
                    notes_str,
                    lead_data.get("last_audio_url"),
                    int(lead_data.get("last_audio_duration") or 0),
                    1 if lead_data.get("is_active", True) else 0,
                ),
            )

    def get_lead(self, lead_id: int) -> Optional[Dict[str, Any]]:
        """Fetch single lead by ID with deserialized JSON attributes."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM dialer_leads WHERE id = ?", (lead_id,)).fetchone()
            return self._deserialize_row(row) if row else None

    def find_lead_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Fetch lead matching phone number (exact or 9-digit suffix)."""
        if not phone:
            return None
        digits = "".join(ch for ch in str(phone) if ch.isdigit())
        suffix = digits[-9:] if len(digits) >= 9 else digits
        if not suffix:
            return None
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM dialer_leads WHERE phone = ? OR phone LIKE ? ORDER BY id DESC LIMIT 1",
                (phone, f"%{suffix}"),
            ).fetchone()
            return self._deserialize_row(row) if row else None

    def get_queue(
        self,
        rep_id: Optional[int] = None,
        status_slug: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        pipeline_id: Optional[int] = None,
        include_closed: bool = False,
        tag: Optional[str] = None,
        slim: bool = False,
    ) -> List[Dict[str, Any]]:
        """Fetch ordered queue or kanban list of leads."""
        base_select = (
            "SELECT id, pipeline_id, name, contact_name, company_name, phone, price, "
            "status_id, status_slug, responsible_user_id, responsible_name, source, "
            "tags_json, last_audio_url, calls_count, is_active, updated_at FROM dialer_leads WHERE 1=1"
            if slim
            else "SELECT * FROM dialer_leads WHERE 1=1"
        )
        query = base_select
        params: List[Any] = []
        if not include_closed:
            query += " AND is_active = 1"
        if pipeline_id:
            query += " AND pipeline_id = ?"
            params.append(pipeline_id)
        if rep_id:
            query += " AND responsible_user_id = ?"
            params.append(rep_id)
        if status_slug and status_slug != "all":
            query += " AND status_slug = ?"
            params.append(status_slug)
        if tag:
            query += " AND tags_json LIKE ?"
            params.append(f"%{tag.strip()}%")
        if search:
            query += " AND (name LIKE ? OR phone LIKE ? OR contact_name LIKE ? OR company_name LIKE ? OR tags_json LIKE ?)"
            term = f"%{search.strip()}%"
            params.extend([term, term, term, term, term])
        query += " ORDER BY calls_count ASC, last_called_at ASC, id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._deserialize_row(r, slim=slim) for r in rows]

    def record_call_action(
        self,
        lead_id: int,
        new_status_slug: str,
        new_status_id: int,
        seller_name: str,
        note: Optional[str] = None,
        next_call_at: Optional[str] = None,
        pipeline_id: Optional[int] = None,
    ) -> None:
        """Update lead after a call action or Kanban drag-and-drop and log the event."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT status_slug, pipeline_id, notes_json FROM dialer_leads WHERE id = ?", (lead_id,)
            ).fetchone()
            old_status = row["status_slug"] if row else "unknown"
            target_pipe = pipeline_id or (row["pipeline_id"] if row else 11162698)
            existing_notes = json.loads(row["notes_json"]) if row and row["notes_json"] else []
            if note:
                existing_notes.append({"text": note, "by": seller_name, "time": "hozir", "type": "note"})
            is_active = 0 if new_status_slug in ("qiziqmadi", "sotuv") else 1
            conn.execute(
                """
                UPDATE dialer_leads SET
                    pipeline_id = ?, status_slug = ?, status_id = ?,
                    calls_count = calls_count + 1, last_called_at = CURRENT_TIMESTAMP,
                    next_call_at = COALESCE(?, next_call_at), notes_json = ?, is_active = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (target_pipe, new_status_slug, new_status_id, next_call_at, json.dumps(existing_notes, ensure_ascii=False), is_active, lead_id),
            )
            conn.execute(
                "INSERT INTO dialer_call_logs (lead_id, seller_name, old_status, new_status, note, next_call_at) VALUES (?, ?, ?, ?, ?, ?);",
                (lead_id, seller_name, old_status, new_status_slug, note or "", next_call_at),
            )

    def attach_call_recording(self, phone: str, audio_url: str, duration: int = 0, manager: str = "") -> Optional[int]:
        """Link an incoming call audio recording to the matching lead by phone."""
        clean = phone.replace(" ", "").replace("-", "").strip()[-9:]
        with self._get_conn() as conn:
            row = conn.execute("SELECT id, notes_json FROM dialer_leads WHERE phone LIKE ? LIMIT 1", (f"%{clean}%",)).fetchone()
            if not row:
                return None
            lead_id = row["id"]
            existing_notes = json.loads(row["notes_json"] or "[]")
            existing_notes.append({"type": "audio", "audio_url": audio_url, "duration": duration, "by": manager or "Sotuvchi", "time": "hozir"})
            conn.execute(
                """
                UPDATE dialer_leads SET
                    last_audio_url = ?, last_audio_duration = ?, notes_json = ?,
                    calls_count = calls_count + 1, last_called_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (audio_url, duration, json.dumps(existing_notes, ensure_ascii=False), lead_id),
            )
            return lead_id

    def add_lead_note(self, lead_id: int, text: str, author: str = "Sotuvchi", note_type: str = "note") -> bool:
        """Append a timeline note, task, or file link to a lead."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT notes_json FROM dialer_leads WHERE id = ?", (lead_id,)).fetchone()
            if not row:
                return False
            notes = json.loads(row["notes_json"] or "[]")
            notes.append({"text": text, "by": author, "time": "hozir", "type": note_type})
            conn.execute("UPDATE dialer_leads SET notes_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (json.dumps(notes, ensure_ascii=False), lead_id))
            return True

    def add_lead_file(self, lead_id: int, name: str, url: str, file_type: str = "document", uploaded_by: str = "Sotuvchi") -> bool:
        """Attach a file/link (KP, Shartnoma, Brief, Brandbook) to a deal card."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT files_json, notes_json FROM dialer_leads WHERE id = ?", (lead_id,)).fetchone()
            if not row:
                return False
            files = json.loads(row["files_json"] or "[]")
            files.append({"name": name, "url": url, "type": file_type, "by": uploaded_by, "time": "hozir"})
            notes = json.loads(row["notes_json"] or "[]")
            notes.append({"text": f"📎 Fayl biriktirildi: {name} ({url})", "by": uploaded_by, "time": "hozir", "type": "file"})
            conn.execute(
                "UPDATE dialer_leads SET files_json = ?, notes_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (json.dumps(files, ensure_ascii=False), json.dumps(notes, ensure_ascii=False), lead_id),
            )
            return True

    def save_ai_analysis(self, lead_id: int, analysis: Dict[str, Any]) -> bool:
        """Store AI call/deal analysis on the lead record."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT id FROM dialer_leads WHERE id = ?", (lead_id,)).fetchone()
            if not row:
                return False
            conn.execute("UPDATE dialer_leads SET ai_analysis_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (json.dumps(analysis, ensure_ascii=False), lead_id))
            return True

    def get_lead_detail(self, lead_id: int) -> Optional[Dict[str, Any]]:
        """Fetch single lead with full call history, notes, BANT/SPIN fields, files, and AI analysis."""
        lead = self.get_lead(lead_id)
        if not lead:
            return None
        with self._get_conn() as conn:
            logs = conn.execute("SELECT * FROM dialer_call_logs WHERE lead_id = ? ORDER BY created_at DESC LIMIT 30", (lead_id,)).fetchall()
            lead["call_logs"] = [dict(log) for log in logs]
            return lead

    def create_or_update_lead(self, lead_data: Dict[str, Any]) -> int:
        """Create or update lead manually from UI."""
        lead_id = lead_data.get("id")
        existing = self.get_lead(lead_id) if lead_id else None
        if not lead_id:
            with self._get_conn() as conn:
                max_id = conn.execute("SELECT MAX(id) FROM dialer_leads").fetchone()[0] or 50000000
                lead_id = max_id + 1
            lead_data["id"] = lead_id
        elif existing:
            merged = {**existing, **lead_data}
            if "custom_fields" in lead_data and isinstance(existing.get("custom_fields"), dict):
                merged["custom_fields"] = {**existing["custom_fields"], **lead_data["custom_fields"]}
            lead_data = merged
        self.upsert_lead(lead_data)
        return lead_id

    def get_stats(self, rep_id: Optional[int] = None, pipeline_id: Optional[int] = None) -> Dict[str, Any]:
        """Compute dialer and pipeline statistics."""
        with self._get_conn() as conn:
            total_active = conn.execute(
                "SELECT COUNT(*) FROM dialer_leads WHERE is_active = 1 AND (? IS NULL OR pipeline_id = ?) AND (? IS NULL OR responsible_user_id = ?)",
                (pipeline_id, pipeline_id, rep_id, rep_id),
            ).fetchone()[0]
            today_calls = conn.execute("SELECT COUNT(*) FROM dialer_call_logs WHERE DATE(created_at) = DATE('now')").fetchone()[0]
            today_won = conn.execute("SELECT COUNT(*) FROM dialer_call_logs WHERE new_status = 'sotuv' AND DATE(created_at) = DATE('now')").fetchone()[0]
            counts_by_status = dict(
                conn.execute(
                    "SELECT status_slug, COUNT(*) FROM dialer_leads WHERE (? IS NULL OR pipeline_id = ?) AND (? IS NULL OR responsible_user_id = ?) GROUP BY status_slug",
                    (pipeline_id, pipeline_id, rep_id, rep_id),
                ).fetchall()
            )
            counts_by_pipeline = dict(conn.execute("SELECT pipeline_id, COUNT(*) FROM dialer_leads GROUP BY pipeline_id").fetchall())
            return {
                "total_active_leads": total_active,
                "calls_today": today_calls,
                "won_today": today_won,
                "by_status": counts_by_status,
                "by_pipeline": counts_by_pipeline,
            }
