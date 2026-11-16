"""Live DB & CRM Data Bridge for Metasell Executive Dashboard.

Fetches active deals, conversation/call response events, tasks, and ad
attribution data directly from Turso / SQLite tables without synthetic fallbacks.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from src.services.command_center.ad_attribution import (
    AdAttributedLead,
    AdCampaignRecord,
)
from src.services.command_center.live_db_parsers import (
    parse_ad_lead_row,
    parse_call_rows,
    parse_campaign_row,
    parse_chat_rows,
    parse_deal_row,
    parse_legacy_rows,
    safe_parse_dt,
)
from src.services.command_center.morning_tasks import MorningTaskItem
from src.services.command_center.speed_to_lead import LeadInteraction
from src.services.command_center.stuck_deals import DealStageRecord
from src.services.utils.db_rows import fetch_rows

logger = logging.getLogger(__name__)


class LiveDataBridge:
    """Bridges database tables with Metasell analytical calculation engines."""

    def __init__(
        self,
        db_connection: Any | None = None,
        *,
        dialer_db_path: str = "data/crm_dialer.db",
        ad_spend_db_path: str = "data/meta_ad_spend.db",
        attribution_db_path: str = "data/meta_ad_attribution.db",
        use_local_files: bool | None = None,
    ) -> None:
        """Initialize data bridge with optional DB handle and local SQLite paths."""
        self.conn = db_connection
        self.dialer_db_path = dialer_db_path
        self.ad_spend_db_path = ad_spend_db_path
        self.attribution_db_path = attribution_db_path
        self.use_local_files = (db_connection is None) if use_local_files is None else use_local_files
        self.last_spend_currency: str = "UZS"

    def _resolve_conn(self) -> Any | None:
        """Resolve database handle from instance, api_state, or get_db()."""
        if self.conn is not None:
            return self.conn
        if not self.use_local_files:
            return None
        try:
            from src.api.routes.state import api_state
            if getattr(api_state, "db_instance", None):
                return api_state.db_instance
        except (ImportError, AttributeError, KeyError, ValueError):
            pass
        try:
            from src.db import get_db
            return get_db()
        except (ImportError, AttributeError, KeyError, ValueError):
            pass
        return None

    def _query_local_sqlite(
        self, db_path: str, sql: str, params: tuple[Any, ...] = ()
    ) -> list[dict[str, Any]]:
        """Query local SQLite database file safely if present on disk."""
        if not self.use_local_files:
            return []
        path = Path(db_path)
        if not path.exists():
            return []
        try:
            conn = sqlite3.connect(str(path))
            conn.row_factory = sqlite3.Row
            rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
            conn.close()
            return rows
        except (sqlite3.Error, OSError, RuntimeError) as exc:
            logger.debug("Local SQLite error for %s: %s", db_path, exc)
            return []

    async def _execute_on_conn(
        self, query: str, params: tuple[Any, ...] = ()
    ) -> list[Any] | None:
        """Safely execute query across direct cursor or fetch_rows."""
        conn = self._resolve_conn()
        if not conn:
            return None

        execute_fn = getattr(conn, "execute", None)
        if callable(execute_fn):
            try:
                res = execute_fn(query, params) if params else execute_fn(query)
                if hasattr(res, "__await__"):
                    res = await res
                if hasattr(res, "fetchall"):
                    rows = res.fetchall()
                    if hasattr(rows, "__await__"):
                        rows = await rows
                    if rows:
                        return list(rows)
            except (KeyError, ValueError, TypeError, sqlite3.Error, OSError, RuntimeError) as exc:
                logger.debug("Direct cursor execute skipped: %s", exc)

        try:
            rows = await fetch_rows(conn, query, params or None)
            if rows:
                return list(rows)
        except (KeyError, ValueError, TypeError, sqlite3.Error, OSError, RuntimeError) as exc:
            logger.debug("fetch_rows query skipped: %s", exc)

        return None

    async def fetch_active_deal_records(self) -> list[DealStageRecord]:
        """Fetch active deals from CRM tables with stage entry timestamps."""
        q_dialer = (
            "SELECT id, name, status_slug, price, responsible_user_id, responsible_name, "
            "COALESCE(last_called_at, updated_at) AS entered_stage_at "
            "FROM dialer_leads "
            "WHERE is_active = 1 "
            "AND status_slug NOT IN ('won', 'lost', 'closed', 'sotuv', 'rad', 'yopilgan') "
            "AND LOWER(COALESCE(name, '')) NOT LIKE 'synthetic test%' "
            "ORDER BY COALESCE(last_called_at, updated_at) ASC LIMIT 200"
        )
        q_deals = (
            "SELECT deal_id, deal_name, stage_id, stage_name, manager_id, manager_name, "
            "amount, entered_stage_at FROM crm_active_deals "
            "WHERE status = 'open' ORDER BY entered_stage_at ASC LIMIT 200"
        )

        rows = (await self._execute_on_conn(q_dialer)) or (await self._execute_on_conn(q_deals))
        if not rows:
            rows = self._query_local_sqlite(self.dialer_db_path, q_dialer)

        return [parse_deal_row(r) for r in rows] if rows else []

    async def fetch_recent_lead_interactions(self, since_days: int = 7) -> list[LeadInteraction]:
        """Fetch recent inbound calls and omnichannel chats without synthetic fallback."""
        cutoff_dt = datetime.now(UTC) - timedelta(days=max(1, since_days))
        cutoff_iso = cutoff_dt.isoformat()
        cutoff_sql = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")

        interactions: list[LeadInteraction] = []
        q_calls = (
            "SELECT call_id, lead_id, phone, manager_id, manager_name, answered, "
            "duration_seconds, COALESCE(occurred_at, created_at) AS created_at "
            "FROM call_events WHERE direction = 'call_in' "
            "AND COALESCE(occurred_at, created_at) >= ? "
            "ORDER BY COALESCE(occurred_at, created_at) DESC LIMIT 200"
        )
        q_legacy = (
            "SELECT lead_id, customer_name, channel, manager_id, created_at, first_response_at "
            "FROM crm_interactions WHERE created_at >= ? ORDER BY created_at DESC LIMIT 300"
        )
        q_chats = (
            "SELECT t.id AS thread_id, t.lead_id, t.channel, t.contact_name, "
            "t.unread_count, t.responsible_name, t.created_at, t.updated_at, "
            "MIN(CASE WHEN m.direction = 'in' THEN m.created_at END) AS first_in_at, "
            "MIN(CASE WHEN m.direction = 'out' THEN m.created_at END) AS first_out_at "
            "FROM crm_chat_threads t "
            "LEFT JOIN crm_chat_messages m ON m.thread_id = t.id "
            "WHERE COALESCE(t.updated_at, t.created_at) >= ? "
            "AND LOWER(COALESCE(t.contact_name, '')) NOT LIKE 'synthetic test%' "
            "GROUP BY t.id ORDER BY t.created_at DESC LIMIT 200"
        )

        call_rows = await self._execute_on_conn(q_calls, (cutoff_iso,))
        if call_rows:
            interactions.extend(parse_call_rows(call_rows, cutoff_dt))
        else:
            legacy_rows = await self._execute_on_conn(q_legacy, (cutoff_sql,))
            if legacy_rows:
                interactions.extend(parse_legacy_rows(legacy_rows, cutoff_dt))

        chat_rows = self._query_local_sqlite(self.dialer_db_path, q_chats, (cutoff_sql,))
        if chat_rows:
            interactions.extend(parse_chat_rows(chat_rows, cutoff_dt))

        return interactions

    async def fetch_ad_attribution_data(
        self, days: int = 30
    ) -> tuple[list[AdCampaignRecord], list[AdAttributedLead]]:
        """Fetch ad spend and attributed lead records from marketing tables."""
        cutoff_date = (datetime.now(UTC) - timedelta(days=max(1, days))).strftime("%Y-%m-%d")
        cq = (
            "SELECT campaign_id, MAX(campaign_name) AS campaign_name, "
            "SUM(COALESCE(spend, 0)) AS spend, SUM(COALESCE(impressions, 0)) AS impressions, "
            "SUM(COALESCE(clicks, 0)) AS clicks, MAX(COALESCE(currency, 'UZS')) AS currency "
            "FROM meta_ad_spend WHERE date >= ? GROUP BY campaign_id"
        )
        lq = (
            "SELECT COALESCE(CAST(lead_id AS TEXT), leadgen_id) AS lead_id, "
            "COALESCE(campaign_id, '') AS campaign_id, lead_won, status_id, "
            "COALESCE(lead_price, 0) AS lead_price "
            "FROM lead_attribution WHERE date(created_at) >= date(?) "
            "AND COALESCE(campaign_id, '') != ''"
        )
        c_rows = await self._execute_on_conn(cq, (cutoff_date,))
        l_rows = await self._execute_on_conn(lq, (cutoff_date,))

        if not c_rows:
            c_rows = self._query_local_sqlite(self.ad_spend_db_path, cq, (cutoff_date,))
        if not l_rows:
            l_rows = self._query_local_sqlite(self.attribution_db_path, lq, (cutoff_date,))

        campaigns = [parse_campaign_row(r) for r in (c_rows or [])]
        leads = [parse_ad_lead_row(r) for r in (l_rows or [])]
        currencies = {str(r.get("currency") or "").upper() for r in (c_rows or []) if isinstance(r, dict)}
        if currencies == {"USD"}:
            self.last_spend_currency = "USD"
        elif "UZS" in currencies or not currencies:
            self.last_spend_currency = "UZS"
        else:
            self.last_spend_currency = next(iter(currencies))
        return campaigns, leads

    async def fetch_executive_extras(self) -> dict[str, Any]:
        """Fetch real loss summary and overdue task count from CRM SQLite store."""
        q_losses = (
            "SELECT COALESCE(NULLIF(TRIM(reason), ''), 'Sabab koʻrsatilmagan') AS reason, "
            "COUNT(*) AS cnt FROM crm_deal_losses GROUP BY reason ORDER BY cnt DESC"
        )
        q_overdue = (
            "SELECT COUNT(*) AS cnt FROM crm_tasks "
            "WHERE COALESCE(is_completed, 0) = 0 AND due_at IS NOT NULL AND due_at < datetime('now')"
        )
        loss_rows = self._query_local_sqlite(self.dialer_db_path, q_losses)
        overdue_rows = self._query_local_sqlite(self.dialer_db_path, q_overdue)
        lost_count = sum(int(r.get("cnt") or 0) for r in loss_rows)
        top_reason = str(loss_rows[0]["reason"]) if loss_rows else "Maʼlumot yoʻq"
        overdue_count = int(overdue_rows[0].get("cnt") or 0) if overdue_rows else 0
        return {
            "lost_count": lost_count,
            "top_loss_reason": top_reason,
            "overdue_tasks_count": overdue_count,
        }

    async def fetch_morning_tasks(self) -> list[MorningTaskItem]:
        """Fetch open CRM tasks for morning triage overview."""
        q_tasks = (
            "SELECT id, COALESCE(CAST(lead_id AS TEXT), '') AS lead_id, "
            "COALESCE(NULLIF(TRIM(lead_name), ''), NULLIF(TRIM(contact_name), ''), 'Lid') AS lead_name, "
            "COALESCE(title, 'Vazifa') AS title, due_at, "
            "COALESCE(responsible_name, 'Menejer') AS responsible_name "
            "FROM crm_tasks WHERE COALESCE(is_completed, 0) = 0 "
            "ORDER BY due_at ASC LIMIT 100"
        )
        rows = self._query_local_sqlite(self.dialer_db_path, q_tasks)
        today = datetime.now(UTC).date()
        items: list[MorningTaskItem] = []
        for r in rows:
            parsed_due = safe_parse_dt(str(r.get("due_at") or ""), None)
            items.append(
                MorningTaskItem(
                    task_id=str(r.get("id") or ""),
                    lead_id=str(r.get("lead_id") or ""),
                    lead_name=str(r.get("lead_name") or "Lid"),
                    text=str(r.get("title") or "Vazifa"),
                    due_date=parsed_due.date() if parsed_due else today,
                    manager_id=str(r.get("responsible_name") or "Menejer"),
                )
            )
        return items

    async def fetch_team_leaderboard(self) -> list[dict[str, Any]]:
        """Aggregate real manager performance from dialer_leads and call_events."""
        q_sales = (
            "SELECT COALESCE(NULLIF(TRIM(responsible_name), ''), 'Belgilanmagan') AS manager_name, "
            "COUNT(*) AS total_leads, "
            "SUM(CASE WHEN status_slug = 'sotuv' THEN 1 ELSE 0 END) AS won_sales, "
            "SUM(CASE WHEN status_slug = 'sotuv' THEN COALESCE(price, 0) ELSE 0 END) AS won_amount "
            "FROM dialer_leads "
            "WHERE LOWER(COALESCE(name, '')) NOT LIKE 'synthetic test%' "
            "GROUP BY manager_name ORDER BY won_amount DESC, won_sales DESC LIMIT 10"
        )
        rows = self._query_local_sqlite(self.dialer_db_path, q_sales)
        if not rows:
            return []

        q_calls = (
            "SELECT COALESCE(NULLIF(TRIM(manager_name), ''), 'Belgilanmagan') AS manager_name, "
            "COUNT(*) AS calls_count, "
            "SUM(COALESCE(duration_seconds, 0)) AS talk_seconds "
            "FROM call_events GROUP BY manager_name"
        )
        call_rows = await self._execute_on_conn(q_calls) or []
        calls_by_mgr = {
            str(r.get("manager_name") or ""): r for r in call_rows if isinstance(r, dict)
        }

        board: list[dict[str, Any]] = []
        for r in rows:
            name = str(r.get("manager_name") or "Belgilanmagan")
            total = int(r.get("total_leads") or 0)
            won = int(r.get("won_sales") or 0)
            call_info = calls_by_mgr.get(name, {})
            board.append(
                {
                    "manager_name": name,
                    "new_leads": total,
                    "won_sales": won,
                    "won_amount": float(r.get("won_amount") or 0.0),
                    "conversion_pct": round((won / total * 100.0) if total else 0.0, 1),
                    "calls_count": int(call_info.get("calls_count") or 0),
                    "talk_time_minutes": int(int(call_info.get("talk_seconds") or 0) / 60),
                }
            )
        return board
