"""Tests for Live DB & CRM data bridge (real schemas and zero fake fallbacks)."""
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from src.services.command_center.live_db_bridge import LiveDataBridge


@pytest.mark.asyncio
async def test_live_data_bridge_returns_empty_without_synthetic_fallback(tmp_path):
    bridge = LiveDataBridge(
        db_connection=None,
        dialer_db_path=str(tmp_path / "missing_dialer.db"),
        ad_spend_db_path=str(tmp_path / "missing_spend.db"),
        attribution_db_path=str(tmp_path / "missing_attr.db"),
        use_local_files=True,
    )
    # Force _resolve_conn to avoid hitting repo's local data/bot.db
    bridge.use_local_files = False

    deals = await bridge.fetch_active_deal_records()
    interactions = await bridge.fetch_recent_lead_interactions()
    campaigns, leads = await bridge.fetch_ad_attribution_data()

    assert deals == []
    assert interactions == []
    assert campaigns == []
    assert leads == []


@pytest.mark.asyncio
async def test_live_data_bridge_with_mock_cursor():
    class FakeCursor:
        async def fetchall(self):
            now_iso = datetime.now(UTC).isoformat()
            return [
                ("deal_99", "Real Mijoz B2B", "prop", "Taklif", "mgr_1", "Aziz", 150_000_000.0, now_iso)
            ]

    class FakeConn:
        async def execute(self, query, params=None):
            return FakeCursor()

    bridge = LiveDataBridge(db_connection=FakeConn())
    deals = await bridge.fetch_active_deal_records()
    assert len(deals) == 1
    assert deals[0].deal_id == "deal_99"
    assert deals[0].deal_name == "Real Mijoz B2B"
    assert deals[0].amount == 150_000_000.0


@pytest.mark.asyncio
async def test_live_data_bridge_reads_real_sqlite_schemas(tmp_path):
    now = datetime.now(UTC)
    recent_sql = (now - timedelta(minutes=25)).strftime("%Y-%m-%d %H:%M:%S")
    old_sql = (now - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")

    dialer_db = tmp_path / "crm_dialer.db"
    with sqlite3.connect(dialer_db) as conn:
        conn.execute(
            "CREATE TABLE dialer_leads (id INTEGER PRIMARY KEY, name TEXT, status_slug TEXT, "
            "price REAL, responsible_user_id INTEGER, responsible_name TEXT, "
            "last_called_at TEXT, updated_at TEXT, is_active INTEGER)"
        )
        conn.execute(
            "INSERT INTO dialer_leads VALUES (1, 'Real B2B Deal', 'jarayonda', 25000000, 10, 'Sardor', NULL, ?, 1)",
            (old_sql,),
        )
        conn.execute(
            "INSERT INTO dialer_leads VALUES (2, 'Closed Deal', 'sotuv', 30000000, 10, 'Sardor', NULL, ?, 1)",
            (recent_sql,),
        )
        conn.execute(
            "INSERT INTO dialer_leads VALUES (3, 'Synthetic Test | Ad Meta', 'yangi', 0, NULL, 'Test', NULL, ?, 1)",
            (recent_sql,),
        )
        conn.execute(
            "CREATE TABLE crm_chat_threads (id INTEGER PRIMARY KEY, lead_id INTEGER, channel TEXT, "
            "contact_name TEXT, unread_count INTEGER, responsible_name TEXT, created_at TEXT, updated_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE crm_chat_messages (id INTEGER PRIMARY KEY, thread_id INTEGER, "
            "direction TEXT, sender_name TEXT, text TEXT, created_at TEXT)"
        )
        conn.execute(
            "INSERT INTO crm_chat_threads VALUES (1, 1, 'telegram', 'Dilshod', 1, 'Sardor', ?, ?)",
            (recent_sql, recent_sql),
        )
        conn.execute(
            "INSERT INTO crm_chat_messages VALUES (1, 1, 'in', 'Dilshod', 'Salom', ?)",
            (recent_sql,),
        )
        conn.execute(
            "INSERT INTO crm_chat_threads VALUES (2, 2, 'instagram', 'Eski Lid', 1, 'Sardor', ?, ?)",
            (old_sql, old_sql),
        )
        conn.execute(
            "CREATE TABLE crm_deal_losses (id INTEGER PRIMARY KEY, reason TEXT)"
        )
        conn.execute("INSERT INTO crm_deal_losses VALUES (1, 'Narx qimmat')")
        conn.execute(
            "CREATE TABLE crm_tasks (id INTEGER PRIMARY KEY, lead_id INTEGER, lead_name TEXT, "
            "contact_name TEXT, title TEXT, responsible_name TEXT, due_at TEXT, is_completed INTEGER)"
        )
        conn.execute(
            "INSERT INTO crm_tasks VALUES (1, 1, 'Real B2B Deal', 'Dilshod', 'Taklif yuborish', 'Sardor', ?, 0)",
            (old_sql,),
        )

    spend_db = tmp_path / "meta_ad_spend.db"
    with sqlite3.connect(spend_db) as conn:
        conn.execute(
            "CREATE TABLE meta_ad_spend (date TEXT, campaign_id TEXT, campaign_name TEXT, "
            "spend REAL, impressions INTEGER, clicks INTEGER, currency TEXT)"
        )
        conn.execute(
            "INSERT INTO meta_ad_spend VALUES (?, 'cmp_1', 'Real Kampaniya', 12.5, 1000, 40, 'USD')",
            (now.strftime("%Y-%m-%d"),),
        )

    attr_db = tmp_path / "meta_ad_attribution.db"
    with sqlite3.connect(attr_db) as conn:
        conn.execute(
            "CREATE TABLE lead_attribution (leadgen_id TEXT PRIMARY KEY, lead_id INTEGER, "
            "campaign_id TEXT, created_at TEXT, lead_price REAL, lead_won INTEGER, status_id INTEGER)"
        )
        conn.execute(
            "INSERT INTO lead_attribution VALUES ('lg_1', 100, 'cmp_1', ?, 15000000, 1, 142)",
            (now.isoformat(),),
        )

    bridge = LiveDataBridge(
        db_connection=None,
        dialer_db_path=str(dialer_db),
        ad_spend_db_path=str(spend_db),
        attribution_db_path=str(attr_db),
        use_local_files=True,
    )

    deals = await bridge.fetch_active_deal_records()
    assert [d.deal_name for d in deals] == ["Real B2B Deal"]

    interactions = await bridge.fetch_recent_lead_interactions()
    assert len(interactions) == 1
    assert interactions[0].customer_name == "Dilshod"
    assert interactions[0].first_response_at is None

    campaigns, ad_leads = await bridge.fetch_ad_attribution_data()
    assert len(campaigns) == 1
    assert campaigns[0].campaign_id == "cmp_1"
    assert bridge.last_spend_currency == "USD"
    assert len(ad_leads) == 1
    assert ad_leads[0].status == "won"
    assert ad_leads[0].won_amount == 15_000_000.0

    extras = await bridge.fetch_executive_extras()
    assert extras["lost_count"] == 1
    assert extras["top_loss_reason"] == "Narx qimmat"
    assert extras["overdue_tasks_count"] == 1

    tasks = await bridge.fetch_morning_tasks()
    assert len(tasks) == 1
    assert tasks[0].lead_name == "Real B2B Deal"

    leaderboard = await bridge.fetch_team_leaderboard()
    assert len(leaderboard) == 1
    assert leaderboard[0]["manager_name"] == "Sardor"
    assert leaderboard[0]["won_sales"] == 1
