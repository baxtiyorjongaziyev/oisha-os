"""
SQLite persistence mixin for CRM daily stats history.
"""
import json
import logging
from contextlib import contextmanager
from datetime import date, timedelta
from typing import List, Optional
from src.services.core.crm.daily_report.models import CRMStats

logger = logging.getLogger(__name__)


class HistoryDBMixin:
    """Handles local SQLite history tracking for comparing daily metrics."""

    @contextmanager
    def _history_conn(self):
        """Single connection point for the isolated daily-stats history cache.

        ``report_history.db`` is deliberately a small, self-contained SQLite
        store accessed synchronously (its callers in handlers/monitors are
        sync). It is NOT the canonical async DB; keeping it separate avoids
        WAL lock contention with the async pool. All access funnels through
        here so there is exactly one raw ``sqlite3.connect`` in this module.
        """
        from src.database_pool import db_pool
        conn = db_pool.get_connection()
        # Yield the global connection, do not close it
        yield conn

    def _ensure_db(self) -> None:
        with self._history_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    report_date TEXT PRIMARY KEY,
                    stats_json  TEXT NOT NULL,
                    created_at  TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.commit()

    def _save_stats(self, for_date: Optional[date], stats: CRMStats) -> None:
        key = (for_date or date.today()).isoformat()
        try:
            with self._history_conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO daily_stats (report_date, stats_json) VALUES (?, ?)",
                    (key, json.dumps(stats.to_dict())),
                )
                conn.commit()
        except Exception as exc:
            logger.debug(f"[CRMDailyReporter] _save_stats: {exc}")

    def _load_prev_stats(self, for_date: Optional[date] = None) -> Optional[CRMStats]:
        target   = (for_date or date.today()) - timedelta(days=1)
        prev_key = target.isoformat()
        try:
            with self._history_conn() as conn:
                row = conn.execute(
                    "SELECT stats_json FROM daily_stats WHERE report_date = ?", (prev_key,)
                ).fetchone()
            if row:
                return CRMStats.from_dict(json.loads(row[0]))
        except Exception as exc:
            logger.debug(f"[CRMDailyReporter] _load_prev_stats: {exc}")
        return None

    def get_history(self, days: int = 7) -> List[CRMStats]:
        """So'nggi N kunlik tarix."""
        result = []
        try:
            with self._history_conn() as conn:
                rows = conn.execute(
                    "SELECT stats_json FROM daily_stats ORDER BY report_date DESC LIMIT ?", (days,)
                ).fetchall()
            for (j,) in rows:
                result.append(CRMStats.from_dict(json.loads(j)))
        except Exception:
            logger.debug(
                "Failed to load report history from SQLite",
                exc_info=True,
            )
        return result

