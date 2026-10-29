"""Digital Pipeline Engine (Raqamli Voronka — amoCRM Enterprise Automation).

Ushbu dvigatel amoCRM Enterprise tarifidagi kabi bosqichlararo triggerlarni
va avtomatik harakatlarni (avto-vazifa, xabar yuborish, bosqich o'zgartirish,
ROP eslatmasi) to'liq avtomatlashtirilgan tarzda boshqaradi.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import json
import logging
import sqlite3
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "data/crm_dialer.db"


class DigitalPipelineEngine:
    """amoCRM 1:1 Raqamli Voronka (Digital Pipeline) avtomatlashtirish markazi."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        self._init_rules_table()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_rules_table(self) -> None:
        """Avtomatlashtirish qoidalari va ijro jurnali jadvallarini yaratish."""
        with self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS crm_automation_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pipeline_id INTEGER NOT NULL,
                    stage_slug TEXT NOT NULL,
                    name TEXT NOT NULL,
                    trigger_type TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    action_payload TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS crm_automation_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_id INTEGER,
                    lead_id INTEGER NOT NULL,
                    trigger_type TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    details TEXT,
                    status TEXT DEFAULT 'success',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS crm_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lead_id INTEGER NOT NULL,
                    lead_name TEXT DEFAULT '',
                    contact_name TEXT DEFAULT '',
                    phone TEXT DEFAULT '',
                    title TEXT NOT NULL,
                    task_type TEXT DEFAULT 'Qo''ng''iroq qilish',
                    responsible_name TEXT DEFAULT 'Shahnoza Abdijabborova',
                    due_at TEXT NOT NULL,
                    is_completed INTEGER DEFAULT 0,
                    result_text TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_dp_stage ON crm_automation_rules(pipeline_id, stage_slug, is_active);")
            conn.commit()

            # Dastlabki Enterprise andoza qoidalarini yaratish
            cnt = conn.execute("SELECT COUNT(*) as c FROM crm_automation_rules").fetchone()["c"]
            if cnt == 0:
                self._seed_default_enterprise_rules(conn)

    def _seed_default_enterprise_rules(self, conn: sqlite3.Connection) -> None:
        """amoCRM Enterprise eng muhim 5 ta avtomatlashtirish qoidasi."""
        rules = [
            (
                11162698,
                "kp",
                "KP dan so'ng 2 kunda qayta bog'lanish vazifasi",
                "stage_enter",
                "create_task",
                json.dumps({
                    "title": "Mijozning Tijoriy Taklif (KP) bo'yicha fikrini olish va e'tirozlarni yopish",
                    "task_type": "Qo'ng'iroq qilish",
                    "delay_days": 2,
                }),
            ),
            (
                11162698,
                "uchrashuv",
                "Uchrashuvga brif tayyorlash vazifasi",
                "stage_enter",
                "create_task",
                json.dumps({
                    "title": "Uchrashuv uchun brif va prezentatsiya materiallarini tayyorlash",
                    "task_type": "Uchrashuv",
                    "delay_days": 1,
                }),
            ),
            (
                11162698,
                "shartnoma",
                "To'lov hisobini nazorat qilish",
                "stage_enter",
                "create_task",
                json.dumps({
                    "title": "Hisob-faktura yuborilganini va to'lov tushganini tekshirish",
                    "task_type": "To'lov nazorati",
                    "delay_days": 1,
                }),
            ),
            (
                11162698,
                "aloqa",
                "Mijozga avtomatik kompaniya taqdimotini yuborish",
                "stage_enter",
                "send_telegram",
                json.dumps({
                    "template": "Assalomu alaykum! Jon Branding agentligi. Sizga agentligimiz portfoliosi va xizmatlar taqdimotini ilova qildik.",
                }),
            ),
            (
                11162698,
                "diagnostika",
                "Diagnostikadan so'ng SPIN xulosasi va taklif tuzish",
                "stage_enter",
                "create_task",
                json.dumps({
                    "title": "Mijoz og'riqlari (SPIN) asosida moslashtirilgan KP tayyorlash",
                    "task_type": "Hujjat tayyorlash",
                    "delay_days": 1,
                }),
            ),
        ]
        for p_id, slug, name, trg, act, payload in rules:
            conn.execute(
                """
                INSERT INTO crm_automation_rules (pipeline_id, stage_slug, name, trigger_type, action_type, action_payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (p_id, slug, name, trg, act, payload),
            )
        conn.commit()

    def get_pipeline_rules(self, pipeline_id: int = 11162698) -> List[Dict[str, Any]]:
        """Voronka bo'yicha barcha avtomatlashtirish qoidalari ro'yxati."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM crm_automation_rules WHERE pipeline_id = ? ORDER BY id ASC", (pipeline_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def add_rule(
        self,
        pipeline_id: int,
        stage_slug: str,
        name: str,
        trigger_type: str,
        action_type: str,
        action_payload: Dict[str, Any],
    ) -> int:
        """Yangi avtomatlashtirish qoidasi qo'shish."""
        with self._get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO crm_automation_rules (pipeline_id, stage_slug, name, trigger_type, action_type, action_payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (pipeline_id, stage_slug, name, trigger_type, action_type, json.dumps(action_payload)),
            )
            conn.commit()
            return int(cur.lastrowid or 0)

    def toggle_rule(self, rule_id: int, is_active: bool) -> bool:
        """Qoidani yoqish yoki o'chirish."""
        with self._get_conn() as conn:
            conn.execute("UPDATE crm_automation_rules SET is_active = ? WHERE id = ?", (1 if is_active else 0, rule_id))
            conn.commit()
            return True

    async def execute_stage_enter_triggers(
        self,
        lead_id: int,
        pipeline_id: int,
        new_stage_slug: str,
        seller_name: str = "Shahnoza Abdijabborova",
    ) -> List[Dict[str, Any]]:
        """Sdelka yangi bosqichga o'tganda barcha mos triggerlarni ishga tushirish."""
        executed: List[Dict[str, Any]] = []
        with self._get_conn() as conn:
            rules = conn.execute(
                """
                SELECT * FROM crm_automation_rules
                WHERE pipeline_id = ? AND (stage_slug = ? OR stage_slug = 'any') AND trigger_type = 'stage_enter' AND is_active = 1
                """,
                (pipeline_id, new_stage_slug),
            ).fetchall()

        for rule in rules:
            r_dict = dict(rule)
            try:
                payload = json.loads(r_dict["action_payload"])
            except Exception:
                payload = {}

            act_type = r_dict["action_type"]
            res = await self._dispatch_action(
                rule_id=r_dict["id"],
                lead_id=lead_id,
                action_type=act_type,
                payload=payload,
                seller_name=seller_name,
            )
            executed.append({"rule_id": r_dict["id"], "name": r_dict["name"], "result": res})

        return executed

    async def _dispatch_action(
        self,
        rule_id: int,
        lead_id: int,
        action_type: str,
        payload: Dict[str, Any],
        seller_name: str,
    ) -> Dict[str, Any]:
        """Trigger amal qilinganda tegishli amallarni bajarish."""
        now_dt = datetime.now()
        details = ""

        if action_type == "create_task":
            delay_days = int(payload.get("delay_days", 1))
            due_at = (now_dt + timedelta(days=delay_days)).strftime("%Y-%m-%d 15:00")
            title = payload.get("title", "Mijoz bilan aloqa")
            task_type = payload.get("task_type", "Qo'ng'iroq qilish")

            with self._get_conn() as conn:
                lead_row = conn.execute("SELECT name, contact_name, phone FROM dialer_leads WHERE id = ?", (lead_id,)).fetchone()
                l_name = lead_row["name"] if lead_row else f"Bitim #{lead_id}"
                c_name = lead_row["contact_name"] if lead_row else ""
                phone = lead_row["phone"] if lead_row else ""

                conn.execute(
                    """
                    INSERT INTO crm_tasks (lead_id, lead_name, contact_name, phone, title, task_type, responsible_name, due_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (lead_id, l_name, c_name, phone, title, task_type, seller_name, due_at),
                )
                conn.commit()

            details = f"Vazifa yaratildi: {title} ({due_at})"
            self._record_lead_audit(lead_id, f"⚡ [Raqamli Voronka] {details}", seller_name)

        elif action_type == "send_telegram":
            msg_text = payload.get("template", "Assalomu alaykum!")
            try:
                from src.services.core.crm.omnichannel_hub import OmnichannelHub
                hub = OmnichannelHub(db_path=self.db_path)
                await hub.send_outbound_reply_async(
                    lead_id=lead_id,
                    channel="Telegram",
                    text=msg_text,
                    sender_name=seller_name,
                )
                details = f"Telegram xabari yuborildi: {msg_text[:40]}..."
                self._record_lead_audit(lead_id, f"⚡ [Raqamli Voronka] {details}", seller_name)
            except Exception as e:
                details = f"Telegram yuborishda xatolik: {e}"

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO crm_automation_logs (rule_id, lead_id, trigger_type, action_type, details)
                VALUES (?, ?, 'stage_enter', ?, ?)
                """,
                (rule_id, lead_id, action_type, details),
            )
            conn.commit()

        return {"action_type": action_type, "details": details}

    def _record_lead_audit(self, lead_id: int, note_text: str, author: str) -> None:
        """Sdelka lentasiga avtomatlashtirish amali haqida yozuv qoldirish."""
        try:
            with self._get_conn() as conn:
                tbl = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dialer_leads'").fetchone()
                if not tbl:
                    return
                row = conn.execute("SELECT notes_json FROM dialer_leads WHERE id = ?", (lead_id,)).fetchone()
                existing_notes: List[Dict[str, Any]] = []
                if row and row["notes_json"]:
                    try:
                        existing_notes = json.loads(row["notes_json"])
                    except Exception:
                        existing_notes = []
                existing_notes.append({
                    "time": "hozir",
                    "by": author or "Oisha AI Avtomatika",
                    "text": note_text,
                    "note_type": "automation",
                })
                conn.execute(
                    "UPDATE dialer_leads SET notes_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (json.dumps(existing_notes), lead_id),
                )
                conn.commit()
        except Exception as exc:
            logger.warning("[DIGITAL-PIPELINE] Audit log failed for lead %s: %s", lead_id, exc)
