"""
SQLite persistence mixin for CRM daily stats history.
"""
import json
import logging
from contextlib import contextmanager
from datetime import date, timedelta
from typing import List, Optional
from src.services.core.crm.daily_report.models import CRMStats, PeriodType, PeriodMetrics

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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS crm_report_snapshots (
                    period_type   TEXT NOT NULL,
                    period_start  TEXT NOT NULL,
                    period_end    TEXT NOT NULL,
                    metrics_json  TEXT NOT NULL,
                    created_at    TEXT DEFAULT (datetime('now')),
                    PRIMARY KEY (period_type, period_start)
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

    def save_snapshot(self, m: PeriodMetrics) -> None:
        try:
            with self._history_conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO crm_report_snapshots "
                    "(period_type, period_start, period_end, metrics_json) VALUES (?, ?, ?, ?)",
                    (
                        m.period_type.value,
                        m.period_start.isoformat(),
                        m.period_end.isoformat(),
                        json.dumps(m.to_dict()),
                    ),
                )
                conn.commit()
        except Exception as exc:
            logger.debug("[CRMPeriodReporter] save_snapshot: %s", exc)

    def load_snapshot(self, ptype: PeriodType, period_start: date):
        try:
            with self._history_conn() as conn:
                row = conn.execute(
                    "SELECT metrics_json FROM crm_report_snapshots "
                    "WHERE period_type = ? AND period_start = ?",
                    (ptype.value, period_start.isoformat()),
                ).fetchone()
            if row:
                return PeriodMetrics.from_dict(json.loads(row[0]))
        except Exception as exc:
            logger.debug("[CRMPeriodReporter] load_snapshot: %s", exc)
        return None

    def list_snapshots(self, ptype: PeriodType, limit: int = 12):
        out = []
        try:
            with self._history_conn() as conn:
                rows = conn.execute(
                    "SELECT metrics_json FROM crm_report_snapshots "
                    "WHERE period_type = ? ORDER BY period_start DESC LIMIT ?",
                    (ptype.value, limit),
                ).fetchall()
            for (j,) in rows:
                out.append(PeriodMetrics.from_dict(json.loads(j)))
        except Exception as exc:
            logger.debug("[CRMPeriodReporter] list_snapshots: %s", exc)
        return out

