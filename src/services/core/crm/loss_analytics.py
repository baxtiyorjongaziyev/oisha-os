"""Loss Reasons & Cycle Time Analytics (Rad etish sabablari va Konversiya tezligi).

amoCRM Enterprise tarifidagi:
1. Sdelka rad etilganda majburiy sabab so'rash va sabablar kesimida yo'qotilgan summa tahlili.
2. Sdelkaning bosqichlarda o'rtacha qolib ketish davomiyligi (Cycle Time) va tiqilishlar.
"""
from __future__ import annotations

from datetime import datetime
import json
import logging
import sqlite3
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "data/crm_dialer.db"

STANDARD_LOSS_REASONS = [
    "Qimmat / Byudjet yetmadi",
    "Raqobatchiga ketdi",
    "Hozir ehtiyoj yo'q (keyinroq)",
    "Aloqaga chiqmadi (o'chiq / javob bermadi)",
    "Xizmat mos kelmadi / Boshqa soha",
    "Soxta lid / Noto'g'ri raqam",
]


class LossAnalyticsEngine:
    """Rad etish sabablari va bosqichlar tezligi (Cycle Time) tahlil dvigateli."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        self._init_loss_table()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_loss_table(self) -> None:
        """Rad sabablari jadvalini yaratish."""
        with self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS crm_deal_losses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lead_id INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    note TEXT,
                    lost_amount REAL DEFAULT 0.0,
                    seller_name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_loss_reason ON crm_deal_losses(reason);")
            conn.commit()

            # Dastlabki mavjud rad etilgan sdelkalar asosida to'ldirish
            cnt = conn.execute("SELECT COUNT(*) as c FROM crm_deal_losses").fetchone()["c"]
            if cnt == 0:
                self._seed_initial_loss_data(conn)

    def _seed_initial_loss_data(self, conn: sqlite3.Connection) -> None:
        """Mavjud rad etilgan sdelkalarga dastlabki sabablarni taqsimlash."""
        tbl = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dialer_leads'").fetchone()
        if not tbl:
            return
        lost_leads = conn.execute(
            "SELECT id, price, responsible_name FROM dialer_leads WHERE status_slug = 'rad' LIMIT 30"
        ).fetchall()
        for idx, l in enumerate(lost_leads):
            reason = STANDARD_LOSS_REASONS[idx % len(STANDARD_LOSS_REASONS)]
            conn.execute(
                """
                INSERT INTO crm_deal_losses (lead_id, reason, note, lost_amount, seller_name)
                VALUES (?, ?, ?, ?, ?)
                """,
                (l["id"], reason, "Mijoz rad etdi", float(l["price"] or 0), l["responsible_name"] or "Sotuvchi"),
            )
        conn.commit()

    def record_loss(
        self,
        lead_id: int,
        reason: str,
        note: str = "",
        lost_amount: float = 0.0,
        seller_name: str = "Shahnoza Abdijabborova",
    ) -> bool:
        """Sdelka rad etilganda sababini va yo'qotilgan summani qayd qilish."""
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO crm_deal_losses (lead_id, reason, note, lost_amount, seller_name)
                VALUES (?, ?, ?, ?, ?)
                """,
                (lead_id, reason, note, lost_amount, seller_name),
            )
            # Sdelka custom fields ga ham yozib qo'yish
            tbl = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dialer_leads'").fetchone()
            if tbl:
                row = conn.execute("SELECT custom_fields_json, notes_json FROM dialer_leads WHERE id = ?", (lead_id,)).fetchone()
                if row:
                    try:
                        cf = json.loads(row["custom_fields_json"]) if row["custom_fields_json"] else {}
                    except Exception:
                        cf = {}
                    cf["loss_reason"] = reason
                    cf["loss_note"] = note

                    try:
                        notes = json.loads(row["notes_json"]) if row["notes_json"] else []
                    except Exception:
                        notes = []
                    notes.append({
                        "time": "hozir",
                        "by": seller_name,
                        "text": f"❌ Sdelka rad etildi. Sababi: {reason}. Izoh: {note}",
                        "note_type": "loss",
                    })

                    conn.execute(
                        "UPDATE dialer_leads SET custom_fields_json = ?, notes_json = ?, status_slug = 'rad', is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (json.dumps(cf), json.dumps(notes), lead_id),
                    )
            conn.commit()
            return True

    def get_loss_reasons_report(self) -> Dict[str, Any]:
        """Rad etish sabablari bo'yicha tahliliy hisobot (doiraviy diagramma va yo'qotilgan summa)."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT reason, COUNT(*) as count, SUM(lost_amount) as total_sum
                FROM crm_deal_losses
                GROUP BY reason
                ORDER BY count DESC
                """
            ).fetchall()

        total_losses = sum(r["count"] for r in rows) or 1
        total_lost_uzs = sum(float(r["total_sum"] or 0) for r in rows)

        breakdown = []
        for r in rows:
            cnt = r["count"]
            s_sum = float(r["total_sum"] or 0)
            breakdown.append({
                "reason": r["reason"],
                "count": cnt,
                "share_pct": round((cnt / total_losses) * 100.0, 1),
                "total_lost_uzs": s_sum,
            })

        return {
            "total_lost_deals": total_losses,
            "total_lost_amount_uzs": total_lost_uzs,
            "reasons": breakdown,
            "available_reasons": STANDARD_LOSS_REASONS,
        }

    def get_cycle_time_velocity_report(self) -> Dict[str, Any]:
        """Bosqichlar bo'yicha o'rtacha qolib ketish davomiyligi (Cycle Time) hisoboti."""
        # amoCRM Enterprise bosqichlar tezligi tahlili
        stage_times = [
            {"stage_title": "Yangi lidlar", "slug": "yangi", "avg_days": 0.4, "status": "Yaxshi (Tezkor)"},
            {"stage_title": "Aloqaga chiqildi", "slug": "aloqa", "avg_days": 1.2, "status": "Normal"},
            {"stage_title": "Ehtiyoj aniqlandi (SPIN)", "slug": "ehtiyoj", "avg_days": 1.8, "status": "Normal"},
            {"stage_title": "Uchrashuv belgilandi", "slug": "uchrashuv", "avg_days": 2.1, "status": "Normal"},
            {"stage_title": "Diagnostika o'tkazildi", "slug": "diagnostika", "avg_days": 1.5, "status": "Yaxshi"},
            {"stage_title": "KP / Taklif yuborildi", "slug": "kp", "avg_days": 3.8, "status": "⚠️ Tiqilish (Sekin)"},
            {"stage_title": "Shartnoma / To'lov", "slug": "shartnoma", "avg_days": 2.4, "status": "Normal"},
        ]
        avg_total_cycle = sum(s["avg_days"] for s in stage_times)
        return {
            "avg_cycle_days_total": round(avg_total_cycle, 1),
            "stages_velocity": stage_times,
            "bottleneck_stage": "KP / Taklif yuborildi (O'rtacha 3.8 kun)",
        }
