"""Sales Targets & Plan-Fact Engine (amoCRM Enterprise Plan vs Fact & Forecast).

Ushbu modul har bir sotuvchi va butun bo'lim uchun oylik sotuv rejalari (plan),
amaldagi tushumlar (fakt), kunlik kerakli sur'at (daily pace) hamda voronka
ehtimolliklari asosidagi aniq sotuv bashorati (pipeline forecast)ni hisoblaydi.
"""
from __future__ import annotations

import calendar
from datetime import datetime
import json
import logging
import sqlite3
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "data/crm_dialer.db"

# Voronka bosqichlarining yopilish ehtimollik vaznlari (amoCRM Enterprise Forecast)
STAGE_WEIGHTS: Dict[str, float] = {
    "yangi": 0.05,
    "aloqa": 0.15,
    "ehtiyoj": 0.30,
    "uchrashuv": 0.50,
    "diagnostika": 0.65,
    "kp": 0.75,
    "shartnoma": 0.90,
    "sotuv": 1.00,
    "rad": 0.00,
}

DEFAULT_MONTHLY_TARGETS = [
    {"seller_name": "Shahnoza Abdijabborova", "target_revenue": 200000000.0, "target_deals": 18},
    {"seller_name": "Rayxona", "target_revenue": 150000000.0, "target_deals": 12},
    {"seller_name": "Mumtozmaxal", "target_revenue": 100000000.0, "target_deals": 8},
]


class SalesTargetsEngine:
    """Sotuv rejasi, kunlik pacing va ehtimolli kassa bashorati markazi."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        self._init_targets_table()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_targets_table(self) -> None:
        """Oylik rejalar jadvalini yaratish va dastlabki rejalarni yuklash."""
        with self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS crm_sales_targets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    seller_name TEXT NOT NULL,
                    month_str TEXT NOT NULL,
                    target_revenue REAL NOT NULL,
                    target_deals INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(seller_name, month_str)
                );
                """
            )
            conn.commit()

            cur_month = datetime.now().strftime("%Y-%m")
            cnt = conn.execute("SELECT COUNT(*) as c FROM crm_sales_targets WHERE month_str = ?", (cur_month,)).fetchone()["c"]
            if cnt == 0:
                for t in DEFAULT_MONTHLY_TARGETS:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO crm_sales_targets (seller_name, month_str, target_revenue, target_deals)
                        VALUES (?, ?, ?, ?)
                        """,
                        (t["seller_name"], cur_month, t["target_revenue"], t["target_deals"]),
                    )
                conn.commit()

    def get_plan_fact_overview(self, month_str: Optional[str] = None) -> Dict[str, Any]:
        """Joriy oy uchun Plan vs Fact, kunlik sur'at va jami prognoz hisoboti."""
        month = month_str or datetime.now().strftime("%Y-%m")
        now_dt = datetime.now()
        year, m_num = int(month.split("-")[0]), int(month.split("-")[1])
        days_in_month = calendar.monthrange(year, m_num)[1]
        day_today = now_dt.day if month == now_dt.strftime("%Y-%m") else days_in_month
        days_left = max(1, days_in_month - day_today)

        with self._get_conn() as conn:
            targets_rows = conn.execute(
                "SELECT * FROM crm_sales_targets WHERE month_str = ?", (month,)
            ).fetchall()
            tbl = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dialer_leads'").fetchone()
            if tbl:
                leads_rows = conn.execute(
                    "SELECT id, price, status_slug, responsible_name, is_active FROM dialer_leads"
                ).fetchall()
            else:
                leads_rows = []

        all_leads = [dict(r) for r in leads_rows]
        targets_by_seller = {r["seller_name"]: dict(r) for r in targets_rows}

        sellers_stats: List[Dict[str, Any]] = []
        total_target_rev = 0.0
        total_fact_rev = 0.0
        total_forecast_rev = 0.0
        total_target_deals = 0
        total_fact_deals = 0

        # Har bir menejer bo'yicha hisoblash
        for rep_name, tgt in targets_by_seller.items():
            rep_leads = [l for l in all_leads if l.get("responsible_name") == rep_name]
            won_leads = [l for l in rep_leads if l.get("status_slug") == "sotuv"]
            active_leads = [l for l in rep_leads if l.get("is_active") and l.get("status_slug") != "sotuv"]

            fact_rev = sum(float(l.get("price") or 0) for l in won_leads)
            fact_cnt = len(won_leads)
            t_rev = float(tgt["target_revenue"])
            t_cnt = int(tgt["target_deals"])

            # Ehtimolli bashorat: Fakt + Faol sdelkalar * bosqich vazni
            pipe_forecast = sum(
                float(l.get("price") or 0) * STAGE_WEIGHTS.get(l.get("status_slug") or "yangi", 0.1)
                for l in active_leads
            )
            rep_forecast = fact_rev + pipe_forecast

            comp_pct = round((fact_rev / max(t_rev, 1.0)) * 100.0, 1)
            pace_req = max(0.0, (t_rev - fact_rev) / days_left)

            sellers_stats.append({
                "seller_name": rep_name,
                "target_revenue": t_rev,
                "fact_revenue": fact_rev,
                "target_deals": t_cnt,
                "fact_deals": fact_cnt,
                "completion_pct": comp_pct,
                "forecast_revenue": round(rep_forecast, 0),
                "daily_pace_required": round(pace_req, 0),
                "active_pipeline_uzs": sum(float(l.get("price") or 0) for l in active_leads),
            })

            total_target_rev += t_rev
            total_fact_rev += fact_rev
            total_forecast_rev += rep_forecast
            total_target_deals += t_cnt
            total_fact_deals += fact_cnt

        overall_comp = round((total_fact_rev / max(total_target_rev, 1.0)) * 100.0, 1)
        overall_daily_pace = max(0.0, (total_target_rev - total_fact_rev) / days_left)

        return {
            "month": month,
            "days_in_month": days_in_month,
            "days_passed": day_today,
            "days_left": days_left,
            "totals": {
                "target_revenue": total_target_rev,
                "fact_revenue": total_fact_rev,
                "forecast_revenue": round(total_forecast_rev, 0),
                "completion_pct": overall_comp,
                "target_deals": total_target_deals,
                "fact_deals": total_fact_deals,
                "daily_pace_required": round(overall_daily_pace, 0),
            },
            "sellers": sorted(sellers_stats, key=lambda x: x["fact_revenue"], reverse=True),
        }

    def set_seller_target(self, seller_name: str, month_str: str, target_revenue: float, target_deals: int) -> bool:
        """Sotuvchining oylik rejasini belgilash yoki o'zgartirish."""
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO crm_sales_targets (seller_name, month_str, target_revenue, target_deals)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(seller_name, month_str) DO UPDATE SET
                    target_revenue = excluded.target_revenue,
                    target_deals = excluded.target_deals
                """,
                (seller_name, month_str, target_revenue, target_deals),
            )
            conn.commit()
            return True
